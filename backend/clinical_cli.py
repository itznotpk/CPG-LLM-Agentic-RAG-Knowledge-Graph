#!/usr/bin/env python3
import json
import asyncio
import aiohttp
import argparse
import sys
import time
import os


class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    DIM = '\033[2m'
    BOLD_RED = '\033[1;31m'


DIV = f"{Colors.DIM}{'─' * 65}{Colors.END}"


def intake_patient() -> dict:
    print(f"{Colors.CYAN}{Colors.BOLD}=== PATIENT INTAKE ==={Colors.END}")
    print(f"{Colors.YELLOW}Hint: For best DDx results, use a concise symptom-focused summary.{Colors.END}")
    chief_complaint = input("Chief complaint (required): ").strip()
    while not chief_complaint:
        chief_complaint = input("Chief complaint (required): ").strip()

    age_str = input("Age: ").strip()
    age = int(age_str) if age_str.isdigit() else None

    sex_str = input("Sex (M/F): ").strip().upper()
    sex = sex_str if sex_str in ("M", "F", "OTHER") else None

    history = input("History (or Enter to skip): ").strip() or None

    comorb_str = input("Comorbidities (comma-separated, or Enter): ").strip()
    comorbidities = [c.strip() for c in comorb_str.split(",") if c.strip()]

    meds_str = input("Current medications (comma-separated, or Enter): ").strip()
    current_medications = [m.strip() for m in meds_str.split(",") if m.strip()]

    allergies_str = input("Allergies (comma-separated, or Enter): ").strip()
    allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]

    vitals_str = input("Vitals (e.g. sbp=160 dbp=95 hr=98 spo2=97, or Enter to skip): ").strip()
    vitals = {}
    if vitals_str:
        for kv in vitals_str.split():
            if '=' in kv:
                k, v = kv.split('=', 1)
                try:
                    vitals[k.lower()] = float(v)
                except ValueError:
                    pass

    return {
        "chief_complaint": chief_complaint,
        "history": history,
        "age": age,
        "sex": sex,
        "comorbidities": comorbidities,
        "current_medications": current_medications,
        "allergies": allergies,
        "vitals": vitals,
    }


