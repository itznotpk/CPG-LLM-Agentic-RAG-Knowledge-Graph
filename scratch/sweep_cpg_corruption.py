"""
READ-ONLY corruption sweep across ALL CPGs.

For each CPG, identify its edges by the set of section titles UNIQUE to that CPG
(titles shared with other CPGs are excluded to avoid cross-CPG miscounting), then
check what fraction of distinct cpg_chunk_id values resolve to a live Postgres chunk.

A high orphan % == leftover cross-DB corruption (same failure mode as Dyslipidaemia).
Does NOT modify anything.
"""
import asyncio, os
from collections import defaultdict
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import asyncpg
load_dotenv()

async def main():
    pg = await asyncpg.connect(os.getenv("DATABASE_URL"))

    # title -> set of cpg_names that use it  (to find collisions)
    rows = await pg.fetch("""
        SELECT DISTINCT metadata->>'cpg_name' AS cpg, title
        FROM documents WHERE metadata->>'cpg_name' IS NOT NULL
    """)
    title_owners = defaultdict(set)
    cpg_titles = defaultdict(list)
    for r in rows:
        title_owners[r["title"]].add(r["cpg"])
        cpg_titles[r["cpg"]].append(r["title"])

    driver = AsyncGraphDatabase.driver(os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

    print(f"{'CPG':52} {'resolve':>9} {'orphan%':>8}  status")
    print("-" * 86)
    flagged = []
    async with driver.session() as session:
        for cpg in sorted(cpg_titles):
            uniq = [t for t in cpg_titles[cpg] if len(title_owners[t]) == 1]
            shared = len(cpg_titles[cpg]) - len(uniq)
            if not uniq:
                print(f"{cpg[:52]:52} {'--':>9} {'--':>8}  no unique titles (can't check by title)")
                continue
            r = await session.run("""
                MATCH ()-[r]->() WHERE r.source_document IN $t AND r.cpg_chunk_id IS NOT NULL
                RETURN collect(DISTINCT r.cpg_chunk_id) AS ids
            """, t=uniq)
            ids = (await r.single())["ids"]
            if not ids:
                print(f"{cpg[:52]:52} {'0 edges':>9} {'--':>8}  (no edges on unique titles)")
                continue
            live = await pg.fetch("SELECT id FROM chunks WHERE id::text = ANY($1::text[])", ids)
            n_live = len({str(x["id"]) for x in live})
            orph = len(ids) - n_live
            pct = 100 * orph / len(ids)
            status = "OK" if pct == 0 else ("MINOR" if pct < 10 else "** CORRUPTION **")
            note = f" ({shared} shared titles skipped)" if shared else ""
            if pct > 0:
                flagged.append((cpg, n_live, len(ids), pct))
            print(f"{cpg[:52]:52} {n_live}/{len(ids):<7} {pct:7.1f}%  {status}{note}")

    print("\n" + "=" * 86)
    if flagged:
        print("FLAGGED for remediation (orphaned cpg_chunk_id):")
        for cpg, l, t, p in sorted(flagged, key=lambda x: -x[3]):
            print(f"   {cpg}: {l}/{t} resolve ({p:.1f}% orphaned)")
    else:
        print("ALL CPGs clean — 0 orphaned chunk references.")
    await pg.close(); await driver.close()
asyncio.run(main())
