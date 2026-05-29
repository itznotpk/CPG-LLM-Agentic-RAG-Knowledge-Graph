"""
Replay failed clinical pipeline jobs from logs/failed_jobs.jsonl.

Each line is a JSON record written by agent/offline_log.py when any LLM/API
call raises during a consultation.  This script POSTs each un-replayed record
to /clinical/plan and marks it `replayed` or `replay_failed` in-place.

Usage (backend must be running):
    python scripts/replay_failed_jobs.py
    python scripts/replay_failed_jobs.py --url http://localhost:8000
    python scripts/replay_failed_jobs.py --dry-run          # print without sending
    python scripts/replay_failed_jobs.py --stage "Stage 5"  # filter by stage prefix
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

_DEFAULT_URL = "http://localhost:8058"
_JOBS_FILE = Path(__file__).parent.parent / "logs" / "failed_jobs.jsonl"


def _load_jobs(path: Path) -> list[tuple[int, dict]]:
    """Return [(line_index, record), ...] for every un-replayed entry."""
    if not path.exists():
        print(f"No failed_jobs file at {path}")
        return []
    jobs = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                print(f"  [WARN] line {i}: invalid JSON, skipping")
                continue
            if rec.get("status") not in ("replayed", "replay_failed"):
                jobs.append((i, rec))
    return jobs


def _rewrite_status(path: Path, line_idx: int, status: str) -> None:
    """Update the status field of a single line in-place (rewrite whole file)."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        rec = json.loads(lines[line_idx])
        rec["status"] = status
        lines[line_idx] = json.dumps(rec, separators=(",", ":"), default=str) + "\n"
        path.write_text("".join(lines), encoding="utf-8")
    except Exception as exc:
        print(f"  [WARN] could not update line {line_idx}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay failed clinical pipeline jobs")
    parser.add_argument("--url", default=_DEFAULT_URL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stage", default=None, help="Filter by stage prefix, e.g. 'Stage 5'")
    args = parser.parse_args()

    jobs = _load_jobs(_JOBS_FILE)
    if not jobs:
        print("No pending failed jobs.")
        return

    if args.stage:
        jobs = [(i, r) for i, r in jobs if r.get("stage", "").startswith(args.stage)]

    print(f"Found {len(jobs)} job(s) to replay → {args.url}/clinical/plan")
    if args.dry_run:
        for i, rec in jobs:
            print(f"  [DRY] line {i}: stage={rec.get('stage')} ts={rec.get('ts')} error={rec.get('error','')[:80]}")
        return

    ok = failed = 0
    with httpx.Client(timeout=120.0) as client:
        for i, rec in jobs:
            case = rec.get("case", {})
            ts = rec.get("ts", "?")
            stage = rec.get("stage", "?")
            print(f"  Replaying line {i}: stage={stage} ts={ts} … ", end="", flush=True)
            try:
                resp = client.post(f"{args.url}/clinical/plan", json={"case": case})
                if resp.status_code == 200:
                    print("OK")
                    _rewrite_status(_JOBS_FILE, i, "replayed")
                    ok += 1
                else:
                    detail = resp.text[:120]
                    print(f"HTTP {resp.status_code}: {detail}")
                    _rewrite_status(_JOBS_FILE, i, "replay_failed")
                    failed += 1
            except Exception as exc:
                print(f"ERROR: {exc}")
                _rewrite_status(_JOBS_FILE, i, "replay_failed")
                failed += 1
            time.sleep(0.5)  # avoid hammering the API

    print(f"\nDone. {ok} replayed, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
