"""
Main ingestion script for processing documents (Markdown, PDF, TXT) into vector DB and knowledge graph.

Enhanced for Clinical Practice Guidelines (CPG) with:
- Hierarchical structure parsing (Section -> Subsection -> Recommendation)
- Metadata extraction (Evidence Level, Grade, Target Population, Category)
- Table extraction to structured JSON
- Algorithm/flowchart description via Vision LLM
- Medical relationship extraction for knowledge graph
"""

import os
import asyncio
import logging
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse

import asyncpg
from dotenv import load_dotenv

# PDF processing
try:
    import pymupdf4llm
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: pymupdf4llm not installed. PDF support disabled. Run: pip install pymupdf4llm")

# CPG-specific parsing
try:
    from .cpg_parser import CPGParser, CPGChunk, CPGMetadataExtractor, create_cpg_parser
    CPG_PARSER_AVAILABLE = True
except ImportError:
    CPG_PARSER_AVAILABLE = False
    print("Warning: CPG parser not available. Using basic PDF processing.")

from .chunker import ChunkingConfig, MarkdownChunker, DocumentChunk
from .embedder import create_embedder
from .graph_builder import create_graph_builder

# Import agent utilities
try:
    from ..agent.db_utils import initialize_database, close_database, db_pool
    from ..agent.graph_utils import initialize_graph, close_graph
    from ..agent.models import IngestionConfig, IngestionResult
