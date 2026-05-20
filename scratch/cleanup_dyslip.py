"""
Clean up Management of Dyslipidaemia (6th Edition) data from both Neo4j and
PostgreSQL before a clean re-ingestion. Remediates the chunk-UUID orphaning
documented in tasks/Ingestion-Reports/Dyslipidaemia6thEdition_Ingest_Report.md §8.

Step 1: Delete all Dyslipidaemia edges from Neo4j (matched on source_document).
Step 2: Delete Dyslipidaemia chunks + documents from PostgreSQL.
"""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# -- Step 1: Neo4j cleanup ------------------------------------------------
print("=" * 60)
print("STEP 1: Neo4j -- Delete Dyslipidaemia edges")
print("=" * 60)

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
)

with driver.session() as session:
    before = session.run(
        "MATCH ()-[r]->() WHERE r.source_document CONTAINS 'Dyslipidaemia' "
        "RETURN count(r) AS c"
    ).single()['c']
    print(f"  Dyslipidaemia edges found: {before}")

    deleted = session.run(
        "MATCH ()-[r]->() WHERE r.source_document CONTAINS 'Dyslipidaemia' "
        "DELETE r RETURN count(r) AS c"
    ).single()['c']
    print(f"  Deleted {deleted} edges")

    remaining = session.run(
        "MATCH ()-[r]->() WHERE r.source_document CONTAINS 'Dyslipidaemia' "
        "RETURN count(r) AS c"
    ).single()['c']
    print(f"  Remaining Dyslipidaemia edges: {remaining}")
    assert remaining == 0, "Neo4j cleanup failed!"

driver.close()

# -- Step 2: PostgreSQL cleanup -------------------------------------------
print()
print("=" * 60)
print("STEP 2: PostgreSQL -- Delete Dyslipidaemia documents + chunks")
print("=" * 60)

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute("""
    SELECT id::text, title FROM documents
    WHERE source ILIKE '%%Dyslipidaemia%%'
       OR metadata->>'cpg_name' ILIKE '%%Dyslipidaemia%%'
""")
docs = cur.fetchall()
print(f"  Found {len(docs)} Dyslipidaemia documents to delete:")
for d in docs:
    print(f"    {d[0][:12]}... {d[1]}")

doc_ids = [d[0] for d in docs]

if doc_ids:
    cur.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Total chunks to delete: {cur.fetchone()[0]}")

    cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} chunks")

    cur.execute("DELETE FROM documents WHERE id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} documents")

conn.commit()

cur.execute("""
    SELECT COUNT(*) FROM documents
    WHERE source ILIKE '%%Dyslipidaemia%%'
       OR metadata->>'cpg_name' ILIKE '%%Dyslipidaemia%%'
""")
remaining = cur.fetchone()[0]
print(f"  Remaining Dyslipidaemia documents: {remaining}")
assert remaining == 0, "PostgreSQL cleanup failed!"
conn.close()

print()
print("=" * 60)
print("[OK] CLEANUP COMPLETE -- Ready for fresh Dyslipidaemia ingestion")
print("=" * 60)
