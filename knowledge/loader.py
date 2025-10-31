"""
Knowledge Loader
Uploads processed chunks with embeddings to Supabase
"""

import logging
import asyncio
from typing import List, Dict, Optional
from supabase import create_client, Client
import json

logger = logging.getLogger("atlas.knowledge.loader")


class KnowledgeLoader:
    """Load knowledge chunks into Supabase database"""

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize the knowledge loader

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (service role for full access)
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = "atlas_core_knowledge"

    def prepare_chunk_for_insert(self, chunk: Dict) -> Dict:
        """
        Prepare a chunk dictionary for database insertion

        Args:
            chunk: Chunk dictionary with embedding

        Returns:
            Dictionary formatted for Supabase insert
        """
        # Convert embedding list to format Supabase expects
        embedding_str = json.dumps(chunk["embedding"])

        return {
            "content": chunk["content"],
            "content_hash": chunk["content_hash"],
            "embedding": embedding_str,
            "category": chunk.get("category"),
            "subcategory": chunk.get("subcategory"),
            "source_file": chunk.get("source_file"),
            "chunk_index": chunk.get("chunk_index"),
            "token_count": chunk.get("token_count"),
            "metadata": json.dumps(chunk.get("metadata", {})),
        }

    def upload_chunk(self, chunk: Dict) -> bool:
        """
        Upload a single chunk to Supabase

        Args:
            chunk: Chunk dictionary with embedding

        Returns:
            True if successful, False otherwise
        """
        try:
            prepared_chunk = self.prepare_chunk_for_insert(chunk)

            response = self.client.table(self.table_name).upsert(
                prepared_chunk, on_conflict="content_hash"
            ).execute()

            logger.debug(f"Uploaded chunk: {chunk.get('content_hash')}")
            return True

        except Exception as e:
            logger.error(f"Error uploading chunk: {e}")
            return False

    def upload_chunks_batch(self, chunks: List[Dict], batch_size: int = 100) -> Dict:
        """
        Upload multiple chunks in batches

        Args:
            chunks: List of chunk dictionaries with embeddings
            batch_size: Number of chunks to upload per batch

        Returns:
            Dictionary with upload statistics
        """
        total = len(chunks)
        successful = 0
        failed = 0

        logger.info(f"Starting upload of {total} chunks in batches of {batch_size}")

        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total - 1) // batch_size + 1

            logger.info(f"Processing batch {batch_num}/{total_batches}")

            try:
                # Prepare all chunks in batch
                prepared_batch = [self.prepare_chunk_for_insert(chunk) for chunk in batch]

                # Upload batch
                response = self.client.table(self.table_name).upsert(
                    prepared_batch, on_conflict="content_hash"
                ).execute()

                successful += len(batch)
                logger.info(f"Successfully uploaded batch {batch_num}")

            except Exception as e:
                logger.error(f"Error uploading batch {batch_num}: {e}")
                # Try uploading individually
                for chunk in batch:
                    if self.upload_chunk(chunk):
                        successful += 1
                    else:
                        failed += 1

        stats = {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
        }

        logger.info(
            f"Upload complete: {successful}/{total} successful ({stats['success_rate']:.1f}%)"
        )
        return stats

    def delete_all_knowledge(self) -> bool:
        """
        Delete all knowledge from the database (use with caution!)

        Returns:
            True if successful
        """
        try:
            logger.warning("Deleting all knowledge from database")
            response = self.client.table(self.table_name).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            logger.info("Successfully deleted all knowledge")
            return True
        except Exception as e:
            logger.error(f"Error deleting knowledge: {e}")
            return False

    def get_knowledge_stats(self) -> Dict:
        """
        Get statistics about the knowledge base

        Returns:
            Dictionary with statistics
        """
        try:
            # Count total chunks
            response = self.client.table(self.table_name).select("id", count="exact").execute()
            total_chunks = response.count

            # Count by category
            category_response = (
                self.client.table(self.table_name)
                .select("category")
                .execute()
            )

            categories = {}
            if category_response.data:
                for row in category_response.data:
                    cat = row.get("category", "Unknown")
                    categories[cat] = categories.get(cat, 0) + 1

            # Get token statistics
            token_response = (
                self.client.table(self.table_name)
                .select("token_count")
                .execute()
            )

            token_counts = [row["token_count"] for row in token_response.data if row.get("token_count")]
            avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0

            stats = {
                "total_chunks": total_chunks,
                "categories": categories,
                "average_tokens_per_chunk": round(avg_tokens, 2),
                "total_tokens": sum(token_counts),
            }

            logger.info(f"Knowledge base stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error getting knowledge stats: {e}")
            return {"error": str(e)}

    def verify_uploads(self, chunks: List[Dict]) -> Dict:
        """
        Verify that uploaded chunks exist in the database

        Args:
            chunks: List of chunks that were uploaded

        Returns:
            Dictionary with verification results
        """
        verified = 0
        missing = []

        logger.info(f"Verifying {len(chunks)} uploaded chunks")

        for chunk in chunks:
            try:
                content_hash = chunk["content_hash"]
                response = (
                    self.client.table(self.table_name)
                    .select("content_hash")
                    .eq("content_hash", content_hash)
                    .execute()
                )

                if response.data:
                    verified += 1
                else:
                    missing.append(content_hash)

            except Exception as e:
                logger.error(f"Error verifying chunk: {e}")
                missing.append(chunk.get("content_hash", "unknown"))

        result = {
            "total_checked": len(chunks),
            "verified": verified,
            "missing": len(missing),
            "missing_hashes": missing[:10],  # First 10 missing
            "verification_rate": (verified / len(chunks) * 100) if chunks else 0,
        }

        logger.info(
            f"Verification complete: {verified}/{len(chunks)} verified ({result['verification_rate']:.1f}%)"
        )
        return result

    def update_chunk_metadata(self, content_hash: str, metadata: Dict) -> bool:
        """
        Update metadata for a specific chunk

        Args:
            content_hash: Hash of the chunk to update
            metadata: New metadata dictionary

        Returns:
            True if successful
        """
        try:
            response = (
                self.client.table(self.table_name)
                .update({"metadata": json.dumps(metadata)})
                .eq("content_hash", content_hash)
                .execute()
            )

            logger.info(f"Updated metadata for chunk: {content_hash}")
            return True

        except Exception as e:
            logger.error(f"Error updating chunk metadata: {e}")
            return False


