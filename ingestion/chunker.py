"""
Markdown document chunker for RAG systems.

Uses LangChain's MarkdownHeaderTextSplitter to split documents by headers,
preserving complete tables and lists.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    """Configuration for chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunk_size: int = 2000
    min_chunk_size: int = 100
    
    def __post_init__(self):
        """Validate configuration."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.min_chunk_size <= 0:
            raise ValueError("Minimum chunk size must be positive")


@dataclass
class DocumentChunk:
    """Represents a document chunk."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]
    token_count: Optional[int] = None
    
    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count is None:
            self.token_count = len(self.content) // 4  # ~4 chars per token


# Regex pattern matching overlap comment blocks in the standardized markdown
# Matches: <!-- OVERLAP CONTENT FROM: ... --> ... <!-- END OVERLAP FROM: ... -->
OVERLAP_BLOCK_PATTERN = re.compile(
    r'<!--\s*=+\s*-->\s*\n'
    r'<!--\s*OVERLAP CONTENT FROM:.*?-->\s*\n'
    r'(?:<!--.*?-->\s*\n)*'
    r'(.*?)'
    r'<!--\s*END OVERLAP FROM:.*?-->',
    re.DOTALL
)


class MarkdownChunker:
    """
    Markdown header-based chunker using LangChain's MarkdownHeaderTextSplitter.
    
    Features:
    - Splits by H1, H2, H3 headers for parent-child chunk architecture
    - Strips overlap blocks (Grades, Levels, Abbreviations) to prevent
      duplicate chunks, then re-attaches them as context to the last chunk
    - Extracts [Grade X, Level Y] tags as structured metadata
    - Tracks parent-child relationships via chunk_type and parent_header
    - Preserves complete tables and lists
    - Includes header hierarchy in metadata for context
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize markdown chunker."""
        self.config = config or ChunkingConfig()
        
        # Split on H1, H2, H3 to isolate clinical topics and recommendations
        self.headers_to_split_on = [
            ("#", "doc_title"),
            ("##", "section"),
            ("###", "subsection")
        ]
        
        self.splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on,
            strip_headers=False  # Keep headers in content for context
        )
    
    def chunk_document(
        self,
        content: str,
        title: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk document by markdown headers.
        
        Args:
            content: Document content (markdown)
            title: Document title
            source: Document source
            metadata: Additional metadata
        
        Returns:
            List of document chunks with header hierarchy in metadata
        """
        if not content.strip():
            return []
        
        base_metadata = {
            "title": title,
            "source": source,
            "chunk_method": "markdown_header",
            **(metadata or {})
        }
        
        # --- Pre-processing: Strip overlap blocks before chunking ---
        # This prevents Grades/Levels/Abbreviations tables from becoming
        # separate searchable chunks (they'd be near-duplicates across files).
        # The stripped content is saved and re-attached to the last real chunk.
        stripped_content, overlap_blocks = self._strip_overlap_blocks(content)
        
        # Split the document (overlap-free)
        docs = self.splitter.split_text(stripped_content)
        
        # Convert to DocumentChunk objects
        chunks = []
        current_pos = 0
        
        for i, doc in enumerate(docs):
            chunk_content = doc.page_content
            
            # Build context path from header hierarchy
            context_parts = []
            for header_key in ["doc_title", "section", "subsection", "subsubsection"]:
                if header_key in doc.metadata:
                    context_parts.append(doc.metadata[header_key])
            
            context_path = " > ".join(context_parts) if context_parts else ""
            
            # Find position in original content
            search_text = chunk_content[:100] if len(chunk_content) >= 100 else chunk_content
            start_pos = content.find(search_text, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(chunk_content)
            
            # Extract Evidence Grade and Level tags
            grades = []
            levels = []
            for match in re.finditer(r'\[Grade\s+(I{1,3}[-]?[a-c]?),\s*Level\s+([A-D])\]', chunk_content, re.IGNORECASE):
                grade_val = match.group(1).upper()
                level_val = match.group(2).upper()
                if grade_val not in grades:
                    grades.append(grade_val)
                if level_val not in levels:
                    levels.append(level_val)
            
            # Calculate parent relationship from headers
            parent_id = None
            chunk_type = "parent"
            if "subsection" in doc.metadata:
                chunk_type = "child"
                parent_id = doc.metadata.get("section") or doc.metadata.get("doc_title")
            elif "section" in doc.metadata:
                chunk_type = "mid"
                parent_id = doc.metadata.get("doc_title")
            
            chunk_metadata = {
                **base_metadata,
                "context_path": context_path,
                "total_chunks": len(docs),
                "chunk_type": chunk_type,
                "parent_header": parent_id,
                **doc.metadata
            }
            if grades and levels:
                chunk_metadata["evidence_grades"] = grades
                chunk_metadata["evidence_levels"] = levels
            
            chunks.append(DocumentChunk(
                content=chunk_content.strip(),
                index=i,
                start_char=start_pos,
                end_char=end_pos,
                metadata=chunk_metadata
            ))
            
            current_pos = end_pos
        
        # Split oversized chunks while preserving context
        final_chunks = []
        for chunk in chunks:
            if len(chunk.content) > self.config.max_chunk_size:
                final_chunks.extend(self._split_large_chunk(chunk))
            else:
                final_chunks.append(chunk)
        
        # --- Post-processing: Re-attach overlap content to last chunk ---
        # The overlap tables (Grades, Levels, Abbreviations) are appended to
        # the last real chunk so the LLM still has them as context, but they
        # are NOT standalone searchable chunks.
        if final_chunks and overlap_blocks:
            combined_overlap = "\n\n---\n\n".join(overlap_blocks)
            last_chunk = final_chunks[-1]
            last_chunk.content += f"\n\n---\n<!-- REFERENCE CONTEXT (not a separate chunk) -->\n\n{combined_overlap}"
            last_chunk.metadata["has_overlap_context"] = True
            last_chunk.metadata["overlap_sources"] = [
                "Grades of Recommendation", "Levels of Evidence", "Abbreviations"
            ]
        
        # Re-index chunks
        for i, chunk in enumerate(final_chunks):
            chunk.index = i
            chunk.metadata["total_chunks"] = len(final_chunks)
        
        return final_chunks
    
    @staticmethod
    def _strip_overlap_blocks(content: str) -> tuple:
        """
        Strip overlap comment blocks from markdown content.
        
        Overlap blocks are wrapped in standardized HTML comments:
            <!-- OVERLAP CONTENT FROM: ... -->
            ... content ...
            <!-- END OVERLAP FROM: ... -->
        
        Returns:
            Tuple of (stripped_content, list_of_overlap_block_texts)
        """
        overlap_blocks = []
        
        def collect_and_remove(match):
            overlap_blocks.append(match.group(1).strip())
            return ""  # Remove from main content
        
        stripped = OVERLAP_BLOCK_PATTERN.sub(collect_and_remove, content)
        
        # Clean up any leftover separator lines from removal
        stripped = re.sub(r'\n{3,}', '\n\n', stripped)
        
        if overlap_blocks:
            logger.info(f"Stripped {len(overlap_blocks)} overlap block(s) before chunking")
        
        return stripped.strip(), overlap_blocks
    
    def _split_large_chunk(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """Split a large chunk into smaller pieces while preserving context."""
        content = chunk.content
        context_path = chunk.metadata.get("context_path", "")
        
        paragraphs = re.split(r'\n\s*\n', content)
        sub_chunks = []
        current_content = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            potential = current_content + "\n\n" + para if current_content else para
            
            if len(potential) <= self.config.chunk_size:
                current_content = potential
            else:
                if current_content:
                    sub_content = current_content
                    if context_path and not sub_content.startswith("#"):
                        sub_content = f"<!-- CONTEXT: {context_path} -->\n\n{sub_content}"
                    
                    sub_chunks.append(DocumentChunk(
                        content=sub_content,
                        index=len(sub_chunks),
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        metadata=chunk.metadata.copy()
                    ))
                current_content = para
        
        if current_content:
            sub_content = current_content
            if context_path and not sub_content.startswith("#"):
                sub_content = f"<!-- CONTEXT: {context_path} -->\n\n{sub_content}"
            
            sub_chunks.append(DocumentChunk(
                content=sub_content,
                index=len(sub_chunks),
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata=chunk.metadata.copy()
            ))
        
        return sub_chunks if sub_chunks else [chunk]


# Convenience function
def create_chunker(config: Optional[ChunkingConfig] = None) -> MarkdownChunker:
    """Create a markdown chunker with the given configuration."""
    return MarkdownChunker(config)


# Example usage
if __name__ == "__main__":
    sample = """
# ED Treatment Algorithm

## Step 1: Assessment
- Medical history
- IIEF-5 questionnaire

## Step 2: Diagnosis

| Type | Description |
|------|-------------|
| Organic | Physical cause |
| Psychogenic | Psychological |

## Step 3: Treatment
### Mild ED
- Lifestyle changes
- PDE5 inhibitors
"""
    
    chunker = MarkdownChunker()
    chunks = chunker.chunk_document(sample, "ED Algorithm", "algorithm.md")
    
    for chunk in chunks:
        print(f"\n--- {chunk.metadata.get('context_path', 'Root')} ---")
        print(f"{chunk.content[:100]}...")