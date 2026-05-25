"""DEMO-004 — T2DM with proliferative diabetic retinopathy (9B71.0).

Exercises the newly ingested ICD-11 chapter 09 (visual system) and the
clinician-broadened T2DM scope that now includes 9B71.0.

Usage: python scripts/run_demo_004_diabetic_retinopathy.py [--url http://localhost:8058]
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
        "Sudden floaters and blurred vision in the right eye for 2 days, "
        "with reduced visual acuity (counting fingers at 2 m). No pain. "
        "Background of poorly controlled T2DM."
    ),
    "history": (
        "60M with 18-year history of T2DM (HbA1c 9.8%, never on insulin), "
        "hypertension, dyslipidaemia, and stage 3a CKD (eGFR 52). Last "
        "diabetic eye screening 3 years ago — flagged as moderate non-"
        "proliferative retinopathy, lost to follow-up. Ophthalmology today: "
        "vitreous haemorrhage right eye on a background of proliferative "
        "diabetic retinopathy bilaterally with neovascularisation of the "
        "disc and elsewhere; macular oedema present. Albumin:creatinine "
        "ratio 78 mg/mmol. Foot exam shows reduced monofilament sensation."
    ),
    "age": 60,
    "sex": "M",
    "comorbidities": [
        "Type 2 Diabetes Mellitus (poorly controlled, 18y)",
        "Proliferative diabetic retinopathy with vitreous haemorrhage",
        "Diabetic macular oedema",
        "Diabetic nephropathy (CKD stage 3a, ACR 78)",
        "Diabetic peripheral neuropathy",
        "Hypertension",
        "Dyslipidaemia",
    ],
    "current_medications": [
        "Metformin 1 g BD",
        "Gliclazide MR 60 mg OD",
        "Perindopril 8 mg OD",
        "Amlodipine 10 mg OD",
        "Atorvastatin 40 mg ON",
        "Aspirin 100 mg OD",
    ],
    "allergies": ["NKDA"],
    "vitals": {
        "sbp": 152, "dbp": 88, "hr": 78, "spo2": 98, "rr": 16, "temp": 36.5,
    },
    "severity_staging": {
        "HbA1c": "9.8%",
        "eGFR": "52",
        "ACR_mg_per_mmol": "78",
        "retinopathy_grade": "Proliferative (bilateral) + macular oedema",
        "visual_acuity_R": "CF @ 2 m",
        "visual_acuity_L": "6/12",
    },
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8058")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print(f"{Colors.CYAN}Running DEMO-004 (T2DM + proliferative diabetic retinopathy) against {url}{Colors.END}\n")
    result = await run_stream(url, "/clinical/plan/stream", {"case": DEMO_CASE})
    if result:
        print_care_plan(result)
    else:
        print(f"{Colors.RED}No final_result returned.{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
