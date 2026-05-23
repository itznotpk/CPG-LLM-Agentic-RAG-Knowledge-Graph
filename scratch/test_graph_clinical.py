"""
Smoke test for clinical_graph_lookup — parameterisable by domain or CPG.

Modes
-----
  python test_graph_clinical.py
      Default: runs the hardcoded AF/anticoagulation scenario (original behaviour).

  python test_graph_clinical.py --domain <name>
      Runs a preset scenario for a known domain. Use --list to see available domains.

  python test_graph_clinical.py --cpg "<cpg_name_substring>"
      Auto-discovers drugs and conditions from the CPG's own KG edges and builds
      a live scenario. Useful immediately after ingesting any new CPG.

  python test_graph_clinical.py --list
      Prints all available preset domain names.

Examples
--------
  python test_graph_clinical.py --domain t1dm
  python test_graph_clinical.py --domain hypertension
  python test_graph_clinical.py --cpg "Growth-Hormone"
  python test_graph_clinical.py --cpg "Type-1-Diabetes"
"""
import sys
import io
import argparse
import asyncio
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph_clinical import clinical_graph_lookup, format_flags_for_prompt
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Preset domain scenarios
# Each entry: (patient_meds, candidate_drugs, comorbidities, allergies, description)
# ---------------------------------------------------------------------------
PRESETS = {
    "af": (
        ["warfarin"],
        ["digoxin", "amiodarone"],
        ["heart failure", "atrial fibrillation"],
        [],
        "Atrial Fibrillation — warfarin + digoxin/amiodarone, HF comorbidity "
        "(requires Atrial-Fibrillation(2012) CPG to be ingested)",
    ),
    "hypertension": (
        ["amlodipine"],
        ["metoprolol", "bisoprolol", "ramipril"],
        ["heart failure", "renal impairment", "diabetes mellitus"],
        [],
        "Hypertension — beta-blockers + ACE inhibitor, HF/renal comorbidities",
    ),
    "t1dm": (
        [],
        ["insulin", "statin", "metformin"],
        ["hypoglycaemia", "dyslipidaemia", "diabetic ketoacidosis"],
        [],
        "Type 1 Diabetes Mellitus — insulin/statin, hypoglycaemia/DKA comorbidities",
    ),
    "heart-failure": (
        ["digoxin", "furosemide"],
        ["dronedarone", "verapamil", "diltiazem"],
        ["heart failure", "renal impairment"],
        [],
        "Heart Failure — dronedarone/verapamil contraindications, HF + renal comorbidities",
    ),
    "dyslipidaemia": (
        ["statin"],
        ["fibrate", "niacin", "ezetimibe"],
        ["myopathy", "liver disease", "renal impairment"],
        [],
        "Dyslipidaemia — statin combinations, myopathy/hepatic comorbidities",
    ),
    "stroke": (
        ["aspirin"],
        ["clopidogrel", "warfarin", "heparin"],
        ["ischaemic stroke", "hypertension", "atrial fibrillation"],
        [],
        "Ischaemic Stroke — antiplatelet/anticoagulant combinations",
    ),
    "growth-hormone": (
        [],
        ["recombinant human growth hormone therapy", "somatropin"],
        ["gh deficiency", "tumor regrowth", "diabetes mellitus"],
        [],
        "Growth Hormone — rhGH therapy, tumor regrowth and diabetes monitoring",
    ),
    "infective-endocarditis": (
        ["penicillin"],
        ["gentamicin", "vancomycin", "rifampicin"],
        ["renal impairment", "infective endocarditis"],
        ["penicillin"],
        "Infective Endocarditis — aminoglycoside/vancomycin interactions, renal monitoring",
    ),
    "ed": (
        ["alpha-blocker", "testosterone"],
        ["phosphodiesterase-5 inhibitor", "pde5i", "tadalafil", "sildenafil"],
        ["organic nitrate", "organic nitrite", "sudden vision loss", "erectile dysfunction"],
        [],
        "Erectile Dysfunction — PDE5i contraindications (nitrates) and alpha-blocker/testosterone interactions",
    ),
    "diabetes-pregnancy": (
        [],
        ["insulin", "metformin", "corticosteroid", "vitamin c and e supplementation"],
        ["hypoglycaemia", "postpartum period", "gestational diabetes mellitus", "pre-eclampsia"],
        [],
        "Diabetes in Pregnancy — insulin monitoring, postpartum dose adjustment, ACE inhibitor/Vitamin C+E contraindications",
    ),
    "thyroid": (
        [],
        ["methimazole", "propylthiouracil", "atd", "levothyroxine", "propranolol"],
        ["agranulocytosis", "hypothyroidism", "hyperthyroidism", "graves' disease",
         "pregnancy", "wbc count", "serum t3 level"],
        [],
        "Thyroid Disorders — antithyroid drug monitoring (WBC, T3), levothyroxine interactions, pregnancy considerations",
    ),
}


