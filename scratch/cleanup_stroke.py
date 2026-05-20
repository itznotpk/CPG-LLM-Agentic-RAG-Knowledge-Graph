"""
Remediate Ischaemic-Stroke(3rd Edition) cross-DB corruption (29.5% orphaned
cpg_chunk_id), same failure mode as Dyslipidaemia.

Edge deletion strategy (collision-aware):
  - UNIQUE titles (17): delete all edges by source_document IN titles.
  - SHARED title 'Section 3: Diagnosis And Initial Assessment' (shared with
    Hypertension): delete ONLY edges whose cpg_chunk_id belongs to a Stroke
    Section-3 chunk — captured BEFORE the Postgres delete so the IDs still resolve.
    Hypertension's Section-3 edges are left untouched.
Then delete Stroke chunks+docs by cpg_name and re-ingest.
"""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

CPG = "Ischaemic-Stroke(3rd Edition)"
SHARED_TITLES = ["Section 3: Diagnosis And Initial Assessment"]

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# All section titles for this CPG, and which are unique vs shared
cur.execute("SELECT DISTINCT title FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
my_titles = {r[0] for r in cur.fetchall()}
cur.execute("""
    SELECT title, count(DISTINCT metadata->>'cpg_name') AS n
    FROM documents WHERE title = ANY(%s) GROUP BY title
""", (list(my_titles),))
owners = {r[0]: r[1] for r in cur.fetchall()}
unique_titles = sorted(t for t in my_titles if owners.get(t, 1) == 1)
print(f"{CPG}: {len(my_titles)} sections, {len(unique_titles)} unique, shared handled: {SHARED_TITLES}")

# Stroke chunk IDs under shared sections (capture BEFORE delete)
cur.execute("""
    SELECT c.id::text FROM chunks c JOIN documents d ON c.document_id = d.id
    WHERE d.metadata->>'cpg_name' = %s AND d.title = ANY(%s)
""", (CPG, SHARED_TITLES))
shared_stroke_ids = [r[0] for r in cur.fetchall()]
print(f"Stroke chunks under shared section(s): {len(shared_stroke_ids)}")

print("\n" + "=" * 60)
print("STEP 1: Neo4j edge deletion")
print("=" * 60)
driver = GraphDatabase.driver(os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))
with driver.session() as s:
    d1 = s.run("MATCH ()-[r]->() WHERE r.source_document IN $t DELETE r RETURN count(r) AS c",
               t=unique_titles).single()['c']
    print(f"  Deleted {d1} edges on unique titles")
    d2 = s.run("""MATCH ()-[r]->() WHERE r.source_document IN $t AND r.cpg_chunk_id IN $ids
                  DELETE r RETURN count(r) AS c""",
               t=SHARED_TITLES, ids=shared_stroke_ids).single()['c']
    print(f"  Deleted {d2} Stroke edges on shared title(s) (Hypertension untouched)")

print("\n" + "=" * 60)
print("STEP 2: PostgreSQL — delete chunks + documents by cpg_name")
print("=" * 60)
cur.execute("SELECT id::text FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
doc_ids = [r[0] for r in cur.fetchall()]
print(f"  Documents: {len(doc_ids)}")
if doc_ids:
    cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} chunks")
    cur.execute("DELETE FROM documents WHERE id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} documents")
conn.commit()
cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
assert cur.fetchone()[0] == 0
conn.close()
driver.close()
print("\n[OK] CLEANUP COMPLETE — ready for clean re-ingest")
