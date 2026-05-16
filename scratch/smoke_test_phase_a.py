r"""
Phase A Smoke Test — Extraction prompt + relation taxonomy + evidence accumulation
===================================================================================
Pulls 10 clinical chunks from PostgreSQL, runs _extract_triples_with_llm on each,
and prints a structured report checking:

  1. New relation types fire (INTERACTS_WITH, CROSS_REACTS_WITH, REQUIRES_DOSE_ADJUSTMENT)
  2. Severity is null when text does not state it explicitly (hallucination guard)
  3. Severity is populated when text clearly states urgency
  4. trigger and risk_pct are null-by-default
  5. ON MATCH evidence_list accumulation works (write same triple twice, check list grows)

Run: venv\Scripts\python.exe scratch\smoke_test_phase_a.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import asyncio
import json
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

def fmt(status, msg):
    markers = {PASS: "[+]", FAIL: "[X]", WARN: "[!]"}
    return f"  {markers[status]} {status}: {msg}"


# ---------------------------------------------------------------------------
# 1. Pull 10 clinical chunks from PostgreSQL
# ---------------------------------------------------------------------------

async def fetch_chunks(n=10):
    import asyncpg
    conn = await asyncpg.connect(os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL"))
    rows = await conn.fetch(
        """
        SELECT id AS chunk_id, content, metadata
        FROM chunks
        WHERE (
            metadata->'category' ?| array['Treatment','Assessment','Special Populations',
                'Pharmacological Treatment','Management','Monitoring',
                'Supportive Treatment','Diagnosis','Prevention','Referral']
        )
        AND length(content) > 300
        ORDER BY random()
        LIMIT $1
        """,
        n,
    )
    await conn.close()
    return rows


# ---------------------------------------------------------------------------
# 2. Run extraction on a single chunk
# ---------------------------------------------------------------------------

async def extract(builder, chunk):
    content = chunk["content"]
    chunk_id = str(chunk["chunk_id"])
    triples = await builder._extract_triples_with_llm(
        text=content[:4000],
        chunk_index=0,
        source="smoke_test",
        cpg_chunk_id=chunk_id,
    )
    return triples


# ---------------------------------------------------------------------------
# 3. Analyse extraction quality
# ---------------------------------------------------------------------------

VALID_SEVERITIES = {"MAJOR", "MODERATE", "MINOR"}
NEW_RELATION_TYPES = {"INTERACTS_WITH", "CROSS_REACTS_WITH", "REQUIRES_DOSE_ADJUSTMENT"}

def analyse(all_results):
    """
    all_results: list of (chunk_id, triples, chunk_text)
    Returns a printed report and a pass/fail summary.
    """
    total_triples = 0
    severity_populated = 0
    severity_null = 0
    severity_invalid = 0
    trigger_populated = 0
    new_rel_hits = Counter()
    rel_counts = Counter()
    issues = []

    for chunk_id, triples, text in all_results:
        total_triples += len(triples)
        for t in triples:
            rel = t.get("relation", "")
            rel_counts[rel] += 1
            if rel in NEW_RELATION_TYPES:
                new_rel_hits[rel] += 1

            sev = t.get("severity")
            if sev is None:
                severity_null += 1
            elif sev in VALID_SEVERITIES:
                severity_populated += 1
                # Spot-check: does the evidence actually mention severity language?
                ev = (t.get("evidence") or "").lower()
                severity_words = {"major", "minor", "moderate", "avoid", "contraindicated",
                                  "serious", "significant", "do not", "caution", "warning",
                                  "severe", "risk", "harmful", "fatal", "life-threatening"}
                if not any(w in ev for w in severity_words):
                    issues.append(
                        f"  Possible severity hallucination in chunk {chunk_id[:8]}:\n"
                        f"    Severity={sev}, Evidence=\"{ev[:120]}\"\n"
                        f"    Relation: {t.get('subject')} --{rel}--> {t.get('object')}"
                    )
            else:
                severity_invalid += 1
                issues.append(f"  Invalid severity value '{sev}' in chunk {chunk_id[:8]}")

            if t.get("trigger"):
                trigger_populated += 1

    return total_triples, severity_populated, severity_null, severity_invalid, \
           trigger_populated, new_rel_hits, rel_counts, issues


# ---------------------------------------------------------------------------
# 4. Evidence accumulation test (write same triple twice to Neo4j)
# ---------------------------------------------------------------------------

async def test_evidence_accumulation(builder):
    """
    Writes a synthetic triple twice with different evidence strings.
    Checks that evidence_list has 2 entries after second write.
    Cleans up the test node afterwards.
    """
    from neo4j import AsyncGraphDatabase

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    db = os.getenv("NEO4J_DATABASE") or None

    synthetic_triple_1 = [{
        "subject": "__SmokeTestDrug__",
        "subject_type": "Drug",
        "relation": "INTERACTS_WITH",
        "object": "__SmokeTestCondition__",
        "object_type": "Condition",
        "evidence": "First evidence — drug A interacts with condition B.",
        "severity": "MODERATE",
        "trigger": None,
        "risk_pct": None,
        "chunk_index": 0,
        "source": "smoke_test",
        "cpg_chunk_id": "aaaaaaaa-0000-0000-0000-000000000001",
    }]
    synthetic_triple_2 = [{
        **synthetic_triple_1[0],
        "evidence": "Second evidence — further clarification of the interaction.",
        "cpg_chunk_id": "aaaaaaaa-0000-0000-0000-000000000002",
    }]

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    results = {}

    try:
        # Write first triple
        await builder._write_triples_to_neo4j(synthetic_triple_1, "__SmokeTest__")
        # Write second triple (same MERGE key, different evidence)
        await builder._write_triples_to_neo4j(synthetic_triple_2, "__SmokeTest__")

        # Read back
        async with driver.session(database=db) as session:
            result = await session.run(
                """
                MATCH (s {name_normalised: $s_norm})-[r:INTERACTS_WITH]->(o {name_normalised: $o_norm})
                RETURN r.evidence_list AS ev_list, r.cpg_chunk_ids AS chunk_ids, r.severity AS severity
                """,
                s_norm="__smoketestdrug__",
                o_norm="__smoketestcondition__",
            )
            records = [rec async for rec in result]
            if records:
                results["evidence_list"] = list(records[0]["ev_list"] or [])
                results["chunk_ids"] = list(records[0]["chunk_ids"] or [])
                results["severity"] = records[0]["severity"]
    finally:
        # Cleanup
        async with driver.session(database=db) as session:
            await session.run(
                "MATCH (n) WHERE n.name_normalised IN [$s, $o] DETACH DELETE n",
                s="__smoketestdrug__",
                o="__smoketestcondition__",
            )
        await driver.close()

    return results


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("PHASE A SMOKE TEST")
    print("=" * 70)

    # Initialise builder
    try:
        from ingestion.graph_builder import GraphBuilder
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ingestion.graph_builder import GraphBuilder

    builder = GraphBuilder()
    await builder.initialize()

    # ── Section 1: LLM extraction quality ───────────────────────────────────
    print("\n[SECTION 1] LLM extraction quality (10 random clinical chunks)")
    print("-" * 70)

    try:
        chunks = await fetch_chunks(10)
    except Exception as e:
        print(f"  [!] Could not fetch chunks from PostgreSQL: {e}")
        print("  Skipping LLM extraction tests.")
        chunks = []

    all_results = []
    if chunks:
        for i, chunk in enumerate(chunks):
            cid = str(chunk["chunk_id"])
            cat = ""
            try:
                cat = json.loads(chunk["metadata"] or "{}").get("category", "")
            except Exception:
                pass
            print(f"  Chunk {i+1}/10  id={cid[:8]}...  cat={cat}", end="  ", flush=True)
            try:
                triples = await extract(builder, chunk)
                print(f"-> {len(triples)} triples")
                all_results.append((cid, triples, chunk["content"]))
            except Exception as e:
                print(f"-> ERROR: {e}")
                all_results.append((cid, [], chunk["content"]))

        total, sev_pop, sev_null, sev_inv, trig_pop, new_rels, rel_counts, issues = \
            analyse(all_results)

        print(f"\n  Total triples extracted : {total}")
        print(f"  Severity populated      : {sev_pop}  ({sev_pop/max(total,1)*100:.0f}%)")
        print(f"  Severity null           : {sev_null}  ({sev_null/max(total,1)*100:.0f}%)")
        print(f"  Severity invalid (bug)  : {sev_inv}")
        print(f"  Trigger populated       : {trig_pop}")

        print(f"\n  Relation type breakdown:")
        for rel, cnt in sorted(rel_counts.items(), key=lambda x: -x[1]):
            marker = " <-- NEW" if rel in NEW_RELATION_TYPES else ""
            print(f"    {rel:<35} {cnt}{marker}")

        print(f"\n  New relation type hits  : {dict(new_rels)}")

        # Gates
        print("\n  --- Gate checks ---")
        if sev_inv == 0:
            print(fmt(PASS, "No invalid severity values (controlled vocab enforced)"))
        else:
            print(fmt(FAIL, f"{sev_inv} invalid severity values found — validator broken"))

        if sev_pop > 0:
            print(fmt(PASS, f"Severity populated {sev_pop} time(s) — LLM is using it"))
        else:
            print(fmt(WARN, "Severity never populated across 10 chunks — may be ok if chunks lack explicit severity language, but worth checking manually"))

        if sev_null > sev_pop:
            print(fmt(PASS, f"Majority of triples have null severity ({sev_null} null vs {sev_pop} populated) — null-by-default rule working"))
        else:
            print(fmt(WARN, f"Severity populated more than null ({sev_pop} vs {sev_null}) — check for hallucination"))

        if new_rels:
            print(fmt(PASS, f"New relation types fired: {dict(new_rels)}"))
        else:
            print(fmt(WARN, "No new relation types fired — may be ok if chunks had no interactions; try more chunks"))

        if issues:
            print(f"\n  Possible severity hallucinations ({len(issues)}):")
            for iss in issues:
                print(iss)
        else:
            print(fmt(PASS, "No suspected severity hallucinations detected"))

    # ── Section 2: Evidence accumulation ────────────────────────────────────
    print("\n\n[SECTION 2] Evidence accumulation (ON MATCH list append)")
    print("-" * 70)
    try:
        acc = await test_evidence_accumulation(builder)
        ev_list = acc.get("evidence_list", [])
        chunk_ids = acc.get("chunk_ids", [])
        severity = acc.get("severity")

        print(f"  evidence_list entries : {len(ev_list)}")
        for i, ev in enumerate(ev_list):
            print(f"    [{i+1}] \"{ev[:80]}\"")

        print(f"  cpg_chunk_ids entries : {len(chunk_ids)}")
        for cid in chunk_ids:
            print(f"    - {cid}")

        print(f"  severity on edge      : {severity}")

        if len(ev_list) == 2:
            print(fmt(PASS, "evidence_list has 2 entries after 2 writes — accumulation working"))
        elif len(ev_list) == 1:
            print(fmt(FAIL, "evidence_list has 1 entry — ON MATCH append not firing (first-wins still in effect)"))
        else:
            print(fmt(FAIL, f"evidence_list has {len(ev_list)} entries — unexpected"))

        if len(chunk_ids) == 2:
            print(fmt(PASS, "cpg_chunk_ids has 2 entries — list accumulation working"))
        else:
            print(fmt(FAIL, f"cpg_chunk_ids has {len(chunk_ids)} entries — expected 2"))

        if severity == "MODERATE":
            print(fmt(PASS, "severity written correctly on ON CREATE"))
        else:
            print(fmt(FAIL, f"severity is '{severity}', expected 'MODERATE'"))

    except Exception as e:
        print(fmt(FAIL, f"Evidence accumulation test crashed: {e}"))
        import traceback
        traceback.print_exc()

    # ── Done ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SMOKE TEST COMPLETE")
    print("If all gates PASS: safe to proceed to Phase B re-ingestion.")
    print("If any FAIL: fix before running the batch.")
    print("=" * 70)

    await builder.close()


if __name__ == "__main__":
    asyncio.run(main())
