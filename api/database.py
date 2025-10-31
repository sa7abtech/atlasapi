"""
Database Module
Handles all Supabase database operations for ATLAS
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client
import hashlib

logger = logging.getLogger("atlas.api.database")


class AtlasDatabase:
    """ATLAS database operations handler"""

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize database connection

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Database connection initialized")

    # ==================== User Management ====================

    def get_or_create_user(self, user_id: int, username: str = None, full_name: str = None) -> Dict:
        """
        Get existing user or create new one

        Args:
            user_id: Telegram user ID
            username: Telegram username
            full_name: User's full name

        Returns:
            User dictionary
        """
        try:
            # Try to get existing user
            response = self.client.table("atlas_users").select("*").eq("user_id", user_id).execute()

            if response.data:
                # Update last seen
                self.client.table("atlas_users").update(
                    {"last_seen_at": datetime.utcnow().isoformat()}
                ).eq("user_id", user_id).execute()
                return response.data[0]

            # Create new user
            new_user = {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "preferred_language": "en",
            }

            response = self.client.table("atlas_users").insert(new_user).execute()
            logger.info(f"Created new user: {user_id}")
            return response.data[0]

        except Exception as e:
            logger.error(f"Error getting/creating user: {e}")
            return {}

    def update_user_stats(self, user_id: int, tokens_used: int = 0, tokens_saved: int = 0):
        """Update user usage statistics"""
        try:
            # Get current stats
            response = self.client.table("atlas_users").select("*").eq("user_id", user_id).execute()

            if response.data:
                user = response.data[0]
                self.client.table("atlas_users").update({
                    "total_conversations": user.get("total_conversations", 0) + 1,
                    "total_tokens_used": user.get("total_tokens_used", 0) + tokens_used,
                    "total_tokens_saved": user.get("total_tokens_saved", 0) + tokens_saved,
                    "last_seen_at": datetime.utcnow().isoformat(),
                }).eq("user_id", user_id).execute()

                logger.debug(f"Updated stats for user {user_id}")

        except Exception as e:
            logger.error(f"Error updating user stats: {e}")

    # ==================== Conversation Management ====================

    def save_conversation(
        self,
        user_id: int,
        user_message: str,
        user_message_embedding: List[float],
        bot_response: str,
        context_chunks: List[str],
        model_used: str,
        tokens_used: int,
        response_time_ms: int,
        language: str = "en",
    ) -> Optional[str]:
        """
        Save conversation to database

        Returns:
            Conversation ID if successful, None otherwise
        """
        try:
            conversation = {
                "user_id": user_id,
                "user_message": user_message,
                "user_message_embedding": json.dumps(user_message_embedding),
                "bot_response": bot_response,
                "context_chunks": context_chunks,
                "model_used": model_used,
                "tokens_used": tokens_used,
                "response_time_ms": response_time_ms,
                "language": language,
            }

            response = self.client.table("atlas_conversations").insert(conversation).execute()

            if response.data:
                conversation_id = response.data[0]["id"]
                logger.info(f"Saved conversation: {conversation_id}")
                return conversation_id

        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return None

    def get_recent_conversations(
        self, user_id: int, limit: int = 5
    ) -> List[Dict]:
        """
        Get recent conversations for a user

        Args:
            user_id: User ID
            limit: Maximum number of conversations to retrieve

        Returns:
            List of conversation dictionaries
        """
        try:
            response = (
                self.client.table("atlas_conversations")
                .select("user_message, bot_response, created_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            conversations = response.data if response.data else []
            logger.debug(f"Retrieved {len(conversations)} recent conversations for user {user_id}")
            return conversations

        except Exception as e:
            logger.error(f"Error getting recent conversations: {e}")
            return []

    # ==================== User Memory Management ====================

    def save_user_memory(
        self,
        user_id: int,
        fact_type: str,
        fact_key: str,
        fact_value: str,
        fact_embedding: List[float],
        confidence_score: float = 1.0,
        source_conversation_id: str = None,
    ) -> bool:
        """
        Save or update user memory fact

        Args:
            user_id: User ID
            fact_type: Type of fact (infrastructure, pain_point, business_context, preference)
            fact_key: Unique key for the fact
            fact_value: The actual fact/value
            fact_embedding: Embedding vector for the fact
            confidence_score: Confidence in this fact (0.0-1.0)
            source_conversation_id: ID of conversation where fact was learned

        Returns:
            True if successful
        """
        try:
            memory = {
                "user_id": user_id,
                "fact_type": fact_type,
                "fact_key": fact_key,
                "fact_value": fact_value,
                "fact_embedding": json.dumps(fact_embedding),
                "confidence_score": confidence_score,
                "source_conversation_id": source_conversation_id,
                "last_referenced_at": datetime.utcnow().isoformat(),
            }

            # Upsert (insert or update)
            response = self.client.table("atlas_client_memory").upsert(
                memory, on_conflict="user_id,fact_key"
            ).execute()

            logger.debug(f"Saved memory for user {user_id}: {fact_key}")
            return True

        except Exception as e:
            logger.error(f"Error saving user memory: {e}")
            return False

    def get_user_memory(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Get user memory facts

        Args:
            user_id: User ID
            limit: Maximum number of facts to retrieve

        Returns:
            List of memory fact dictionaries
        """
        try:
            response = (
                self.client.table("atlas_client_memory")
                .select("fact_type, fact_key, fact_value, confidence_score")
                .eq("user_id", user_id)
                .order("last_referenced_at", desc=True)
                .limit(limit)
                .execute()
            )

            memories = response.data if response.data else []
            logger.debug(f"Retrieved {len(memories)} memory facts for user {user_id}")
            return memories

        except Exception as e:
            logger.error(f"Error getting user memory: {e}")
            return []

    def update_memory_reference(self, user_id: int, fact_key: str):
        """Update the last referenced timestamp and increment counter for a memory"""
        try:
            # Get current times_referenced
            response = (
                self.client.table("atlas_client_memory")
                .select("times_referenced")
                .eq("user_id", user_id)
                .eq("fact_key", fact_key)
                .execute()
            )

            if response.data:
                current_times = response.data[0].get("times_referenced", 0)
                self.client.table("atlas_client_memory").update({
                    "times_referenced": current_times + 1,
                    "last_referenced_at": datetime.utcnow().isoformat(),
                }).eq("user_id", user_id).eq("fact_key", fact_key).execute()

        except Exception as e:
            logger.error(f"Error updating memory reference: {e}")

    # ==================== Cache Management ====================

    def get_cached_response(self, query_hash: str) -> Optional[Dict]:
        """
        Get cached response for a query

        Args:
            query_hash: Hash of the normalized query

        Returns:
            Cached response dictionary if found and not expired, None otherwise
        """
        try:
            response = (
                self.client.table("atlas_insights_cache")
                .select("*")
                .eq("query_hash", query_hash)
                .gt("expires_at", datetime.utcnow().isoformat())
                .execute()
            )

            if response.data:
                cache_entry = response.data[0]

                # Increment hit count
                self.client.table("atlas_insights_cache").update({
                    "hit_count": cache_entry.get("hit_count", 0) + 1,
                    "last_hit_at": datetime.utcnow().isoformat(),
                }).eq("query_hash", query_hash).execute()

                logger.info(f"Cache hit for query: {query_hash}")
                return cache_entry

            logger.debug(f"Cache miss for query: {query_hash}")
            return None

        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None

    def save_cached_response(
        self,
        query_text: str,
        query_embedding: List[float],
        cached_response: str,
        language: str = "en",
        expiry_hours: int = 24,
    ) -> bool:
        """
        Save response to cache

        Args:
            query_text: Original query text
            query_embedding: Query embedding vector
            cached_response: Response to cache
            language: Language of the query
            expiry_hours: Hours until cache expires

        Returns:
            True if successful
        """
        try:
            query_hash = hashlib.md5(query_text.lower().encode()).hexdigest()
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

            cache_entry = {
                "query_hash": query_hash,
                "query_text": query_text,
                "query_embedding": json.dumps(query_embedding),
                "cached_response": cached_response,
                "language": language,
                "expires_at": expires_at.isoformat(),
            }

            response = self.client.table("atlas_insights_cache").upsert(
                cache_entry, on_conflict="query_hash"
            ).execute()

            logger.info(f"Cached response for query: {query_hash}")
            return True

        except Exception as e:
            logger.error(f"Error saving cached response: {e}")
            return False

    def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries

        Returns:
            Number of entries deleted
        """
        try:
            response = (
                self.client.table("atlas_insights_cache")
                .delete()
                .lt("expires_at", datetime.utcnow().isoformat())
                .execute()
            )

            count = len(response.data) if response.data else 0
            logger.info(f"Cleaned up {count} expired cache entries")
            return count

        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
            return 0

    # ==================== Analytics ====================

    def get_conversation_analytics(self, days: int = 7) -> Dict:
        """
        Get conversation analytics for the past N days

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with analytics data
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)

            response = (
                self.client.table("atlas_conversations")
                .select("*")
                .gte("created_at", since_date.isoformat())
                .execute()
            )

            conversations = response.data if response.data else []

            if not conversations:
                return {"total_conversations": 0, "unique_users": 0}

            total_conversations = len(conversations)
            unique_users = len(set(c["user_id"] for c in conversations))
            total_tokens = sum(c.get("tokens_used", 0) for c in conversations)
            avg_response_time = (
                sum(c.get("response_time_ms", 0) for c in conversations) / total_conversations
            )

            gpt4_usage = sum(1 for c in conversations if c.get("model_used") == "gpt-4")
            gpt35_usage = sum(1 for c in conversations if c.get("model_used") == "gpt-3.5-turbo")

            analytics = {
                "period_days": days,
                "total_conversations": total_conversations,
                "unique_users": unique_users,
                "total_tokens_used": total_tokens,
                "avg_tokens_per_conversation": total_tokens / total_conversations,
                "avg_response_time_ms": avg_response_time,
                "gpt4_usage": gpt4_usage,
                "gpt35_usage": gpt35_usage,
            }

            return analytics

        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return {"error": str(e)}
