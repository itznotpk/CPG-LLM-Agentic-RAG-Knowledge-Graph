"""
Auto-map unresolved retrieval gold placeholders to live Postgres chunk UUIDs.

This is a pragmatic labelling helper for eval/gold_sets/retrieval_gold.jsonl:
- It only updates rows whose relevant_chunk_ids still contain REPLACE_WITH_*.
- It scopes candidates by the row's document_filter.
- It scores chunks by overlap with relevant_keywords, query, notes, and metadata.
- It writes the chosen chunks.id values back into relevant_chunk_ids.

The output is auditable: each updated row receives label_provenance,
auto_label_score, and auto_label_candidates with short previews.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold_sets" / "retrieval_gold.jsonl"


FILTER_TO_CPG_SLUG = {
    "Atrial Fibrillation": "Atrial-Fibrillation(2012)",
    "Cancer Pain": "Cancer-Pain(2nd Edition)",
    "Patient Safety Minimal Monitoring": "Patient-Safety-Minimal-Monitoring",
    "Pre-Anaesthetic Assessment": "Pre-Anaesthetic-Assessment",
    "Anaesthesia Medication Safety": "Anaesthesia-Medication-Safety",
    "Anaesthesia Safe Medication Use": "Anaesthesia-Medication-Safety",
    "STEMI": "STEMI(4th Edition)",
    "NSTE-ACS": "NSTE-ACS(3rd Edition)",
    "NSTEMI": "NSTEMI(2011)",
    "Heart Failure": "Heart-Failure(5th Edition)",
    "Hypertension": "Hypertension(5th Edition)",
    "Dyslipidaemia": "Dyslipidaemia(6th-Edition)",
    "Stable Coronary Artery Disease": "Stable-Coronary-Artery-Disease(2nd Edition)",
    "Percutaneous Coronary Intervention": "Percutaneous-Coronary-Intervention",
    "Pulmonary Arterial Hypertension": "Pulmonary-Arterial-Hypertension(2011)",
    "Heart Disease in Pregnancy": "Heart-Disease-in-Pregnancy(2nd Edition)",
    "Infective Endocarditis": "Prevention-Diagnosis-Management-of-IE",
    "Ischaemic Stroke": "Ischaemic-Stroke(3rd Edition)",
    "Breast Cancer": "Breast-Cancer(3rd Edition)",
    "Colorectal Carcinoma": "Colorectal-Carcinoma(2017)",
    "Nasopharyngeal Carcinoma": "Nasopharyngeal-Carcinoma",
    "Erectile Dysfunction": "Erectile-Dysfunction(2024)",
    "Primary Secondary Prevention of CVD": "Primary-Secondary-Prevention-of-CVD(2017)",
    "CVD Prevention in Women": "CVD-Prevention-Women(2016)",
    "Cervical Cancer": "Cervical-Cancer(2nd Edition)",
    "Obesity Management": "Obesity-Management(2023)",
    "T2 Diabetes Mellitus": "T2-Diabetes-Mellitus(6th-Edition)",
    "Thyroid Disorders": "Thyroid-Disorders(2019)",
    "Diabetes in Pregnancy": "Diabetes-in-Pregnancy(2017)",
    "Type 1 Diabetes Mellitus": "Type-1-Diabetes-Mellitus-Children_Adolescents(2016)",
    "Growth Hormone": "Growth-Hormone-Children-Adults(2010)",
}


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "can",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "should",
    "the", "to", "what", "when", "where", "which", "with",
}


@dataclass
class Candidate:
    chunk_id: str
    score: float
    keyword_hits: list[str]
    title: str
    context_path: str
    preview: str


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def unresolved(row: dict[str, Any]) -> bool:
    return any(str(cid).startswith("REPLACE_WITH_") for cid in row.get("relevant_chunk_ids", []))


def norm(text: str) -> str:
    text = text.lower()
    text = text.replace("≤", "<=").replace("≥", ">=").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9%./<>+=-]+", " ", text)


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9+./<>=%-]{1,}", norm(text)) if t not in STOPWORDS}


def phrase_present(phrase: str, haystack: str) -> bool:
    p = norm(phrase).strip()
    if not p:
        return False
    return p in haystack


def score_chunk(row: dict[str, Any], chunk: asyncpg.Record) -> Candidate:
    metadata = chunk["metadata"] or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    title = metadata.get("h2_title") or metadata.get("title") or ""
    context_path = metadata.get("context_path") or ""
    haystack_raw = " ".join([
        chunk["content"] or "",
        title,
        context_path,
        metadata.get("source") or "",
    ])
    haystack = norm(haystack_raw)

    keywords = [str(k) for k in row.get("relevant_keywords", [])]
    keyword_hits = [k for k in keywords if phrase_present(k, haystack)]

    score = 0.0
    for kw in keywords:
        kw_tokens = tokens(kw)
        if not kw_tokens:
            continue
        hit_tokens = sum(1 for t in kw_tokens if t in haystack)
        if phrase_present(kw, haystack):
            score += 4.0 + len(kw_tokens)
        elif hit_tokens:
            score += hit_tokens / len(kw_tokens)

    query_tokens = tokens(row.get("query", ""))
    notes_tokens = tokens(row.get("notes", ""))
    score += 0.35 * sum(1 for t in query_tokens if t in haystack)
    score += 0.25 * sum(1 for t in notes_tokens if t in haystack)

    # Prefer answer-bearing chunks over table-of-contents or intro chunks when tied.
    level = (metadata.get("chunk_level") or chunk["chunk_level"] or "").lower()
    if level in {"h2", "h3"}:
        score += 0.5
    if "appendix" in norm(title) and "appendix" not in norm(row.get("query", "")):
        score -= 0.5

    preview = re.sub(r"\s+", " ", (chunk["content"] or "")).strip()[:260]
    return Candidate(
        chunk_id=str(chunk["chunk_id"]),
        score=round(score, 3),
        keyword_hits=keyword_hits,
        title=title,
        context_path=context_path,
        preview=preview,
    )


async def resolve_doc_ids(conn: asyncpg.Connection, document_filter: str) -> list[str]:
    slug = FILTER_TO_CPG_SLUG.get(document_filter)
    if slug:
        rows = await conn.fetch(
            "SELECT id::text AS id FROM documents WHERE metadata->>'cpg_name' = $1",
            slug,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id::text AS id
            FROM documents
            WHERE metadata->>'cpg_name' ILIKE $1
               OR title ILIKE $1
            """,
            f"%{document_filter}%",
        )
    return [r["id"] for r in rows]


