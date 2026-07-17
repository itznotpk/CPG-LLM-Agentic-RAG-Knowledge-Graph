"""Idempotent demo seed for the follow-up ecosystem rehearsal.

Ensures a demo patient + a finalized consultation with a care plan exist,
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

# The plan is stored section-by-section — there is no consultations.treatment_plan
# column. Shapes here must match what the UI persists, since bot_poller.load_plan
# reconstructs the plan dict from exactly these columns.
DEMO_SUMMARY = "HFrEF optimisation: start bisoprolol, daily weights, review 2 weeks."
DEMO_MEDS = {
    "start": [{"id": 1, "name": "Bisoprolol", "dose": "2.5 mg OD, titrate to target 10 mg OD",
               "reason": "Beta-blockers improve survival in HFrEF", "accepted": True}],
    "stop": [],
    "continue": [],
}
DEMO_MONITORING = [
    {"id": 1, "parameter": "Daily weight", "schedule": "daily for 2 weeks",
     "target": "report gain >2 kg in 3 days"},
    {"id": 2, "parameter": "Breathlessness at rest", "schedule": "daily",
     "target": "any worsening to be reported"},
]
DEMO_LIFESTYLE = [{"id": 1, "goal": "Sodium restriction <2 g/day", "accepted": True}]


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
                """UPDATE consultations
                      SET care_plan_summary = $2, medication_recommendations = $3,
                          monitoring = $4, lifestyle_goals = $5
                    WHERE id = $1""",
                cid, DEMO_SUMMARY, json.dumps(DEMO_MEDS),
                json.dumps(DEMO_MONITORING), json.dumps(DEMO_LIFESTYLE),
            )
        else:
            cid = (await conn.fetchrow(
                """INSERT INTO consultations
                     (patient_nric, care_plan_summary, medication_recommendations,
                      monitoring, lifestyle_goals)
                   VALUES ($1, $2, $3, $4, $5) RETURNING id""",
                DEMO_NRIC, DEMO_SUMMARY, json.dumps(DEMO_MEDS),
                json.dumps(DEMO_MONITORING), json.dumps(DEMO_LIFESTYLE),
            ))["id"]
        print(f"Demo consultation id: {cid}")
        print(f'Enroll: curl -X POST http://localhost:8058/followup/enroll '
              f'-H "Content-Type: application/json" '
              f'-d "{{\\"consultation_id\\": {cid}, \\"patient_nric\\": \\"{DEMO_NRIC}\\"}}"')
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