# ---------------------------------------------------------------------------
# Auto-discovery: build a scenario from any CPG's own KG edges
# ---------------------------------------------------------------------------

async def autodiscover_scenario(cpg_substring: str):
    """
    Query Neo4j for Drug nodes with safety-critical edges sourced from the
    target CPG, then build patient_meds / candidate_drugs / comorbidities
    from the real graph data.

    Returns (patient_meds, candidate_drugs, comorbidities, allergies, description).
    """
    driver = AsyncGraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    async with driver.session() as s:
        # Step 1: get this CPG's unique section titles from Postgres via Neo4j
        # (we use source_document to identify the CPG's edges)
        # First find source_documents that contain the substring
        r = await s.run(
            """
            MATCH ()-[r]->()
            WHERE r.source_document CONTAINS $sub AND r.source_document IS NOT NULL
            RETURN DISTINCT r.source_document AS doc
            LIMIT 30
            """,
            sub=cpg_substring,
        )
        docs = [rec["doc"] async for rec in r]

        if not docs:
            print(f"  [WARN] No edges found with source_document containing '{cpg_substring}'")
            print("         Try a different substring (e.g. the section title prefix).")
            await driver.close()
            return None

        print(f"  Matched {len(docs)} source_document(s) for '{cpg_substring}'")

        # Step 2: find Drug nodes with safety-critical edges from those docs
        r2 = await s.run(
            """
            MATCH (d:Drug)-[r:CONTRAINDICATED_WITH|REQUIRES_MONITORING|INTERACTS_WITH
                           |REQUIRES_DOSE_ADJUSTMENT|FIRST_LINE_FOR|INDICATED_FOR]->(c)
            WHERE r.source_document IN $docs
            RETURN d.name_normalised AS drug,
                   type(r) AS rel,
                   c.name_normalised AS condition,
                   coalesce(r.severity, '') AS severity
            LIMIT 60
            """,
            docs=docs,
        )
        rows = await r2.data()

    await driver.close()

    if not rows:
        print(f"  [WARN] No Drug safety edges found for '{cpg_substring}'.")
        print("         The CPG may not have Drug→Condition safety edges, or the")
        print("         source_document substring didn't match. Try --cpg with a")
        print("         section title word (e.g. 'Insulin Therapy', 'Section 7').")
        return None

    # Build sets — prioritise CONTRAINDICATED/INTERACTS for candidate_drugs
    safety_rels = {"CONTRAINDICATED_WITH", "INTERACTS_WITH", "REQUIRES_DOSE_ADJUSTMENT"}
    candidate_drugs = list({r["drug"] for r in rows if r["rel"] in safety_rels})[:6]
    if not candidate_drugs:
        candidate_drugs = list({r["drug"] for r in rows})[:6]

    comorbidities = list({r["condition"] for r in rows if r["condition"]})[:6]

    # patient_meds: pick drugs that appear as objects of INTERACTS_WITH (the "other drug")
    r_inter = rows  # reuse same batch — pick condition names that look drug-like
    # heuristic: conditions with short names or containing common drug suffixes
    drug_like = [
        c["condition"] for c in rows
        if c["rel"] == "INTERACTS_WITH" and c["condition"]
    ]
    patient_meds = list(set(drug_like))[:3]

    desc = (
        f"Auto-discovered from CPG edges matching '{cpg_substring}' "
        f"({len(rows)} safety edges across {len(docs)} sections)"
    )
    return patient_meds, candidate_drugs, comorbidities, [], desc


