"""DEMO-003 — pregnancy with rheumatic mitral stenosis + arrhythmia.

Exercises the clinician-broadened Heart-Disease-in-Pregnancy scope
(valvular BB60-BB6Z + supraventricular arrhythmia) and the sex-aware
CPG filter (must route despite pregnancy code being female-only).

Usage: python scripts/run_demo_003_pregnancy_heart.py [--url http://localhost:8058]
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
        "Progressive exertional dyspnoea (NYHA III), orthopnoea, and "
        "intermittent palpitations at 28 weeks gestation. One presyncopal "
        "episode climbing stairs yesterday."
    ),
    "history": (
        "32F G2P1 at 28+3 weeks gestation with known rheumatic mitral "
        "stenosis (childhood rheumatic fever, valve area 1.2 cm² on "
        "pre-pregnancy echo, mean gradient 8 mmHg). First pregnancy "
        "uneventful 4 years ago when MS was mild. Now with worsening "
        "dyspnoea since 24 weeks and new paroxysmal atrial fibrillation "
        "captured on Holter (rate 130–150 during episodes, 2–4 hours, "
        "self-terminating). No prior thromboembolism. Echo today: MV area "
        "1.0 cm², mean gradient 14 mmHg, mild pulmonary hypertension "
        "(PASP 48 mmHg), LA dilated, preserved LV function."
    ),
    "age": 32,
    "sex": "F",
    "comorbidities": [
        "Rheumatic mitral stenosis (moderate-severe in pregnancy)",
        "Paroxysmal atrial fibrillation (new in pregnancy)",
        "Pulmonary hypertension (mild, secondary)",
        "Pregnancy 28+3 weeks (G2P1)",
        "Iron-deficiency anaemia",
    ],
    "current_medications": [
        "Bisoprolol 2.5 mg OD (started 24 weeks for HR control)",
        "Folic acid 5 mg OD",
        "Ferrous sulphate 200 mg BD",
        "Pregnancy multivitamin OD",
    ],
    "allergies": ["NKDA"],
    "vitals": {
        "sbp": 118, "dbp": 72, "hr": 96, "spo2": 96, "rr": 22, "temp": 36.6,
    },
    "severity_staging": {
        "NYHA": "III",
        "gestational_age": "28+3 weeks",
        "WHO_mWHO_class": "III–IV",
        "MV_area_cm2": "1.0",
        "MV_mean_gradient_mmHg": "14",
        "PASP_mmHg": "48",
    },
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8058")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print(f"{Colors.CYAN}Running DEMO-003 (pregnancy + valvular heart disease) against {url}{Colors.END}\n")
    result = await run_stream(url, "/clinical/plan/stream", {"case": DEMO_CASE})
    if result:
        print_care_plan(result)
    else:
        print(f"{Colors.RED}No final_result returned.{Colors.END}")


if __name__ == "__main__":
    asyncio.run(main())
