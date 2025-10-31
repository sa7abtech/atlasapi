"""
ATLAS FastAPI Backend
Main API application for handling chat requests
"""

import logging
import logging.config
import time
import re
import asyncio
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic, APIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import sys
sys.path.append("..")

from config import settings, ATLAS_SYSTEM_PROMPT, build_context_prompt, get_log_config
from api.database import AtlasDatabase
from api.vector_search import VectorSearchEngine
from api.learning import BatchLearningEngine

# Configure logging
logging.config.dictConfig(get_log_config())
logger = logging.getLogger("atlas.api")

# Initialize FastAPI app
app = FastAPI(
    title="ATLAS API",
    description="AI Assistant for AWS Cloud Consulting",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global instances
db: Optional[AtlasDatabase] = None
search_engine: Optional[VectorSearchEngine] = None
openai_client: Optional[AsyncOpenAI] = None
claude_client: Optional[AsyncAnthropic] = None
learning_engine: Optional[BatchLearningEngine] = None
scheduler: Optional[AsyncIOScheduler] = None


# Scheduled job: Run batch learning for all active users
async def run_scheduled_batch_learning():
    """Run batch learning for all users who had conversations in the past day"""
    try:
        logger.info("Starting scheduled batch learning...")

        # Get all unique user IDs from recent conversations
        response = (
            db.client.table("atlas_conversations")
            .select("user_id")
            .gte("created_at", f"NOW() - INTERVAL '{settings.BATCH_LEARNING_LOOKBACK_DAYS} days'")
            .execute()
        )

        if not response.data:
            logger.info("No users to process for batch learning")
            return

        user_ids = list(set(conv["user_id"] for conv in response.data))
        logger.info(f"Running batch learning for {len(user_ids)} users")

        # Run batch learning for each user
        for user_id in user_ids:
            try:
                result = await learning_engine.run_batch_learning(
                    user_id=user_id,
                    lookback_days=settings.BATCH_LEARNING_LOOKBACK_DAYS,
                    max_conversations=settings.BATCH_LEARNING_MAX_CONVERSATIONS,
                )
                logger.info(f"Batch learning for user {user_id}: {result}")
            except Exception as e:
                logger.error(f"Error in batch learning for user {user_id}: {e}")

        logger.info("Scheduled batch learning completed")

    except Exception as e:
        logger.error(f"Error in scheduled batch learning: {e}")


# Helper function to extract user facts from conversation
def extract_user_facts(user_message: str, bot_response: str) -> list[Dict]:
    """
    Extract key facts from conversation using pattern matching
    Returns list of facts to save to memory
    """
    facts = []
    message_lower = user_message.lower()

    # Pattern: "my name is X" or "I'm X"
    name_patterns = [
        r"my name is (\w+)",
        r"i'm (\w+)",
        r"i am (\w+)",
        r"call me (\w+)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, message_lower)
        if match:
            name = match.group(1).capitalize()
            facts.append({
                "fact_type": "business_context",
                "fact_key": "user_name",
                "fact_value": name,
                "confidence": 0.95
            })
            break

    # Pattern: "my company is X" or "company name is X"
    company_patterns = [
        r"my company (?:is |name is )?([a-zA-Z0-9]+)",
        r"company (?:is |name is )?([a-zA-Z0-9]+)",
        r"we(?:'re| are) ([a-zA-Z0-9]+)",
    ]
    for pattern in company_patterns:
        match = re.search(pattern, message_lower)
        if match:
            company = match.group(1)
            facts.append({
                "fact_type": "business_context",
                "fact_key": "company_name",
                "fact_value": company,
                "confidence": 0.95
            })
            break

    # Pattern: "using X" or "running X" (infrastructure)
    infra_patterns = [
        r"using (odoo|sage|aws|ec2|rds|s3)",
        r"running (odoo|sage|aws|ec2|rds|s3)",
        r"we have (odoo|sage|aws|ec2|rds|s3)",
    ]
    for pattern in infra_patterns:
        match = re.search(pattern, message_lower)
        if match:
            tech = match.group(1).upper()
            facts.append({
                "fact_type": "infrastructure",
                "fact_key": f"uses_{tech.lower()}",
                "fact_value": f"Uses {tech}",
                "confidence": 0.85
            })

    return facts


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    user_id: int
    message: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    language: Optional[str] = "en"


class ChatResponse(BaseModel):
    response: str
    model_used: str
    tokens_used: int
    response_time_ms: int
    from_cache: bool
    context_chunks_used: int


class UserStatsResponse(BaseModel):
    user_id: int
    total_conversations: int
    total_tokens_used: int
    total_tokens_saved: int
    preferred_language: str


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global db, search_engine, openai_client, claude_client, learning_engine, scheduler

    try:
        # Validate settings
        settings.validate()

        # Initialize database
        db = AtlasDatabase(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY,
        )
        logger.info("Database connection initialized")

        # Initialize vector search engine
        search_engine = VectorSearchEngine(
            database=db,
            openai_api_key=settings.OPENAI_API_KEY,
            embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        )
        logger.info("Vector search engine initialized")

        # Initialize OpenAI client (for embeddings)
        openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client initialized (for embeddings)")

        # Initialize Claude client (for chat) if API key is set
        if settings.CLAUDE_API_KEY:
            claude_client = AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
            logger.info("Claude client initialized (for chat)")

            # Initialize batch learning engine (uses Claude Haiku for cost efficiency)
            learning_engine = BatchLearningEngine(database=db, anthropic_client=claude_client)
            logger.info("Batch learning engine initialized")

            # Setup automatic batch learning scheduler
            if settings.BATCH_LEARNING_ENABLED:
                scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.TIMEZONE))

                # Parse learning time (HH:MM format)
                hour, minute = map(int, settings.BATCH_LEARNING_TIME.split(':'))

                # Schedule batch learning daily at specified time
                scheduler.add_job(
                    run_scheduled_batch_learning,
                    trigger=CronTrigger(hour=hour, minute=minute, timezone=settings.TIMEZONE),
                    id='batch_learning',
                    name='Automatic Batch Learning',
                    replace_existing=True
                )

                scheduler.start()
                logger.info(f"Batch learning scheduler started - will run daily at {settings.BATCH_LEARNING_TIME} {settings.TIMEZONE}")
        else:
            logger.info("Claude API key not set, using OpenAI for chat")

        logger.info("ATLAS API started successfully")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("ATLAS API shutting down")

    # Shutdown scheduler if running
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Batch learning scheduler stopped")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": db is not None,
            "search_engine": search_engine is not None,
            "openai": openai_client is not None,
            "claude": claude_client is not None,
        },
        "chat_provider": "claude" if claude_client else "openai"
    }


# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint
    Handles user queries with context retrieval and response generation
    """
    start_time = time.time()

    try:
        # Ensure user exists in database
        user = db.get_or_create_user(
            user_id=request.user_id,
            username=request.username,
            full_name=request.full_name,
        )

        # Update preferred language if provided
        if request.language and request.language != user.get("preferred_language"):
            db.client.table("atlas_users").update(
                {"preferred_language": request.language}
            ).eq("user_id", request.user_id).execute()

        # Check cache first
        cached_response = search_engine.check_cache(request.message)
        if cached_response:
            # Update user stats for tokens saved
            estimated_tokens_saved = 500  # Approximate
            db.update_user_stats(
                user_id=request.user_id,
                tokens_used=0,
                tokens_saved=estimated_tokens_saved,
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            return ChatResponse(
                response=cached_response["cached_response"],
                model_used="cached",
                tokens_used=0,
                response_time_ms=response_time_ms,
                from_cache=True,
                context_chunks_used=0,
            )

        # Build context (knowledge + history + memory)
        context = search_engine.build_context(
            user_id=request.user_id,
            query=request.message,
            top_k_knowledge=settings.TOP_K_KNOWLEDGE_CHUNKS,
            max_conversation_history=settings.MAX_CONVERSATION_HISTORY,
            max_context_tokens=settings.MAX_CONTEXT_TOKENS,
        )

        # Classify query complexity and select model
        complexity, recommended_model = search_engine.classify_query_complexity(request.message)

        # Select model based on complexity (for both Claude and OpenAI)
        if complexity == "complex":
            claude_model = settings.CLAUDE_MODEL_COMPLEX
            openai_model = settings.OPENAI_CHAT_MODEL_COMPLEX
        else:
            claude_model = settings.CLAUDE_MODEL_SIMPLE
            openai_model = settings.OPENAI_CHAT_MODEL_SIMPLE

        logger.info(f"Using {'Claude ' + claude_model if claude_client else 'OpenAI ' + openai_model} for {complexity} query from user {request.user_id}")

        # Build full prompt with context
        full_prompt = build_context_prompt(
            knowledge_chunks=context["knowledge_chunks"],
            user_memory=context["user_memory"],
            conversation_history=context["conversation_history"],
            user_query=request.message,
        )

        # Generate response using Claude (or OpenAI as fallback)
        if claude_client:
            # Use Claude for chat with retry logic
            max_retries = 2
            retry_delay = 1

            for attempt in range(max_retries + 1):
                try:
                    chat_completion = await claude_client.messages.create(
                        model=claude_model,
                        max_tokens=1000,
                        temperature=0.5,
                        system=ATLAS_SYSTEM_PROMPT,
                        messages=[
                            {"role": "user", "content": full_prompt},
                        ],
                    )
                    response_text = chat_completion.content[0].text
                    tokens_used = chat_completion.usage.input_tokens + chat_completion.usage.output_tokens
                    model_used = f"claude-{claude_model}"
                    break  # Success, exit retry loop

                except APIError as e:
                    if "overloaded" in str(e).lower() and attempt < max_retries:
                        logger.warning(f"Claude API overloaded, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        # Give up and fallback to OpenAI
                        logger.error(f"Claude API failed after {attempt + 1} attempts, falling back to OpenAI: {e}")
                        chat_completion = await openai_client.chat.completions.create(
                            model=openai_model,
                            messages=[
                                {"role": "system", "content": ATLAS_SYSTEM_PROMPT},
                                {"role": "user", "content": full_prompt},
                            ],
                            temperature=0.5,
                            max_tokens=1000,
                        )
                        response_text = chat_completion.choices[0].message.content
                        tokens_used = chat_completion.usage.total_tokens
                        model_used = f"openai-{openai_model}"
                        break
        else:
            # Fallback to OpenAI
            chat_completion = await openai_client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": ATLAS_SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=0.5,
                max_tokens=1000,
            )
            response_text = chat_completion.choices[0].message.content
            tokens_used = chat_completion.usage.total_tokens
            model_used = openai_model

        # FORCE remove repetitive endings that the AI keeps adding despite instructions
        banned_endings = [
            r"Ready to tackle.*?\?",
            r"Let's make (?:some )?moves!?.*",
            r"Time to make (?:those )?moves!?.*",
            r"What's next on (?:the|our) agenda.*?\?",
            r"Ready to dive.*?\?",
            r"Let's boost.*?success.*",
            r"Ready to make moves.*?\?",
            r"Let's keep.*?smooth.*?\?",
            r"What(?:'s| is) (?:next|good|up).*?\?",
            r"Which (?:path|one|option).*?\?",
            r"Give me (?:context|more|details).*",
            r"What specific.*?\?",
            r"Tell me.*?\?",
            r"Want me to.*?\?",
            r"Need (?:more|any).*?\?",
            r"How (?:about|does).*?\?",
            r"Do you (?:know|think|want|need).*?\?",
            r"Know what.*?\?",
        ]

        for pattern in banned_endings:
            response_text = re.sub(pattern, "", response_text, flags=re.IGNORECASE)

        # Remove last sentence if it ends with conversational words/phrases or encouragement
        conversational_endings = [
            r"[\.!]\s+[^\.!]+(?:honestly|right|here|anyway|though)[\.\?!]*$",
            r"\.\s+You picked (?:right|wrong)[\.\?!]*$",
            r"\.\s+Pretty .*? business partner.*$",
            r"\.\s+That's how you (?:get|become|learn).*$",
            r"\.\s+Keep (?:asking|learning|doing|going).*$",
            r"\.\s+You're (?:learning|getting|doing).*$",
        ]

        for pattern in conversational_endings:
            response_text = re.sub(pattern, ".", response_text, flags=re.IGNORECASE)

        # Clean up any trailing punctuation or whitespace
        response_text = response_text.rstrip(" .!?").strip()

        response_time_ms = int((time.time() - start_time) * 1000)

        # Save conversation to database
        conversation_id = db.save_conversation(
            user_id=request.user_id,
            user_message=request.message,
            user_message_embedding=context["query_embedding"],
            bot_response=response_text,
            context_chunks=[chunk.get("id") for chunk in context["knowledge_chunks"]],
            model_used=model_used,
            tokens_used=tokens_used,
            response_time_ms=response_time_ms,
            language=request.language,
        )

        # Extract and save user facts to memory
        extracted_facts = extract_user_facts(request.message, response_text)
        for fact in extracted_facts:
            try:
                # Generate embedding for the fact value using OpenAI
                embedding_response = await openai_client.embeddings.create(
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    input=fact["fact_value"]
                )
                fact_embedding = embedding_response.data[0].embedding

                # Save to memory
                db.save_user_memory(
                    user_id=request.user_id,
                    fact_type=fact["fact_type"],
                    fact_key=fact["fact_key"],
                    fact_value=fact["fact_value"],
                    fact_embedding=fact_embedding,
                    confidence_score=fact["confidence"],
                    source_conversation_id=conversation_id,
                )
                logger.info(f"Saved memory for user {request.user_id}: {fact['fact_key']} = {fact['fact_value']}")
            except Exception as e:
                logger.error(f"Error saving fact to memory: {e}")

        # Update user stats
        db.update_user_stats(
            user_id=request.user_id,
            tokens_used=tokens_used,
            tokens_saved=0,
        )

        # Cache simple responses
        if complexity == "simple":
            db.save_cached_response(
                query_text=request.message,
                query_embedding=context["query_embedding"],
                cached_response=response_text,
                language=request.language,
                expiry_hours=settings.CACHE_EXPIRY_HOURS,
            )

        logger.info(
            f"Chat completed for user {request.user_id}: "
            f"{tokens_used} tokens, {response_time_ms}ms, {len(context['knowledge_chunks'])} chunks"
        )

        return ChatResponse(
            response=response_text,
            model_used=model_used,
            tokens_used=tokens_used,
            response_time_ms=response_time_ms,
            from_cache=False,
            context_chunks_used=len(context["knowledge_chunks"]),
        )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# User stats endpoint
@app.get("/users/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(user_id: int):
    """Get user statistics"""
    try:
        response = db.client.table("atlas_users").select("*").eq("user_id", user_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = response.data[0]

        return UserStatsResponse(
            user_id=user["user_id"],
            total_conversations=user.get("total_conversations", 0),
            total_tokens_used=user.get("total_tokens_used", 0),
            total_tokens_saved=user.get("total_tokens_saved", 0),
            preferred_language=user.get("preferred_language", "en"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoint
@app.get("/analytics")
async def get_analytics(days: int = 7):
    """Get conversation analytics"""
    try:
        analytics = db.get_conversation_analytics(days=days)
        return analytics

    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Knowledge base stats endpoint
@app.get("/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics"""
    try:
        from knowledge.loader import KnowledgeLoader

        loader = KnowledgeLoader(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY,
        )

        stats = loader.get_knowledge_stats()
        return stats

    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache cleanup endpoint
@app.post("/cache/cleanup")
async def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        count = db.cleanup_expired_cache()
        return {"deleted_entries": count}

    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch learning endpoint
@app.post("/learn/batch/{user_id}")
async def run_batch_learning(user_id: int, lookback_days: int = 1, max_conversations: int = 20):
    """
    Run batch learning for a user
    Analyzes recent conversations to extract deep insights
    """
    try:
        if not learning_engine:
            raise HTTPException(
                status_code=503,
                detail="Batch learning not available (Claude API key required)"
            )

        result = await learning_engine.run_batch_learning(
            user_id=user_id,
            lookback_days=lookback_days,
            max_conversations=max_conversations,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch learning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development(),
        log_level=settings.LOG_LEVEL.lower(),
    )
