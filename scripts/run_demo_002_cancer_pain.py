"""DEMO-002 — metastatic breast cancer with opioid-refractory bone pain.

Exercises the clinician-broadened Cancer-Pain scope (chapter 02 + MG30.1).

Usage: python scripts/run_demo_002_cancer_pain.py [--url http://localhost:8058]
"""
import argparse
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical_cli import run_stream, print_care_plan, Colors

DEMO_CASE = {
    "chief_complaint": (
        "Severe progressive lower-back and right-hip bone pain for 3 weeks, "
        "now opioid-refractory at oral morphine 120 mg/day equivalent, with "
        "breakthrough pain on weight-bearing and overnight."
    ),
    "history": (
        "55F with ER+/PR+/HER2- invasive ductal carcinoma of right breast "
        "diagnosed 2023, treated with lumpectomy + adjuvant chemoradiotherapy "
        "+ tamoxifen. Restaging 2025 confirmed multifocal osteolytic bone "
        "metastases (lumbar spine, pelvis, right femur). Currently on letrozole "
        "+ palbociclib + monthly denosumab. Pain previously controlled on "
        "oxycodone PRN; escalated to MS Contin 60 mg BD + breakthrough morphine "
        "with inadequate relief over the past month. No bowel/bladder dysfunction. "
        "No new neurological deficit. ECOG 2."
    ),
    "age": 55,
    "sex": "F",
    "comorbidities": [
        "Metastatic breast carcinoma (bone-dominant)",
        "Hypertension",
        "Osteopenia",
        "Anxiety",
    ],
    "current_medications": [
        "Letrozole 2.5 mg OD",
        "Palbociclib 125 mg OD (3 weeks on / 1 week off)",
        "Denosumab 120 mg SC monthly",
        "MS Contin 60 mg BD",
        "Morphine IR 10 mg PRN (q4h breakthrough)",
        "Paracetamol 1 g QID",
        "Pregabalin 75 mg BD",
        "Pantoprazole 40 mg OD",
        "Lorazepam 0.5 mg PRN",
    ],
    "allergies": ["NKDA"],
    "vitals": {
        "sbp": 138, "dbp": 82, "hr": 92, "spo2": 98, "rr": 18, "temp": 36.7,
    },
    "severity_staging": {
        "ECOG": "2",
        "pain_NRS": "8/10 at rest, 10/10 on movement",
        "stage": "IV (bone-dominant metastatic)",
        "ER": "positive",
        "HER2": "negative",
    },
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8058")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print(f"{Colors.CYAN}Running DEMO-002 (cancer pain) against {url}{Colors.END}\n")
    result = await run_stream(url, "/clinical/plan/stream", {"case": DEMO_CASE})
    if result:
        print_care_plan(result)
    else:
        print(f"{Colors.RED}No final_result returned.{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
