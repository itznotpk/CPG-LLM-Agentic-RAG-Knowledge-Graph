"""Non-interactive runner for EVALUATION_FRAMEWORK_README.md Case 8.

T2DM + HFrEF + Obesity (Metabolic Heart Failure). Posts the canned case to
the live /clinical/plan/stream SSE endpoint, captures every event + the final
TreatmentPlan, and writes both a JSON trace and a readable Markdown summary
under tasks/eval_runs/.

Usage:
    python scripts/run_eval_case_08.py             # uses http://localhost:8058
    python scripts/run_eval_case_08.py --url http://localhost:8000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tasks" / "eval_runs"

CASE_8 = {
    "chief_complaint": "Newly diagnosed HFrEF (LVEF 25%) in obese T2DM patient on metformin + gliclazide.",
    "history": (
        "62-year-old male, BMI 34 (obese), Type 2 Diabetes (HbA1c 8.4%) on Metformin 1g BD "
        "and Gliclazide MR 60mg OD, newly diagnosed Heart Failure with reduced Ejection "
        "Fraction (HFrEF, LVEF 25%). Clinically stable and euvolemic. Asking what medication "
        "changes are required and how to adjust the anti-diabetic regimen."
    ),
    "age": 62,
    "sex": "M",
    "comorbidities": ["Type 2 Diabetes Mellitus", "Obesity (BMI 34)", "HFrEF (LVEF 25%)"],
    "current_medications": ["Metformin 1g BD", "Gliclazide MR 60mg OD"],
    "allergies": [],
    "vitals": {"sbp": 128, "dbp": 76, "egfr": 58},
}


async def stream_case(url: str) -> tuple[list[dict], dict | None]:
    events: list[dict] = []
    final_result: dict | None = None
    timeout = aiohttp.ClientTimeout(total=900, connect=10)
    headers = {"Connection": "close", "Accept": "text/event-stream"}
    payload = {"case": CASE_8}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{url}/clinical/plan/stream", json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HTTP {resp.status}: {text}")
                sys.exit(1)
            ev_type = None
            async for line in resp.content:
                s = line.decode("utf-8").strip()
                if not s:
                    continue
                if s.startswith("event:"):
                    ev_type = s[6:].strip()
                elif s.startswith("data:") and ev_type:
                    data_str = s[5:].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        ev_type = None
                        continue
                    events.append({"event": ev_type, "data": data})
                    if ev_type == "stage_update":
                        status = data.get("status")
                        stage = data.get("stage")
                        name = data.get("name", "")
                        if status == "running":
                            print(f"[Stage {stage}] {name} >>")
                        elif status == "complete":
                            print(f"[Stage {stage}] {name} OK")
                        elif status == "error":
                            print(f"[Stage {stage}] {name} ERR")
                    elif ev_type == "sub_step":
                        print(f"  -> {data.get('detail','')}")
                    elif ev_type == "final_result":
                        final_result = data
                    elif ev_type == "error":
                        print(f"ERROR: {data}")
                    elif ev_type == "done":
                        ev_type = None
                        break
                    ev_type = None
    return events, final_result


def write_summary(md_path: Path, final: dict) -> None:
    plan = final.get("treatment_plan", {}) or {}
    ddx = final.get("ddx", []) or []
    safety = final.get("safety_report") or {}
    lines: list[str] = []
    lines.append("# Case 8 Run — T2DM + HFrEF + Obesity")
    lines.append("")
    lines.append(f"- Run at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- elapsed_ms: {final.get('elapsed_ms', 0)}")
    lines.append(f"- ICD primary: {plan.get('icd_primary', 'n/a')}")
    lines.append(f"- Confidence: {plan.get('confidence', 0)}")
    lines.append("")
    lines.append("## DDx top 5")
    for i, d in enumerate(ddx[:5], 1):
        sim = d.get("similarity") or d.get("probability") or 0
        lines.append(f"{i}. {d.get('code','')} — {d.get('title','')} ({sim:.3f})")
    lines.append("")
    lines.append("## Summary")
    lines.append(plan.get("summary", "(none)"))
    lines.append("")
    lines.append("## Recommendations")
    for r in plan.get("recommendations", []) or []:
        action = (r.get("action") or "?").upper()
        lines.append(
            f"- [{action}] {r.get('intervention','')} — "
            f"{r.get('rationale','')} (src: {r.get('cpg_source','')}, grade: {r.get('evidence_grade','')})"
        )
    lines.append("")
    lines.append("## Monitoring")
    for m in plan.get("monitoring", []) or []:
        if isinstance(m, dict):
            lines.append(f"- {m.get('parameter','?')}: {m.get('schedule','')} target={m.get('target','')}")
        else:
            lines.append(f"- {m}")
    lines.append("")
    lines.append("## Safety Flags")
    for f in (safety.get("flags") or []):
        lines.append(
            f"- [{f.get('severity','?')}/{f.get('source','?')}] {f.get('issue','')}"
        )
    lines.append(f"- safe_to_proceed: {safety.get('safe_to_proceed')}")
    lines.append("")
    lines.append("## Unresolved")
    for u in plan.get("unresolved_questions", []) or []:
        lines.append(f"- {u}")
    md_path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8058")
    args = parser.parse_args()
    url = args.url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = OUT_DIR / f"case08_{stamp}_trace.json"
    summary_path = OUT_DIR / f"case08_{stamp}_summary.md"

    t0 = time.monotonic()
    events, final = await stream_case(url)
    elapsed = time.monotonic() - t0

    trace_path.write_text(
        json.dumps({"case": CASE_8, "events": events, "final": final}, indent=2),
        encoding="utf-8",
    )
    if final:
        write_summary(summary_path, final)
        print(f"\nWrote {summary_path}")
    print(f"Wrote {trace_path}")
    print(f"Total wall time: {elapsed:.1f}s")
    return 0 if final else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
