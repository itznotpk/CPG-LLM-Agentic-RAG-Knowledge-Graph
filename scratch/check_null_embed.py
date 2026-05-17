# -*- coding: utf-8 -*-
"""Find the specific h2/h3 leaf chunk with null embedding and diagnose why."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import psycopg2
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Find the null-embedding leaf chunks
cur.execute("""
    SELECT c.id, c.chunk_level, c.chunk_index, d.title,
           length(c.content) as content_len,
           left(c.content, 200) as preview,
           c.parent_chunk_id,
           (SELECT COUNT(*) FROM chunks child WHERE child.parent_chunk_id = c.id) as child_count
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
      AND c.chunk_level IN ('h2', 'h3')
      AND c.embedding IS NULL
    ORDER BY d.title, c.chunk_index
""")
rows = cur.fetchall()

print(f"=== Null-embedding leaf chunks: {len(rows)} ===\n")
for r in rows:
    chunk_id, level, idx, title, content_len, preview, parent_id, child_count = r
    print(f"Document: {title}")
    print(f"  Chunk ID:    {chunk_id}")
    print(f"  Level:       {level}")
    print(f"  Index:       {idx}")
    print(f"  Content len: {content_len} chars")
    print(f"  Parent ID:   {parent_id}")
    print(f"  Children:    {child_count}")
    print(f"  Preview:     {preview[:150]}...")
    print()

    # Check if this h2 has h3 children (making it a sub-split parent)
    if child_count > 0:
        print(f"  >>> This IS a sub-split parent with {child_count} children - should be excluded from FAIL")
    else:
        print(f"  >>> This is a TRUE LEAF with no children - embedding should NOT be null")
        # Check if there's something weird about the content
        cur.execute("SELECT content FROM chunks WHERE id = %s", (chunk_id,))
        full_content = cur.fetchone()[0]
        print(f"  >>> Full content length: {len(full_content)} chars")
        print(f"  >>> First 500 chars:")
        print(f"  {full_content[:500]}")
        print(f"  >>> Last 200 chars:")
        print(f"  {full_content[-200:]}")

conn.close()
