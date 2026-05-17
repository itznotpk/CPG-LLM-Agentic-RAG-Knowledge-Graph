"""Check if the cpg_chunk_ids in Neo4j still resolve to PostgreSQL chunks."""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Get sample cpg_chunk_ids from Neo4j
URI = os.getenv('NEO4J_URI')
USER = os.getenv('NEO4J_USER')
PASSWORD = os.getenv('NEO4J_PASSWORD')

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
sample_ids = []
with driver.session() as session:
    res = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_ids IS NOT NULL
        UNWIND r.cpg_chunk_ids AS cid
        RETURN DISTINCT cid
        LIMIT 20
    """)
    for rec in res:
        sample_ids.append(rec['cid'])
driver.close()

print(f"Sampled {len(sample_ids)} unique cpg_chunk_ids from Neo4j")

# Check how many resolve in PostgreSQL
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
found = 0
missing = 0
for cid in sample_ids:
    cur.execute("SELECT id FROM chunks WHERE id = %s", (cid,))
    if cur.fetchone():
        found += 1
    else:
        missing += 1
        print(f"  MISSING in Postgres: {cid}")

print(f"\nResolved: {found}/{len(sample_ids)}")
print(f"Missing:  {missing}/{len(sample_ids)}")

# Also check: how does verify_cpg_ingest find edges for a CPG?
# It likely looks for cpg_chunk_ids that match chunks belonging to the CPG
cur.execute("""
    SELECT c.id
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
    LIMIT 5
""")
pg_chunk_ids = [r[0] for r in cur.fetchall()]
print(f"\nSample Postgres chunk IDs for Breast Cancer:")
for cid in pg_chunk_ids:
    print(f"  {cid}")

conn.close()
