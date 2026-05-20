"""
PROPER Dyslipidaemia cleanup (supersedes cleanup_dyslip.py).

Root cause of incomplete first cleanup: it matched edges via
`source_document CONTAINS 'Dyslipidaemia'`, which only caught the British-spelled
Section 7 title. The CPG's other sections use American spelling ('Dyslipidemia')
or generic titles, so their stale edges from the killed partial ingest survived
and now show as orphaned cpg_chunk_id (63/133 distinct IDs, ~47%).

Fix: delete edges by the CPG's ACTUAL section titles. Two titles ('Appendices',
'Section 1: Introduction') collide with other CPGs AND carry zero Dyslipidaemia
edges, so they are excluded for safety.
"""
import psycopg2
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# 13 titles unique to Dyslipidaemia(6th-Edition). 'Appendices' and
# 'Section 1: Introduction' deliberately excluded (collide w/ other CPGs, 0 edges).
SAFE_TITLES = [
    "Section 10: Management Of Dyslipidemia In Specific Conditions",
    "Section 11: Specific Lipid Disorders",
    "Section 12: Management In Special Groups",
    "Section 13: Adherence To Lifestyle Changes And Medications",
    "Section 14: Quality Indicators & Performance Measures",
    "Section 2: Measurement Of Lipids And Apolipoproteins",
    "Section 3: Classification Of Dyslipidemia",
    "Section 4: Dyslipidemia As A CV Risk Factor",
    "Section 5: Global Cardiovascular Risk Assessment",
    "Section 6: Target Lipid Levels",
    "Section 7: Management Of Dyslipidaemia",
    "Section 8: Primary Prevention",
    "Section 9: Secondary Prevention",
]

print("=" * 60)
print("STEP 1: Neo4j -- Delete ALL Dyslipidaemia edges (by section title)")
print("=" * 60)
driver = GraphDatabase.driver(os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD')))
with driver.session() as session:
    before = session.run(
        "MATCH ()-[r]->() WHERE r.source_document IN $t RETURN count(r) AS c",
        t=SAFE_TITLES).single()['c']
    print(f"  Edges matching the 13 unique titles: {before}")
    deleted = session.run(
        "MATCH ()-[r]->() WHERE r.source_document IN $t DELETE r RETURN count(r) AS c",
        t=SAFE_TITLES).single()['c']
    print(f"  Deleted {deleted} edges")
    remaining = session.run(
        "MATCH ()-[r]->() WHERE r.source_document IN $t RETURN count(r) AS c",
        t=SAFE_TITLES).single()['c']
    print(f"  Remaining: {remaining}")
    assert remaining == 0
driver.close()

print("\n" + "=" * 60)
print("STEP 2: PostgreSQL -- Delete Dyslipidaemia documents + chunks (by cpg_name)")
print("=" * 60)
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("SELECT id::text FROM documents WHERE metadata->>'cpg_name' = 'Dyslipidaemia(6th-Edition)'")
doc_ids = [r[0] for r in cur.fetchall()]
print(f"  Documents: {len(doc_ids)}")
if doc_ids:
    cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} chunks")
    cur.execute("DELETE FROM documents WHERE id = ANY(%s::uuid[])", (doc_ids,))
    print(f"  Deleted {cur.rowcount} documents")
conn.commit()
cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'cpg_name' = 'Dyslipidaemia(6th-Edition)'")
assert cur.fetchone()[0] == 0
conn.close()

print("\n" + "=" * 60)
print("[OK] FULL CLEANUP COMPLETE -- ready for clean re-ingest")
print("=" * 60)
