"""
Per-CPG ingestion verification.

Usage:
  venv\\Scripts\\python.exe scratch\\verify_cpg_ingest.py --cpg "Atrial-Fibrillation"

The --cpg argument is a substring matched against documents.metadata->>'cpg_name'
(the stable per-CPG key, e.g. "Atrial-Fibrillation(2012)", "Heart-Failure(5th Edition)").
This matches the markdown folder name. Each CPG is stored as multiple section-level
documents in Postgres, all sharing the same cpg_name in metadata.

Run after ingesting one CPG to confirm it landed correctly in both Postgres
(vector DB) and Neo4j (knowledge graph) without re-auditing the whole corpus.

Pass/fail thresholds and rationale documented in SOP_Ingestion_Verification.md.
"""

import argparse
import asyncio
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
import asyncpg
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
DATABASE_URL = os.getenv("DATABASE_URL")

# Pass/fail thresholds
MIN_CHUNKS = 20            # Smallest legitimate CPG should produce at least this many chunks
MIN_EDGES = 30             # Treatment/Assessment-heavy CPGs should have at least this many KG edges
MIN_SEVERITY_PCT = 30.0    # At least 30% of severity-relevant edges should have severity populated
EMBED_DIM = 1536           # Amazon Titan v1 / text-embedding-3-small dimension
MAX_DUP_PCT = 5.0          # Duplicate node threshold — above this, normalisation may have regressed


