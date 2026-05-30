"""Non-interactive runner for EVALUATION_FRAMEWORK_README.md Case 12.

Full Metabolic Syndrome — newly diagnosed T2DM + HTN + Dyslipidaemia + Obesity
Class II in a 46M (Malay) presenting for comprehensive health screening. Tests
**multi-CPG priority-ordering** across 5 Malaysian CPGs (Obesity 2023, T2DM 6th,
Dyslipidaemia 6th, Hypertension 5th, Primary-Secondary CVD Prevention 2017),
**refuse-to-compute** on the patient's own sub-questions (CVD risk %, bariatric
remission %), and correct deferral to bariatric MDT with the Asian referral
threshold cited.

Posts the canned case to the live /clinical/plan/stream SSE endpoint, captures
every event + the final TreatmentPlan, and writes both a JSON trace and a
readable Markdown summary under tasks/eval_runs/.

Usage:
    python scripts/run_eval_case_12.py             # uses http://localhost:8058
    python scripts/run_eval_case_12.py --url http://localhost:8000
    python scripts/run_eval_case_12.py --dry-run   # validate payload only, no HTTP
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

CASE_12 = {
    "chief_complaint": (
        "Comprehensive health screening. Multiple risk factors identified at this visit. "
        "Patient asking about CVD risk and whether bariatric surgery would cure his diabetes."
    ),
    "history": (
        "CC: Comprehensive health screening. Multiple risk factors identified at this visit.\n"
        "    Patient asking about CVD risk and whether bariatric surgery would cure his diabetes.\n"
        "HPI: Malay ethnicity. Non-smoker, occasional alcohol, sedentary office worker.\n"
        "      BP 148/94 confirmed on 2 separate visits. BMI 38.5 (height not measured at this visit).\n"
        "PE / Labs: HbA1c 9.2%, LDL 4.4 mmol/L, HDL 0.9, TG 2.4, eGFR 82, UACR 8 mg/g,\n"
        "      fasting glucose 9.8 mmol/L."
    ),
    "age": 46,
    "sex": "M",
    "comorbidities": [
        "Type 2 Diabetes Mellitus (newly diagnosed)",
        "Hypertension (newly confirmed)",
        "Dyslipidaemia (newly noted)",
        "Obesity Class II",
    ],
    "current_medications": [],
    "allergies": [],
    "vitals": {
        "sbp": 148,
        "dbp": 94,
        "hr": 78,
        "spO2": 98,
        "weight": 112,
        "temp": 36.7,
        # BMI 38.5 stated in the vignette; height not measured, so BMI is recorded
        # directly rather than derived from weight/height in the workflow.
        "bmi": 38.5,
    },
    "severity_staging": {
        "HbA1c": "9.2",
        "eGFR": "82",
    },
}


async def stream_case(url: str) -> tuple[list[dict], dict | None]:
    events: list[dict] = []
    final_result: dict | None = None
    timeout = aiohttp.ClientTimeout(total=900, connect=10)
    headers = {"Connection": "close", "Accept": "text/event-stream"}
    payload = {"case": CASE_12}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{url}/clinical/plan/stream", json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HTTP {resp.status}: {text}")
                sys.exit(1)
            ev_type = None
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
    cpgs_matched = final.get("cpgs_matched", []) or []
    lines: list[str] = []
    lines.append("# Case 12 Run — Full Metabolic Syndrome (multi-CPG reconciliation)")
    lines.append("")
    lines.append(f"- Run at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- elapsed_ms: {final.get('elapsed_ms', 0)}")
    lines.append(f"- ICD primary: {plan.get('icd_primary', 'n/a')}")
    lines.append(f"- Confidence: {plan.get('confidence', 0)}")
    lines.append("")
    lines.append("## CPGs matched")
    if cpgs_matched:
        for name in cpgs_matched:
            lines.append(f"- {name}")
    else:
        lines.append("- (none reported)")
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
    lines.append("## Red flags")
    for rf in plan.get("red_flags", []) or []:
        lines.append(f"- {rf}")
    lines.append("")
    lines.append("## Safety Flags")
    for f in (safety.get("flags") or []):
        title = f.get('title') or f.get('flag_type', '?')
        detail = f.get('detail') or f.get('issue', '')
        severity = f.get('severity', '?')
        source = f.get('source', '?')
        lines.append(f"- [{severity}/{source}] {title}")
        if detail:
            lines.append(f"  {detail}")
    lines.append(f"- safe_to_proceed: {safety.get('safe_to_proceed')}")
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


def dry_run() -> int:
    """Validate the payload without hitting the network. Lists the expected
    multi-CPG / refuse-to-compute behaviours from EVALUATION_FRAMEWORK_README
    §Case 12 so a reviewer can confirm the case is wired correctly before
    pointing it at a live server."""
    print("Case 12 -- Full Metabolic Syndrome  (DRY RUN)")
    print("=" * 64)
    print("Endpoint that would be called: POST /clinical/plan/stream")
    print()
    print("Payload (case):")
    print(json.dumps({"case": CASE_12}, indent=2, ensure_ascii=False))
    print()
    print("Expected multi-CPG / refusal behaviours (per EVALUATION_FRAMEWORK_README):")
    print("  1. Cite all 5 CPGs explicitly:")
    print("       - Obesity Management (2023)")
    print("       - T2DM (6th Edition)")
    print("       - Dyslipidaemia (6th Edition)")
    print("       - Hypertension (5th Edition)")
    print("       - Primary-Secondary CVD Prevention (2017)")
    print("  2. Priority-ordered plan: lifestyle -> anti-diabetic (GLP-1 RA")
    print("     dual-indication +/- SGLT2i + metformin) -> high-intensity statin")
    print("     -> ACE-I/ARB for HTN -> bariatric referral.")
    print("  3. REFUSE to compute a CVD risk percentage (system retrieves CPG")
    print("     risk thresholds, does not calculate Framingham/SCORE itself).")
    print("  4. REFUSE to quote a single bariatric T2DM remission percentage")
    print("     (defer prognosis to bariatric MDT).")
    print("  5. Bariatric referral threshold cited: Asian BMI >= 37.5 + >= 1")
    print("     comorbidity (patient BMI 38.5 with T2DM + HTN + dyslipidaemia).")
    print("  6. Continuing-plan note: start statin + ACE-I + metformin +")
    print("     GLP-1 RA WHILE awaiting bariatric review (no pharmacotherapy delay).")
    print()
    print("Quick sanity checks on the payload:")
    print(f"  - chief_complaint mentions screening/CVD/bariatric: "
          f"{'screening' in CASE_12['chief_complaint'].lower() and 'bariatric' in CASE_12['chief_complaint'].lower()}")
    print(f"  - 4 comorbidities present:    {len(CASE_12['comorbidities']) == 4}")
    print(f"  - drug-naive (no current meds): {len(CASE_12['current_medications']) == 0}")
    print(f"  - BP hypertensive:             sbp={CASE_12['vitals']['sbp']} dbp={CASE_12['vitals']['dbp']}")
    print(f"  - BMI in obesity range:        bmi={CASE_12['vitals']['bmi']}")
    print(f"  - HbA1c above target:          HbA1c={CASE_12['severity_staging']['HbA1c']}")
    print(f"  - eGFR staged:                 eGFR={CASE_12['severity_staging']['eGFR']}")
    print()
    print("OK -- payload is well-formed. Re-run without --dry-run against a live")
    print("server to actually execute the pipeline.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8058")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the payload and print expected behaviours without hitting the server",
    )
    args = parser.parse_args()

    if args.dry_run:
        return dry_run()

    url = args.url.rstrip("/")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = OUT_DIR / f"case12_{stamp}_trace.json"
    summary_path = OUT_DIR / f"case12_{stamp}_summary.md"

    t0 = time.monotonic()
    events, final = await stream_case(url)
    elapsed = time.monotonic() - t0

    trace_path.write_text(
        json.dumps({"case": CASE_12, "events": events, "final": final}, indent=2),
        encoding="utf-8",
    )
    if final:
        write_summary(summary_path, final)
        print(f"\nWrote {summary_path}")
    print(f"Wrote {trace_path}")
    print(f"Total wall time: {elapsed:.1f}s")
    return 0 if final else 1


def _entry() -> int:
    args_peek = sys.argv[1:]
    if "--dry-run" in args_peek:
        parser = argparse.ArgumentParser()
        parser.add_argument("--url", default="http://localhost:8058")
        parser.add_argument("--dry-run", action="store_true")
        parser.parse_args()
        return dry_run()
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(_entry())
