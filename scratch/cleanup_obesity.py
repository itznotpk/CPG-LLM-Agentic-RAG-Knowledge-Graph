"""
Remove all Obesity-Management(2023) data from Neo4j and Postgres.
Collision-aware: checks which section titles are shared with other CPGs
before deleting edges, to avoid touching other CPGs' data.
"""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

CPG = "Obesity-Management(2023)"

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Step 0: get all section titles for this CPG and identify unique vs shared
cur.execute("SELECT DISTINCT title FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
my_titles = {r[0] for r in cur.fetchall()}
print(f"Sections found in Postgres: {len(my_titles)}")
for t in sorted(my_titles):
    print(f"  - {t}")

if not my_titles:
    print("\n[INFO] No documents found for this CPG — already clean.")
    conn.close()
    exit()

cur.execute("""
    SELECT title, count(DISTINCT metadata->>'cpg_name') AS n
    FROM documents WHERE title = ANY(%s) GROUP BY title
""", (list(my_titles),))
owners = {r[0]: r[1] for r in cur.fetchall()}
unique_titles = sorted(t for t in my_titles if owners.get(t, 1) == 1)
shared_titles = sorted(t for t in my_titles if owners.get(t, 1) > 1)
print(f"\nUnique titles ({len(unique_titles)}): {unique_titles}")
print(f"Shared titles ({len(shared_titles)}): {shared_titles}")

# For shared titles, capture Obesity chunk IDs before deleting
shared_obesity_ids = []
if shared_titles:
    cur.execute("""
        SELECT c.id::text FROM chunks c JOIN documents d ON c.document_id = d.id
        WHERE d.metadata->>'cpg_name' = %s AND d.title = ANY(%s)
    """, (CPG, shared_titles))
    shared_obesity_ids = [r[0] for r in cur.fetchall()]
    print(f"Obesity chunks under shared section(s): {len(shared_obesity_ids)}")

print("\n" + "=" * 60)
print("STEP 1: Neo4j edge deletion")
print("=" * 60)
driver = GraphDatabase.driver(os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))

with driver.session() as s:
    d1 = 0
    if unique_titles:
        d1 = s.run("MATCH ()-[r]->() WHERE r.source_document IN $t DELETE r RETURN count(r) AS c",
                   t=unique_titles).single()['c']
        print(f"  Deleted {d1} edges on unique titles")
    else:
        print("  No unique titles — skipping unique-title delete")

    d2 = 0
    if shared_obesity_ids:
        d2 = s.run("""MATCH ()-[r]->() WHERE r.source_document IN $t AND r.cpg_chunk_id IN $ids
                      DELETE r RETURN count(r) AS c""",
                   t=shared_titles, ids=shared_obesity_ids).single()['c']
        print(f"  Deleted {d2} Obesity edges on shared title(s)")

    # Prune orphan nodes
    orphans = s.run("MATCH (n) WHERE NOT (n)--() DELETE n RETURN count(n) AS c").single()['c']
    print(f"  Pruned {orphans} orphan nodes")

print("\n" + "=" * 60)
print("STEP 2: Postgres — delete chunks + documents by cpg_name")
print("=" * 60)
cur.execute("SELECT id::text FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
doc_ids = [r[0] for r in cur.fetchall()]
print(f"  Documents to delete: {len(doc_ids)}")
if doc_ids:
    cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} chunks")
    cur.execute("DELETE FROM documents WHERE id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} documents")
conn.commit()

# Verify clean
cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'cpg_name' = %s", (CPG,))
remaining = cur.fetchone()[0]
assert remaining == 0, f"Expected 0 documents, found {remaining}"
conn.close()
driver.close()

print(f"\n[OK] CLEANUP COMPLETE — {CPG} fully removed. Ready for re-ingest.")
