"""
ATLAS Batch Learning Module
Analyzes conversations in batches to extract deep insights about users
Uses Claude Haiku for cost-effective learning
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic

from api.database import AtlasDatabase
from config import settings
from config.prompts import BATCH_LEARNING_PROMPT

logger = logging.getLogger("atlas.learning")


class BatchLearningEngine:
    """Analyzes batches of conversations to extract user insights"""

    def __init__(self, database: AtlasDatabase, anthropic_client: AsyncAnthropic):
        self.db = database
        self.claude = anthropic_client

    async def run_batch_learning(
        self,
        user_id: int,
        lookback_days: int = 1,
        max_conversations: int = 20,
    ) -> Dict:
        """
        Run batch learning for a user

        Args:
            user_id: User ID to analyze
            lookback_days: How many days back to analyze
            max_conversations: Maximum conversations to analyze

        Returns:
            Dictionary with extracted insights and metadata
        """
        try:
            logger.info(f"Starting batch learning for user {user_id}")

            # Fetch recent conversations
            conversations = self._fetch_recent_conversations(
                user_id, lookback_days, max_conversations
            )

            if not conversations:
                logger.info(f"No conversations found for user {user_id}")
                return {
                    "success": False,
                    "message": "No conversations to analyze",
                    "insights_extracted": 0,
                }

            # Format conversations for analysis
            formatted_convos = self._format_conversations(conversations)

            # Extract insights using Claude Haiku (cheap!)
            insights = await self._extract_insights(formatted_convos)

            if not insights:
                logger.warning(f"Failed to extract insights for user {user_id}")
                return {
                    "success": False,
                    "message": "Failed to extract insights",
                    "insights_extracted": 0,
                }

            # Save insights to memory
            insights_saved = await self._save_insights(user_id, insights)

            logger.info(
                f"Batch learning completed for user {user_id}: {insights_saved} insights saved"
            )

            return {
                "success": True,
                "user_id": user_id,
                "conversations_analyzed": len(conversations),
                "insights_extracted": insights_saved,
                "timestamp": datetime.now().isoformat(),
                "insights_preview": self._get_insights_preview(insights),
            }

        except Exception as e:
            logger.error(f"Error in batch learning for user {user_id}: {e}")
            return {
                "success": False,
                "message": str(e),
                "insights_extracted": 0,
            }

    def _fetch_recent_conversations(
        self, user_id: int, lookback_days: int, max_conversations: int
    ) -> List[Dict]:
        """Fetch recent conversations for analysis"""
        try:
            cutoff_date = datetime.now() - timedelta(days=lookback_days)

            response = (
                self.db.client.table("atlas_conversations")
                .select("user_message, bot_response, created_at")
                .eq("user_id", user_id)
                .gte("created_at", cutoff_date.isoformat())
                .order("created_at", desc=False)  # Oldest first for chronological flow
                .limit(max_conversations)
                .execute()
            )

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            return []

    def _format_conversations(self, conversations: List[Dict]) -> str:
        """Format conversations for Claude analysis"""
        formatted = []
        for i, convo in enumerate(conversations, 1):
            formatted.append(
                f"[Conversation {i}]\n"
                f"User: {convo['user_message']}\n"
                f"ATLAS: {convo['bot_response']}\n"
            )
        return "\n".join(formatted)

    async def _extract_insights(self, conversations: str) -> Optional[Dict]:
        """Use Claude Haiku to extract insights from conversations"""
        try:
            prompt = BATCH_LEARNING_PROMPT.format(conversations=conversations)

            response = await self.claude.messages.create(
                model="claude-3-haiku-20240307",  # Cheap model for extraction
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for more consistent extraction
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse JSON response
            response_text = response.content[0].text
            insights = json.loads(response_text)

            logger.info(f"Extracted insights: {len(insights)} categories")
            return insights

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse insights JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error extracting insights: {e}")
            return None

    async def _save_insights(self, user_id: int, insights: Dict) -> int:
        """Save extracted insights to database"""
        saved_count = 0

        try:
            # Generate embedding for insights (for future semantic search)
            from openai import AsyncOpenAI

            openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            # Save personal info
            if insights.get("personal_info"):
                for key, value in insights["personal_info"].items():
                    if value:
                        embedding_response = await openai_client.embeddings.create(
                            model=settings.OPENAI_EMBEDDING_MODEL, input=str(value)
                        )
                        embedding = embedding_response.data[0].embedding

                        self.db.save_user_memory(
                            user_id=user_id,
                            fact_type="personal",
                            fact_key=key,
                            fact_value=str(value),
                            fact_embedding=embedding,
                            confidence_score=0.9,
                            source_conversation_id=None,
                        )
                        saved_count += 1

            # Save business context
            if insights.get("business_context"):
                for key, value in insights["business_context"].items():
                    if value:
                        embedding_response = await openai_client.embeddings.create(
                            model=settings.OPENAI_EMBEDDING_MODEL,
                            input=str(value) if not isinstance(value, list) else ", ".join(value),
                        )
                        embedding = embedding_response.data[0].embedding

                        self.db.save_user_memory(
                            user_id=user_id,
                            fact_type="business_context",
                            fact_key=key,
                            fact_value=json.dumps(value)
                            if isinstance(value, list)
                            else str(value),
                            fact_embedding=embedding,
                            confidence_score=0.85,
                            source_conversation_id=None,
                        )
                        saved_count += 1

            # Save pain points
            if insights.get("pain_points"):
                for pain_point in insights["pain_points"]:
                    embedding_response = await openai_client.embeddings.create(
                        model=settings.OPENAI_EMBEDDING_MODEL,
                        input=pain_point["description"],
                    )
                    embedding = embedding_response.data[0].embedding

                    self.db.save_user_memory(
                        user_id=user_id,
                        fact_type="pain_point",
                        fact_key=f"pain_{pain_point['area']}",
                        fact_value=pain_point["description"],
                        fact_embedding=embedding,
                        confidence_score=0.8
                        if pain_point.get("severity") == "high"
                        else 0.6,
                        source_conversation_id=None,
                    )
                    saved_count += 1

            # Save learning goals
            if insights.get("learning_goals"):
                for goal in insights["learning_goals"]:
                    embedding_response = await openai_client.embeddings.create(
                        model=settings.OPENAI_EMBEDDING_MODEL, input=goal["topic"]
                    )
                    embedding = embedding_response.data[0].embedding

                    self.db.save_user_memory(
                        user_id=user_id,
                        fact_type="learning_goal",
                        fact_key=f"goal_{goal['topic'].replace(' ', '_').lower()}",
                        fact_value=json.dumps(goal),
                        fact_embedding=embedding,
                        confidence_score=0.9 if goal.get("urgency") == "high" else 0.7,
                        source_conversation_id=None,
                    )
                    saved_count += 1

            # Save preferences
            if insights.get("preferences"):
                for key, value in insights["preferences"].items():
                    if value:
                        embedding_response = await openai_client.embeddings.create(
                            model=settings.OPENAI_EMBEDDING_MODEL, input=str(value)
                        )
                        embedding = embedding_response.data[0].embedding

                        self.db.save_user_memory(
                            user_id=user_id,
                            fact_type="preference",
                            fact_key=key,
                            fact_value=json.dumps(value)
                            if isinstance(value, list)
                            else str(value),
                            fact_embedding=embedding,
                            confidence_score=0.85,
                            source_conversation_id=None,
                        )
                        saved_count += 1

            # Save relationship insights
            if insights.get("relationship_insights"):
                for key, value in insights["relationship_insights"].items():
                    if value:
                        embedding_response = await openai_client.embeddings.create(
                            model=settings.OPENAI_EMBEDDING_MODEL,
                            input=str(value) if not isinstance(value, list) else ", ".join(value),
                        )
                        embedding = embedding_response.data[0].embedding

                        self.db.save_user_memory(
                            user_id=user_id,
                            fact_type="relationship",
                            fact_key=key,
                            fact_value=json.dumps(value)
                            if isinstance(value, list)
                            else str(value),
                            fact_embedding=embedding,
                            confidence_score=0.75,
                            source_conversation_id=None,
                        )
                        saved_count += 1

            logger.info(f"Saved {saved_count} insights for user {user_id}")
            return saved_count

        except Exception as e:
            logger.error(f"Error saving insights: {e}")
            return saved_count

    def _get_insights_preview(self, insights: Dict) -> Dict:
        """Generate a preview of extracted insights"""
        preview = {}

        if insights.get("personal_info", {}).get("name"):
            preview["name"] = insights["personal_info"]["name"]

        if insights.get("business_context", {}).get("company_name"):
            preview["company"] = insights["business_context"]["company_name"]

        if insights.get("pain_points"):
            preview["pain_points_count"] = len(insights["pain_points"])

        if insights.get("learning_goals"):
            preview["learning_goals_count"] = len(insights["learning_goals"])

        if insights.get("preferences", {}).get("communication_style"):
            preview["communication_style"] = insights["preferences"][
                "communication_style"
            ]

        return preview
