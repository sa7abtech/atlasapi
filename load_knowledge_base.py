#!/usr/bin/env python3
"""
ATLAS Knowledge Base Loader
Processes and uploads all knowledge base files to Supabase
"""

import sys
import logging
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from knowledge.processor import MarkdownProcessor
from knowledge.embeddings import EmbeddingGenerator
from knowledge.loader import KnowledgeLoader
from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def find_markdown_files() -> List[Path]:
    """Find all markdown files in the knowledge/data directory"""
    data_dir = Path(__file__).parent / "knowledge" / "data"
    markdown_files = []

    # Find all .md files recursively
    for md_file in data_dir.rglob("*.md"):
        # Skip sample playbook
        if md_file.name != "sample_playbook.md":
            markdown_files.append(md_file)

    return sorted(markdown_files)


def main():
    """Main processing pipeline"""

    print("\n" + "=" * 70)
    print("  ATLAS KNOWLEDGE BASE LOADER")
    print("=" * 70 + "\n")

    # Validate environment
    try:
        settings.validate()
        logger.info("✓ Environment variables validated")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        print(f"\n❌ Error: {e}")
        print("Please check your .env file and ensure all required variables are set.\n")
        sys.exit(1)

    # Find all markdown files
    logger.info("Searching for markdown files...")
    markdown_files = find_markdown_files()

    if not markdown_files:
        logger.error("No markdown files found in knowledge/data/")
        print("\n❌ No markdown files found in knowledge/data/")
        print("Please add your knowledge base files to knowledge/data/\n")
        sys.exit(1)

    print(f"\n📚 Found {len(markdown_files)} knowledge base files:")
    for f in markdown_files:
        rel_path = f.relative_to(Path(__file__).parent)
        print(f"   • {rel_path}")
    print()

    # Step 1: Process all markdown files
    print("=" * 70)
    print("STEP 1: Processing Markdown Files")
    print("=" * 70 + "\n")

    processor = MarkdownProcessor(
        min_chunk_tokens=500,
        max_chunk_tokens=750,
        overlap_tokens=50
    )

    all_chunks = []
    for md_file in markdown_files:
        try:
            logger.info(f"Processing: {md_file.name}")
            chunks = processor.process_markdown_file(str(md_file))
            all_chunks.extend(chunks)
            print(f"✓ {md_file.name}: {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Error processing {md_file.name}: {e}")
            print(f"❌ {md_file.name}: Failed - {e}")

    print(f"\n📊 Total chunks created: {len(all_chunks)}")

    # Calculate statistics
    total_tokens = sum(chunk['token_count'] for chunk in all_chunks)
    avg_tokens = total_tokens / len(all_chunks) if all_chunks else 0

    print(f"📊 Total tokens: {total_tokens:,}")
    print(f"📊 Average tokens per chunk: {avg_tokens:.1f}")

    # Category breakdown
    categories = {}
    for chunk in all_chunks:
        cat = chunk.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n📂 Categories:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {cat}: {count} chunks")

    # Step 2: Generate embeddings
    print("\n" + "=" * 70)
    print("STEP 2: Generating OpenAI Embeddings")
    print("=" * 70 + "\n")

    embedder = EmbeddingGenerator(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_EMBEDDING_MODEL,
        batch_size=settings.EMBEDDING_BATCH_SIZE
    )

    try:
        logger.info("Generating embeddings (this may take a few minutes)...")
        chunks_with_embeddings = embedder.embed_chunks(all_chunks)
        print(f"✓ Generated {len(chunks_with_embeddings)} embeddings")

        # Verify embedding quality
        quality = embedder.verify_embedding_quality(chunks_with_embeddings)
        print(f"\n📊 Embedding Quality Check:")
        print(f"   • Dimension: {quality['embedding_dimension']}")
        print(f"   • All same dimension: {quality['all_same_dimension']}")
        print(f"   • Zero vectors: {quality['zero_vectors']}")
        print(f"   • Average magnitude: {quality['average_magnitude']:.4f}")

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        print(f"\n❌ Failed to generate embeddings: {e}")
        print("Please check your OpenAI API key and quota.\n")
        sys.exit(1)

    # Step 3: Upload to Supabase
    print("\n" + "=" * 70)
    print("STEP 3: Uploading to Supabase")
    print("=" * 70 + "\n")

    loader = KnowledgeLoader(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
    )

    try:
        logger.info("Uploading chunks to Supabase...")
        upload_stats = loader.upload_chunks_batch(
            chunks_with_embeddings,
            batch_size=100
        )

        print(f"\n📤 Upload Results:")
        print(f"   • Total: {upload_stats['total']}")
        print(f"   • Successful: {upload_stats['successful']}")
        print(f"   • Failed: {upload_stats['failed']}")
        print(f"   • Success rate: {upload_stats['success_rate']:.1f}%")

    except Exception as e:
        logger.error(f"Error uploading to Supabase: {e}")
        print(f"\n❌ Failed to upload: {e}")
        print("Please check your Supabase credentials and connection.\n")
        sys.exit(1)

    # Step 4: Verify uploads
    print("\n" + "=" * 70)
    print("STEP 4: Verifying Uploads")
    print("=" * 70 + "\n")

    try:
        logger.info("Verifying uploaded chunks...")
        verification = loader.verify_uploads(chunks_with_embeddings)

        print(f"✓ Verification Results:")
        print(f"   • Checked: {verification['total_checked']}")
        print(f"   • Verified: {verification['verified']}")
        print(f"   • Missing: {verification['missing']}")
        print(f"   • Verification rate: {verification['verification_rate']:.1f}%")

        if verification['missing'] > 0:
            print(f"\n⚠️  Some chunks were not found. First few missing:")
            for hash in verification['missing_hashes'][:5]:
                print(f"   • {hash}")

    except Exception as e:
        logger.error(f"Error verifying uploads: {e}")
        print(f"\n⚠️  Could not verify uploads: {e}")

    # Step 5: Get final statistics
    print("\n" + "=" * 70)
    print("STEP 5: Knowledge Base Statistics")
    print("=" * 70 + "\n")

    try:
        stats = loader.get_knowledge_stats()

        print(f"📊 Knowledge Base Summary:")
        print(f"   • Total chunks: {stats.get('total_chunks', 0)}")
        print(f"   • Average tokens per chunk: {stats.get('average_tokens_per_chunk', 0):.1f}")
        print(f"   • Total tokens: {stats.get('total_tokens', 0):,}")

        if 'categories' in stats and stats['categories']:
            print(f"\n   Categories:")
            for cat, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
                print(f"      • {cat}: {count}")

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        print(f"\n⚠️  Could not retrieve statistics: {e}")

    # Success!
    print("\n" + "=" * 70)
    print("  ✅ KNOWLEDGE BASE LOADING COMPLETE!")
    print("=" * 70 + "\n")

    print("🎉 Your ATLAS knowledge base is ready!")
    print("\nNext steps:")
    print("1. Start the services:")
    print("   ./start.sh")
    print("\n2. Test your bot on Telegram")
    print("\n3. Try these queries:")
    print("   • 'How can I optimize my AWS costs?'")
    print("   • 'Tell me about Odoo migration strategies'")
    print("   • 'What are the opportunities in Morocco B2B market?'")
    print("\n4. Monitor usage:")
    print("   curl http://localhost:8000/analytics")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)