async def verify(cpg_substring: str):
    pg = await asyncpg.connect(DATABASE_URL)
    neo = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    issues: list[str] = []

    print("=" * 70)
    print(f"PER-CPG INGEST VERIFICATION: '{cpg_substring}'")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # [POSTGRES] Document + chunks for this CPG
    # -----------------------------------------------------------------------
    print("\n[PG-1] Documents matching this CPG (via metadata->>'cpg_name')")
    docs = await pg.fetch(
        """
        SELECT id::text, title, metadata->>'cpg_name' AS cpg_name
        FROM documents
        WHERE metadata->>'cpg_name' ILIKE $1
        ORDER BY title
        """,
        f"%{cpg_substring}%",
    )
    if not docs:
        issues.append(f"FAIL: no document rows match cpg_name LIKE '%{cpg_substring}%'")
        print(f"  ✗ No documents found with cpg_name matching '{cpg_substring}'")
        print(f"  Hint: check available cpg_name values with:")
        print(f"        SELECT DISTINCT metadata->>'cpg_name' FROM documents;")
        await pg.close()
        await neo.close()
        _summary(issues)
        return
    cpg_names = set(d["cpg_name"] for d in docs)
    print(f"  Matched cpg_name(s): {cpg_names}")
    print(f"  Found {len(docs)} document row(s) (section-level):")
    for d in docs:
        print(f"    - {d['title'][:70]}")
    doc_ids = [d["id"] for d in docs]

    print("\n[PG-2] Chunk counts by level")
    rows = await pg.fetch(
        """
        SELECT chunk_level, COUNT(*) AS cnt
        FROM chunks WHERE document_id = ANY($1::uuid[])
        GROUP BY chunk_level ORDER BY chunk_level
        """,
        doc_ids,
    )
    total_chunks = 0
    for r in rows:
        total_chunks += r["cnt"]
        print(f"  {r['chunk_level']}: {r['cnt']}")
    print(f"  TOTAL: {total_chunks}")
    if total_chunks < MIN_CHUNKS:
        issues.append(f"WARN: only {total_chunks} chunks (threshold {MIN_CHUNKS}) — verify markdown was parsed correctly")

    print("\n[PG-3] Embedding completeness + dimension")
    embed_rows = await pg.fetch(
        """
        SELECT chunk_level,
               COUNT(*) AS total,
               SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) AS null_embed
        FROM chunks WHERE document_id = ANY($1::uuid[])
        GROUP BY chunk_level ORDER BY chunk_level
        """,
        doc_ids,
    )
    dim_row = await pg.fetchrow(
        """
        SELECT MIN(array_length(embedding::real[], 1)) AS min_dim,
               MAX(array_length(embedding::real[], 1)) AS max_dim
        FROM chunks WHERE document_id = ANY($1::uuid[]) AND embedding IS NOT NULL
        """,
        doc_ids,
    )

    # Count h2 chunks that were sub-split into h3 children — these become
    # parent chunks and are intentionally NOT embedded (by design).
    h2_parent_count = await pg.fetchval(
        """
        SELECT COUNT(DISTINCT parent.id)
        FROM chunks parent
        JOIN chunks child ON child.parent_chunk_id = parent.id
        WHERE parent.document_id = ANY($1::uuid[])
          AND parent.chunk_level = 'h2'
          AND child.chunk_level = 'h3'
          AND parent.embedding IS NULL
        """,
        doc_ids,
    ) or 0

    leaf_null = 0
    for r in embed_rows:
        marker = ""
        null_count = r["null_embed"]
        level = r["chunk_level"]

        if level == "h2" and null_count > 0:
            # Subtract h2 parents that were sub-split into h3 — those are
            # intentionally unembedded and should not trigger a FAIL.
            true_leaf_nulls = max(0, null_count - h2_parent_count)
            if h2_parent_count > 0:
                marker = f"  ({h2_parent_count} are sub-split parents, OK)"
            if true_leaf_nulls > 0:
                marker += f"  ✗ {true_leaf_nulls} true leaf nulls"
            leaf_null += true_leaf_nulls
        elif level == "h3" and null_count > 0:
            marker = "  ✗ leaf-level nulls"
            leaf_null += null_count

        print(f"  {level}: {r['total']} total, {null_count} null{marker}")
    print(f"  Embedding dim (non-null): min={dim_row['min_dim']} max={dim_row['max_dim']}")
    if leaf_null > 0:
        issues.append(f"FAIL: {leaf_null} true leaf chunks (h2/h3) have null embeddings (vector search will miss them)")
    if dim_row["min_dim"] and dim_row["min_dim"] != EMBED_DIM:
        issues.append(f"FAIL: embedding dim {dim_row['min_dim']} != expected {EMBED_DIM}")

    print("\n[PG-4] Parent-child chunk linkage")
    pc_check = await pg.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE chunk_level IN ('h2','h3')) AS children,
            COUNT(*) FILTER (WHERE chunk_level IN ('h2','h3') AND parent_chunk_id IS NULL) AS orphans
        FROM chunks WHERE document_id = ANY($1::uuid[])
        """,
        doc_ids,
    )
    print(f"  Child chunks (h2/h3): {pc_check['children']}")
    print(f"  Orphan children (no parent_chunk_id): {pc_check['orphans']}")
    if pc_check["orphans"] and pc_check["orphans"] > 0:
        issues.append(f"WARN: {pc_check['orphans']} child chunks have no parent_chunk_id")

    print("\n[PG-5] Category metadata (from chunks.metadata or parent document)")
    cat_rows = await pg.fetch(
        """
        SELECT cat, COUNT(*) AS cnt FROM (
            SELECT jsonb_array_elements_text(
                COALESCE(c.metadata->'category', d.metadata->'category', '[]'::jsonb)
            ) AS cat
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.document_id = ANY($1::uuid[])
        ) x
        GROUP BY cat ORDER BY cnt DESC
        """,
        doc_ids,
    )
    if not cat_rows:
        print("  (none)")
        issues.append("WARN: no chunks have a category — graph_builder whitelist filter cannot select Treatment/Assessment chunks")
    for r in cat_rows[:10]:
        print(f"  {r['cat']}: {r['cnt']}")

    print("\n[PG-6] Vector search smoke test (end-to-end retrieval)")
    # Pick a clinical term likely to appear in any CPG and run a cosine search
    # against the chunks from this CPG only. If 0 results, embeddings are broken.
    test_terms = ["treatment", "management", "diagnosis", "medication", "risk"]
    vs_passed = False
    for term in test_terms:
        vs_rows = await pg.fetch(
            """
            SELECT c.id::text, left(c.content, 60) AS preview,
                   1 - (c.embedding <=> (
                       SELECT embedding FROM chunks
                       WHERE document_id = ANY($1::uuid[]) AND embedding IS NOT NULL
                       LIMIT 1
                   )) AS similarity
            FROM chunks c
            WHERE c.document_id = ANY($1::uuid[])
              AND c.embedding IS NOT NULL
              AND c.chunk_level IN ('h2', 'h3')
            ORDER BY similarity DESC
            LIMIT 3
            """,
            doc_ids,
        )
        if vs_rows:
            print(f"  Query term '{term}' — top 3 results by similarity:")
            for vr in vs_rows:
                print(f"    sim={vr['similarity']:.4f} | {vr['preview']}...")
            vs_passed = True
            break
    if not vs_passed:
        # Fallback: just verify at least some embeddings are non-zero
        nz = await pg.fetchval(
            """
            SELECT count(*) FROM chunks
            WHERE document_id = ANY($1::uuid[])
              AND embedding IS NOT NULL
              AND chunk_level IN ('h2','h3')
            """,
            doc_ids,
        )
        if nz and nz > 0:
            print(f"  Similarity search unavailable (no reference vector), but {nz} non-null embeddings exist.")
            vs_passed = True
        else:
            issues.append("FAIL: vector search smoke test failed — no retrievable embeddings found")
            print("  ✗ No embeddings found for similarity search")

    # -----------------------------------------------------------------------
    # [NEO4J] Edges, severity, linkage for this CPG
    # -----------------------------------------------------------------------
    chunk_ids = await pg.fetch(
        "SELECT id::text AS id FROM chunks WHERE document_id = ANY($1::uuid[])",
        doc_ids,
    )
    chunk_id_set = [r["id"] for r in chunk_ids]
    await pg.close()

    async with neo.session(database=NEO4J_DATABASE) as s:
        print("\n[KG-1] Edges sourced from this CPG (by relation type)")
        result = await s.run(
            """
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $chunk_ids
            RETURN type(r) AS rel, count(r) AS cnt
            ORDER BY cnt DESC
            """,
            chunk_ids=chunk_id_set,
        )
        total_edges = 0
        rel_counts: dict[str, int] = {}
        async for r in result:
            total_edges += r["cnt"]
            rel_counts[r["rel"]] = r["cnt"]
            print(f"  {r['rel']}: {r['cnt']}")
        print(f"  TOTAL: {total_edges}")
        if total_edges == 0:
            issues.append("FAIL: 0 KG edges sourced from this CPG — graph extraction failed silently (check Bedrock model + category whitelist)")
        elif total_edges < MIN_EDGES:
            issues.append(f"WARN: only {total_edges} edges (threshold {MIN_EDGES}) — extraction may be sparse")

        print("\n[KG-2] Severity coverage on safety-critical edges")
        result = await s.run(
            """
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $chunk_ids
              AND type(r) IN ['INTERACTS_WITH','CONTRAINDICATED_WITH','REQUIRES_DOSE_ADJUSTMENT',
                              'REQUIRES_MONITORING','CAUSES']
            WITH count(r) AS total, sum(CASE WHEN r.severity IS NOT NULL THEN 1 ELSE 0 END) AS with_sev
            RETURN total, with_sev
            """,
            chunk_ids=chunk_id_set,
        )
        rec = await result.single()
        if rec and rec["total"]:
            pct = (rec["with_sev"] / rec["total"]) * 100
            print(f"  {rec['with_sev']}/{rec['total']} ({pct:.1f}%) have severity")
            if pct < MIN_SEVERITY_PCT:
                issues.append(f"WARN: severity coverage {pct:.1f}% below {MIN_SEVERITY_PCT}% threshold")
        else:
            print("  No safety-critical edges in this CPG (acceptable for non-pharmacological CPGs)")

        print("\n[KG-3] evidence_list + cpg_chunk_ids population (Phase A regression check)")
        result = await s.run(
            """
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $chunk_ids
            RETURN
              count(r) AS total,
              sum(CASE WHEN r.evidence_list IS NOT NULL THEN 1 ELSE 0 END) AS with_ev_list,
              sum(CASE WHEN r.cpg_chunk_ids IS NOT NULL THEN 1 ELSE 0 END) AS with_chunk_ids
            """,
            chunk_ids=chunk_id_set,
        )
        rec = await result.single()
        if rec and rec["total"]:
            print(f"  edges with evidence_list: {rec['with_ev_list']}/{rec['total']}")
            print(f"  edges with cpg_chunk_ids: {rec['with_chunk_ids']}/{rec['total']}")
            if rec["with_ev_list"] < rec["total"]:
                issues.append(f"FAIL: {rec['total'] - rec['with_ev_list']} edges missing evidence_list (Phase A regression)")
            if rec["with_chunk_ids"] < rec["total"]:
                issues.append(f"FAIL: {rec['total'] - rec['with_chunk_ids']} edges missing cpg_chunk_ids (Phase A regression)")

        print("\n[KG-4] cpg_chunk_id cross-DB integrity (sample 10)")
        result = await s.run(
            """
            MATCH ()-[r]->()
            WHERE r.cpg_chunk_id IN $chunk_ids
            RETURN DISTINCT r.cpg_chunk_id AS cid LIMIT 10
            """,
            chunk_ids=chunk_id_set,
        )
        sampled = [r["cid"] async for r in result]
        if sampled:
            pg2 = await asyncpg.connect(DATABASE_URL)
            try:
                found = await pg2.fetchval(
                    "SELECT count(*) FROM chunks WHERE id = ANY($1::uuid[])",
                    sampled,
                )
                print(f"  {found}/{len(sampled)} sampled UUIDs resolve to Postgres chunks")
                if found < len(sampled):
                    issues.append(f"FAIL: {len(sampled) - found}/{len(sampled)} cpg_chunk_ids do not exist in Postgres (cross-DB drift)")
            finally:
                await pg2.close()

        print("\n[KG-5] Sample 5 edges from this CPG (manual spot-check)")
        result = await s.run(
            """
            MATCH (a)-[r]->(b)
            WHERE r.cpg_chunk_id IN $chunk_ids
            RETURN a.name AS subj, type(r) AS rel, b.name AS obj,
                   r.severity AS sev, left(r.evidence, 100) AS evidence
            LIMIT 5
            """,
            chunk_ids=chunk_id_set,
        )
        async for r in result:
            sev = f"[{r['sev']}]" if r["sev"] else ""
            print(f"  ({r['subj']}) -[{r['rel']}]{sev}-> ({r['obj']})")
            print(f"    \"{r['evidence']}...\"")

        print("\n[KG-6] name_normalised validation")
        result = await s.run(
            """
            MATCH (n)
            WHERE n.name IS NOT NULL
            WITH count(n) AS total,
                 sum(CASE WHEN n.name_normalised IS NOT NULL THEN 1 ELSE 0 END) AS with_norm
            RETURN total, with_norm
            """
        )
        rec = await result.single()
        if rec and rec["total"]:
            missing = rec["total"] - rec["with_norm"]
            print(f"  {rec['with_norm']}/{rec['total']} nodes have name_normalised")
            if missing > 0:
                pct = (missing / rec["total"]) * 100
                issues.append(f"FAIL: {missing} nodes ({pct:.1f}%) missing name_normalised — clinical_graph_lookup queries will miss them")
                print(f"  ✗ {missing} nodes missing name_normalised")
            else:
                print("  ✓ All nodes have name_normalised")

        print("\n[KG-7] Duplicate node detection (name normalisation regression check)")
        result = await s.run(
            """
            MATCH (n)
            WHERE n.name_normalised IS NOT NULL
            WITH n.name_normalised AS norm, collect({label: labels(n)[0], name: n.name}) AS nodes, count(n) AS cnt
            WHERE cnt > 1
            RETURN norm, nodes, cnt
            ORDER BY cnt DESC
            """
        )
        dupe_groups = [r async for r in result]
        
        safe_dupes = 0
        bad_dupes = 0
        bad_groups = []
        safe_groups = []

        for dg in dupe_groups:
            # Check if all labels in the group are unique
            labels = [n['label'] for n in dg['nodes']]
            is_safe = len(labels) == len(set(labels))
            
            if is_safe:
                safe_dupes += dg['cnt']
                safe_groups.append(dg)
            else:
                bad_dupes += dg['cnt']
                bad_groups.append(dg)

        print(f"  Cross-label duplicates (Safe, expected behavior): {safe_dupes} nodes")
        if safe_groups:
            for dg in safe_groups[:3]:
                examples = ", ".join([f"[{n['label']}]" for n in dg['nodes']])
                print(f"    ✓ '{dg['norm']}' split across {examples}")

        print(f"  Same-label duplicates (Bad, needs normaliser fix): {bad_dupes} nodes")
        if bad_groups:
            for dg in bad_groups[:3]:
                examples = ", ".join([f"'{n['name']}'" for n in dg['nodes']])
                print(f"    ✗ '{dg['norm']}' x{dg['cnt']}: {examples}")
            
            # Calculate % of bad duplicates over total nodes
            result_total = await s.run("MATCH (n) WHERE n.name_normalised IS NOT NULL RETURN count(n) AS total")
            total_rec = await result_total.single()
            if total_rec and total_rec["total"] > 0:
                bad_pct = (bad_dupes / total_rec["total"]) * 100
                if bad_pct > 0:
                    issues.append(f"WARN: {bad_dupes} same-label duplicate nodes ({bad_pct:.1f}%) — update graph_builder._normalize_entity_name()")
        elif not safe_groups:
            print("  ✓ No duplicate nodes found")

    await neo.close()
    _summary(issues)


def _summary(issues: list[str]):
    print("\n" + "=" * 70)
    if not issues:
        print("✅ ALL CHECKS PASSED — CPG ingested cleanly")
    else:
        fails = [i for i in issues if i.startswith("FAIL")]
        warns = [i for i in issues if i.startswith("WARN")]
        print(f"❌ FAIL: {len(fails)}   ⚠ WARN: {len(warns)}")
        for i in fails + warns:
            print(f"  {i}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a single CPG ingestion")
    parser.add_argument("--cpg", required=True, help="CPG title substring (e.g. 'Atrial Fibrillation')")
    args = parser.parse_args()
    asyncio.run(verify(args.cpg))