async def _stream_events(url: str, endpoint: str, payload: dict):
    """Yield (event_type, data) tuples from an SSE endpoint."""
    timeout = aiohttp.ClientTimeout(total=900, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            headers = {"Connection": "close", "Accept": "text/event-stream"}
            async with session.post(f"{url}{endpoint}", json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"{Colors.RED}HTTP Error {resp.status}: {text}{Colors.END}")
                    if "ValidationError" in text:
                        with open("debug_output.json", "w") as f:
                            f.write(text)
                        print("Dumped raw error to debug_output.json")
                    sys.exit(1)

                event_type = None
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    if line_str.startswith("event:"):
                        event_type = line_str[6:].strip()
                    elif line_str.startswith("data:") and event_type:
                        data_str = line_str[5:].strip()
                        try:
                            data = json.loads(data_str)
                            yield event_type, data
                        except json.JSONDecodeError as e:
                            print(f"{Colors.RED}JSON parse error: {e}{Colors.END}")
                        event_type = None
        except aiohttp.ClientError as e:
            print(f"{Colors.RED}Connection error: {e}{Colors.END}")
            sys.exit(1)


def _print_thinking(buffer: list[str], node: str = ""):
    if not buffer:
        return
    text = "".join(buffer)
    label = f"AI Reasoning ({node})" if node else "AI Reasoning"
    print(f"\n{Colors.DIM}╔══ {label} ══")
    if len(text) > 600:
        print(f"║ {text[:600]}")
        print(f"║ ... [truncated — {len(text)} chars total]")
    else:
        for line in text.split("\n"):
            if line.strip():
                print(f"║ {line}")
    print(f"╚{'═' * (len(label) + 6)}{Colors.END}\n")


def _print_ddx_table(ddx: list):
    print(f"\n╔══ DIFFERENTIAL DIAGNOSIS {'═' * 34}╗")
    print(f"║  {'#':<3} {'ICD-11':<8} {'Condition':<28}  {'Score':<6} {'':5} ║")

    for i, d in enumerate(ddx, 1):
        code = d.get("code", "")[:8]
        title = d.get("title", "")[:28]
        score_val = d.get("similarity", d.get("probability", 0))
        score = f"{int(score_val * 100)}%" if score_val else "N/A"
        marker = "← AI" if i == 1 else "    "

        print(f"║  {i:<3} {code:<8} {title:<28}  {score:<6} {marker:<5} ║")

    print(f"╚{'═' * 58}╝\n")

    if ddx:
        reasoning_list = ddx[0].get("reasoning", [])
        if reasoning_list:
            reasoning = " | ".join(reasoning_list) if isinstance(reasoning_list, list) else str(reasoning_list)
            print(f"AI reasoning for #1: {Colors.DIM}{reasoning}{Colors.END}\n")


async def run_stream(url: str, endpoint: str, payload: dict) -> dict | None:
    """Stream a clinical pipeline endpoint, print live progress, return final_result."""
    thinking_buffer: list[str] = []
    thinking_node: str = ""
    final_result = None
    stage_start_times = {}

    async for event_type, data in _stream_events(url, endpoint, payload):
        if event_type == "stage_update":
            status = data.get("status")
            name = data.get("name", "")
            stage = data.get("stage", "")

            if status == "running":
                stage_start_times[stage] = time.monotonic()
                print(f"[Stage {stage}] {name} {Colors.YELLOW}▶ running{Colors.END}")
            elif status == "complete":
                elapsed = time.monotonic() - stage_start_times.get(stage, time.monotonic())
                if thinking_buffer:
                    _print_thinking(thinking_buffer, thinking_node)
                    thinking_buffer = []
                    thinking_node = ""
                print(f"[Stage {stage}] {name} {Colors.GREEN}✓ {elapsed:.1f}s{Colors.END}")
                # DDx available immediately after Stage 2 — print table now
                if stage == 2 and data.get("data"):
                    _print_ddx_table(data["data"])
            elif status == "error":
                print(f"[Stage {stage}] {name} {Colors.RED}✗ error{Colors.END}")

        elif event_type == "thinking_delta":
            thinking_buffer.append(data.get("chunk", ""))
            thinking_node = data.get("node", "")

        elif event_type == "sub_step":
            detail = data.get("detail", "")
            badge = data.get("badge", "")
            badge_str = f"  [{badge}]" if badge else ""
            print(f"  → {detail}{badge_str}")

        elif event_type == "final_result":
            final_result = data

        elif event_type == "error":
            detail = data.get("detail", str(data))
            print(f"{Colors.RED}Error: {detail}{Colors.END}")
            if "ValidationError" in detail:
                with open("debug_output.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("Dumped raw error to debug_output.json")
            sys.exit(1)

        elif event_type == "done":
            break

    return final_result


def prompt_ddx_override(ddx: list) -> dict | None:
    """
    Prompt the clinician to accept the AI pick or select a different ICD.
    Returns the selected DDxResult dict if override, None if accepting AI pick.
    """
    while True:
        choice = input("Accept AI suggestion #1 and generate care plan? [Y/n/1-5]: ").strip().lower()
        if not choice or choice in ("y", "1"):
            return None
        if choice.isdigit() and 2 <= int(choice) <= len(ddx):
            selected = ddx[int(choice) - 1]
            return {
                "code": selected.get("code", ""),
                "title": selected.get("title", ""),
                "probability": selected.get("similarity", selected.get("probability", 0.0)),
                "reasoning": selected.get("reasoning", []),
            }
        if choice == "n":
            code = input("Custom ICD-11 code: ").strip()
            title = input("Custom condition title: ").strip()
            return {"code": code, "title": title, "probability": 1.0, "reasoning": []}
        print("Please enter Y, n, or a number 1–5.")


def print_care_plan(result: dict):
    plan = result.get("treatment_plan", {})
    if not plan:
        print(f"{Colors.RED}No treatment plan found in result.{Colors.END}")
        return

    icd = plan.get("icd_primary", "Unknown")
    conf = int(plan.get("confidence", 0.0) * 100)

    inner = f"  CARE PLAN  —  ICD-11: {icd}  (confidence {conf}%)"
    width = 62
    print(f"╔{'═' * width}╗")
    print(f"║{inner:<{width}}║")
    print(f"╚{'═' * width}╝\n")

    # Section 1 — Summary
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 1) Summary{Colors.END}")
    print(plan.get("summary", "(no summary)"))
    print()

    # Section 2 — Medication Changes
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 2) Medication Changes{Colors.END}")
    recs = plan.get("recommendations", [])
    pharma = [r for r in recs if r.get("type") == "pharmacological"]
    action_labels = {
        "start":          f"{Colors.GREEN}START{Colors.END}",
        "stop":           f"{Colors.RED}STOP{Colors.END}",
        "change":         f"{Colors.YELLOW}CHANGE{Colors.END}",
        "continue":       f"{Colors.DIM}CONTINUE{Colors.END}",
        "contraindicated": f"{Colors.BOLD_RED}CONTRAINDICATED{Colors.END}",
    }
    for act_key in ("start", "stop", "change", "continue", "contraindicated"):
        group = [r for r in pharma if r.get("action") == act_key]
        if group:
            print(f"\n  {Colors.BOLD}── {act_key.upper()} ──{Colors.END}")
            for r in group:
                print(f"  • {Colors.BOLD}{r.get('intervention')}{Colors.END}")
                grade = r.get("evidence_grade")
                if grade:
                    print(f"         Evidence: {Colors.YELLOW}{grade}{Colors.END}  |  Source: {r.get('cpg_source')}")
                else:
                    print(f"         Source: {r.get('cpg_source')}")
                print(f"    {Colors.DIM}{r.get('rationale')}{Colors.END}")
                cc = r.get("contraindications_checked", [])
                if cc:
                    print(f"         Checked against: {', '.join(cc)}")
                print()

    # Section 3 — Patient Education & Counselling
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 3) Patient Education & Counselling{Colors.END}")
    lifestyle = [r for r in recs if r.get("type") == "lifestyle"]
    for r in lifestyle:
        print(f"  • {r.get('intervention')} — {Colors.DIM}{r.get('rationale')}{Colors.END}")
    if not lifestyle:
        print(f"  {Colors.DIM}(none retrieved){Colors.END}")
    print()

    # Section 4 — Monitoring & Next Steps
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 4) Monitoring & Next Steps{Colors.END}")
    investigations = [r for r in recs if r.get("type") in ("investigation", "procedure")]
    if investigations:
        print("  Tests & Procedures:")
        for r in investigations:
            print(f"  • {r.get('intervention')}")
            print(f"    {Colors.DIM}{r.get('rationale')}{Colors.END}")
        print()
    monitoring = plan.get("monitoring", [])
    if monitoring:
        print("  Monitoring:")
        for m in monitoring:
            if isinstance(m, dict):
                param = m.get("parameter", "?")
                sched = m.get("schedule", "")
                target = m.get("target") or ""
                ref = m.get("cpg_ref", "")
                print(f"  • {Colors.BOLD}{param}{Colors.END}")
                if sched:
                    print(f"      Schedule: {sched}")
                if target:
                    print(f"      Target:   {target}")
                if ref:
                    print(f"      Source:   {Colors.DIM}{ref}{Colors.END}")
            else:
                print(f"  • {m}")
        print()
    red_flags = plan.get("red_flags", [])
    if red_flags:
        print("  Red Flags — return immediately if:")
        for rf in red_flags:
            print(f"  {Colors.RED}⚠  {rf}{Colors.END}")
    print()

    # Section 5 — Referrals
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 5) Referrals{Colors.END}")
    referrals = [r for r in recs if r.get("type") == "referral"]
    for r in referrals:
        print(f"  • {r.get('intervention')}")
        print(f"    {Colors.DIM}Rationale: {r.get('rationale')}  |  Source: {r.get('cpg_source')}{Colors.END}")
    if not referrals:
        print(f"  {Colors.DIM}(none retrieved){Colors.END}")
    print()

    # Section 6 — Follow-up
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## 6) Follow-up{Colors.END}")
    for f in plan.get("follow_up", []):
        print(f"  • {f}")
    if not plan.get("follow_up"):
        print(f"  {Colors.DIM}(none retrieved){Colors.END}")
    print()

    # Sources
    print(DIV)
    print(f"{Colors.CYAN}{Colors.BOLD}## Sources{Colors.END}")
    sources = sorted({r.get("cpg_source") for r in recs if r.get("cpg_source")})
    for i, s in enumerate(sources, 1):
        print(f"  [{i}]  {s}")
    print()

    # Unresolved questions
    unresolved = plan.get("unresolved_questions", [])
    print(f"{'─' * 65}")
    print(f"Unresolved Questions ({len(unresolved)}):")
    for u in unresolved:
        print(f"  {Colors.DIM}• {u}{Colors.END}")
    print(f"{'─' * 65}")
    print(f"Total elapsed: {result.get('elapsed_ms', 0) / 1000:.1f}s\n")


async def main():
    parser = argparse.ArgumentParser(description="Clinical Pipeline Terminal Test Harness")
    parser.add_argument('--url', default='http://localhost:8058', help='Base URL for the API (default: http://localhost:8058)')
    args = parser.parse_args()
    url = args.url.rstrip("/")

    case = intake_patient()
    print(f"\n{Colors.CYAN}Starting clinical pipeline…{Colors.END}\n")

    # Stage 2–5: full pipeline. DDx table is printed inside run_stream after Stage 2 completes.
    final_result = await run_stream(url, "/clinical/plan/stream", {"case": case})
    if not final_result:
        print(f"{Colors.RED}Pipeline returned no result.{Colors.END}")
        return

    # DDx was already printed during streaming; prompt for override using final_result.ddx
    ddx = final_result.get("ddx", [])
    selected = prompt_ddx_override(ddx)

    if selected:
        print(f"\n{Colors.CYAN}Re-synthesizing plan for: {selected['title']} ({selected['code']})…{Colors.END}\n")
        final_result = await run_stream(
            url,
            "/clinical/plan/resynthesize/stream",
            {"case": case, "selected_diagnoses": [selected]},
        )

    if final_result:
        print_care_plan(final_result)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}Terminated.{Colors.END}")