# ---------------------------------------------------------------------------
# Run one scenario
# ---------------------------------------------------------------------------

async def run_scenario(patient_meds, candidate_drugs, comorbidities, allergies, description):
    print(f"\n  Description : {description}")
    print(f"  patient_meds: {patient_meds}")
    print(f"  candidates  : {candidate_drugs}")
    print(f"  comorbids   : {comorbidities}")
    print(f"  allergies   : {allergies}")

    flags = await clinical_graph_lookup(
        patient_meds=patient_meds,
        candidate_drugs=candidate_drugs,
        comorbidities=comorbidities,
        allergies=allergies,
    )

    print(f"\n  Flags returned: {len(flags)}")
    for f in flags:
        sev = f" [{f.severity}]" if f.severity else ""
        print(f"    [{f.flag_type}]{sev}: {f.subject} <-> {f.object}  ({f.relation})")
        evidence = f.evidence_list[0] if f.evidence_list else f.evidence
        if evidence:
            print(f"      Evidence: \"{evidence[:120]}\"")

    print()
    prompt_block = format_flags_for_prompt(flags)
    print("  --- Prompt block preview ---")
    for line in prompt_block.splitlines()[:8]:
        print(f"  {line}")
    if prompt_block.count("\n") > 8:
        print("  ...")

    return flags


# ---------------------------------------------------------------------------
# Empty-input crash guard (always runs)
# ---------------------------------------------------------------------------

async def run_empty_guard():
    print("\nTest: Empty inputs (crash guard — expected 0 flags)")
    flags = await clinical_graph_lookup()
    status = "PASS" if len(flags) == 0 else "FAIL (unexpected flags)"
    print(f"  Flags returned: {len(flags)} — {status}")
    return len(flags) == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--domain", metavar="NAME",
                       help="Run a preset domain scenario (use --list to see options)")
    group.add_argument("--cpg", metavar="SUBSTRING",
                       help="Auto-discover scenario from CPG edges matching this substring")
    group.add_argument("--list", action="store_true",
                       help="List available preset domain names and exit")
    args = parser.parse_args()

    if args.list:
        print("Available preset domains (use with --domain <name>):\n")
        for name, (*_, desc) in PRESETS.items():
            print(f"  {name:<25} {desc}")
        return

    print("=" * 70)
    print("SMOKE TEST: clinical_graph_lookup")
    print("=" * 70)

    if args.cpg:
        print(f"\n[AUTO-DISCOVER MODE] CPG substring: '{args.cpg}'")
        result = await autodiscover_scenario(args.cpg)
        if result is None:
            print("\n[FAIL] Could not build a scenario — see warnings above.")
            sys.exit(1)
        patient_meds, candidate_drugs, comorbidities, allergies, desc = result
        flags = await run_scenario(patient_meds, candidate_drugs, comorbidities, allergies, desc)
        gate = "PASS" if len(flags) > 0 else "WARN (0 flags — domain gap or no safety edges for these inputs)"

    elif args.domain:
        name = args.domain.lower()
        if name not in PRESETS:
            print(f"Unknown domain '{name}'. Use --list to see available options.")
            sys.exit(1)
        print(f"\n[PRESET MODE] Domain: '{name}'")
        patient_meds, candidate_drugs, comorbidities, allergies, desc = PRESETS[name]
        flags = await run_scenario(patient_meds, candidate_drugs, comorbidities, allergies, desc)
        gate = "PASS" if len(flags) > 0 else "WARN (0 flags — CPG for this domain may not be ingested yet)"

    else:
        # Default: original AF scenario (backwards-compatible)
        print("\n[DEFAULT MODE] AF/anticoagulation scenario (hardcoded)")
        print("  (Use --domain or --cpg to test other domains)")
        patient_meds, candidate_drugs, comorbidities, allergies, desc = PRESETS["af"]
        flags = await run_scenario(patient_meds, candidate_drugs, comorbidities, allergies, desc)
        gate = "PASS" if len(flags) > 0 else "WARN (0 flags — Atrial-Fibrillation(2012) CPG not yet ingested)"

    await run_empty_guard()

    print("\n" + "=" * 70)
    print(f"RESULT: {gate}")
    print("=" * 70)


asyncio.run(main())
