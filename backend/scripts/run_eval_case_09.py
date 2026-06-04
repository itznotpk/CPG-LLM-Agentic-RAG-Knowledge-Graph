"""Non-interactive runner for EVALUATION_FRAMEWORK_README.md Case 9.

AF + Post-PCI (DES) + T2DM — KG-Sourced DDI Discovery from Free-Text Meds.
Posts the canned case to the live /clinical/plan/stream SSE endpoint,
captures every event + the final TreatmentPlan, and writes both a JSON
trace and a readable Markdown summary under tasks/eval_runs/.

Showcase capability: KG-sourced safety flags (`source="graph"`) — the
clinician volunteers extra meds in prose; the system must surface
warfarin x fluconazole and warfarin x amiodarone interactions from Neo4j.

Usage:
    python scripts/run_eval_case_09.py             # uses http://localhost:8058
    python scripts/run_eval_case_09.py --url http://localhost:8000
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

CASE_9 = {
    "chief_complaint": "Post-PCI day 1. Need full antithrombotic plan and review of current medications.",
    "history": (
        "CC: Post-PCI day 1. Need full antithrombotic plan and review of current medications.\n"
        "HPI: NSTEMI s/p primary PCI with DES yesterday. AF with CHA2DS2-VASc 4. "
        "Amiodarone running since last year for rate control. Fluconazole day 9 of 14 "
        "for oesophageal candidiasis.\n"
        "PE / Labs: INR 2.4 today (no severity slot — recorded here)."
    ),
    "age": 67,
    "sex": "F",
    "comorbidities": [
        "Non-valvular Atrial Fibrillation (CHA2DS2-VASc 4)",
        "NSTEMI status-post primary PCI with Drug-Eluting Stent (yesterday)",
        "Type 2 Diabetes Mellitus",
        "Oesophageal candidiasis",
    ],
    "current_medications": [
        "Warfarin 5mg OD",
        "Amiodarone 200mg OD",
        "Metformin 1g BD",
        "Sitagliptin 100mg OD",
        "Fluconazole 100mg OD",
    ],
    "allergies": [],
    "vitals": {"sbp": 132, "dbp": 78, "hr": 72, "spO2": 97, "weight": 64, "temp": 36.7, "egfr": 64},
    "severity_staging": {"HbA1c": "7.1", "eGFR": "64", "INR": "2.4", "CHA2DS2-VASc": "4"},
}


async def stream_case(url: str) -> tuple[list[dict], dict | None]:
    events: list[dict] = []
    final_result: dict | None = None
    timeout = aiohttp.ClientTimeout(total=900, connect=10)
    headers = {"Connection": "close", "Accept": "text/event-stream"}
    payload = {"case": CASE_9}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{url}/clinical/plan/stream", json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HTTP {resp.status}: {text}")
                sys.exit(1)
            ev_type = None
            # Read raw bytes to avoid aiohttp line-length limits (handles large safety_review JSON)
            buffer = b""
            async for chunk in resp.content.iter_chunked(8192):
                buffer += chunk
                lines = buffer.split(b"\n")
                buffer = lines[-1]
                for line_bytes in lines[:-1]:
                    s = line_bytes.decode("utf-8").strip()
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
            if buffer.strip():
                s = buffer.decode("utf-8").strip()
                if s.startswith("data:") and ev_type:
                    data_str = s[5:].strip()
                    try:
                        data = json.loads(data_str)
                        events.append({"event": ev_type, "data": data})
                        if ev_type == "final_result":
                            final_result = data
                    except json.JSONDecodeError:
                        pass
    return events, final_result


def write_summary(md_path: Path, final: dict) -> None:
    plan = final.get("treatment_plan", {}) or {}
    ddx = final.get("ddx", []) or []
    safety = final.get("safety_report") or {}
    lines: list[str] = []
    lines.append("# Case 9 Run — AF + Post-PCI (DES) + T2DM")
    lines.append("")
    lines.append(f"- Run at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- elapsed_ms: {final.get('elapsed_ms', 0)}")
    lines.append(f"- ICD primary: {plan.get('icd_primary', 'n/a')}")
    lines.append(f"- Confidence: {plan.get('confidence', 0)}")
    lines.append("")
    lines.append("## DDx top 5 (LLM-reranked)")
    for i, d in enumerate(ddx[:5], 1):
        final_score = d.get("final_score")
        sim = d.get("similarity") or d.get("probability") or 0
        math_rank = d.get("math_rank")
        score_str = f"final={final_score:.3f}" if isinstance(final_score, (int, float)) else f"sim={sim:.3f}"
        rank_str = f", math_rank={math_rank}" if math_rank else ""
        lines.append(f"{i}. {d.get('code','')} — {d.get('title','')} ({score_str}{rank_str})")
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
    llm_count = 0
    graph_count = 0
    for f in (safety.get("flags") or []):
        title = f.get('title') or f.get('flag_type', '?')
        detail = f.get('detail') or f.get('issue', '')
        severity = f.get('severity', '?')
        source = f.get('source', '?')
        if source == "llm":
            llm_count += 1
        elif source == "graph":
            graph_count += 1
        lines.append(f"- [{severity}/{source}] {title}")
        if detail:
            lines.append(f"  {detail}")
    lines.append("")
    lines.append(f"- safe_to_proceed: {safety.get('safe_to_proceed')}")
    lines.append(f"- flag source counts: llm={llm_count}, graph={graph_count}")
    lines.append("")
    lines.append("## Unresolved")
    for u in plan.get("unresolved_questions", []) or []:
        lines.append(f"- {u}")
    audit = plan.get("gate_audit", []) or []
    if audit:
        lines.append("")
        lines.append("## Gate audit (ruled out)")
        for a in audit:
            lines.append(f"- {a}")
    md_path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8058")
    args = parser.parse_args()
    url = args.url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = OUT_DIR / f"case09_{stamp}_trace.json"
    summary_path = OUT_DIR / f"case09_{stamp}_summary.md"

    t0 = time.monotonic()
    events, final = await stream_case(url)
    elapsed = time.monotonic() - t0

    trace_path.write_text(
        json.dumps({"case": CASE_9, "events": events, "final": final}, indent=2),
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
