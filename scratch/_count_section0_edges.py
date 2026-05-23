"""How many CVD-Prevention-Women KG edges reference section-0 chunks?

Schema: edges have BOTH
  - r.cpg_chunk_id   (singular, the primary chunk that produced the edge)
  - r.cpg_chunk_ids  (array, accumulated via MERGE across runs)

The verifier uses the singular field to count "edges sourced from this CPG".
We care about all the ways section-0 references appear so we know the blast
radius of re-ingesting section 0.
"""
import os, sys
from dotenv import load_dotenv
import psycopg2
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# 1. All CVD chunk UUIDs grouped by section
pg = psycopg2.connect(os.environ["DATABASE_URL"])
cur = pg.cursor()
cur.execute("""
    SELECT c.id::text, d.title
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE d.metadata->>'cpg_name' ILIKE '%CVD-Prevention-Women%'
""")
chunk_to_section = {row[0]: row[1] for row in cur.fetchall()}
cvd_chunk_ids = set(chunk_to_section.keys())
section0_ids = {cid for cid, title in chunk_to_section.items() if title.startswith("Section 0")}

print(f"Total CVD chunks in PG: {len(cvd_chunk_ids)}")
print(f"Section-0 chunks in PG: {len(section0_ids)}")

# 2. Pull all CVD-sourced edges from Neo4j
driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
)
with driver.session() as sess:
    res = sess.run("""
        MATCH (a)-[r]->(b)
        WHERE r.cpg_chunk_id IN $ids
        RETURN a.name AS subj, type(r) AS rel, b.name AS obj,
               r.cpg_chunk_id AS primary_id,
               r.cpg_chunk_ids AS array_ids,
               r.evidence AS evidence
    """, ids=list(cvd_chunk_ids))
    edges = [dict(r) for r in res]

print(f"\nTotal CVD edges (matched via r.cpg_chunk_id): {len(edges)}")

# Breakdown by what re-ingesting section 0 would do to each edge
primary_in_s0 = 0     # primary cpg_chunk_id is a section-0 chunk
array_only_s0 = 0     # primary not in s0, but cpg_chunk_ids array contains s0
array_mixed = 0       # array has section-0 AND non-section-0 entries
array_purely_s0 = 0   # cpg_chunk_ids array is entirely section-0
no_s0_touch = 0       # no section-0 reference at all

primary_purely_s0 = []  # primary in s0 AND array (if any) is only s0
primary_s0_array_mixed = []  # primary in s0 but array also has non-s0 refs

for e in edges:
    pid = e["primary_id"]
    arr = e["array_ids"] or []
    s0_in_arr = [c for c in arr if c in section0_ids]
    non_s0_in_arr = [c for c in arr if c not in section0_ids]

    p_is_s0 = pid in section0_ids

    if p_is_s0:
        primary_in_s0 += 1
        if non_s0_in_arr:
            primary_s0_array_mixed.append(e)
        else:
            primary_purely_s0.append(e)
    elif s0_in_arr:
        array_only_s0 += 1
        if non_s0_in_arr:
            array_mixed += 1
        else:
            array_purely_s0 += 1
    else:
        no_s0_touch += 1

print("\n=== Blast radius if we re-ingest section 0 ===")
print(f"Edges where PRIMARY r.cpg_chunk_id is in section 0: {primary_in_s0}")
print(f"  ...of which array also has non-section-0 refs (safe): {len(primary_s0_array_mixed)}")
print(f"  ...of which array is purely section-0 (loses all linkage): {len(primary_purely_s0)}  <-- WORST CASE")
print(f"Edges where primary is non-s0 but ARRAY contains s0 refs: {array_only_s0}")
print(f"Edges with no section-0 reference anywhere: {no_s0_touch}")

print("\n--- Sample of 'primary in s0, array purely s0' edges (worst case) ---")
for e in primary_purely_s0[:15]:
    print(f"  ({e['subj']}) -[{e['rel']}]-> ({e['obj']})")
    print(f"     primary={e['primary_id']}  array={e['array_ids']}")
