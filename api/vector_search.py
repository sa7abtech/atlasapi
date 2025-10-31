"""
Vector Search Module
Handles semantic search using pgvector and context retrieval
"""

import logging
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI, OpenAI
import tiktoken

logger = logging.getLogger("atlas.api.vector_search")


class VectorSearchEngine:
    """Semantic search engine using embeddings and pgvector"""

    def __init__(self, database, openai_api_key: str, embedding_model: str = "text-embedding-ada-002"):
        """
        Initialize vector search engine

        Args:
            database: AtlasDatabase instance
            openai_api_key: OpenAI API key
            embedding_model: Embedding model to use
        """
        self.db = database
        self.client = database.client
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.async_openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query

        Args:
            query: Query text

        Returns:
            Embedding vector
        """
        try:
            query_clean = query.replace("\n", " ")
            response = self.openai_client.embeddings.create(
                input=[query_clean], model=self.embedding_model
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for query: {query[:50]}...")
            return embedding

        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise

    async def generate_query_embedding_async(self, query: str) -> List[float]:
        """Generate embedding asynchronously"""
        try:
            query_clean = query.replace("\n", " ")
            response = await self.async_openai_client.embeddings.create(
                input=[query_clean], model=self.embedding_model
            )
            embedding = response.data[0].embedding
            return embedding

        except Exception as e:
            logger.error(f"Error generating query embedding async: {e}")
            raise

    def search_knowledge(
        self, query_embedding: List[float], top_k: int = 3, similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        Search knowledge base using vector similarity

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching knowledge chunks
        """
        try:
            # Convert embedding to PostgreSQL vector format
            embedding_str = json.dumps(query_embedding)

            # Use Supabase RPC for vector similarity search
            # Note: You may need to adjust this based on your Supabase setup
            # This uses cosine distance: 1 - cosine_distance = cosine_similarity
            response = self.client.rpc(
                "match_knowledge",
                {
                    "query_embedding": embedding_str,
                    "match_threshold": 1 - similarity_threshold,  # Convert to distance
                    "match_count": top_k,
                },
            ).execute()

            if response.data:
                results = response.data
                logger.info(f"Found {len(results)} relevant knowledge chunks")
                return results

            # Fallback: manual search if RPC not available
            logger.warning("RPC function not found, using fallback search")
            return self._fallback_search(query_embedding, top_k)

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            # Use fallback method
            return self._fallback_search(query_embedding, top_k)

    def _fallback_search(self, query_embedding: List[float], top_k: int = 3) -> List[Dict]:
        """Fallback search method using client-side similarity calculation"""
        try:
            # Get all knowledge chunks (or a sample)
            response = self.client.table("atlas_core_knowledge").select("*").limit(100).execute()

            if not response.data:
                return []

            # Calculate similarities
            results = []
            for chunk in response.data:
                try:
                    chunk_embedding = json.loads(chunk["embedding"])
                    similarity = self._cosine_similarity(query_embedding, chunk_embedding)

                    results.append({
                        "id": chunk["id"],
                        "content": chunk["content"],
                        "category": chunk.get("category"),
                        "similarity": similarity,
                    })
                except Exception as e:
                    logger.error(f"Error processing chunk: {e}")
                    continue

            # Sort by similarity and return top k
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"Error in fallback search: {e}")
            return []

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np

        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def build_context(
        self,
        user_id: int,
        query: str,
        top_k_knowledge: int = 3,
        max_conversation_history: int = 5,
        max_context_tokens: int = 2000,
    ) -> Dict:
        """
        Build comprehensive context for query including knowledge, history, and user memory

        Args:
            user_id: User ID
            query: User query
            top_k_knowledge: Number of knowledge chunks to retrieve
            max_conversation_history: Number of recent conversations to include
            max_context_tokens: Maximum total tokens for context

        Returns:
            Dictionary with context components and token count
        """
        try:
            logger.info(f"Building context for user {user_id}")

            # 1. Generate query embedding
            query_embedding = self.generate_query_embedding(query)

            # 2. Search knowledge base
            knowledge_chunks = self.search_knowledge(query_embedding, top_k=top_k_knowledge)

            # 3. Get conversation history
            conversation_history = self.db.get_recent_conversations(
                user_id, limit=max_conversation_history
            )

            # 4. Get user memory
            user_memory = self.db.get_user_memory(user_id)

            # 5. Calculate token usage
            context_parts = {
                "knowledge_chunks": knowledge_chunks,
                "conversation_history": conversation_history,
                "user_memory": user_memory,
                "query": query,
                "query_embedding": query_embedding,
            }

            # Count tokens for each part
            knowledge_tokens = sum(
                self.count_tokens(chunk.get("content", "")) for chunk in knowledge_chunks
            )
            history_tokens = sum(
                self.count_tokens(conv.get("user_message", "") + conv.get("bot_response", ""))
                for conv in conversation_history
            )
            memory_tokens = sum(
                self.count_tokens(f"{mem.get('fact_key', '')}: {mem.get('fact_value', '')}")
                for mem in user_memory
            )
            query_tokens = self.count_tokens(query)

            total_tokens = knowledge_tokens + history_tokens + memory_tokens + query_tokens

            # Trim if over budget
            if total_tokens > max_context_tokens:
                logger.warning(
                    f"Context exceeds token budget ({total_tokens} > {max_context_tokens}), trimming"
                )
                context_parts = self._trim_context(
                    context_parts, max_context_tokens
                )

            context_parts["token_count"] = {
                "knowledge": knowledge_tokens,
                "history": history_tokens,
                "memory": memory_tokens,
                "query": query_tokens,
                "total": total_tokens,
            }

            logger.info(
                f"Context built: {len(knowledge_chunks)} chunks, "
                f"{len(conversation_history)} history, {len(user_memory)} memories, "
                f"{total_tokens} tokens"
            )

            return context_parts

        except Exception as e:
            logger.error(f"Error building context: {e}")
            return {
                "knowledge_chunks": [],
                "conversation_history": [],
                "user_memory": [],
                "query": query,
                "token_count": {"total": 0},
            }

    def _trim_context(self, context_parts: Dict, max_tokens: int) -> Dict:
        """
        Trim context to fit within token budget
        Priority: knowledge > memory > history

        Args:
            context_parts: Context components
            max_tokens: Maximum tokens allowed

        Returns:
            Trimmed context
        """
        # Keep query and embeddings as-is
        query = context_parts["query"]
        query_embedding = context_parts.get("query_embedding", [])

        # Prioritize knowledge chunks
        knowledge = context_parts["knowledge_chunks"][:3]  # Keep top 3
        memory = context_parts["user_memory"][:5]  # Keep top 5
        history = context_parts["conversation_history"][:3]  # Keep top 3

        trimmed = {
            "knowledge_chunks": knowledge,
            "user_memory": memory,
            "conversation_history": history,
            "query": query,
            "query_embedding": query_embedding,
        }

        logger.info("Context trimmed to fit token budget")
        return trimmed

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))

    def normalize_query(self, query: str) -> str:
        """
        Normalize query for caching
        Removes greetings, standardizes terminology

        Args:
            query: Raw query

        Returns:
            Normalized query
        """
        # Remove common greetings and pleasantries
        greetings = [
            "hello",
            "hi",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "bonjour",
            "salut",
            "مرحبا",
            "please",
            "thanks",
            "thank you",
        ]

        query_lower = query.lower().strip()

        for greeting in greetings:
            query_lower = query_lower.replace(greeting, "")

        # Remove extra whitespace
        normalized = " ".join(query_lower.split())

        return normalized

    def get_query_hash(self, query: str) -> str:
        """
        Get hash for query (for caching)

        Args:
            query: Query text

        Returns:
            MD5 hash of normalized query
        """
        normalized = self.normalize_query(query)
        return hashlib.md5(normalized.encode()).hexdigest()

    def check_cache(self, query: str) -> Optional[Dict]:
        """
        Check if query response is cached

        Args:
            query: User query

        Returns:
            Cached response if available, None otherwise
        """
        query_hash = self.get_query_hash(query)
        cached = self.db.get_cached_response(query_hash)

        if cached:
            logger.info(f"Cache hit for query: {query[:50]}...")
            return cached

        return None

    def classify_query_complexity(self, query: str) -> Tuple[str, str]:
        """
        Classify query complexity to determine which model to use

        Args:
            query: User query

        Returns:
            Tuple of (complexity_level, recommended_model)
        """
        token_count = self.count_tokens(query)

        # Simple heuristics for classification
        simple_keywords = [
            "what is",
            "how much",
            "when",
            "where",
            "who",
            "define",
            "explain",
        ]
        complex_keywords = [
            "compare",
            "analyze",
            "design",
            "architecture",
            "implement",
            "migrate",
            "optimize",
            "troubleshoot",
        ]

        query_lower = query.lower()

        # Check for simple patterns
        if any(keyword in query_lower for keyword in simple_keywords) and token_count < 100:
            return ("simple", "gpt-3.5-turbo")

        # Check for complex patterns
        if any(keyword in query_lower for keyword in complex_keywords) or token_count > 300:
            return ("complex", "gpt-4")

        # Default to simple for cost efficiency
        return ("medium", "gpt-3.5-turbo")


# Create RPC function for Supabase (to be run on Supabase SQL editor)
SUPABASE_MATCH_FUNCTION_SQL = """
-- Create function for vector similarity search
CREATE OR REPLACE FUNCTION match_knowledge(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 3
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    category TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        atlas_core_knowledge.id,
        atlas_core_knowledge.content,
        atlas_core_knowledge.category,
        1 - (atlas_core_knowledge.embedding <=> query_embedding) AS similarity
    FROM atlas_core_knowledge
    WHERE 1 - (atlas_core_knowledge.embedding <=> query_embedding) > match_threshold
    ORDER BY atlas_core_knowledge.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""
