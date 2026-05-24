"""
Phase E sign-off: drive the 3 Gap_KG_Rebuild_Plan fixture cases directly
through clinical_graph_lookup and report whether each yields a non-empty
flag with a citation (cpg_chunk_id) — the pass criterion the plan defines.

Run: venv\\Scripts\\python.exe scratch\\phase_e_fixtures.py
"""
import sys, io, asyncio, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph_clinical import clinical_graph_lookup, ClinicalFlag


FIXTURES = [
    {
        "name": "1. RAAS double-block",
        "patient_meds": ["amlodipine", "lisinopril"],
        "candidate_drugs": ["ramipril"],
        "comorbidities": ["hypertension"],
        "allergies": [],
        "expected": "INTERACTION",
    },
    {
        "name": "2. Spironolactone + CKD eGFR<25",
        "patient_meds": [],
        "candidate_drugs": ["spironolactone"],
        "comorbidities": ["chronic kidney disease", "hypertension"],
        "allergies": [],
        "expected": "DOSE_ADJUSTMENT or CONTRAINDICATION",
    },
    {
        "name": "3. HCTZ + sulfa allergy",
        "patient_meds": [],
        "candidate_drugs": ["hydrochlorothiazide"],
        "comorbidities": ["hypertension"],
        "allergies": ["sulfa", "sulfonamide"],
        "expected": "ALLERGY_CROSS",
    },
]


def summarise_flag(f: ClinicalFlag) -> str:
    cite = f.cpg_chunk_id or "(no citation!)"
    sev = f"[{f.severity}]" if f.severity else ""
    ev = (f.evidence or "")[:120].replace("\n", " ")
    return f"    - {f.flag_type}{sev} {f.subject} ↔ {f.object}\n      src={f.source_document} chunk={cite}\n      ev=\"{ev}…\""


async def main():
    print("=" * 72)
    print("PHASE E FIXTURES — KG Lookup Sign-Off")
    print("=" * 72)
    results = []
    for fx in FIXTURES:
        print(f"\n{fx['name']}")
        print(f"  meds={fx['patient_meds']}  candidates={fx['candidate_drugs']}")
        print(f"  comorb={fx['comorbidities']}  allergies={fx['allergies']}")
        print(f"  expected: {fx['expected']}")
        flags = await clinical_graph_lookup(
            patient_meds=fx["patient_meds"],
            candidate_drugs=fx["candidate_drugs"],
            comorbidities=fx["comorbidities"],
            allergies=fx["allergies"],
        )
        non_empty = len(flags) > 0
        with_citation = any(f.cpg_chunk_id for f in flags)
        print(f"  → {len(flags)} flag(s) returned; citation present: {with_citation}")
        for f in flags[:5]:
            print(summarise_flag(f))
        results.append({
            "name": fx["name"],
            "expected": fx["expected"],
            "flags": len(flags),
            "with_citation": with_citation,
            "pass": non_empty and with_citation,
        })

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    passed = sum(1 for r in results if r["pass"])
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"  [{mark}] {r['name']:40s} flags={r['flags']} cite={r['with_citation']}")
    print(f"\n  {passed}/{len(results)} fixtures pass")


if __name__ == "__main__":
    asyncio.run(main())
