"""
Ingest ED Diagnosis Algorithm markdown into database.
This script ADDS chunks to the database - does NOT delete existing data.
"""
import asyncio
import json
import os
from datetime import datetime

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.chunker import MarkdownChunker, ChunkingConfig
from ingestion.embedder import create_embedder
from agent.db_utils import initialize_database, close_database, db_pool

async def ingest_markdown_file(file_path: str):
    """Ingest a single markdown file into the database."""
    
    print("=" * 60)
    print("INGESTING MARKDOWN TO DATABASE")
    print("=" * 60)
    print(f"File: {file_path}")
    print("⚠️  This will ADD to the database, NOT overwrite existing data")
    print("=" * 60)
    
    # Initialize database connection
    print("\n1. Connecting to database...")
    await initialize_database()
    
    try:
        # Read the markdown file
        print("\n2. Reading markdown file...")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title from first H1 header
        title = os.path.basename(file_path).replace('.md', '')
        for line in content.split('\n')[:10]:
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        source = os.path.basename(file_path)
        
        print(f"   Title: {title}")
        print(f"   Source: {source}")
        print(f"   Content length: {len(content)} chars")
        
        # Chunk the document
        print("\n3. Chunking document (splitting by # headers)...")
        chunker = MarkdownChunker(ChunkingConfig(
            chunk_size=3000,  # Larger since we only split on #
            max_chunk_size=5000
        ))
        
        chunks = chunker.chunk_document(content, title, source)
        print(f"   Created {len(chunks)} chunks")
        
        for i, chunk in enumerate(chunks):
            print(f"   - Chunk {i+1}: {chunk.metadata.get('doc_title', 'N/A')[:50]}... ({len(chunk.content)} chars)")
        
        # Generate embeddings
        print("\n4. Generating embeddings...")
        embedder = create_embedder()
        embedded_chunks = await embedder.embed_chunks(chunks)
        print(f"   Generated embeddings for {len(embedded_chunks)} chunks")
        
        # Save to database
        print("\n5. Saving to PostgreSQL (INSERT, no overwrite)...")
        
        metadata = {
            "file_path": file_path,
            "file_size": len(content),
            "ingestion_date": datetime.now().isoformat(),
            "chunk_method": "markdown_header_h1_only"
        }
        
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
                print(f"   Document ID: {document_id}")
                
                # Insert chunks
                for chunk in embedded_chunks:
                    embedding_data = None
                    if hasattr(chunk, 'embedding') and chunk.embedding:
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
                
                print(f"   Inserted {len(embedded_chunks)} chunks")
        
        print("\n" + "=" * 60)
        print("✅ INGESTION COMPLETE")
        print("=" * 60)
        print(f"Document ID: {document_id}")
        print(f"Chunks created: {len(embedded_chunks)}")
        print(f"Existing data: PRESERVED (no overwrite)")
        
    finally:
        await close_database()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    # Default to ED Diagnosis file in markdown folder
    file_path = "markdown/ED Diagnosis And Treatment Algorithm.md"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    asyncio.run(ingest_markdown_file(file_path))