async def fetch_chunks(conn: asyncpg.Connection, doc_ids: list[str]) -> list[asyncpg.Record]:
    if not doc_ids:
        return []
    return await conn.fetch(
        """
        SELECT c.id::text AS chunk_id,
               c.content,
               c.metadata,
               c.chunk_level
        FROM chunks c
        WHERE c.document_id = ANY($1::uuid[])
          AND c.embedding IS NOT NULL
        """,
        doc_ids,
    )


def pick_candidates(candidates: list[Candidate], max_ids: int) -> list[Candidate]:
    ranked = sorted(candidates, key=lambda c: (c.score, len(c.keyword_hits)), reverse=True)
    if not ranked:
        return []
    chosen = ranked[:max_ids]
    # If the third candidate is weak, keep the label tighter.
    return [c for c in chosen if c.score >= max(2.0, ranked[0].score * 0.35)]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Update retrieval_gold.jsonl")
    parser.add_argument("--max-ids", type=int, default=3, help="Max chunks to label per unresolved row")
    parser.add_argument("--min-score", type=float, default=2.0, help="Minimum top candidate score")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set")

    rows = load_jsonl(GOLD)
    unresolved_rows = [r for r in rows if unresolved(r)]
    print(f"Unresolved before: {len(unresolved_rows)} / {len(rows)}")

    conn = await asyncpg.connect(database_url)
    try:
        updated = 0
        skipped: list[tuple[str, str]] = []
        for row in unresolved_rows:
            doc_ids = await resolve_doc_ids(conn, row.get("document_filter", ""))
            if not doc_ids:
                skipped.append((row["id"], "no document match"))
                continue
            chunks = await fetch_chunks(conn, doc_ids)
            candidates = [score_chunk(row, c) for c in chunks]
            chosen = pick_candidates(candidates, args.max_ids)
            if not chosen or chosen[0].score < args.min_score:
                skipped.append((row["id"], "no confident chunk candidate"))
                continue

            row["relevant_chunk_ids"] = [c.chunk_id for c in chosen]
            row["label_provenance"] = "auto-mapped from DB chunk keyword/content scoring (scratch/auto_map_retrieval_gold.py)"
            row["auto_label_score"] = chosen[0].score
            row["auto_label_candidates"] = [
                {
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "keyword_hits": c.keyword_hits,
                    "title": c.title,
                    "context_path": c.context_path,
                    "preview": c.preview,
                }
                for c in chosen
            ]
            updated += 1

        remaining = sum(1 for r in rows if unresolved(r))
        print(f"Auto-mapped: {updated}")
        print(f"Remaining unresolved if written: {remaining}")
        if skipped:
            print("Skipped:")
            for rid, reason in skipped[:40]:
                print(f"  {rid}: {reason}")
            if len(skipped) > 40:
                print(f"  ... {len(skipped) - 40} more")

        if args.write:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = GOLD.with_suffix(f".jsonl.bak_{stamp}")
            shutil.copy2(GOLD, backup)
            write_jsonl(GOLD, rows)
            print(f"Wrote {GOLD}")
            print(f"Backup {backup}")
        else:
            print("Dry run only. Re-run with --write to update the file.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
