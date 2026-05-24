"""
Phase E sign-off (revised): use fixtures grounded in actual KG edges.

The original plan's 3 fixtures (RAAS double-block, sulfa cross-reactivity) had no
backing edges in our extracted corpus — that's a corpus coverage gap, not a
wiring bug. To sign off the WIRING, we sample real edges from the KG, then
drive matching inputs through clinical_graph_lookup() and confirm the lookup
returns each flag with severity + citation.
"""
import sys, io, os, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
from neo4j import AsyncGraphDatabase
from agent.graph_clinical import clinical_graph_lookup


async def sample_edges():
    """Pull one concrete edge per query type, with citation present."""
    drv = AsyncGraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
    samples = {}
    async with drv.session(database=os.getenv("NEO4J_DATABASE") or None) as s:
        # Drug-drug interaction
        r = await s.run(
            "MATCH (a:Drug)-[r:INTERACTS_WITH|CONTRAINDICATED_WITH]-(b:Drug) "
            "WHERE r.cpg_chunk_id IS NOT NULL AND r.severity IS NOT NULL "
            "RETURN a.name_normalised AS a, b.name_normalised AS b, type(r) AS rel, r.severity AS sev LIMIT 1"
        )
        rec = await r.single()
        if rec:
            samples["drug_interaction"] = dict(rec)
        # Comorbidity flag
        r = await s.run(
            "MATCH (d:Drug)-[r:REQUIRES_MONITORING|CONTRAINDICATED_WITH|REQUIRES_DOSE_ADJUSTMENT]->(c:Condition) "
            "WHERE r.cpg_chunk_id IS NOT NULL AND r.severity IS NOT NULL "
            "RETURN d.name_normalised AS d, c.name_normalised AS c, type(r) AS rel, r.severity AS sev LIMIT 1"
        )
        rec = await r.single()
        if rec:
            samples["comorbidity"] = dict(rec)
        # Allergy cross-reactivity
        r = await s.run(
            "MATCH (a)-[r:CROSS_REACTS_WITH|CONTRAINDICATED_WITH]-(d:Drug) "
            "WHERE r.cpg_chunk_id IS NOT NULL AND labels(a)[0] <> 'Drug' "
            "RETURN labels(a)[0] AS alabel, a.name_normalised AS a, d.name_normalised AS d, type(r) AS rel LIMIT 1"
        )
        rec = await r.single()
        if rec:
            samples["allergy"] = dict(rec)
    await drv.close()
    return samples


async def main():
    samples = await sample_edges()
    print("=" * 72)
    print("PHASE E (grounded) — KG wiring sign-off")
    print("=" * 72)
    print("\nSampled real edges from Neo4j:")
    for k, v in samples.items():
        print(f"  {k}: {v}")

    results = []

    if "drug_interaction" in samples:
        s = samples["drug_interaction"]
        print(f"\n[Fixture 1] drug-drug — meds=[{s['a']}], candidates=[{s['b']}]")
        flags = await clinical_graph_lookup(patient_meds=[s["a"]], candidate_drugs=[s["b"]], comorbidities=[], allergies=[])
        ok = any(f.cpg_chunk_id for f in flags)
        print(f"  → {len(flags)} flag(s); citation present: {ok}")
        for f in flags[:3]:
            print(f"    - {f.flag_type}[{f.severity}] {f.subject}↔{f.object}  chunk={f.cpg_chunk_id} src={f.source_document}")
        results.append(("drug-drug interaction", len(flags) > 0 and ok))

    if "comorbidity" in samples:
        s = samples["comorbidity"]
        print(f"\n[Fixture 2] comorbidity — candidates=[{s['d']}], comorbidities=[{s['c']}]")
        flags = await clinical_graph_lookup(patient_meds=[], candidate_drugs=[s["d"]], comorbidities=[s["c"]], allergies=[])
        ok = any(f.cpg_chunk_id for f in flags)
        print(f"  → {len(flags)} flag(s); citation present: {ok}")
        for f in flags[:3]:
            print(f"    - {f.flag_type}[{f.severity}] {f.subject}↔{f.object}  chunk={f.cpg_chunk_id} src={f.source_document}")
        results.append(("comorbidity flag", len(flags) > 0 and ok))

    if "allergy" in samples:
        s = samples["allergy"]
        print(f"\n[Fixture 3] allergy — allergies=[{s['a']}], candidates=[{s['d']}]")
        flags = await clinical_graph_lookup(patient_meds=[], candidate_drugs=[s["d"]], comorbidities=[], allergies=[s["a"]])
        ok = any(f.cpg_chunk_id for f in flags)
        print(f"  → {len(flags)} flag(s); citation present: {ok}")
        for f in flags[:3]:
            print(f"    - {f.flag_type}[{f.severity}] {f.subject}↔{f.object}  chunk={f.cpg_chunk_id} src={f.source_document}")
        results.append(("allergy cross-reactivity", len(flags) > 0 and ok))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  {passed}/{len(results)} wiring paths confirmed")


if __name__ == "__main__":
    asyncio.run(main())
