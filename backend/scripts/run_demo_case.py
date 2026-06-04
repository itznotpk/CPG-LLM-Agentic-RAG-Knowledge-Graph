"""Run the multimorbid-ACS demo case end-to-end against the live API.

Usage: python scripts/run_demo_case.py [--url http://localhost:8058]
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
        "Central chest tightness for 2 hours, radiating to left jaw, with "
        "diaphoresis and mild breathlessness. Onset at rest."
    ),
    "history": (
        "68M with longstanding T2DM (12y, HbA1c 8.4%), HTN, dyslipidaemia, "
        "permanent AF (CHA2DS2-VASc 4), prior PCI to LAD (2021) for stable "
        "CAD, HFrEF (LVEF 38%, NYHA II), CKD stage 3b (eGFR 38). Ex-smoker "
        "30 pack-years. Elective dental extraction planned in 7 days."
    ),
    "age": 68,
    "sex": "M",
    "comorbidities": [
        "Type 2 Diabetes Mellitus",
        "Hypertension",
        "Dyslipidaemia",
        "Permanent Atrial Fibrillation",
        "Stable Coronary Artery Disease",
        "Heart Failure with reduced ejection fraction",
        "Chronic Kidney Disease stage 3b",
        "Obesity class II",
    ],
    "current_medications": [
        "Metformin 1 g BD",
        "Empagliflozin 10 mg OD",
        "Atorvastatin 40 mg ON",
        "Bisoprolol 5 mg OD",
        "Perindopril 4 mg OD",
        "Apixaban 5 mg BD",
        "Furosemide 40 mg OD",
        "Sildenafil 50 mg PRN",
        "Aspirin 100 mg OD",
    ],
    "allergies": ["Penicillin (rash)"],
    "vitals": {
        "sbp": 158, "dbp": 96, "hr": 104, "spo2": 94, "rr": 22, "temp": 36.8,
    },
    "severity_staging": {
        "NYHA": "II",
        "LVEF": "38%",
        "CKD_stage": "3b",
        "eGFR": "38",
        "HbA1c": "8.4%",
        "CHA2DS2_VASc": "4",
        "BMI": "32.6",
    },
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8058")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print(f"{Colors.CYAN}Running DEMO-001 (multimorbid ACS) against {url}{Colors.END}\n")
    result = await run_stream(url, "/clinical/plan/stream", {"case": DEMO_CASE})
    if result:
        print_care_plan(result)
    else:
        print(f"{Colors.RED}No final_result returned.{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