def main():
    """Example usage and pipeline runner"""
    import sys
    import os
    from processor import MarkdownProcessor
    from embeddings import EmbeddingGenerator

    logging.basicConfig(level=logging.INFO)

    # Check for required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not all([supabase_url, supabase_key, openai_key]):
        print("Error: Required environment variables not set")
        print("Required: SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python loader.py <markdown_file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    print("\n=== ATLAS Knowledge Loading Pipeline ===\n")

    # Step 1: Process markdown
    print("Step 1: Processing markdown file...")
    processor = MarkdownProcessor()
    chunks = processor.process_markdown_file(file_path)
    print(f"✓ Processed {len(chunks)} chunks")

    # Step 2: Generate embeddings
    print("\nStep 2: Generating embeddings...")
    embedder = EmbeddingGenerator(api_key=openai_key)
    chunks_with_embeddings = embedder.embed_chunks(chunks)
    print(f"✓ Generated {len(chunks_with_embeddings)} embeddings")

    # Verify embedding quality
    quality = embedder.verify_embedding_quality(chunks_with_embeddings)
    print(f"✓ Embedding quality check: {quality}")

    # Step 3: Upload to Supabase
    print("\nStep 3: Uploading to Supabase...")
    loader = KnowledgeLoader(supabase_url=supabase_url, supabase_key=supabase_key)
    upload_stats = loader.upload_chunks_batch(chunks_with_embeddings)
    print(f"✓ Upload complete: {upload_stats}")

    # Step 4: Verify uploads
    print("\nStep 4: Verifying uploads...")
    verification = loader.verify_uploads(chunks_with_embeddings)
    print(f"✓ Verification: {verification}")

    # Step 5: Get knowledge base stats
    print("\nStep 5: Knowledge base statistics...")
    stats = loader.get_knowledge_stats()
    print(f"✓ Stats: {stats}")

    print("\n=== Pipeline Complete ===")


if __name__ == "__main__":
    main()
