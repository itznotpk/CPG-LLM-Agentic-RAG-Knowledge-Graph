"""
I/O helpers: load JSONL gold sets, write timestamped result CSV/JSON.
Used by every eval script — no layer-specific logic here.
"""

from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

EVAL_DIR = Path(__file__).parent
GOLD_DIR = EVAL_DIR / "gold_sets"
RESULTS_DIR = EVAL_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_jsonl(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.is_absolute():
        path = GOLD_DIR / path
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_results(name: str, rows: list[dict], summary: dict) -> tuple[Path, Path]:
    ts = _timestamp()
    csv_path = RESULTS_DIR / f"{name}_{ts}.csv"
    json_path = RESULTS_DIR / f"{name}_{ts}.json"

    if rows:
        keys = list(rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in keys})

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2, ensure_ascii=False)

    return csv_path, json_path


def print_summary(name: str, summary: dict) -> None:
    print(f"\n=== {name} ===")
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k:<25} {v:.4f}")
        else:
            print(f"  {k:<25} {v}")
