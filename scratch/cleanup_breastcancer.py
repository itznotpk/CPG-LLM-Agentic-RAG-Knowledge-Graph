"""
Clean up Breast Cancer data from both PostgreSQL and Neo4j before re-ingestion.
Step 1: Delete Breast Cancer chunks + documents from PostgreSQL
Step 2: Delete Neo4j edges with stale cpg_chunk_ids (Breast Cancer only)
"""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# ── Step 1: PostgreSQL cleanup ──────────────────────────────────────────
print("=" * 60)
print("STEP 1: PostgreSQL — Delete Breast Cancer documents + chunks")
print("=" * 60)

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Get document IDs first
cur.execute("""
    SELECT id::text, title FROM documents
    WHERE metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
""")
docs = cur.fetchall()
print(f"  Found {len(docs)} Breast Cancer documents to delete:")
for d in docs:
    print(f"    {d[0][:12]}... {d[1]}")

doc_ids = [d[0] for d in docs]

# Count chunks before delete
cur.execute("""
    SELECT COUNT(*) FROM chunks
    WHERE document_id = ANY(%s::uuid[])
""", (doc_ids,))
chunk_count = cur.fetchone()[0]
print(f"  Total chunks to delete: {chunk_count}")

# Delete chunks first (FK constraint), then documents
cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
chunks_deleted = cur.rowcount
print(f"  Deleted {chunks_deleted} chunks")

cur.execute("DELETE FROM documents WHERE id = ANY(%s::uuid[])", (doc_ids,))
docs_deleted = cur.rowcount
print(f"  Deleted {docs_deleted} documents")

conn.commit()

# Verify nothing remains
cur.execute("""
    SELECT COUNT(*) FROM documents
    WHERE metadata->>'cpg_name' ILIKE '%%Breast-Cancer%%'
""")
remaining = cur.fetchone()[0]
print(f"  Remaining Breast Cancer documents: {remaining}")
assert remaining == 0, "PostgreSQL cleanup failed!"
print("  ✓ PostgreSQL cleanup complete")
conn.close()

# ── Step 2: Neo4j cleanup ───────────────────────────────────────────────
print()
print("=" * 60)
print("STEP 2: Neo4j — Delete stale Breast Cancer edges")
print("=" * 60)

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

# The old Breast Cancer cpg_chunk_ids are the 261 stale UUIDs.
# We know ALL current Postgres chunk IDs, so delete edges whose
# cpg_chunk_id is NOT in the current set (i.e. orphaned edges).
# But we must be careful not to delete edges from OTHER CPGs.

# Approach: Get all CURRENT chunk IDs from Postgres (all CPGs),
# then delete edges whose cpg_chunk_id is NOT in that set.
conn2 = psycopg2.connect(os.getenv('DATABASE_URL'))
cur2 = conn2.cursor()
cur2.execute("SELECT id::text FROM chunks")
all_current_ids = set(r[0] for r in cur2.fetchall())
print(f"  Current Postgres chunk IDs (all CPGs): {len(all_current_ids)}")
conn2.close()

with driver.session() as session:
    # Count edges with stale cpg_chunk_ids
    res = session.run("""
        MATCH ()-[r]->()
        WHERE r.cpg_chunk_id IS NOT NULL
        RETURN r.cpg_chunk_id AS cid
    """)
    stale_ids = []
    valid_ids = []
    for rec in res:
        if rec['cid'] in all_current_ids:
            valid_ids.append(rec['cid'])
        else:
            stale_ids.append(rec['cid'])

    stale_set = set(stale_ids)
    print(f"  Edges with valid cpg_chunk_id: {len(valid_ids)}")
    print(f"  Edges with STALE cpg_chunk_id (to delete): {len(stale_ids)} ({len(stale_set)} unique)")

    if stale_ids:
        # Delete stale edges
        res2 = session.run("""
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $stale_ids
            DELETE r
            RETURN count(r) as deleted
        """, stale_ids=list(stale_set))
        deleted = res2.single()['deleted']
        print(f"  Deleted {deleted} stale edges from Neo4j")

    # Also clean up any orphan nodes (nodes with no remaining edges)
    res3 = session.run("""
        MATCH (n)
        WHERE n.name IS NOT NULL
          AND NOT (n)-[]-()
        RETURN count(n) as orphans
    """)
    orphans = res3.single()['orphans']
    print(f"  Orphan nodes (no edges): {orphans}")

    if orphans > 0:
        session.run("""
            MATCH (n)
            WHERE n.name IS NOT NULL
              AND NOT (n)-[]-()
            DELETE n
        """)
        print(f"  Deleted {orphans} orphan nodes")

    # Final count
    res4 = session.run("MATCH ()-[r]->() RETURN count(r) as total")
    print(f"  Remaining total edges in Neo4j: {res4.single()['total']}")

driver.close()

print()
print("=" * 60)
print("✓ CLEANUP COMPLETE — Ready for fresh Breast Cancer ingestion")
print("=" * 60)
