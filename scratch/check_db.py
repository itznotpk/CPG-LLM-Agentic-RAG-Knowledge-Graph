"""Check what's in the database and embedding dimensions."""
import asyncio
import asyncpg
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # 1. How many documents?
    docs = await conn.fetch("SELECT id, title, source FROM documents ORDER BY title")
    print(f"\n=== DOCUMENTS ({len(docs)}) ===")
    for d in docs:
        title = d['title'][:60].encode('ascii', 'replace').decode()
        source = d['source'][:40]
        print(f"  {title} | {source}")
    
    # 2. How many chunks?
    chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
    print(f"\n=== TOTAL CHUNKS: {chunk_count} ===")
    
    # 3. Check embedding dimensions
    dim_check = await conn.fetch("""
        SELECT 
            array_length(c.embedding::real[], 1) as embed_dim,
            COUNT(*) as cnt
        FROM chunks c
        WHERE c.embedding IS NOT NULL
        GROUP BY array_length(c.embedding::real[], 1)
    """)
    print(f"\n=== EMBEDDING DIMENSIONS ===")
    for row in dim_check:
        print(f"  Dimension {row['embed_dim']}: {row['cnt']} chunks")
    
    # 4. Heart Failure chunks
    hf_count = await conn.fetchval("""
        SELECT COUNT(*) FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE LOWER(d.title) LIKE '%heart%' OR LOWER(d.source) LIKE '%heart%'
    """)
    print(f"\n=== HEART FAILURE CHUNKS: {hf_count} ===")
    
    # 5. Column type
    col_info = await conn.fetchrow("""
        SELECT pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        WHERE c.relname = 'chunks' AND a.attname = 'embedding'
    """)
    if col_info:
        print(f"\n=== COLUMN TYPE: {col_info['data_type']} ===")
    
    # 6. What is VECTOR_DIMENSION env?
    print(f"\n=== ENV CONFIG ===")
    print(f"  VECTOR_DIMENSION={os.getenv('VECTOR_DIMENSION')}")
    print(f"  EMBEDDING_MODEL={os.getenv('EMBEDDING_MODEL')}")
    print(f"  EMBEDDING_PROVIDER={os.getenv('EMBEDDING_PROVIDER')}")
    
    await conn.close()

asyncio.run(main())
