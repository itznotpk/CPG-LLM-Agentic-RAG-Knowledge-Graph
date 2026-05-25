"""Validate (and optionally expand) the icd11_scope code lists in
tasks/Next-Step/Last Step Improvement/DDx Gap/cpg_scope_review.md against
the local icd11_codes table (populated by ddx/ingest_icd11_full.py from
WHO ICD-11 MMS 2024-01). Codes missing from the local table fall back to
a live WHO API lookup.

Usage:
    python scripts/verify_icd_codes_against_who.py --cpg "Heart-Disease-in-Pregnancy(2nd Edition)"
    python scripts/verify_icd_codes_against_who.py --all-edited           # all 7 edited CPGs
    python scripts/verify_icd_codes_against_who.py --all-edited --expand  # also rewrite ranges -> child code lists in the .md

`--expand` rewrites block-range tokens like `2A00-2F9Z` or `BB60-BB9Z`
into explicit child code lists pulled from icd11_codes, in place in the
review file (one targeted line per CPG; rationale & hierarchy lines are
left untouched).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

REVIEW_PATH = ROOT / "tasks" / "Next-Step" / "Last Step Improvement" / "DDx Gap" / "cpg_scope_review.md"

EDITED_CPGS = [
    "Heart-Disease-in-Pregnancy(2nd Edition)",
    "Cancer-Pain(2nd Edition)",
    "Colorectal-Carcinoma(2017)",
    "Stable-Coronary-Artery-Disease(2nd Edition)",
    "T2-Diabetes-Mellitus(6th-Edition)",
    "Type-1-Diabetes-Mellitus-Children_Adolescents(2016)",
    "Growth-Hormone-Children-Adults(2010)",
]

CODE_TOKEN = re.compile(r"`([^`]+)`")
RANGE_TOKEN = re.compile(r"^([0-9A-Z]{2,4})-([0-9A-Z]{2,4})$")
PLAIN_CODE = re.compile(r"^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$")


# --------------------------------------------------------------------------- WHO API

WHO_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
WHO_BASE = "https://id.who.int/icd/release"


async def who_token(http: httpx.AsyncClient) -> str:
    cid = os.getenv("ICD11_API_CLIENT_ID")
    csec = os.getenv("ICD11_API_CLIENT_SECRET")
    if not (cid and csec):
        raise RuntimeError("ICD11_API_CLIENT_ID / SECRET missing in .env")
    resp = await http.post(
        WHO_TOKEN_URL,
        data={"client_id": cid, "client_secret": csec,
              "scope": "icdapi_access", "grant_type": "client_credentials"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def who_lookup(http: httpx.AsyncClient, token: str, code: str) -> str | None:
    rel = os.getenv("ICD11_API_RELEASE_ID", "2024-01")
    lin = os.getenv("ICD11_API_LINEARIZATION", "mms")
    lang = os.getenv("ICD11_API_LANGUAGE", "en")
    url = f"{WHO_BASE}/11/{rel}/{lin}/codeinfo/{code}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json",
               "API-Version": "v2", "Accept-Language": lang}
    resp = await http.get(url, headers=headers, follow_redirects=True)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", {})
    if isinstance(title, dict):
        return title.get("@value")
    return str(title) if title else None


# --------------------------------------------------------------------------- review file

def parse_review(text: str) -> dict[str, dict]:
    """Return {cpg_name: {'header': str, 'scope_line_idx': int, 'codes': [tokens], 'lines': [str]}}."""
    out: dict[str, dict] = {}
    lines = text.splitlines()
    cur = None
    for i, raw in enumerate(lines):
        if raw.startswith("## "):
            header = raw[3:].strip()
            name = re.sub(r"\s*(✅|⚠️).*$", "", header).strip()
            cur = {"header_idx": i, "scope_line_idx": None, "codes": []}
            out[name] = cur
            continue
        if cur is None:
            continue
        if re.match(r"-\s*Proposed icd11_scope\s*:", raw, re.IGNORECASE):
            cur["scope_line_idx"] = i
            cur["codes"] = CODE_TOKEN.findall(raw)
    return out


# --------------------------------------------------------------------------- DB lookup / expansion

async def db_lookup(conn: asyncpg.Connection, code: str) -> str | None:
    row = await conn.fetchrow("SELECT title FROM icd11_codes WHERE code = $1", code)
    return row["title"] if row else None


def _code_sort_key(code: str) -> tuple:
    """Sort 2A00 < 2A00.0 < 2A01 by lex on the alphanumeric prefix then dotted suffix."""
    head, _, tail = code.partition(".")
    return (head, tail)


async def expand_range(conn: asyncpg.Connection, start: str, end: str) -> list[str]:
    """Return all codes c with _code_sort_key(start) <= key(c) <= key(end).
    Restricted to codes in the same chapter prefix (first 2 chars must match start)."""
    # Use only the first character of the start code as a coarse filter
    # (so ranges like 2A00-2F9Z that span multiple BB-prefix blocks are not truncated).
    prefix = start[:1]
    rows = await conn.fetch(
        "SELECT code FROM icd11_codes WHERE code LIKE $1 ORDER BY code",
        prefix + "%",
    )
    keep = []
    lo, hi = _code_sort_key(start), _code_sort_key(end)
    for r in rows:
        c = r["code"]
        k = _code_sort_key(c)
        if lo <= k <= hi:
            keep.append(c)
    return keep


# --------------------------------------------------------------------------- main

async def run(cpg_filter: list[str], expand: bool) -> int:
    text = REVIEW_PATH.read_text(encoding="utf-8")
    parsed = parse_review(text)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL missing in .env")
    conn = await asyncpg.connect(db_url)

    async with httpx.AsyncClient(timeout=30) as http:
        who_tok: str | None = None  # lazy

        report: dict[str, dict] = {}
        new_lines = text.splitlines()

        for cpg in cpg_filter:
            if cpg not in parsed:
                print(f"!! {cpg}: not found in review file", file=sys.stderr)
                continue
            sec = parsed[cpg]
            codes_raw = sec["codes"]
            valid: list[str] = []
            missing: list[str] = []
            expanded_from_ranges: dict[str, list[str]] = {}

            for tok in codes_raw:
                # strip trailing inline annotations like "[clinician verify]"
                t = tok.strip()
                m_range = RANGE_TOKEN.match(t)
                if m_range:
                    start, end = m_range.group(1), m_range.group(2)
                    children = await expand_range(conn, start, end)
                    if not children:
                        missing.append(t + "  (range expanded to 0 codes)")
                    else:
                        expanded_from_ranges[t] = children
                        valid.extend(children)
                    continue
                if not PLAIN_CODE.match(t):
                    # skip annotation tokens (e.g. multi-word "clinician verify ...")
                    continue
                title = await db_lookup(conn, t)
                if title:
                    valid.append(t)
                else:
                    if who_tok is None:
                        who_tok = await who_token(http)
                    who_title = await who_lookup(http, who_tok, t)
                    if who_title:
                        valid.append(t + "  [in WHO MMS but missing from local icd11_codes]")
                    else:
                        missing.append(t)

            report[cpg] = {
                "n_valid": len(valid),
                "n_missing": len(missing),
                "missing": missing,
                "ranges": expanded_from_ranges,
            }

            if expand and expanded_from_ranges:
                # Rewrite the scope line: replace each `RANGE` token with
                # backticked expanded child codes.
                idx = sec["scope_line_idx"]
                line = new_lines[idx]
                for rng, kids in expanded_from_ranges.items():
                    rep = ", ".join(f"`{c}`" for c in kids)
                    line = line.replace(f"`{rng}`", rep)
                new_lines[idx] = line

        if expand:
            REVIEW_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print(f"[expand] rewrote ranges in {REVIEW_PATH}")

    await conn.close()

    # ---------------------------------------------------------- report
    print("\n=== ICD-11 validation report ===\n")
    any_missing = False
    for cpg, r in report.items():
        print(f"## {cpg}")
        print(f"   valid: {r['n_valid']}   missing: {r['n_missing']}")
        for rng, kids in r["ranges"].items():
            print(f"   range {rng:>14}  -> {len(kids)} child codes")
        for m in r["missing"]:
            print(f"   MISSING: {m}")
            any_missing = True
        print()
    return 1 if any_missing else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpg", action="append", default=[],
                    help="CPG name (repeatable). Default: --all-edited.")
    ap.add_argument("--all-edited", action="store_true",
                    help="Validate all 7 clinician-edited CPGs.")
    ap.add_argument("--expand", action="store_true",
                    help="Rewrite block ranges -> explicit child code lists in the review file.")
    args = ap.parse_args()
    cpgs = args.cpg or (EDITED_CPGS if args.all_edited else [])
    if not cpgs:
        ap.error("Pass --cpg <name> or --all-edited")
    rc = asyncio.run(run(cpgs, expand=args.expand))
    sys.exit(rc)


if __name__ == "__main__":
    main()
