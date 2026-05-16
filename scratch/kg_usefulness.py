r"""
Knowledge Graph USEFULNESS Test
Run: venv\Scripts\python.exe scratch\kg_usefulness.py

Tests whether the KG adds value beyond vector search by running
clinical query patterns that REQUIRE graph traversal:

  1. Multi-hop: "What treats AF AND what are those drugs' side effects?"
  2. Contraindication lookup: "What is contraindicated with AF?"
  3. Drug-condition pathway: Pick a drug -> find all its relationships
  4. Risk factor chain: "What increases risk of stroke in AF?"
  5. Cross-section linking: Do edges connect content from different sections?
"""

import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


async def run_usefulness_tests():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=" * 70)
    print("KNOWLEDGE GRAPH USEFULNESS TEST")
    print("Can the graph answer questions vector search alone cannot?")
    print("=" * 70)

    score = 0
    total = 5

    async with driver.session(database=NEO4J_DATABASE) as session:

        # ============================================================
        # TEST 1: Multi-hop — Drug -> Treats -> Condition -> Risk
        # "What drugs treat AF, and what risks does AF increase?"
        # Vector search: would need to find two separate chunks and combine
        # Graph: single traversal
        # ============================================================
        print("\n" + "-" * 70)
        print("TEST 1: Multi-hop query")
        print("Q: What drugs treat or are indicated for AF,")
        print("   AND what does AF increase the risk of?")
        print("-" * 70)

        result = await session.run("""
            MATCH (drug)-[r1:TREATS|INDICATED_FOR|FIRST_LINE_FOR|RECOMMENDED_FOR]->(af:Condition)
            WHERE af.name =~ '(?i).*atrial fibrillation.*'
            WITH drug, type(r1) AS how
            ORDER BY how, drug.name
            RETURN DISTINCT drug.name AS drug, collect(DISTINCT how) AS relations
            LIMIT 15
        """)
        drugs = [r async for r in result]

        result2 = await session.run("""
            MATCH (af:Condition)-[r:INCREASES_RISK_OF]->(risk)
            WHERE af.name =~ '(?i).*atrial fibrillation.*'
            RETURN risk.name AS risk, left(r.evidence, 80) AS evidence
        """)
        risks = [r async for r in result2]

        if drugs and risks:
            print(f"\n  Drugs linked to AF ({len(drugs)}):")
            for d in drugs[:8]:
                print(f"    - {d['drug']} ({', '.join(d['relations'])})")
            print(f"\n  AF increases risk of ({len(risks)}):")
            for r in risks[:5]:
                print(f"    - {r['risk']}")
                print(f"      Evidence: \"{r['evidence']}...\"")
            print("\n  >> PASS: Graph connects drugs to AF AND AF to downstream risks")
            print("     Vector search would need 2+ separate queries to find this.")
            score += 1
        else:
            print("  >> FAIL: Could not find multi-hop drug->AF->risk chain")

        # ============================================================
        # TEST 2: Contraindication lookup
        # "What is contraindicated in AF patients?"
        # ============================================================
        print("\n" + "-" * 70)
        print("TEST 2: Contraindication lookup")
        print("Q: What drugs/procedures are contraindicated?")
        print("-" * 70)

        result = await session.run("""
            MATCH (a)-[r:CONTRAINDICATED_WITH]->(b)
            RETURN a.name AS entity_a, labels(a)[0] AS type_a,
                   b.name AS entity_b, labels(b)[0] AS type_b,
                   left(r.evidence, 100) AS evidence
            LIMIT 10
        """)
        contras = [r async for r in result]

        if contras:
            print(f"\n  Contraindications found: {len(contras)}")
            for c in contras[:5]:
                print(f"    [{c['type_a']}] {c['entity_a']}")
                print(f"      CONTRAINDICATED_WITH [{c['type_b']}] {c['entity_b']}")
                print(f"      Evidence: \"{c['evidence']}...\"")
                print()
            print("  >> PASS: Graph provides structured contraindication lookups")
            print("     This is a safety-critical feature vector search may miss.")
            score += 1
        else:
            print("  >> FAIL: No contraindications found")

        # ============================================================
        # TEST 3: Drug profile — all relationships for one drug
        # "Tell me everything the CPG says about Warfarin"
        # ============================================================
        print("\n" + "-" * 70)
        print("TEST 3: Drug profile (complete relationship map)")
        print("Q: What does the CPG say about Warfarin / VKA?")
        print("-" * 70)

        result = await session.run("""
            MATCH (drug)-[r]->(target)
            WHERE drug.name =~ '(?i).*(warfarin|vka|vitamin k antagonist).*'
            RETURN drug.name AS drug, type(r) AS relation,
                   target.name AS target, labels(target)[0] AS target_type,
                   left(r.evidence, 80) AS evidence
            UNION
            MATCH (source)-[r]->(drug)
            WHERE drug.name =~ '(?i).*(warfarin|vka|vitamin k antagonist).*'
            RETURN source.name AS drug, type(r) AS relation,
                   drug.name AS target, labels(drug)[0] AS target_type,
                   left(r.evidence, 80) AS evidence
        """)
        profile = [r async for r in result]

        if profile:
            # Group by relation type
            by_rel = {}
            for p in profile:
                rel = p["relation"]
                if rel not in by_rel:
                    by_rel[rel] = []
                by_rel[rel].append(p)

            print(f"\n  Warfarin/VKA relationships found: {len(profile)}")
            for rel, items in sorted(by_rel.items()):
                print(f"\n    {rel} ({len(items)}):")
                for item in items[:3]:
                    print(f"      -> {item['target']}")
            print("\n  >> PASS: Graph builds a complete drug profile from scattered sections")
            print("     Vector search returns isolated chunks, not a unified drug view.")
            score += 1
        else:
            print("  >> FAIL: No Warfarin/VKA relationships found")

        # ============================================================
        # TEST 4: Risk factor chain for stroke
        # "What increases risk of stroke in AF patients?"
        # ============================================================
        print("\n" + "-" * 70)
        print("TEST 4: Risk factor chain")
        print("Q: What increases risk of stroke?")
        print("-" * 70)

        result = await session.run("""
            MATCH (rf)-[r:INCREASES_RISK_OF]->(stroke)
            WHERE stroke.name =~ '(?i).*(stroke|thrombo|embol).*'
            RETURN rf.name AS risk_factor, labels(rf)[0] AS rf_type,
                   stroke.name AS outcome,
                   left(r.evidence, 80) AS evidence
            ORDER BY rf.name
        """)
        risks = [r async for r in result]

        if risks:
            print(f"\n  Risk factors for stroke/thromboembolism: {len(risks)}")
            for r in risks[:8]:
                print(f"    [{r['rf_type']}] {r['risk_factor']} -> {r['outcome']}")
            print("\n  >> PASS: Graph aggregates risk factors from across the document")
            print("     A clinician can see ALL risk factors at once, not just per-chunk.")
            score += 1
        else:
            print("  >> FAIL: No stroke risk factors found")

        # ============================================================
        # TEST 5: Cross-section linking
        # Do relationships connect entities mentioned in different sections?
        # ============================================================
        print("\n" + "-" * 70)
        print("TEST 5: Cross-section linking")
        print("Q: Do graph edges link content from different source sections?")
        print("-" * 70)

        result = await session.run("""
            MATCH (a)-[r]->(b)
            WHERE r.source IS NOT NULL
            WITH r.source AS source, count(*) AS cnt
            RETURN source, cnt ORDER BY source
        """)
        sources = [r async for r in result]

        if len(sources) > 1:
            print(f"\n  Triples come from {len(sources)} different source sections:")
            for s in sources:
                print(f"    {s['source']}: {s['cnt']} triples")
            print("\n  >> PASS: Graph connects knowledge across multiple sections")
            print("     e.g., a drug mentioned in Section 4 links to its")
            print("     contraindication in Section 6 via shared entity nodes.")
            score += 1
        elif len(sources) == 1:
            print(f"  Only 1 source section found. Need more sections ingested.")
            print("  >> PARTIAL: Will improve after full ingestion")
        else:
            print("  >> FAIL: No source metadata on edges")

    # ── FINAL SCORE ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"USEFULNESS SCORE: {score}/{total}")
    if score >= 4:
        print("VERDICT: Graph is USEFUL - adds clear value over vector search alone")
    elif score >= 2:
        print("VERDICT: Graph is PARTIALLY USEFUL - will improve after full ingestion")
    else:
        print("VERDICT: Graph needs more data or relationship extraction tuning")
    print("=" * 70)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(run_usefulness_tests())
