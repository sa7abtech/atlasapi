"""
Embeddings Generator
Generates OpenAI embeddings for text chunks
"""

import logging
import time
from typing import List, Dict, Optional
import asyncio
from openai import AsyncOpenAI, OpenAI
import numpy as np

logger = logging.getLogger("atlas.knowledge.embeddings")


class EmbeddingGenerator:
    """Generate embeddings using OpenAI API"""

    def __init__(self, api_key: str, model: str = "text-embedding-ada-002", batch_size: int = 50):
        """
        Initialize the embedding generator

        Args:
            api_key: OpenAI API key
            model: Embedding model to use
            batch_size: Number of texts to process in parallel
        """
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.embedding_dimension = 1536  # text-embedding-ada-002 dimension

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Replace newlines for better embedding quality
            text = text.replace("\n", " ")

            response = self.client.embeddings.create(input=[text], model=self.model)

            embedding = response.data[0].embedding

            logger.debug(f"Generated embedding for text of length {len(text)}")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def generate_embedding_async(self, text: str) -> List[float]:
        """
        Generate embedding asynchronously

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            text = text.replace("\n", " ")

            response = await self.async_client.embeddings.create(input=[text], model=self.model)

            embedding = response.data[0].embedding
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding async: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            # Process in batches to avoid rate limits
            all_embeddings = []

            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                batch = [text.replace("\n", " ") for text in batch]

                logger.info(
                    f"Processing embedding batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1}"
                )

                response = self.client.embeddings.create(input=batch, model=self.model)

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # Rate limiting: wait between batches
                if i + self.batch_size < len(texts):
                    time.sleep(1)  # 1 second between batches

            logger.info(f"Generated {len(all_embeddings)} embeddings")
            return all_embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings in batch: {e}")
            raise

    async def generate_embeddings_batch_async(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts asynchronously

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            all_embeddings = []

            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                batch = [text.replace("\n", " ") for text in batch]

                logger.info(
                    f"Processing async embedding batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1}"
                )

                response = await self.async_client.embeddings.create(input=batch, model=self.model)

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # Rate limiting
                if i + self.batch_size < len(texts):
                    await asyncio.sleep(1)

            logger.info(f"Generated {len(all_embeddings)} embeddings asynchronously")
            return all_embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings in batch async: {e}")
            raise

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Add embeddings to chunk dictionaries

        Args:
            chunks: List of chunk dictionaries from processor

        Returns:
            List of chunks with added 'embedding' field
        """
        logger.info(f"Generating embeddings for {len(chunks)} chunks")

        # Extract text content
        texts = [chunk["content"] for chunk in chunks]

        # Generate embeddings
        embeddings = self.generate_embeddings_batch(texts)

        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        logger.info("Successfully added embeddings to all chunks")
        return chunks

    async def embed_chunks_async(self, chunks: List[Dict]) -> List[Dict]:
        """
        Add embeddings to chunk dictionaries asynchronously

        Args:
            chunks: List of chunk dictionaries from processor

        Returns:
            List of chunks with added 'embedding' field
        """
        logger.info(f"Generating embeddings for {len(chunks)} chunks asynchronously")

        texts = [chunk["content"] for chunk in chunks]
        embeddings = await self.generate_embeddings_batch_async(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        logger.info("Successfully added embeddings to all chunks asynchronously")
        return chunks

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0 to 1)
        """
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def verify_embedding_quality(self, chunks: List[Dict]) -> Dict:
        """
        Verify the quality of generated embeddings

        Args:
            chunks: List of chunks with embeddings

        Returns:
            Dictionary with quality metrics
        """
        if not chunks or "embedding" not in chunks[0]:
            return {"error": "No embeddings found"}

        embeddings = [chunk["embedding"] for chunk in chunks]

        # Check dimensions
        dimensions = [len(emb) for emb in embeddings]
        all_same_dim = len(set(dimensions)) == 1

        # Check for zero vectors
        zero_vectors = sum(1 for emb in embeddings if all(v == 0 for v in emb))

        # Calculate average magnitude
        magnitudes = [np.linalg.norm(emb) for emb in embeddings]
        avg_magnitude = np.mean(magnitudes)

        metrics = {
            "total_embeddings": len(embeddings),
            "embedding_dimension": dimensions[0] if dimensions else 0,
            "all_same_dimension": all_same_dim,
            "zero_vectors": zero_vectors,
            "average_magnitude": float(avg_magnitude),
            "min_magnitude": float(min(magnitudes)) if magnitudes else 0,
            "max_magnitude": float(max(magnitudes)) if magnitudes else 0,
        }

        logger.info(f"Embedding quality check: {metrics}")
        return metrics


def main():
    """Example usage"""
    import sys
    import os

    logging.basicConfig(level=logging.INFO)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Example texts
    texts = [
        "AWS cloud migration can reduce infrastructure costs by 40-60%",
        "Odoo ERP system is popular in Morocco for business management",
        "Multi-currency support is essential for Moroccan businesses dealing internationally",
    ]

    generator = EmbeddingGenerator(api_key=api_key)

    # Generate single embedding
    print("\n=== Single Embedding ===")
    embedding = generator.generate_embedding(texts[0])
    print(f"Generated embedding of dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    # Generate batch embeddings
    print("\n=== Batch Embeddings ===")
    embeddings = generator.generate_embeddings_batch(texts)
    print(f"Generated {len(embeddings)} embeddings")

    # Calculate similarity
    print("\n=== Similarity Check ===")
    sim = generator.cosine_similarity(embeddings[0], embeddings[1])
    print(f"Similarity between first two texts: {sim:.4f}")


if __name__ == "__main__":
    main()
