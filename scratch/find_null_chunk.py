import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def main():
    pg = await asyncpg.connect(DATABASE_URL)
    cpg_substring = "Cancer-Pain"
    query = """
        SELECT c.id, c.chunk_level, c.content, d.title
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE d.metadata->>'cpg_name' ILIKE $1
          AND c.embedding IS NULL
          AND c.chunk_level IN ('h2', 'h3')
    """
    rows = await pg.fetch(query, f"%{cpg_substring}%")
    
    # We need to filter out the h2 chunks that have h3 children, as verify_cpg_ingest does.
    h2_parent_ids = await pg.fetch(
        """
        SELECT DISTINCT parent.id
        FROM chunks parent
        JOIN chunks child ON child.parent_chunk_id = parent.id
        JOIN documents d ON parent.document_id = d.id
        WHERE d.metadata->>'cpg_name' ILIKE $1
          AND parent.chunk_level = 'h2'
          AND child.chunk_level = 'h3'
          AND parent.embedding IS NULL
        """, f"%{cpg_substring}%"
    )
    h2_parent_ids_set = {r["id"] for r in h2_parent_ids}
    
    for r in rows:
        if r["id"] not in h2_parent_ids_set:
            print(f"FOUND TRUE LEAF NULL CHUNK!")
            print(f"Chunk ID: {r['id']}")
            print(f"Document: {r['title']}")
            print(f"Level: {r['chunk_level']}")
            print(f"Content:\n{repr(r['content'][:200])}")
            print("---")
            
    await pg.close()

if __name__ == "__main__":
    asyncio.run(main())
