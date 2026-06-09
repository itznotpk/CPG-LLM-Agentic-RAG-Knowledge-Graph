"""
§4.3.1 grounding-store integrity verifier — screenshot-friendly companion to the
pytest smoke suites (tests/test_grounding_store_smoke.py + tests/test_kg_store_smoke.py).

The pytest suites are the CI gate (they assert pass/fail); this script prints the
SAME invariants together with their live measured values, so the terminal output is
meaningful report evidence rather than a bare list of green PASS lines.

Run:  cd backend; python scripts/verify_grounding_stores.py
Exit: 0 = all checks pass, 1 = at least one failed, 2 = a store was unreachable.
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()

OK = "✓"   # ✓
NO = "✗"   # ✗
EXPECTED_DIM = 1536

_failures = 0
_unreachable = False


def check(label: str, passed: bool, measured: str) -> None:
    """Print one aligned result row and track failures."""
    global _failures
    mark = OK if passed else NO
    if not passed:
        _failures += 1
    print(f"   [{mark}] {label:<52} {measured}")


def section(title: str) -> None:
    print(f"\n  {title}\n  " + "-" * 68)


async def verify_pgvector() -> None:
    global _unreachable
    url = os.getenv("DATABASE_URL")
    print("=" * 74)
    print("  GROUNDING STORE 1/2 — Neon pgvector (CPG text + ICD-11 DDx space)")
    print("=" * 74)
    if not url:
        print("   SKIPPED — DATABASE_URL not set")
        _unreachable = True
        return
    try:
        conn = await asyncpg.connect(url)
    except Exception as e:  # noqa: BLE001
        print(f"   UNREACHABLE — {type(e).__name__}: {e}")
        _unreachable = True
        return

    try:
        section("Connectivity & silent-drop guard")
        ext = await conn.fetchval("SELECT 1 FROM pg_extension WHERE extname='vector'")
        check("pgvector extension installed", ext == 1, "pg_extension: vector")
        await conn.execute("SET ivfflat.probes = 100")
        probes = await conn.fetchval("SHOW ivfflat.probes")
        check("SET ivfflat.probes = 100 takes effect", probes == "100", f"probes = {probes}")

        section("Embedding dimension (must be 1536 — Titan space)")
        for table, col in [("chunks", "embedding"),
                           ("documents", "scope_embedding"),
                           ("icd11_codes", "embedding")]:
            dim = await conn.fetchval(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid=$1::regclass AND attname=$2 AND NOT attisdropped",
                table, col,
            )
            check(f"{table}.{col}", dim == EXPECTED_DIM, f"vector({dim})")

        section("ivfflat indexes present (DDx / scope vector paths)")
        for idx in ["idx_chunks_embedding", "idx_documents_scope_embedding"]:
            d = await conn.fetchval("SELECT indexdef FROM pg_indexes WHERE indexname=$1", idx)
            check(idx, bool(d) and "ivfflat" in d.lower(), "ivfflat" if d else "MISSING")

        section("Corpus completeness")
        docs = await conn.fetchval("SELECT count(*) FROM documents")
        chunks = await conn.fetchval("SELECT count(*) FROM chunks")
        check("documents ingested", docs > 0, f"{docs} rows")
        check("chunks ingested", chunks > 0, f"{chunks} rows")
        unembedded_leaves = await conn.fetchval(
            "SELECT count(*) FROM chunks c WHERE c.embedding IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM chunks ch WHERE ch.parent_chunk_id=c.id)"
        )
        parent_null = await conn.fetchval(
            "SELECT count(*) FROM chunks c WHERE c.embedding IS NULL "
            "AND EXISTS (SELECT 1 FROM chunks ch WHERE ch.parent_chunk_id=c.id)"
        )
        check("every leaf chunk embedded", unembedded_leaves == 0,
              f"{unembedded_leaves} unembedded leaves ({parent_null} parents skipped by design)")

        section("Routing scope wiring (verified CPGs)")
        verified = await conn.fetchval("SELECT count(*) FROM documents WHERE scope_verified=TRUE")
        check("scope_verified documents exist", verified > 0, f"{verified} verified")
        no_scope = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE scope_verified=TRUE "
            "AND cardinality(icd11_scope)=0 AND cardinality(procedure_scope)=0"
        )
        check("verified docs carry routing scope", no_scope == 0, f"{no_scope} missing scope")
        no_emb = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE scope_verified=TRUE AND scope_embedding IS NULL"
        )
        check("verified docs carry scope_embedding", no_emb == 0, f"{no_emb} missing embedding")

        section("DDx vector table populated")
        icd_total = await conn.fetchval("SELECT count(*) FROM icd11_codes")
        icd_emb = await conn.fetchval("SELECT count(*) FROM icd11_codes WHERE embedding IS NOT NULL")
        check("icd11_codes embedded", icd_total > 0 and icd_emb > 0,
              f"{icd_emb}/{icd_total} embedded")
    finally:
        await conn.close()


async def verify_kg() -> None:
    global _unreachable
    print("\n" + "=" * 74)
    print("  GROUNDING STORE 2/2 — Neo4j knowledge graph (drug-safety web)")
    print("=" * 74)
    uri = os.getenv("NEO4J_URI")
    if not uri:
        print("   SKIPPED — NEO4J_URI not set")
        _unreachable = True
        return
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        uri, auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        max_connection_lifetime=300, keep_alive=True,
        liveness_check_timeout=30, connection_acquisition_timeout=60,
    )
    db = os.getenv("NEO4J_DATABASE") or None

    async def scalar(cypher: str) -> int:
        res = await session.run(cypher)
        row = await res.single()
        return row[0]

    try:
        async with driver.session(database=db) as session:
            section("Connectivity (Aura idle-drop / paused guard)")
            check("round-trip query (RETURN 1)", await scalar("RETURN 1") == 1, "reachable")

            section("Required node labels present & non-empty")
            for label in ["Drug", "Condition"]:
                c = await scalar(f"MATCH (n:{label}) RETURN count(n)")
                check(f":{label}", c > 0, f"{c} nodes")

            section("Required relationship types present & non-empty")
            for rel in ["CONTRAINDICATED_WITH", "INTERACTS_WITH", "REQUIRES_MONITORING",
                        "FIRST_LINE_FOR", "RECOMMENDED_FOR", "REQUIRES_REFERRAL"]:
                c = await scalar(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
                note = "  (sparse — by design, see §4.3.1)" if rel == "INTERACTS_WITH" else ""
                check(f":{rel}", c > 0, f"{c} edges{note}")

            section("Match-key integrity (name_normalised is the IN-clause key)")
            for label in ["Drug", "Condition"]:
                total = await scalar(f"MATCH (n:{label}) RETURN count(n)")
                miss = await scalar(f"MATCH (n:{label}) WHERE n.name_normalised IS NULL RETURN count(n)")
                check(f":{label} name_normalised coverage", miss == 0,
                      f"{total - miss}/{total} ({'100%' if miss == 0 else 'GAP'})")
            bad = await scalar(
                "MATCH (a)-[:CONTRAINDICATED_WITH]->(b) "
                "WHERE a.name_normalised IS NULL OR b.name_normalised IS NULL RETURN count(*)"
            )
            check("no unnamed-endpoint CONTRAINDICATED_WITH edges", bad == 0, f"{bad} bad edges")
    except Exception as e:  # noqa: BLE001
        print(f"   UNREACHABLE — {type(e).__name__}: {e}")
        _unreachable = True
    finally:
        await driver.close()


async def main() -> int:
    print("\n  ClearPath — §4.3.1 Grounding-Store Integrity Verification\n")
    await verify_pgvector()
    await verify_kg()
    print("\n" + "=" * 74)
    if _unreachable:
        print("  RESULT: a store was unreachable — see above (env vars / Aura state).")
        return 2
    if _failures == 0:
        print(f"  RESULT: ALL CHECKS PASSED  {OK}   (both grounding stores verified)")
        print("=" * 74)
        return 0
    print(f"  RESULT: {_failures} CHECK(S) FAILED  {NO}")
    print("=" * 74)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
