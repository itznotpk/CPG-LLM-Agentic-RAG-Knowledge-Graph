"""Check if Neo4j cpg_chunk_id values match current Postgres chunk IDs for Breast Cancer."""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Get current Postgres chunk IDs for Breast Cancer
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("""
    SELECT c.id::text
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
""")
pg_ids = set(r[0] for r in cur.fetchall())
print(f"Postgres chunk IDs for Breast Cancer: {len(pg_ids)}")
conn.close()

# Get Neo4j cpg_chunk_id values
driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)
with driver.session() as session:
    res = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_id IS NOT NULL
        RETURN DISTINCT r.cpg_chunk_id AS cid
    """)
    neo_ids = set(rec['cid'] for rec in res)
    print(f"Unique cpg_chunk_id values in Neo4j: {len(neo_ids)}")

# Cross reference
matched = pg_ids & neo_ids
only_pg = pg_ids - neo_ids
only_neo = neo_ids - pg_ids

print(f"\nMatched (in both): {len(matched)}")
print(f"Only in Postgres (no Neo4j edge): {len(only_pg)}")
print(f"Only in Neo4j (stale, not in Postgres): {len(only_neo)}")

if only_neo:
    print(f"\nSample stale Neo4j cpg_chunk_ids (not in Postgres):")
    for cid in list(only_neo)[:5]:
        print(f"  {cid}")

driver.close()
