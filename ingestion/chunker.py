"""
Markdown document chunker for RAG systems.

Uses LangChain's MarkdownHeaderTextSplitter to split documents by headers,
preserving complete tables and lists.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

try:
    import tiktoken
    _enc = tiktoken.encoding_for_model("text-embedding-3-small")
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logger = logging.getLogger(__name__)



@dataclass
class ChunkingConfig:
    """Configuration for chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    def __post_init__(self):
        """Validate configuration."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")


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
            if TIKTOKEN_AVAILABLE:
                self.token_count = len(_enc.encode(self.content))
            else:
                self.token_count = len(self.content) // 4  # ~4 chars per token


# Regex pattern matching overlap comment blocks in the standardized markdown.
# Supports BOTH formats:
#   NEW (standardized):  <!-- OVERLAP CONTENT --> ... <!-- END OVERLAP CONTENT -->
#   OLD (legacy):        <!-- ======= -->
#                        <!-- OVERLAP CONTENT FROM: ... --> ... <!-- END OVERLAP FROM: ... -->
OVERLAP_BLOCK_PATTERN = re.compile(
    r'(?:'
        # --- NEW format (standardized PAH/BC files) ---
        r'<!--\s*OVERLAP CONTENT\s*-->'
        r'\s*\n'
        r'(.*?)'
        r'<!--\s*END OVERLAP CONTENT\s*-->'
    r'|'
        # --- OLD format (legacy files with FROM: labels) ---
        r'<!--\s*=+\s*-->\s*\n'
        r'<!--\s*OVERLAP CONTENT FROM:.*?-->\s*\n'
        r'(?:<!--.*?-->\s*\n)*'
        r'(.*?)'
        r'<!--\s*END OVERLAP FROM:.*?-->'
    r')',
    re.DOTALL
)


class MarkdownChunker:
    """
    Markdown header-based chunker using LangChain's MarkdownHeaderTextSplitter.
    
    Features:
    - Splits by H1 headers only (file-per-section architecture)
    - Strips overlap blocks (Grades, Levels, Abbreviations) to prevent
      duplicate chunks, then re-attaches them as context to the last chunk
    - Extracts [Grade X, Level Y] tags as structured metadata
    - Oversized chunks are auto-split by paragraphs with context preserved
    - Preserves complete tables and lists
    - Includes header hierarchy in metadata for context
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize markdown chunker."""
        self.config = config or ChunkingConfig()
        
        # Split on H1, H2, and H3 to ensure chunks aren't too large
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
        header_docs = self.splitter.split_text(stripped_content)
        
        # Apply recursive character text splitter on top to ensure no chunk exceeds limit
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size * 4, # rough approx of chars for chunk_size tokens
            chunk_overlap=self.config.chunk_overlap * 4,
            separators=["\n\n", "\n", " ", ""]
        )
        
        docs = text_splitter.split_documents(header_docs)
        
        # Convert to DocumentChunk objects
        chunks = []
        current_pos = 0
        
        for i, doc in enumerate(docs):
            chunk_content = doc.page_content
            
            # Build context path from header hierarchy
            context_parts = []
            for header_key in ["doc_title", "section", "subsection"]:
                if header_key in doc.metadata:
                    context_parts.append(doc.metadata[header_key])
            
            context_path = " > ".join(context_parts) if context_parts else ""
            
            # Find position in original content
            search_text = chunk_content[:100] if len(chunk_content) >= 100 else chunk_content
            start_pos = stripped_content.find(search_text, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(chunk_content)
            
            # Extract Evidence Grade, Level, and WHO Class tags
            # Supports multiple CPG formats:
            #   PAH: **[Grade I]**, **[Level C]**, **[Grade II-a, Level B]**, **[WHO Class III]**
            #   BC:  **[level I]**
            #   ED:  [Grade I-a, Level A]
            grades = []
            levels = []
            who_classes = []
            
            # Pattern 1: Combined [Grade X, Level Y] (with optional bold **)
            for m in re.finditer(r'\*{0,2}\[Grade\s+(I{1,3}[-]?[a-c]?),\s*Level\s+([A-C])\]\*{0,2}', chunk_content, re.IGNORECASE):
                g = m.group(1).upper()
                lv = m.group(2).upper()
                if g not in grades: grades.append(g)
                if lv not in levels: levels.append(lv)
            
            # Pattern 2: Standalone [Grade X] (no Level)
            for m in re.finditer(r'\*{0,2}\[Grade\s+(I{1,3}[-]?[a-c]?)\]\*{0,2}', chunk_content, re.IGNORECASE):
                g = m.group(1).upper()
                if g not in grades: grades.append(g)
            
            # Pattern 3: Standalone [Level X] (PAH: **[Level C]**, BC: **[level I]**)
            for m in re.finditer(r'\*{0,2}\[(?:L|l)evel\s+([A-C]|I{1,3})\]\*{0,2}', chunk_content):
                lv = m.group(1).upper()
                if lv not in levels: levels.append(lv)
            
            # Pattern 4: [WHO Class I-IV] (PAH functional classification)
            for m in re.finditer(r'\*{0,2}\[WHO\s+Class\s+(I{1,3}V?|IV)(?:[-\s]?[A-Z])?\]\*{0,2}', chunk_content, re.IGNORECASE):
                w = m.group(1).upper()
                if w not in who_classes: who_classes.append(w)
            
            chunk_metadata = {
                **base_metadata,
                "context_path": context_path,
                "total_chunks": len(docs),
                **doc.metadata
            }
            if grades:
                chunk_metadata["evidence_grades"] = grades
            if levels:
                chunk_metadata["evidence_levels"] = levels
            if who_classes:
                chunk_metadata["who_functional_classes"] = who_classes
            
            chunks.append(DocumentChunk(
                content=chunk_content.strip(),
                index=i,
                start_char=start_pos,
                end_char=end_pos,
                metadata=chunk_metadata
            ))
            
            current_pos = end_pos
        
        final_chunks = chunks
        
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
        
        if final_chunks:
            sizes = [len(c.content) for c in final_chunks]
            logger.info(
                f"📊 Chunk stats for '{title}': "
                f"count={len(sizes)}, "
                f"min={min(sizes)}, max={max(sizes)}, "
                f"avg={sum(sizes)//len(sizes)}, "
                f"has_evidence={sum(1 for c in final_chunks if c.metadata.get('evidence_grades') or c.metadata.get('evidence_levels'))}"
            )
            
        return final_chunks
    
    @staticmethod
    def _strip_overlap_blocks(content: str) -> tuple:
        """
        Strip overlap comment blocks from markdown content.
        
        Supports both formats:
            NEW: <!-- OVERLAP CONTENT --> ... <!-- END OVERLAP CONTENT -->
            OLD: <!-- OVERLAP CONTENT FROM: ... --> ... <!-- END OVERLAP FROM: ... -->
        
        Returns:
            Tuple of (stripped_content, list_of_overlap_block_texts)
        """
        overlap_blocks = []
        
        def collect_and_remove(match):
            # Alternation: group(1) = new format, group(2) = old format
            block_text = match.group(1) or match.group(2) or ""
            if block_text.strip():
                overlap_blocks.append(block_text.strip())
            return ""  # Remove from main content
        
        stripped = OVERLAP_BLOCK_PATTERN.sub(collect_and_remove, content)
        
        # Clean up any leftover separator lines from removal
        stripped = re.sub(r'\n{3,}', '\n\n', stripped)
        
        if overlap_blocks:
            logger.info(f"Stripped {len(overlap_blocks)} overlap block(s) before chunking")
        
        return stripped.strip(), overlap_blocks


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