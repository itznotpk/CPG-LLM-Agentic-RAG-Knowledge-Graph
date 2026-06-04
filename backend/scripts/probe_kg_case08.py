"""KG probe for Case 8 — is the Stage 6 KG verifier blank because of drug-name
parsing or because the KG genuinely lacks the sulfonylurea/HF + metformin/eGFR
edges?

Replays the same calls the Stage 6 verifier makes:
  1. match_plan_drugs(<verbose plan interventions>)  -> normalised drug map
  2. clinical_graph_lookup(...)                       -> KG flags

Reports both intermediate and final results so we know which layer failed.

Usage:
    python scripts/probe_kg_case08.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from agent.graph_clinical import (  # noqa: E402
    clinical_graph_lookup,
    match_plan_drugs,
)

PLAN_INTERVENTIONS_VERBOSE = [
    "Initiate an ACE inhibitor (e.g. ramipril, perindopril, or enalapril) at low dose, uptitrating to maximum tolerated dose",
    "ARNI (sacubitril/valsartan) may be considered as a first-line RAS blocker in ACE-I-naive patients",
    "Initiate a beta-blocker (carvedilol, bisoprolol, or metoprolol succinate) at low dose, uptitrating to maximum tolerated dose",
    "Add SGLT2 inhibitor (dapagliflozin or empagliflozin)",
    "Continue metformin 1g BD",
    "Review gliclazide MR 60mg OD",
    "Consider GLP-1 receptor agonist with proven CV benefit (e.g. liraglutide, semaglutide, dulaglutide) if glycaemic targets not met after SGLT2-i addition",
]

PATIENT_MEDS = ["Metformin 1g BD", "Gliclazide MR 60mg OD"]
COMORBIDITIES = ["Type 2 Diabetes Mellitus", "Obesity (BMI 34)", "HFrEF (LVEF 25%)"]
PATIENT_PARAMS = {"egfr": 58, "sbp": 128, "dbp": 76}


async def main() -> int:
    print("=== Step 1: match_plan_drugs against verbose interventions ===")
    drug_idx_map = await match_plan_drugs(PLAN_INTERVENTIONS_VERBOSE)
    print(f"  matched {len(drug_idx_map)} drug(s)")
    for k, v in drug_idx_map.items():
        print(f"    {k!r:30s} -> intervention idx {v}")

    if not drug_idx_map:
        print("\n[CONCLUSION] match_plan_drugs returned EMPTY.")
        print("  -> Stage 6 KG verifier short-circuits here. Root cause: drug-name")
        print("     parsing cannot extract canonical drug names from verbose plan text.")
        return 0

    print("\n=== Step 2: clinical_graph_lookup with matched drugs ===")
    candidate_drugs = list(drug_idx_map.keys())
    flags = await clinical_graph_lookup(
        patient_meds=PATIENT_MEDS,
        candidate_drugs=candidate_drugs,
        comorbidities=COMORBIDITIES,
        allergies=[],
        patient_params=PATIENT_PARAMS,
    )
    print(f"  {len(flags)} KG flag(s) returned")
    for f in flags:
        print(f"    [{f.flag_type}/{f.severity}] {f.subject} --{f.relation}--> {f.object}")
        if f.evidence:
            print(f"        evidence: {f.evidence[:120]}")
        if f.threshold_param:
            print(f"        threshold: {f.threshold_param} {f.threshold_op} {f.threshold_value} breach={f.threshold_breach}")

    print("\n=== Step 3: Targeted probe — sulfonylurea+HF edge check ===")
    # Force-feed canonical names and see if the KG has the edge.
    canonical_flags = await clinical_graph_lookup(
        patient_meds=["gliclazide"],
        candidate_drugs=["gliclazide", "metformin"],
        comorbidities=["heart failure", "HFrEF"],
        allergies=[],
        patient_params=PATIENT_PARAMS,
    )
    print(f"  {len(canonical_flags)} flag(s) with canonical names")
    for f in canonical_flags:
        print(f"    [{f.flag_type}/{f.severity}] {f.subject} --{f.relation}--> {f.object}")

    print("\n[CONCLUSION]")
    if not flags and not canonical_flags:
        print("  KG genuinely lacks sulfonylurea-in-HF and metformin/eGFR-monitoring edges.")
        print("  Fix: add Cypher upsert for (:Drug{name:'gliclazide'})-[:CONTRAINDICATED_WITH]->(:Condition{name:'heart failure'})")
        print("       and similar for the metformin eGFR monitoring rule.")
    elif not flags and canonical_flags:
        print("  Drug-name parsing fails on verbose plan interventions but KG has the edges.")
        print("  Fix: tighten match_plan_drugs() to extract canonical drug names from verbose strings.")
    elif flags:
        print("  KG verifier returned flags here but produced 0 in the actual run — investigate")
        print("  _kg_flag_to_safety filtering (e.g. MONITORING flags are dropped by _KG_FLAG_TYPE_MAP).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
