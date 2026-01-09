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


class MarkdownChunker:
    """
    Markdown header-based chunker using LangChain's MarkdownHeaderTextSplitter.
    
    Features:
    - Splits only by H1 headers (#) - each chunk is a complete section
    - Keeps ##, ###, #### subsections within the same chunk
    - Preserves complete tables and lists
    - Includes header hierarchy in metadata for context
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize markdown chunker."""
        self.config = config or ChunkingConfig()
        
        # Only split on H1 (#) - keeps all subsections together
        self.headers_to_split_on = [
            ("#", "doc_title"),
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
        
        # Split the document
        docs = self.splitter.split_text(content)
        
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
            
            chunk_metadata = {
                **base_metadata,
                "context_path": context_path,
                "total_chunks": len(docs),
                **doc.metadata
            }
            
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
        
        # Re-index chunks
        for i, chunk in enumerate(final_chunks):
            chunk.index = i
            chunk.metadata["total_chunks"] = len(final_chunks)
        
        return final_chunks
    
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