except ImportError:
    # For direct execution or testing
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agent.db_utils import initialize_database, close_database, db_pool
    from agent.graph_utils import initialize_graph, close_graph
    from agent.models import IngestionConfig, IngestionResult

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Pipeline for ingesting documents into vector DB and knowledge graph."""
    
    def __init__(
        self,
        config: IngestionConfig,
        documents_folder: str = "documents",
        clean_before_ingest: bool = False,
        use_cpg_parser: bool = True,  # Enable CPG parsing for medical documents
        save_processed: bool = True   # Save processed markdown to disk
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            config: Ingestion configuration
            documents_folder: Folder containing markdown documents
            clean_before_ingest: Whether to clean existing data before ingestion
            use_cpg_parser: Whether to use CPG-specific parsing for PDFs
            save_processed: Whether to save processed markdown files to disk
        """
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest
        self.use_cpg_parser = use_cpg_parser and CPG_PARSER_AVAILABLE
        self.save_processed = save_processed
        
        # Create processed output folder
        self.processed_folder = os.path.join(documents_folder, "_processed")
        if self.save_processed:
            os.makedirs(self.processed_folder, exist_ok=True)
        
        # Initialize components - use MarkdownChunker for structured docs
        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            max_chunk_size=config.max_chunk_size
        )
        
        self.chunker = MarkdownChunker(self.chunker_config)
        self.embedder = create_embedder()
        self.graph_builder = create_graph_builder()
        
        # CPG Parser for structured PDF processing
        if self.use_cpg_parser:
            self.cpg_parser = create_cpg_parser(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap
            )
            logger.info("CPG Parser enabled for structured PDF processing")
        else:
            self.cpg_parser = None
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connections."""
        if self._initialized:
            return
        
        logger.info("Initializing ingestion pipeline...")
        
        # Initialize database connections
        await initialize_database()
        await initialize_graph()
        await self.graph_builder.initialize()
        
        self._initialized = True
        logger.info("Ingestion pipeline initialized")
    
    async def close(self):
        """Close database connections."""
        if self._initialized:
            await self.graph_builder.close()
            await close_graph()
            await close_database()
            self._initialized = False
    
    async def ingest_documents(
        self,
        progress_callback: Optional[callable] = None
    ) -> List[IngestionResult]:
        """
        Ingest all documents from the documents folder.
        
        Args:
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of ingestion results
        """
        if not self._initialized:
            await self.initialize()
        
        # Clean existing data if requested
        if self.clean_before_ingest:
            await self._clean_databases()
        
        # Find all markdown files
        markdown_files = self._find_markdown_files()
        
        if not markdown_files:
            logger.warning(f"No markdown files found in {self.documents_folder}")
            return []
        
        logger.info(f"Found {len(markdown_files)} markdown files to process")
        
        results = []
        
        for i, file_path in enumerate(markdown_files):
            try:
                logger.info(f"Processing file {i+1}/{len(markdown_files)}: {file_path}")
                
                result = await self._ingest_single_document(file_path)
                results.append(result)
                
                if progress_callback:
                    progress_callback(i + 1, len(markdown_files))
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                results.append(IngestionResult(
                    document_id="",
                    title=os.path.basename(file_path),
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    processing_time_ms=0,
                    errors=[str(e)]
                ))
        
        # Log summary
        total_chunks = sum(r.chunks_created for r in results)
        total_errors = sum(len(r.errors) for r in results)
        
        logger.info(f"Ingestion complete: {len(results)} documents, {total_chunks} chunks, {total_errors} errors")
        
        return results
    
    async def _ingest_single_document(self, file_path: str) -> IngestionResult:
        """
        Ingest a single document.
        
        For PDF files with CPG parser enabled, uses hierarchical structure extraction.
        For other files, uses standard chunking.
        
        Args:
            file_path: Path to the document file
        
        Returns:
            Ingestion result
        """
        start_time = datetime.now()
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Check if this is a CPG PDF that should use structured parsing
        if file_ext == '.pdf' and self.use_cpg_parser:
            return await self._ingest_cpg_pdf(file_path, start_time)
        
        # Standard processing for non-CPG documents
        # Read document
        document_content = self._read_document(file_path)
        document_title = self._extract_title(document_content, file_path)
        document_source = os.path.relpath(file_path, self.documents_folder)
        
        # Extract metadata from content
        document_metadata = self._extract_document_metadata(document_content, file_path)
        
        logger.info(f"Processing document: {document_title}")
        
        # Chunk the document
        chunks = self.chunker.chunk_document(
            content=document_content,
            title=document_title,
            source=document_source,
            metadata=document_metadata
        )
        
        if not chunks:
            logger.warning(f"No chunks created for {document_title}")
            return IngestionResult(
                document_id="",
                title=document_title,
                chunks_created=0,
                entities_extracted=0,
                relationships_created=0,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                errors=["No chunks created"]
            )
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # Extract entities if configured
        entities_extracted = 0
        if self.config.extract_entities:
            chunks = await self.graph_builder.extract_entities_from_chunks(chunks)
            entities_extracted = sum(
                len(chunk.metadata.get("entities", {}).get("conditions", [])) +
                len(chunk.metadata.get("entities", {}).get("medications", [])) +
                len(chunk.metadata.get("entities", {}).get("procedures", []))
                for chunk in chunks
            )
            logger.info(f"Extracted {entities_extracted} entities")
        
        # Generate embeddings
        embedded_chunks = await self.embedder.embed_chunks(chunks)
        logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
        
        # Save to PostgreSQL
        document_id = await self._save_to_postgres(
            document_title,
            document_source,
            document_content,
            embedded_chunks,
            document_metadata
        )
        
        logger.info(f"Saved document to PostgreSQL with ID: {document_id}")
        
        # Add to knowledge graph (if enabled)
        relationships_created = 0
        graph_errors = []
        
        if not self.config.skip_graph_building:
            try:
                logger.info("Building knowledge graph relationships (this may take several minutes)...")
                graph_result = await self.graph_builder.add_document_to_graph(
                    chunks=embedded_chunks,
                    document_title=document_title,
                    document_source=document_source,
                    document_metadata=document_metadata
                )
                
                relationships_created = graph_result.get("episodes_created", 0)
                graph_errors = graph_result.get("errors", [])
                
                logger.info(f"Added {relationships_created} episodes to knowledge graph")
                
            except Exception as e:
                error_msg = f"Failed to add to knowledge graph: {str(e)}"
                logger.error(error_msg)
                graph_errors.append(error_msg)
        else:
            logger.info("Skipping knowledge graph building (skip_graph_building=True)")
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return IngestionResult(
            document_id=document_id,
            title=document_title,
            chunks_created=len(chunks),
            entities_extracted=entities_extracted,
            relationships_created=relationships_created,
            processing_time_ms=processing_time,
            errors=graph_errors
        )
    
    async def _ingest_cpg_pdf(self, file_path: str, start_time: datetime) -> IngestionResult:
        """
        Ingest a CPG PDF document with hierarchical structure parsing.
        
        This method:
        1. Parses PDF with structure-aware processing
        2. Extracts tables to JSON format
        3. Describes algorithms/flowcharts with Vision LLM
        4. Creates parent-child chunk relationships
        5. Extracts evidence levels and metadata
        6. Builds medical relationship graph
        
        Args:
            file_path: Path to the PDF file
            start_time: Processing start time
            
        Returns:
            Ingestion result
        """
        document_source = os.path.relpath(file_path, self.documents_folder)
        graph_errors = []
        
        try:
            # Parse CPG PDF with hierarchical structure
            logger.info(f"Parsing CPG PDF with structural analysis: {file_path}")
            full_content, cpg_chunks, doc_metadata = await self.cpg_parser.parse_pdf(file_path)
            
            document_title = doc_metadata.get('title', os.path.splitext(os.path.basename(file_path))[0])
            logger.info(f"Parsed CPG: {document_title} - {len(cpg_chunks)} chunks, {doc_metadata.get('table_count', 0)} tables, {doc_metadata.get('algorithm_count', 0)} algorithms")
            
            # Save processed content to disk for inspection
            if self.save_processed:
                await self._save_processed_files(file_path, full_content, cpg_chunks, doc_metadata)
            
            if not cpg_chunks:
                return IngestionResult(
                    document_id="",
                    title=document_title,
                    chunks_created=0,
                    entities_extracted=0,
                    relationships_created=0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    errors=["No chunks created from CPG PDF"]
                )
            
            # Convert CPGChunks to DocumentChunks with metadata
            document_chunks = []
            for cpg_chunk in cpg_chunks:
                # Build metadata with CPG-specific fields
                chunk_metadata = {
                    "section_hierarchy": cpg_chunk.section_hierarchy,
                    "parent_section": cpg_chunk.parent_section,
                    "evidence_level": cpg_chunk.evidence_level,
                    "grade": cpg_chunk.grade,
                    "target_population": cpg_chunk.target_population,
                    "category": cpg_chunk.category,
                    "is_recommendation": cpg_chunk.is_recommendation,
                    "is_table": cpg_chunk.is_table,
                    "is_algorithm": cpg_chunk.is_algorithm,
                    "page_numbers": cpg_chunk.page_numbers,
                    "title": document_title,
                    "source": document_source,
                    **cpg_chunk.metadata
                }
                
                # Add table data if present
                if cpg_chunk.table_data:
                    chunk_metadata["structured_content"] = cpg_chunk.table_data
                
                doc_chunk = DocumentChunk(
                    content=cpg_chunk.content,
                    index=cpg_chunk.index,
                    start_char=cpg_chunk.start_char,
                    end_char=cpg_chunk.end_char,
                    metadata=chunk_metadata,
                    token_count=cpg_chunk.token_count
                )
                document_chunks.append(doc_chunk)
            
            # Extract medical entities
            entities_extracted = 0
            if self.config.extract_entities:
                document_chunks = await self.graph_builder.extract_entities_from_chunks(document_chunks)
                entities_extracted = sum(
                    len(chunk.metadata.get("entities", {}).get("conditions", [])) +
                    len(chunk.metadata.get("entities", {}).get("medications", [])) +
                    len(chunk.metadata.get("entities", {}).get("procedures", [])) +
                    len(chunk.metadata.get("entities", {}).get("diagnostic_tools", []))
                    for chunk in document_chunks
                )
                logger.info(f"Extracted {entities_extracted} medical entities")
            
            # Generate embeddings
            embedded_chunks = await self.embedder.embed_chunks(document_chunks)
            logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
            
            # Save to PostgreSQL with CPG metadata
            document_id = await self._save_cpg_to_postgres(
                document_title,
                document_source,
                full_content,
                embedded_chunks,
                doc_metadata
            )
            
            logger.info(f"Saved CPG document to PostgreSQL with ID: {document_id}")
            
            # Build knowledge graph with medical relationships
            relationships_created = 0
            
            if not self.config.skip_graph_building:
                try:
                    logger.info("Building medical knowledge graph with relationships...")
                    
                    # First, extract medical relationships
                    rel_result = await self.graph_builder.build_relationship_graph(
                        embedded_chunks,
                        document_title
                    )
                    logger.info(f"Extracted {rel_result['total']} medical relationships: {rel_result['counts']}")
                    
                    # Add to Graphiti knowledge graph
                    graph_result = await self.graph_builder.add_document_to_graph(
                        chunks=embedded_chunks,
                        document_title=document_title,
                        document_source=document_source,
                        document_metadata=doc_metadata
                    )
                    
                    relationships_created = graph_result.get("episodes_created", 0)
                    graph_errors = graph_result.get("errors", [])
                    
                    logger.info(f"Added {relationships_created} episodes to knowledge graph")
                    
                except Exception as e:
                    error_msg = f"Failed to add to knowledge graph: {str(e)}"
                    logger.error(error_msg)
                    graph_errors.append(error_msg)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return IngestionResult(
                document_id=document_id,
                title=document_title,
                chunks_created=len(embedded_chunks),
                entities_extracted=entities_extracted,
                relationships_created=relationships_created,
                processing_time_ms=processing_time,
                errors=graph_errors
            )
            
        except Exception as e:
            logger.error(f"CPG PDF processing failed: {e}")
            # Fall back to standard processing
            logger.info("Falling back to standard PDF processing...")
            
            document_content = self._read_document(file_path)
            document_title = self._extract_title(document_content, file_path)
            document_metadata = self._extract_document_metadata(document_content, file_path)
            
            # Use standard chunking
            chunks = self.chunker.chunk_document(
                content=document_content,
                title=document_title,
                source=document_source,
                metadata=document_metadata
            )
            
            if self.config.extract_entities:
                chunks = await self.graph_builder.extract_entities_from_chunks(chunks)
            
            embedded_chunks = await self.embedder.embed_chunks(chunks)
            
            document_id = await self._save_to_postgres(
                document_title,
                document_source,
                document_content,
                embedded_chunks,
                document_metadata
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return IngestionResult(
                document_id=document_id,
                title=document_title,
                chunks_created=len(chunks),
                entities_extracted=0,
                relationships_created=0,
                processing_time_ms=processing_time,
                errors=[f"CPG parsing failed, used fallback: {str(e)}"]
            )
    
    async def _save_cpg_to_postgres(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[DocumentChunk],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Save CPG document and chunks to PostgreSQL with full metadata.
        
        Includes CPG-specific columns: evidence_level, grade, target_population,
        category, section_hierarchy, is_recommendation, is_table, is_algorithm.
        """
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Insert document
                document_result = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id::text
                    """,
                    title,
                    source,
                    content,
                    json.dumps(metadata)
                )
                
                document_id = document_result["id"]
                
                # First pass: Insert all chunks and collect IDs
                chunk_ids = {}
                for chunk in chunks:
                    # Convert embedding to PostgreSQL vector string format
                    embedding_data = None
                    if hasattr(chunk, 'embedding') and chunk.embedding:
                        embedding_data = '[' + ','.join(map(str, chunk.embedding)) + ']'
                    
                    # Extract CPG metadata
                    meta = chunk.metadata
                    section_hierarchy = meta.get("section_hierarchy", [])
                    structured_content = meta.get("structured_content")
                    
                    result = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index, metadata, token_count,
                            section_hierarchy, evidence_level, grade, target_population, category,
                            is_recommendation, is_table, is_algorithm, structured_content
                        )
                        VALUES (
                            $1::uuid, $2, $3::vector, $4, $5, $6,
                            $7, $8, $9, $10, $11,
                            $12, $13, $14, $15
                        )
                        RETURNING id::text
                        """,
                        document_id,
                        chunk.content,
                        embedding_data,
                        chunk.index,
                        json.dumps(meta),
                        chunk.token_count,
                        section_hierarchy,
                        meta.get("evidence_level"),
                        meta.get("grade"),
                        meta.get("target_population"),
                        meta.get("category"),
                        meta.get("is_recommendation", False),
                        meta.get("is_table", False),
                        meta.get("is_algorithm", False),
                        json.dumps(structured_content) if structured_content else None
                    )
                    
                    chunk_ids[chunk.index] = result["id"]
                
                # Second pass: Update parent_chunk_id for hierarchical relationships
                # This creates parent-child links between section and subsection chunks
                for chunk in chunks:
                    parent_section = chunk.metadata.get("parent_section")
                    if parent_section:
                        # Find the chunk with this section as its title
                        for other_chunk in chunks:
                            if other_chunk.metadata.get("section_hierarchy", [])[-1:] == [parent_section]:
                                await conn.execute(
                                    """
                                    UPDATE chunks SET parent_chunk_id = $1::uuid
                                    WHERE id = $2::uuid
                                    """,
                                    chunk_ids.get(other_chunk.index),
                                    chunk_ids.get(chunk.index)
                                )
                                break
                
                return document_id
    
    async def _save_processed_files(
        self,
        original_path: str,
        full_content: str,
        cpg_chunks: List,
        doc_metadata: Dict[str, Any]
    ) -> None:
        """
        Save processed CPG content to disk for inspection/debugging.
        
        Creates the following files in documents/_processed/:
        - {filename}.md - Full markdown content
        - {filename}_chunks.json - All chunks with metadata
        - {filename}_structure.json - Document structure and metadata
        
        Args:
            original_path: Original PDF file path
            full_content: Extracted markdown content
            cpg_chunks: List of CPGChunk objects
            doc_metadata: Document-level metadata
        """
        try:
            base_name = os.path.splitext(os.path.basename(original_path))[0]
            
            # 1. Save full markdown content
            md_path = os.path.join(self.processed_folder, f"{base_name}.md")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {doc_metadata.get('title', base_name)}\n\n")
                f.write(f"*Processed on: {datetime.now().isoformat()}*\n\n")
                f.write(f"*Pages: {doc_metadata.get('page_count', 'N/A')}*\n\n")
                f.write("---\n\n")
                f.write(full_content)
            logger.info(f"Saved processed markdown: {md_path}")
            
            # 2. Save chunks with metadata as JSON
            chunks_path = os.path.join(self.processed_folder, f"{base_name}_chunks.json")
            chunks_data = []
            for chunk in cpg_chunks:
                chunk_dict = {
                    "index": chunk.index,
                    "content": chunk.content[:500] + "..." if len(chunk.content) > 500 else chunk.content,
                    "content_length": len(chunk.content),
                    "section_hierarchy": chunk.section_hierarchy,
                    "parent_section": chunk.parent_section,
                    "evidence_level": chunk.evidence_level,
                    "grade": chunk.grade,
                    "target_population": chunk.target_population,
                    "category": chunk.category,
                    "is_recommendation": chunk.is_recommendation,
                    "is_table": chunk.is_table,
                    "is_algorithm": chunk.is_algorithm,
                    "page_numbers": chunk.page_numbers,
                }
                if chunk.table_data:
                    chunk_dict["table_data"] = chunk.table_data
                if chunk.algorithm_description:
                    chunk_dict["algorithm_description"] = chunk.algorithm_description[:300] + "..."
                chunks_data.append(chunk_dict)
            
            with open(chunks_path, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved chunks JSON: {chunks_path}")
            
            # 3. Save document structure summary
            structure_path = os.path.join(self.processed_folder, f"{base_name}_structure.json")
            structure_data = {
                "title": doc_metadata.get('title'),
                "page_count": doc_metadata.get('page_count'),
                "parse_date": doc_metadata.get('parse_date'),
                "total_chunks": len(cpg_chunks),
                "table_count": doc_metadata.get('table_count', 0),
                "algorithm_count": doc_metadata.get('algorithm_count', 0),
                "sections": doc_metadata.get('sections', []),
                "chunk_summary": {
                    "recommendations": sum(1 for c in cpg_chunks if c.is_recommendation),
                    "tables": sum(1 for c in cpg_chunks if c.is_table),
                    "algorithms": sum(1 for c in cpg_chunks if c.is_algorithm),
                    "by_grade": {
                        "Grade A": sum(1 for c in cpg_chunks if c.grade == "Grade A"),
                        "Grade B": sum(1 for c in cpg_chunks if c.grade == "Grade B"),
                        "Grade C": sum(1 for c in cpg_chunks if c.grade == "Grade C"),
                        "Key Recommendation": sum(1 for c in cpg_chunks if c.grade == "Key Recommendation"),
                    },
                    "by_category": {},
                    "by_population": {},
                }
            }
            
            # Count by category and population
            for chunk in cpg_chunks:
                if chunk.category:
                    structure_data["chunk_summary"]["by_category"][chunk.category] = \
                        structure_data["chunk_summary"]["by_category"].get(chunk.category, 0) + 1
                if chunk.target_population:
                    structure_data["chunk_summary"]["by_population"][chunk.target_population] = \
                        structure_data["chunk_summary"]["by_population"].get(chunk.target_population, 0) + 1
            
            with open(structure_path, 'w', encoding='utf-8') as f:
                json.dump(structure_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved structure JSON: {structure_path}")
            
            print(f"\n📁 Processed files saved to: {self.processed_folder}")
            print(f"   • {base_name}.md - Full markdown content")
            print(f"   • {base_name}_chunks.json - Chunks with metadata")
            print(f"   • {base_name}_structure.json - Document structure\n")
            
        except Exception as e:
            logger.warning(f"Failed to save processed files: {e}")
    
    def _find_markdown_files(self) -> List[str]:
        """Find all document files (markdown, txt, pdf) in the documents folder."""
        if not os.path.exists(self.documents_folder):
            logger.error(f"Documents folder not found: {self.documents_folder}")
            return []
        
        patterns = ["*.md", "*.markdown", "*.txt"]
        
        # Add PDF support if available
        if PDF_SUPPORT:
            patterns.append("*.pdf")
        
        files = []
        
        for pattern in patterns:
            found_files = glob.glob(os.path.join(self.documents_folder, "**", pattern), recursive=True)
            # Exclude files in _processed folder
            files.extend([f for f in found_files if "_processed" not in f])
        
        return sorted(files)
    
    def _read_document(self, file_path: str) -> str:
        """Read document content from file (supports .md, .txt, .pdf)."""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Handle PDF files
        if file_ext == '.pdf':
            if not PDF_SUPPORT:
                raise ValueError(f"PDF support not available. Install pymupdf4llm: pip install pymupdf4llm")
            
            logger.info(f"Converting PDF to markdown: {file_path}")
            try:
                # Convert PDF to markdown with table support
                markdown_content = pymupdf4llm.to_markdown(
                    file_path,
                    page_chunks=False,  # Get full document, not per-page
                    write_images=False,  # Skip image extraction for now
                )
                logger.info(f"PDF converted: {len(markdown_content)} characters")
                return markdown_content
            except Exception as e:
                logger.error(f"Failed to convert PDF {file_path}: {e}")
                raise
        
        # Handle text files (md, txt, markdown)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
    
    def _extract_title(self, content: str, file_path: str) -> str:
        """Extract title from document content or filename."""
        # Try to find markdown title
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # Fallback to filename
        return os.path.splitext(os.path.basename(file_path))[0]
    
    def _extract_document_metadata(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract metadata from document content."""
        metadata = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now().isoformat()
        }
        
        # Try to extract YAML frontmatter
        if content.startswith('---'):
            try:
                import yaml
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    frontmatter = content[4:end_marker]
                    yaml_metadata = yaml.safe_load(frontmatter)
                    if isinstance(yaml_metadata, dict):
                        metadata.update(yaml_metadata)
            except ImportError:
                logger.warning("PyYAML not installed, skipping frontmatter extraction")
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
        
        # Extract some basic metadata from content
        lines = content.split('\n')
        metadata['line_count'] = len(lines)
        metadata['word_count'] = len(content.split())
        
        return metadata
    
    async def _save_to_postgres(
        self,
        title: str,
        source: str,
        content: str,
        chunks: List[DocumentChunk],
        metadata: Dict[str, Any]
    ) -> str:
        """Save document and chunks to PostgreSQL."""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Insert document
                document_result = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id::text
                    """,
                    title,
                    source,
                    content,
                    json.dumps(metadata)
                )
                
                document_id = document_result["id"]
                
                # Insert chunks
                for chunk in chunks:
                    # Convert embedding to PostgreSQL vector string format
                    embedding_data = None
                    if hasattr(chunk, 'embedding') and chunk.embedding:
                        # PostgreSQL vector format: '[1.0,2.0,3.0]' (no spaces after commas)
                        embedding_data = '[' + ','.join(map(str, chunk.embedding)) + ']'
                    
                    await conn.execute(
                        """
                        INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, token_count)
                        VALUES ($1::uuid, $2, $3::vector, $4, $5, $6)
                        """,
                        document_id,
                        chunk.content,
                        embedding_data,
                        chunk.index,
                        json.dumps(chunk.metadata),
                        chunk.token_count
                    )
                
                return document_id
    
    async def _clean_databases(self):
        """Clean existing data from databases."""
        logger.warning("Cleaning existing data from databases...")
        
        # Clean PostgreSQL
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM messages")
                await conn.execute("DELETE FROM sessions")
                await conn.execute("DELETE FROM chunks")
                await conn.execute("DELETE FROM documents")
        
        logger.info("Cleaned PostgreSQL database")
        
        # Clean knowledge graph
        await self.graph_builder.clear_graph()
        logger.info("Cleaned knowledge graph")


async def main():
    """Main function for running ingestion."""
    parser = argparse.ArgumentParser(description="Ingest documents into vector DB and knowledge graph")
    parser.add_argument("--documents", "-d", default="documents", help="Documents folder path")
    parser.add_argument("--clean", "-c", action="store_true", help="Clean existing data before ingestion")
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size for splitting documents")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap size")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic chunking")
    parser.add_argument("--no-entities", action="store_true", help="Disable entity extraction")
    parser.add_argument("--fast", "-f", action="store_true", help="Fast mode: skip knowledge graph building")
    parser.add_argument("--no-cpg", action="store_true", help="Disable CPG-specific PDF parsing (use basic parsing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create ingestion configuration
    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        use_semantic_chunking=not args.no_semantic,
        extract_entities=not args.no_entities,
        skip_graph_building=args.fast
    )
    
    # Create and run pipeline
    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=args.clean,
        use_cpg_parser=not args.no_cpg
    )
    
    def progress_callback(current: int, total: int):
        print(f"Progress: {current}/{total} documents processed")
    
    try:
        start_time = datetime.now()
        
        results = await pipeline.ingest_documents(progress_callback)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # Print summary
        print("\n" + "="*60)
        print("INGESTION SUMMARY")
        print("="*60)
        print(f"Documents processed: {len(results)}")
        print(f"Total chunks created: {sum(r.chunks_created for r in results)}")
        print(f"Total entities extracted: {sum(r.entities_extracted for r in results)}")
        print(f"Total graph episodes: {sum(r.relationships_created for r in results)}")
        print(f"Total errors: {sum(len(r.errors) for r in results)}")
        print(f"Total processing time: {total_time:.2f} seconds")
        print()
        
        if pipeline.use_cpg_parser:
            print("CPG Features:")
            print("  ✓ Hierarchical structure parsing enabled")
            print("  ✓ Table extraction to JSON enabled")
            print("  ✓ Evidence level/Grade metadata extraction")
            print("  ✓ Medical relationship extraction")
            print()
        
        # Print individual results
        for result in results:
            status = "✓" if not result.errors else "✗"
            print(f"{status} {result.title}: {result.chunks_created} chunks, {result.entities_extracted} entities, {result.relationships_created} relationships")
            
            if result.errors:
                for error in result.errors:
                    print(f"  Error: {error}")
        
    except KeyboardInterrupt:
        print("\nIngestion interrupted by user")
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise
    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())