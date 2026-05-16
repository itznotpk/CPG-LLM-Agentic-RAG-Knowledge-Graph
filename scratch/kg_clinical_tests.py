r"""
Clinical KG Query Tests: Contraindications, Comorbidities, Treatment Pathways
Run: venv\Scripts\python.exe scratch\kg_clinical_tests.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


async def run_clinical_tests():
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print("=" * 70)
    print("CLINICAL KNOWLEDGE GRAPH QUERY TESTS")
    print("=" * 70)

    async with driver.session(database=NEO4J_DATABASE) as session:

        # ============================================================
        # TEST 1: DRUG CONTRAINDICATIONS
        # "What should I NOT give this patient?"
        # ============================================================
        print("\n" + "=" * 70)
        print("TEST 1: DRUG CONTRAINDICATIONS")
        print("Clinical question: What drugs are contraindicated, and with what?")
        print("=" * 70)

        result = await session.run("""
            MATCH (drug)-[r:CONTRAINDICATED_WITH]->(target)
            RETURN drug.name AS drug, labels(drug)[0] AS drug_type,
                   target.name AS contraindicated_with, labels(target)[0] AS target_type,
                   r.evidence AS evidence, r.source AS source_section
            ORDER BY drug.name
        """)
        contras = [r async for r in result]

        if contras:
            # Group by drug
            by_drug = {}
            for c in contras:
                drug = c["drug"]
                if drug not in by_drug:
                    by_drug[drug] = []
                by_drug[drug].append(c)

            print(f"\n  Total contraindication edges: {len(contras)}")
            print(f"  Drugs with contraindications: {len(by_drug)}")

            for drug, items in sorted(by_drug.items()):
                print(f"\n  [{drug}]")
                for item in items:
                    print(f"    X  CONTRAINDICATED WITH: {item['contraindicated_with']} ({item['target_type']})")
                    if item["evidence"]:
                        ev = item["evidence"][:120]
                        print(f"       Evidence: \"{ev}...\"")
                    if item["source_section"]:
                        print(f"       Source: {item['source_section']}")
        else:
            print("  No contraindications found in graph.")

        # Also check reverse direction
        result2 = await session.run("""
            MATCH (target)-[r:CONTRAINDICATED_WITH]->(drug:Drug)
            RETURN target.name AS entity, labels(target)[0] AS entity_type,
                   drug.name AS drug, r.evidence AS evidence
        """)
        reverse = [r async for r in result2]
        if reverse:
            print(f"\n  Additional reverse contraindications: {len(reverse)}")
            for rv in reverse[:5]:
                print(f"    {rv['entity']} ({rv['entity_type']}) X CONTRAINDICATED WITH {rv['drug']}")

        # ============================================================
        # TEST 2: COMORBIDITIES
        # "What conditions co-occur with or are caused by AF?"
        # ============================================================
        print("\n\n" + "=" * 70)
        print("TEST 2: COMORBIDITIES & ASSOCIATED CONDITIONS")
        print("Clinical question: What conditions are associated with AF?")
        print("=" * 70)

        # Conditions that AF increases risk of
        result = await session.run("""
            MATCH (af:Condition)-[r:INCREASES_RISK_OF|CAUSES]->(comorbid)
            WHERE af.name =~ '(?i).*(atrial fibrillation|AF).*'
            RETURN af.name AS source, type(r) AS relationship,
                   comorbid.name AS comorbidity, labels(comorbid)[0] AS type,
                   r.evidence AS evidence
            ORDER BY relationship, comorbid.name
        """)
        af_causes = [r async for r in result]

        # Conditions that increase risk OF AF
        result2 = await session.run("""
            MATCH (risk_factor)-[r:INCREASES_RISK_OF|CAUSES]->(af:Condition)
            WHERE af.name =~ '(?i).*(atrial fibrillation|AF).*'
            RETURN risk_factor.name AS risk_factor, labels(risk_factor)[0] AS rf_type,
                   type(r) AS relationship,
                   r.evidence AS evidence
            ORDER BY risk_factor.name
        """)
        causes_af = [r async for r in result2]

        # Conditions assessed together with AF
        result3 = await session.run("""
            MATCH (condition:Condition)-[r]->(other)
            WHERE condition.name =~ '(?i).*(atrial fibrillation|AF).*'
            AND type(r) <> 'INCREASES_RISK_OF' AND type(r) <> 'CAUSES'
            RETURN condition.name AS af, type(r) AS relationship,
                   other.name AS related, labels(other)[0] AS related_type
            ORDER BY relationship
        """)
        other_rels = [r async for r in result3]

        print(f"\n  A) AF INCREASES RISK OF / CAUSES ({len(af_causes)}):")
        if af_causes:
            for c in af_causes:
                print(f"     AF --{c['relationship']}--> {c['comorbidity']} ({c['type']})")
                if c["evidence"]:
                    print(f"        \"{c['evidence'][:100]}...\"")
        else:
            print("     (none found)")

        print(f"\n  B) WHAT INCREASES RISK OF / CAUSES AF ({len(causes_af)}):")
        if causes_af:
            for c in causes_af:
                print(f"     {c['risk_factor']} ({c['rf_type']}) --{c['relationship']}--> AF")
                if c["evidence"]:
                    print(f"        \"{c['evidence'][:100]}...\"")
        else:
            print("     (none found)")

        print(f"\n  C) OTHER AF ASSOCIATIONS ({len(other_rels)}):")
        if other_rels:
            for o in other_rels[:10]:
                print(f"     AF --{o['relationship']}--> {o['related']} ({o['related_type']})")
        else:
            print("     (none found)")

        # ============================================================
        # TEST 3: TREATMENT PATHWAYS (First-line -> Second-line)
        # "What do I try first, and what's the backup?"
        # ============================================================
        print("\n\n" + "=" * 70)
        print("TEST 3: TREATMENT PATHWAYS (First-line vs Second-line)")
        print("Clinical question: What's the treatment hierarchy?")
        print("=" * 70)

        # First-line treatments
        result = await session.run("""
            MATCH (drug)-[r:FIRST_LINE_FOR]->(condition)
            RETURN drug.name AS treatment, labels(drug)[0] AS treatment_type,
                   condition.name AS indication, labels(condition)[0] AS condition_type,
                   r.evidence AS evidence, r.source AS source
            ORDER BY condition.name, drug.name
        """)
        first_line = [r async for r in result]

        # Second-line treatments
        result2 = await session.run("""
            MATCH (drug)-[r:SECOND_LINE_FOR]->(condition)
            RETURN drug.name AS treatment, labels(drug)[0] AS treatment_type,
                   condition.name AS indication, labels(condition)[0] AS condition_type,
                   r.evidence AS evidence, r.source AS source
            ORDER BY condition.name, drug.name
        """)
        second_line = [r async for r in result2]

        # Monitoring requirements
        result3 = await session.run("""
            MATCH (drug)-[r:REQUIRES_MONITORING]->(monitor)
            RETURN drug.name AS drug, monitor.name AS monitoring,
                   labels(monitor)[0] AS monitor_type,
                   r.evidence AS evidence
            ORDER BY drug.name
        """)
        monitoring = [r async for r in result3]

        print(f"\n  FIRST-LINE TREATMENTS ({len(first_line)}):")
        if first_line:
            for f in first_line:
                print(f"    1st: {f['treatment']} ({f['treatment_type']}) --> {f['indication']}")
                if f["evidence"]:
                    print(f"        \"{f['evidence'][:100]}...\"")
        else:
            print("    (none found)")

        print(f"\n  SECOND-LINE TREATMENTS ({len(second_line)}):")
        if second_line:
            for s in second_line:
                print(f"    2nd: {s['treatment']} ({s['treatment_type']}) --> {s['indication']}")
                if s["evidence"]:
                    print(f"        \"{s['evidence'][:100]}...\"")
        else:
            print("    (none found)")

        print(f"\n  MONITORING REQUIREMENTS ({len(monitoring)}):")
        if monitoring:
            for m in monitoring:
                print(f"    {m['drug']} --> monitor: {m['monitoring']} ({m['monitor_type']})")
                if m["evidence"]:
                    print(f"        \"{m['evidence'][:100]}...\"")
        else:
            print("    (none found)")

        # ── Clinical scenario walkthrough ────────────────────────
        print("\n\n" + "=" * 70)
        print("CLINICAL SCENARIO: 72-year-old with new AF")
        print("Q: What treatment, what to avoid, what to monitor?")
        print("=" * 70)

        result = await session.run("""
            MATCH (drug)-[r]->(target)
            WHERE drug.name =~ '(?i).*(warfarin|vka|dabigatran|aspirin|amiodarone|digoxin).*'
            AND type(r) IN ['TREATS', 'INDICATED_FOR', 'FIRST_LINE_FOR',
                           'CONTRAINDICATED_WITH', 'REQUIRES_MONITORING',
                           'HAS_DOSAGE', 'CAUSES']
            RETURN drug.name AS drug, type(r) AS action,
                   target.name AS target, labels(target)[0] AS target_type
            ORDER BY drug.name, action
        """)
        scenario = [r async for r in result]

        if scenario:
            by_drug = {}
            for s in scenario:
                d = s["drug"]
                if d not in by_drug:
                    by_drug[d] = []
                by_drug[d].append(s)

            for drug, actions in sorted(by_drug.items()):
                print(f"\n  [{drug}]")
                for a in actions[:6]:
                    marker = "X" if a["action"] == "CONTRAINDICATED_WITH" else \
                             "!" if a["action"] == "CAUSES" else \
                             ">" if a["action"] == "REQUIRES_MONITORING" else "+"
                    print(f"    {marker} {a['action']}: {a['target']}")

    print("\n" + "=" * 70)
    print("TESTS COMPLETE")
    print("=" * 70)

    await driver.close()


if __name__ == "__main__":
    asyncio.run(run_clinical_tests())
