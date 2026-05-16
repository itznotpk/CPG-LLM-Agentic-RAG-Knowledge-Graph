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
import sys
import asyncio
import logging
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse

# Force UTF-8 on stdout/stderr so clinical content with non-cp1252 characters
# (e.g. β, →, ₂) does not crash ingestion on Windows and silently drop a whole
# section. Without this, a single Greek/arrow/subscript glyph raises
# UnicodeEncodeError and the file's chunks are never persisted.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
        save_processed: bool = True,  # Save processed markdown to disk
        dry_run: bool = False         # Run without saving
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            config: Ingestion configuration
            documents_folder: Folder containing markdown documents
            clean_before_ingest: Whether to clean existing data before ingestion
            use_cpg_parser: Whether to use CPG-specific parsing for PDFs
            save_processed: Whether to save processed markdown files to disk
            dry_run: Whether to skip DB saving and embeddings
        """
        self.config = config
        self.documents_folder = documents_folder
        self.clean_before_ingest = clean_before_ingest
        self.use_cpg_parser = use_cpg_parser and CPG_PARSER_AVAILABLE
        self.save_processed = save_processed
        self.dry_run = dry_run
        
        # Create processed output folder
        self.processed_folder = os.path.join(documents_folder, "_processed")
        if self.save_processed and not self.dry_run:
            os.makedirs(self.processed_folder, exist_ok=True)
        
        # Initialize components - use MarkdownChunker for structured docs
        self.chunker_config = ChunkingConfig(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
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
        
        if self.dry_run:
            logger.info("Dry-run mode: skipping database and graph initialization")
            self._initialized = True
            return
        
        # Initialize database connections
        await initialize_database()
        
        # Only initialize Neo4j graph if graph building is enabled
        if not self.config.skip_graph_building:
            await initialize_graph()
            await self.graph_builder.initialize()
        else:
            logger.info("Skipping Neo4j graph initialization (--skip-graph)")
        
        self._initialized = True
        logger.info("Ingestion pipeline initialized")
    
    async def close(self):
        """Close database connections."""
        if self._initialized and not self.dry_run:
            if not self.config.skip_graph_building:
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
        
        if self.dry_run:
            self._print_dry_run_summary(document_title, chunks)
            return IngestionResult(
                document_id="(dry-run)",
                title=document_title,
                chunks_created=len(chunks),
                entities_extracted=0,
                relationships_created=0,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                errors=[]
            )
        
        # Extract entities for standard RAG metadata (PostgreSQL)
        chunks = await self.graph_builder.extract_entities_from_chunks(
            chunks,
            use_llm=not self.config.skip_graph_building
        )
        entities_extracted = sum(len(c.metadata.get("entities", {})) for c in chunks)
        
        # Extract LLM relationship triples BEFORE saving to PostgreSQL
        # so they are included in the metadata JSON column
        relationships_created = 0
        all_triples = []
        rel_counts = {}
        
        if not self.config.skip_graph_building:
            logger.info("Extracting LLM relationship triples...")
            for chunk in chunks:
                triples = await self.graph_builder._extract_triples_with_llm(
                    text=chunk.content,
                    chunk_index=chunk.index,
                    source=chunk.metadata.get("source", "")
                )
                
                # Attach triples to chunk metadata so they are saved to PostgreSQL
                chunk.metadata["relationships"] = triples
                
                for t in triples:
                    t["source_document"] = document_title
                    rel = t.get("relation", "OTHER")
                    rel_counts[rel] = rel_counts.get(rel, 0) + 1
                
                all_triples.extend(triples)
            
            relationships_created = len(all_triples)
            logger.info(f"Extracted {relationships_created} triples: {rel_counts}")
        
        # Generate embeddings and save to PostgreSQL (unless skipping vector DB)
        document_id = ""
        embedded_chunks = chunks  # fallback for graph-only mode
        
        if not self.config.skip_vector_db:
            embedded_chunks = await self.embedder.embed_chunks(chunks)
            logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
            
            # Save to PostgreSQL (now includes relationships in metadata)
            document_id = await self._save_to_postgres(
                document_title,
                document_source,
                document_content,
                embedded_chunks,
                document_metadata
            )
            logger.info(f"Saved document to PostgreSQL with ID: {document_id}")
        else:
            logger.info("Skipping PostgreSQL vector DB (skip_vector_db=True)")
        
        # Write triples to Neo4j + Graphiti knowledge graph
        graph_errors = []
        
        if not self.config.skip_graph_building:
            try:
                logger.info("Writing triples to Neo4j and Graphiti...")
                
                # Write extracted triples to Neo4j as typed edges
                if all_triples:
                    await self.graph_builder._write_triples_to_neo4j(all_triples, document_title)
                    logger.info(f"Wrote {len(all_triples)} triples to Neo4j")
                
                # Add to Graphiti knowledge graph
                graph_result = await self.graph_builder.add_document_to_graph(
                    chunks=embedded_chunks,
                    document_title=document_title,
                    document_source=document_source,
                    document_metadata=document_metadata
                )
                
                graph_errors = graph_result.get("errors", [])
                logger.info(f"Added {graph_result.get('episodes_created', 0)} episodes to knowledge graph")
                
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
            
            if self.dry_run:
                self._print_dry_run_summary(document_title, document_chunks)
                return IngestionResult(
                    document_id="(dry-run)",
                    title=document_title,
                    chunks_created=len(document_chunks),
                    entities_extracted=0,
                    relationships_created=0,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    errors=[]
                )
            
            # Extract entities for standard RAG metadata (PostgreSQL)
            document_chunks = await self.graph_builder.extract_entities_from_chunks(
                document_chunks,
                use_llm=not self.config.skip_graph_building
            )
            entities_extracted = sum(len(c.metadata.get("entities", {})) for c in document_chunks)
            
            # Extract LLM relationship triples BEFORE saving to PostgreSQL
            # so they are included in the metadata JSON column
            relationships_created = 0
            all_triples = []
            rel_counts = {}
            
            if not self.config.skip_graph_building:
                logger.info("Extracting LLM relationship triples...")
                for chunk in document_chunks:
                    triples = await self.graph_builder._extract_triples_with_llm(
                        text=chunk.content,
                        chunk_index=chunk.index,
                        source=chunk.metadata.get("source", "")
                    )
                    
                    # Attach triples to chunk metadata so they are saved to PostgreSQL
                    chunk.metadata["relationships"] = triples
                    
                    for t in triples:
                        t["source_document"] = document_title
                        rel = t.get("relation", "OTHER")
                        rel_counts[rel] = rel_counts.get(rel, 0) + 1
                    
                    all_triples.extend(triples)
                
                relationships_created = len(all_triples)
                logger.info(f"Extracted {relationships_created} triples: {rel_counts}")
            
            # Generate embeddings
            embedded_chunks = await self.embedder.embed_chunks(document_chunks)
            logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
            
            # Save to PostgreSQL with CPG metadata (now includes relationships)
            document_id = await self._save_to_postgres(
                document_title,
                document_source,
                full_content,
                embedded_chunks,
                doc_metadata
            )
            
            logger.info(f"Saved CPG document to PostgreSQL with ID: {document_id}")
            
            # Write triples to Neo4j + Graphiti knowledge graph
            graph_errors = []
            
            if not self.config.skip_graph_building:
                try:
                    # Write extracted triples to Neo4j as typed edges
                    if all_triples:
                        await self.graph_builder._write_triples_to_neo4j(all_triples, document_title)
                        logger.info(f"Wrote {len(all_triples)} triples to Neo4j")
                    
                    # Add to Graphiti knowledge graph (episodes)
                    graph_result = await self.graph_builder.add_document_to_graph(
                        chunks=embedded_chunks,
                        document_title=document_title,
                        document_source=document_source,
                        document_metadata=doc_metadata
                    )
                    
                    graph_errors = graph_result.get("errors", [])
                    logger.info(f"Added {graph_result.get('episodes_created', 0)} episodes to knowledge graph")
                    
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
            
            # Entity extraction removed — handled by build_relationship_graph (LLM triples)
            
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
                    "content": chunk.content,  # Full content saved for debugging
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
        
        # Handle text files (md, txt, markdown). Strict UTF-8 only: silent
        # fallback to latin-1 / cp1252 produced mojibake (â, Ã, â¥) baked into
        # both embedded text and KG triples. Fail loud so the offending file
        # can be re-saved as UTF-8 before re-ingest.
        with open(file_path, 'r', encoding='utf-8', errors='strict') as f:
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
        
        # Try to extract <!-- METADATA --> HTML comment blocks (Breast Cancer format)
        import re
        meta_match = re.search(
            r'<!--\s*METADATA\s*\n(.*?)\n\s*-->',
            content, re.DOTALL
        )
        if meta_match:
            meta_block = meta_match.group(1)
            # Fields that should be stored as arrays (comma-separated → list)
            ARRAY_FIELDS = {'category', 'treatment_type'}
            for line in meta_block.strip().split('\n'):
                line = line.strip()
                if ':' in line:
                    key, _, value = line.partition(':')
                    key = key.strip()
                    value = value.strip()
                    if key and value:  # Only add non-empty values
                        if key in ARRAY_FIELDS:
                            # Split comma-separated values into a list, strip each
                            metadata[key] = [v.strip() for v in value.split(',') if v.strip()]
                        else:
                            metadata[key] = value
        
        # Extract CPG name from parent folder (e.g. "Breast-Cancer(3rd Edition)")
        parent_folder = os.path.basename(os.path.dirname(file_path))
        if parent_folder and parent_folder != self.documents_folder:
            metadata["cpg_name"] = parent_folder
        
        # Extract section number from filename (e.g. "section-20-..." -> 20)
        basename = os.path.basename(file_path)
        sec_match = re.match(r'section-(\d+)', basename)
        if sec_match:
            metadata["section_number"] = int(sec_match.group(1))
        
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
                # Upsert document — never overwrite scope columns set by the
                # classifier/verifier (icd11_scope, scope_verified, verified_at, verified_by).
                document_result = await conn.fetchrow(
                    """
                    INSERT INTO documents (title, source, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (source) DO UPDATE SET
                        title      = EXCLUDED.title,
                        content    = EXCLUDED.content,
                        metadata   = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id::text
                    """,
                    title,
                    source,
                    content,
                    json.dumps(metadata)
                )

                document_id = document_result["id"]

                # Delete old chunks for this document
                await conn.execute(
                    "DELETE FROM chunks WHERE document_id = $1::uuid",
                    document_id
                )

                # Three-pass insert to satisfy FK ordering:
                #   Pass 1 — H1 parents (no embedding)
                #   Pass 2 — cap-split H2 intermediates (no embedding, parent → H1)
                #   Pass 3 — normal H2 + H3 + h1_leaf (embedded, parent → H1 or cap-split H2)

                h1_chunks = [c for c in chunks if c.chunk_level == "h1"]
                cap_h2_chunks = [
                    c for c in chunks
                    if c.chunk_level == "h2" and c.metadata.get("cap_split")
                ]
                leaf_chunks = [
                    c for c in chunks
                    if c.chunk_level in ("h2", "h3", "h1_leaf")
                    and not c.metadata.get("cap_split")
                ]

                # Pass 1: H1 parents → build index→UUID map
                parent_uuid_by_index: Dict[int, str] = {}
                for chunk in h1_chunks:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index, metadata,
                            token_count, chunk_level, start_char, end_char, parent_chunk_id
                        )
                        VALUES (
                            $1::uuid, $2, NULL, $3, $4,
                            $5, $6, $7, $8, NULL
                        )
                        RETURNING id::text
                        """,
                        document_id,
                        chunk.content,
                        chunk.index,
                        json.dumps(chunk.metadata),
                        chunk.token_count,
                        chunk.chunk_level,
                        chunk.start_char,
                        chunk.end_char,
                    )
                    parent_uuid_by_index[chunk.index] = row["id"]

                # Pass 2: cap-split H2 intermediates → build index→UUID map for H3 children
                h2_uuid_by_index: Dict[int, str] = {}
                for chunk in cap_h2_chunks:
                    # Resolve H1 parent by nearest preceding H1 index
                    h1_parent_id = chunk.metadata.get("parent_chunk_id")
                    if h1_parent_id is None:
                        for idx in sorted(parent_uuid_by_index.keys(), reverse=True):
                            if idx < chunk.index:
                                h1_parent_id = parent_uuid_by_index[idx]
                                break
                    cap_meta = {**chunk.metadata}
                    if h1_parent_id:
                        cap_meta["parent_chunk_id"] = h1_parent_id
                    row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index, metadata,
                            token_count, chunk_level, start_char, end_char, parent_chunk_id
                        )
                        VALUES (
                            $1::uuid, $2, NULL, $3, $4,
                            $5, $6, $7, $8, $9::uuid
                        )
                        RETURNING id::text
                        """,
                        document_id,
                        chunk.content,
                        chunk.index,
                        json.dumps(cap_meta),
                        chunk.token_count,
                        chunk.chunk_level,
                        chunk.start_char,
                        chunk.end_char,
                        h1_parent_id,
                    )
                    h2_uuid_by_index[chunk.index] = row["id"]
                    chunk.metadata["chunk_id"] = row["id"]
                    chunk.metadata["parent_chunk_id"] = h1_parent_id

                # Pass 3: normal H2 + H3 + h1_leaf (all embedded)
                for chunk in leaf_chunks:
                    embedding_data = None
                    if hasattr(chunk, 'embedding') and chunk.embedding:
                        embedding_data = '[' + ','.join(map(str, chunk.embedding)) + ']'

                    if chunk.chunk_level == "h3":
                        # H3 parent is the cap-split H2, keyed by cap_split_h2_index
                        cap_idx = chunk.metadata.get("cap_split_h2_index")
                        parent_chunk_id = h2_uuid_by_index.get(cap_idx) if cap_idx is not None else None
                    else:
                        # Normal H2 / h1_leaf — parent is the nearest preceding H1
                        parent_chunk_id = chunk.metadata.get("parent_chunk_id")
                        if parent_chunk_id is None:
                            for idx in sorted(parent_uuid_by_index.keys(), reverse=True):
                                if idx < chunk.index:
                                    parent_chunk_id = parent_uuid_by_index[idx]
                                    break

                    child_meta = {**chunk.metadata}
                    if parent_chunk_id:
                        child_meta["parent_chunk_id"] = parent_chunk_id

                    child_row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, content, embedding, chunk_index, metadata,
                            token_count, chunk_level, start_char, end_char, parent_chunk_id
                        )
                        VALUES (
                            $1::uuid, $2, $3::vector, $4, $5,
                            $6, $7, $8, $9, $10::uuid
                        )
                        RETURNING id::text
                        """,
                        document_id,
                        chunk.content,
                        embedding_data,
                        chunk.index,
                        json.dumps(child_meta),
                        chunk.token_count,
                        chunk.chunk_level,
                        chunk.start_char,
                        chunk.end_char,
                        parent_chunk_id,
                    )
                    chunk.metadata["chunk_id"] = child_row["id"]
                    chunk.metadata["parent_chunk_id"] = parent_chunk_id

                return document_id

    def _print_dry_run_summary(self, title: str, chunks: List[DocumentChunk]):
        sizes = [len(c.content) for c in chunks]
        print(f"\n[DOC] {title}")
        print(f"   Chunks: {len(chunks)}")
        print(f"   Sizes:  {sizes}")
        print(f"   Total chars: {sum(sizes)}")
        for i, chunk in enumerate(chunks):
            preview = chunk.content[:120].replace('\n', ' ')
            print(f"   [{i}] ({len(chunk.content)} chars) {preview}...")
            if chunk.metadata.get("evidence_grades"):
                print(f"       Grades: {chunk.metadata['evidence_grades']}")
            if chunk.metadata.get("evidence_levels"):
                print(f"       Levels: {chunk.metadata['evidence_levels']}")
    
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
    parser.add_argument("--skip-graph", action="store_true", help="Skip Neo4j graph building (vector DB only)")
    parser.add_argument("--skip-pg", action="store_true", help="Skip PostgreSQL vector DB (graph only)")
    parser.add_argument("--no-cpg", action="store_true", help="Disable CPG-specific PDF parsing (use basic parsing)")
    parser.add_argument("--dry-run", action="store_true", help="Run chunking without database writes or embedding generation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create ingestion configuration
    # --fast is a shortcut for --skip-graph
    skip_graph = args.fast or args.skip_graph
    
    config = IngestionConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        use_semantic_chunking=not args.no_semantic,
        extract_entities=not args.no_entities,
        skip_graph_building=skip_graph,
        skip_vector_db=args.skip_pg
    )
    
    if skip_graph and args.skip_pg:
        print("ERROR: Cannot skip both --skip-graph and --skip-pg. Nothing would be saved!")
        return
    
    if skip_graph:
        print("Mode: Vector DB only (skipping Neo4j graph)")
    elif args.skip_pg:
        print("Mode: Graph only (skipping PostgreSQL vector DB)")
    
    # Create and run pipeline
    pipeline = DocumentIngestionPipeline(
        config=config,
        documents_folder=args.documents,
        clean_before_ingest=args.clean,
        use_cpg_parser=not args.no_cpg,
        dry_run=args.dry_run
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
            print("  [OK] Hierarchical structure parsing enabled")
            print("  [OK] Table extraction to JSON enabled")
            print("  [OK] Evidence level/Grade metadata extraction")
            print("  [OK] Medical relationship extraction")
            print()
        
        # Print individual results
        for result in results:
            status = "[OK]" if not result.errors else "[ERR]"
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