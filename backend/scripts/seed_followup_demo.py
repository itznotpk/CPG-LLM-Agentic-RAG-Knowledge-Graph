"""Idempotent demo seed for the follow-up ecosystem rehearsal.

Ensures a demo patient + a finalized consultation with a treatment_plan exist,
then prints the enroll curl. Run with the backend up.

Usage: python backend/scripts/seed_followup_demo.py [--url http://localhost:8058]
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DEMO_NRIC = "990101-14-1234"
DEMO_PLAN = {
    "summary": "HFrEF optimisation: start bisoprolol, daily weights, review 2 weeks.",
    "recommendations": [
        {"intervention": "[START] Bisoprolol 2.5 mg OD", "recommendation_type": "pharmacological", "action": "start"},
    ],
    "monitoring": [{"parameter": "daily weight", "schedule": "daily for 2 weeks"}],
    "follow_up": [{"when": "2 weeks", "what": "symptom + weight review"}],
    "safety_netting": ["Worsening breathlessness at rest", "Ankle swelling", "Weight gain >2 kg in 3 days"],
}


async def main():
    conn = await asyncpg.connect(os.environ["SUPABASE_DB_URL"])
    try:
        await conn.execute(
            """INSERT INTO patients (nric, full_name, date_of_birth, gender)
               VALUES ($1, 'Demo Ahmad bin Ali', '1999-01-01', 'male')
               ON CONFLICT (nric) DO NOTHING""",
            DEMO_NRIC,
        )
        row = await conn.fetchrow(
            "SELECT id FROM consultations WHERE patient_nric = $1 ORDER BY id DESC LIMIT 1", DEMO_NRIC
        )
        if row:
            cid = row["id"]
            await conn.execute(
                "UPDATE consultations SET treatment_plan = $2 WHERE id = $1",
                cid, json.dumps(DEMO_PLAN),
            )
        else:
            cid = (await conn.fetchrow(
                """INSERT INTO consultations (patient_nric, treatment_plan)
                   VALUES ($1, $2) RETURNING id""",
                DEMO_NRIC, json.dumps(DEMO_PLAN),
            ))["id"]
        print(f"Demo consultation id: {cid}")
        print(f'Enroll: curl -X POST http://localhost:8058/followup/enroll '
              f'-H "Content-Type: application/json" '
              f'-d "{{\\"consultation_id\\": {cid}, \\"patient_nric\\": \\"{DEMO_NRIC}\\"}}"')
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
