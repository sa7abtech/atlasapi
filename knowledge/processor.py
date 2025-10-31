"""
Knowledge Processor
Handles markdown file chunking into semantic chunks for embedding
"""

import re
import hashlib
import logging
from typing import List, Dict, Optional
from pathlib import Path
import tiktoken

logger = logging.getLogger("atlas.knowledge.processor")


class MarkdownProcessor:
    """Process markdown documents into semantic chunks"""

    def __init__(
        self,
        min_chunk_tokens: int = 500,
        max_chunk_tokens: int = 750,
        overlap_tokens: int = 50,
    ):
        """
        Initialize the markdown processor

        Args:
            min_chunk_tokens: Minimum tokens per chunk
            max_chunk_tokens: Maximum tokens per chunk
            overlap_tokens: Number of overlapping tokens between chunks
        """
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")  # For OpenAI models

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        return len(self.encoding.encode(text))

    def read_markdown_file(self, file_path: str) -> str:
        """Read markdown file content"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"Successfully read file: {file_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def extract_metadata_from_content(self, content: str) -> Dict:
        """
        Extract metadata from markdown content
        Looks for patterns like:
        - # Headings for categories
        - --- for separators
        - Frontmatter metadata
        """
        metadata = {
            "categories": [],
            "topics": [],
            "has_code_blocks": False,
            "has_lists": False,
        }

        # Extract main headings as categories
        headings = re.findall(r"^#+ (.+)$", content, re.MULTILINE)
        if headings:
            metadata["categories"] = headings[:3]  # Top 3 headings

        # Check for code blocks
        if "```" in content:
            metadata["has_code_blocks"] = True

        # Check for lists
        if re.search(r"^[\*\-\+] ", content, re.MULTILINE):
            metadata["has_lists"] = True

        return metadata

    def split_by_sections(self, content: str) -> List[Dict]:
        """
        Split markdown content by sections (headers)
        Returns list of sections with their content and level
        """
        sections = []
        current_section = {"level": 0, "title": "Introduction", "content": ""}

        lines = content.split("\n")
        for line in lines:
            # Check if line is a header
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                # Save previous section if it has content
                if current_section["content"].strip():
                    sections.append(current_section.copy())

                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {"level": level, "title": title, "content": line + "\n"}
            else:
                current_section["content"] += line + "\n"

        # Add the last section
        if current_section["content"].strip():
            sections.append(current_section)

        logger.info(f"Split content into {len(sections)} sections")
        return sections

    def create_chunks_from_section(self, section: Dict) -> List[str]:
        """
        Create token-sized chunks from a section
        Tries to keep sections together, but splits if too large
        """
        content = section["content"].strip()
        token_count = self.count_tokens(content)

        # If section fits in one chunk, return it
        if token_count <= self.max_chunk_tokens:
            return [content]

        # Otherwise, split by paragraphs
        paragraphs = content.split("\n\n")
        chunks = []
        current_chunk = section["title"] if section.get("title") else ""
        current_tokens = self.count_tokens(current_chunk)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = self.count_tokens(para)

            # If adding this paragraph exceeds max, save current chunk
            if current_tokens + para_tokens > self.max_chunk_tokens and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap (last sentence or heading)
                overlap = self._get_overlap(current_chunk)
                current_chunk = overlap + "\n\n" + para
                current_tokens = self.count_tokens(current_chunk)
            else:
                current_chunk += "\n\n" + para
                current_tokens += para_tokens

        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get overlap text (last sentence or last N tokens)"""
        sentences = re.split(r"[.!?]+", text)
        if len(sentences) > 1:
            overlap = sentences[-2].strip()  # Second to last sentence
            if self.count_tokens(overlap) <= self.overlap_tokens:
                return overlap

        # Fall back to last N tokens
        tokens = self.encoding.encode(text)
        overlap_tokens = tokens[-self.overlap_tokens :]
        return self.encoding.decode(overlap_tokens)

    def generate_chunk_hash(self, content: str) -> str:
        """Generate a unique hash for chunk content"""
        return hashlib.md5(content.encode()).hexdigest()

    def categorize_chunk(self, chunk: str, section: Dict) -> Dict:
        """
        Categorize a chunk based on its content and section
        Returns category and subcategory
        """
        content_lower = chunk.lower()
        title_lower = section.get("title", "").lower()

        # Define categories based on keywords
        category_keywords = {
            "AWS Cloud": ["aws", "cloud", "ec2", "s3", "rds", "lambda", "infrastructure"],
            "Cost Optimization": ["cost", "savings", "pricing", "budget", "roi", "optimize"],
            "Odoo/ERP": ["odoo", "erp", "sage", "migration", "crm"],
            "Technical Architecture": [
                "architecture",
                "design",
                "system",
                "database",
                "api",
            ],
            "Morocco Market": [
                "morocco",
                "maroc",
                "maghreb",
                "mad",
                "dirham",
                "casablanca",
            ],
            "Best Practices": ["best practice", "recommendation", "should", "must", "guideline"],
            "Troubleshooting": [
                "problem",
                "issue",
                "error",
                "troubleshoot",
                "debug",
                "fix",
            ],
        }

        # Find matching categories
        matched_categories = []
        for category, keywords in category_keywords.items():
            if any(keyword in content_lower or keyword in title_lower for keyword in keywords):
                matched_categories.append(category)

        # Determine primary category
        if matched_categories:
            primary_category = matched_categories[0]
            subcategory = matched_categories[1] if len(matched_categories) > 1 else None
        else:
            primary_category = "General Knowledge"
            subcategory = None

        return {"category": primary_category, "subcategory": subcategory}

    def process_markdown_file(self, file_path: str) -> List[Dict]:
        """
        Process a markdown file into semantic chunks with metadata

        Returns:
            List of chunk dictionaries with content, metadata, and embeddings info
        """
        logger.info(f"Processing markdown file: {file_path}")

        # Read file
        content = self.read_markdown_file(file_path)

        # Extract global metadata
        global_metadata = self.extract_metadata_from_content(content)

        # Split into sections
        sections = self.split_by_sections(content)

        # Process each section into chunks
        all_chunks = []
        chunk_index = 0

        for section in sections:
            section_chunks = self.create_chunks_from_section(section)

            for chunk_content in section_chunks:
                # Generate metadata for this chunk
                token_count = self.count_tokens(chunk_content)
                content_hash = self.generate_chunk_hash(chunk_content)
                categorization = self.categorize_chunk(chunk_content, section)

                chunk_data = {
                    "content": chunk_content,
                    "content_hash": content_hash,
                    "token_count": token_count,
                    "chunk_index": chunk_index,
                    "category": categorization["category"],
                    "subcategory": categorization["subcategory"],
                    "source_file": Path(file_path).name,
                    "section_title": section.get("title"),
                    "section_level": section.get("level"),
                    "metadata": {
                        **global_metadata,
                        "section": section.get("title"),
                    },
                }

                all_chunks.append(chunk_data)
                chunk_index += 1

        logger.info(
            f"Processed {len(all_chunks)} chunks from {len(sections)} sections. "
            f"Average tokens per chunk: {sum(c['token_count'] for c in all_chunks) / len(all_chunks):.0f}"
        )

        return all_chunks

    def process_multiple_files(self, file_paths: List[str]) -> List[Dict]:
        """Process multiple markdown files"""
        all_chunks = []

        for file_path in file_paths:
            try:
                chunks = self.process_markdown_file(file_path)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue

        logger.info(f"Total chunks from all files: {len(all_chunks)}")
        return all_chunks


def main():
    """Example usage"""
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python processor.py <markdown_file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    processor = MarkdownProcessor()
    chunks = processor.process_markdown_file(file_path)

    print(f"\nProcessed {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks[:3]):  # Show first 3
        print(f"\n--- Chunk {i+1} ---")
        print(f"Category: {chunk['category']}")
        print(f"Tokens: {chunk['token_count']}")
        print(f"Content preview: {chunk['content'][:200]}...")


if __name__ == "__main__":
    main()
