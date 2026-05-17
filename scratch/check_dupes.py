"""Check for duplicate Breast Cancer documents and chunks in PostgreSQL."""
import psycopg2, os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# 1. Check how many document rows exist for Breast Cancer
cur.execute("""
    SELECT id, title, created_at
    FROM documents
    WHERE metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
    ORDER BY title, created_at
""")
rows = cur.fetchall()
print(f"=== Total document rows for Breast Cancer: {len(rows)} ===")
for r in rows:
    print(f"  {r[2]}  {r[0][:12]}...  {r[1]}")

# 2. Check for duplicate titles
cur.execute("""
    SELECT title, COUNT(*) as cnt
    FROM documents
    WHERE metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
    GROUP BY title
    HAVING COUNT(*) > 1
    ORDER BY title
""")
dupes = cur.fetchall()
print(f"\n=== Duplicate titles: {len(dupes)} ===")
for d in dupes:
    print(f"  {d[0]}: {d[1]} copies")

# 3. Total chunks per document
cur.execute("""
    SELECT d.title, d.id, d.created_at, COUNT(c.id) as chunk_count
    FROM documents d
    LEFT JOIN chunks c ON c.document_id = d.id
    WHERE d.metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
    GROUP BY d.title, d.id, d.created_at
    ORDER BY d.title, d.created_at
""")
rows = cur.fetchall()
print(f"\n=== Chunks per document row ===")
for r in rows:
    print(f"  {r[2]}  {r[1][:12]}...  chunks={r[3]}  {r[0]}")

conn.close()
