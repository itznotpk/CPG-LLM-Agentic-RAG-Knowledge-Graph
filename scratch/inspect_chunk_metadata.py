import asyncio
import asyncpg
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def main():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Query 5 chunks with hierarchies or section numbers
    rows = await conn.fetch("""
        SELECT c.id::text, c.chunk_level, c.metadata, d.title 
        FROM chunks c 
        JOIN documents d ON c.document_id = d.id 
        WHERE c.metadata IS NOT NULL 
        LIMIT 10
    """)
    
    print("=== CHUNK METADATA SAMPLE ===")
    for row in rows:
        meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else (row['metadata'] or {})
        print(f"\nDoc: {row['title']}")
        print(f"Level: {row['chunk_level']}")
        print(f"Metadata keys: {list(meta.keys())}")
        if 'section_hierarchy' in meta:
            print(f"  section_hierarchy: {meta['section_hierarchy']}")
        if 'section_number' in meta:
            print(f"  section_number: {meta['section_number']}")
        if 'section_title' in meta:
            print(f"  section_title: {meta['section_title']}")
        if 'h2_title' in meta:
            print(f"  h2_title: {meta['h2_title']}")
        if 'h3_title' in meta:
            print(f"  h3_title: {meta['h3_title']}")
            
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
