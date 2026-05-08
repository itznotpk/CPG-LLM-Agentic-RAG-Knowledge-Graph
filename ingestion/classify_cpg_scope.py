"""
CPG Scope Classifier — Step 03.

Classifies each CPG in the documents table with ICD-11 scope codes by:
1. Grouping document rows by CPG (via metadata.cpg_name or source path)
2. Sending summary content to the LLM for ICD-11 scope proposal
3. Validating and writing the scope to the DB
4. Generating tasks/cpg_scope_review.md for clinician review

Usage:
    python -m ingestion.classify_cpg_scope               # full run
    python -m ingestion.classify_cpg_scope --dry-run     # no DB writes, no review file
    python -m ingestion.classify_cpg_scope --only "Atrial-Fibrillation(2012),STEMI(4th Edition)"
"""

import argparse
import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import asyncpg
import openai
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

from agent.providers import get_ingestion_model  # noqa: E402 — needs dotenv loaded first

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MAX_CONTENT_CHARS = 12_000

# ICD-11 code patterns: 3–4 char block OR range
_ICD_CODE_PATTERN = re.compile(
    r'^[0-9A-Z]{2,4}(\.[0-9A-Z]{1,2})?$|^[0-9A-Z]{2,4}-[0-9A-Z]{2,4}$'
)

SYSTEM_PROMPT = (
    "You are a precise ICD-11 coding expert. Given a Malaysian Clinical Practice Guideline "
    "(CPG)'s name and summary content, identify the ICD-11 block codes (3-character) or ranges "
    "that this CPG provides treatment guidance for.\n\n"
    "Rules:\n"
    "- Be conservative. Only include codes for which the CPG offers actionable diagnostic or "
    "treatment guidance.\n"
    "- Use 3-character block codes (e.g. \"BC81\", \"BA00\") OR ranges in the format "
    "\"BA00-BA04\" when a CPG covers a contiguous block.\n"
    "- If the CPG is procedure-oriented (e.g. anaesthesia, surgical safety) rather than "
    "disease-oriented, leave icd11_scope EMPTY and populate procedure_scope with short "
    "snake_case tags such as \"pre_op_assessment\", \"intraop_monitoring\", \"anaesthetic_safety\".\n"
    "- Every CPG must end with at least one non-empty array — either icd11_scope or "
    "procedure_scope.\n"
    "- Return STRICT JSON only. No markdown fences, no commentary, no leading/trailing text.\n\n"
    "Return JSON shape:\n"
    '{"icd11_scope": ["BC81", "BC9Z"], "procedure_scope": [], '
    '"rationale": "Atrial fibrillation and related arrhythmias..."}'
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ScopeProposal(BaseModel):
    icd11_scope: list[str] = []
    procedure_scope: list[str] = []
    rationale: str


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class DocumentRow:
    id: str
    source: str
    title: str
    cpg_name: str
    file_path: str


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------

def derive_group_key(source: str) -> str | None:
    """
    Derive CPG group key from a document source string.

    - Path with directory: parent directory name
      e.g. 'markdown/AF(2012)/section-7.md' -> 'AF(2012)'
    - Bare filename with extension: stem
      e.g. 'CPG X.md' -> 'CPG X'
    - No extension and no separator: unmappable -> None
      e.g. 'weird-id-string' -> None
    """
    normalised = source.replace('\\', '/')
    path = PurePosixPath(normalised)
    parts = path.parts

    if len(parts) >= 2:
        return parts[-2]

    name = path.name
    if '.' in name:
        return path.stem

    return None


def validate_icd_codes(codes: list[str]) -> list[str]:
    """Return only well-formed ICD-11 codes; log and drop the rest."""
    valid = []
    for code in codes:
        c = code.strip()
        if _ICD_CODE_PATTERN.match(c):
            valid.append(c)
        else:
            logger.warning("Dropping invalid ICD code: %r", c)
    return valid


def strip_code_fence(text: str) -> str:
    """Remove markdown code fences from LLM text output."""
    text = text.strip()
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    return text.strip()


def parse_scope_proposal(raw: str) -> ScopeProposal:
    """
    Parse a raw LLM response into a ScopeProposal.

    Strips code fences, json.loads, validates with Pydantic.
    Raises json.JSONDecodeError or ValidationError on failure.
    """
    cleaned = strip_code_fence(raw)
    data = json.loads(cleaned)
    proposal = ScopeProposal(**data)
    proposal = ScopeProposal(
        icd11_scope=validate_icd_codes(proposal.icd11_scope),
        procedure_scope=proposal.procedure_scope,
        rationale=proposal.rationale,
    )
    if not proposal.icd11_scope and not proposal.procedure_scope:
        raise ValueError("Both icd11_scope and procedure_scope are empty after validation")
    return proposal


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def get_db_connection() -> asyncpg.Connection:
    import os
    url = os.getenv('DATABASE_URL')
    if not url:
        raise ValueError('DATABASE_URL environment variable not set')
    return await asyncpg.connect(url)


async def fetch_document_groups(
    conn: asyncpg.Connection,
) -> tuple[dict[str, list[DocumentRow]], list[str]]:
    """Fetch all documents and group by CPG. Returns (groups, unmappable)."""
    rows = await conn.fetch(
        "SELECT id::text, source, title, metadata FROM documents ORDER BY source"
    )

    groups: dict[str, list[DocumentRow]] = {}
    unmappable: list[str] = []

    for row in rows:
        meta = json.loads(row['metadata'])
        cpg_name = meta.get('cpg_name')
        file_path = meta.get('file_path', '')

        if cpg_name:
            group_key = cpg_name
        else:
            group_key = derive_group_key(row['source'])
            if group_key is None:
                logger.warning("Unmappable source: %r", row['source'])
                unmappable.append(row['source'])
                continue

        doc = DocumentRow(
            id=row['id'],
            source=row['source'],
            title=row['title'],
            cpg_name=group_key,
            file_path=file_path,
        )
        groups.setdefault(group_key, []).append(doc)

    logger.info(
        "Discovery: %d groups, %d rows, %d unmappable",
        len(groups),
        sum(len(v) for v in groups.values()),
        len(unmappable),
    )
    for key, docs in sorted(groups.items()):
        logger.info("  %s: %d rows", key, len(docs))

    return groups, unmappable


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

_PRIORITY_PREFIXES = ('section-0-', 'section-1-', 'section-0.', 'section-1.')


def _section_priority(doc: DocumentRow) -> int:
    basename = Path(doc.file_path.replace('\\', '/')).name if doc.file_path else doc.source
    for i, prefix in enumerate(_PRIORITY_PREFIXES):
        if basename.startswith(prefix):
            return i
    return len(_PRIORITY_PREFIXES)


def get_summary_content(group_key: str, docs: list[DocumentRow]) -> str:
    """Build summary content for the LLM prompt (up to MAX_CONTENT_CHARS)."""
    sorted_docs = sorted(docs, key=_section_priority)
    picked = sorted_docs[:2]

    contents = []
    for doc in picked:
        if doc.file_path:
            fp = Path(doc.file_path.replace('\\', '/'))
            if not fp.is_absolute():
                fp = PROJECT_ROOT / fp
            if fp.exists():
                try:
                    text = fp.read_text(encoding='utf-8', errors='replace')
                    contents.append(text)
                    continue
                except OSError as e:
                    logger.warning("Cannot read %s: %s", fp, e)
        logger.warning("File not found for %r in group %r; using title only", doc.source, group_key)
        contents.append(f"# {doc.title}")

    combined = '\n\n--- next section ---\n\n'.join(contents)
    if len(combined) > MAX_CONTENT_CHARS:
        combined = combined[:MAX_CONTENT_CHARS] + '\n\n[...truncated]'
    return combined


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def _get_openai_client() -> openai.AsyncOpenAI:
    """
    Build a raw openai.AsyncOpenAI client from the same env vars that
    get_ingestion_model() uses, so the provider selection is honoured.
    Using the raw client avoids pydantic_ai's strict ChatCompletion schema
    validation (which rejects non-OpenAI providers that return unknown
    service_tier values).
    """
    # Calling get_ingestion_model() ensures the env-validation side-effects run
    # (e.g. provider check), but we don't need the returned pydantic_ai object.
    get_ingestion_model()
    return openai.AsyncOpenAI(
        base_url=os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1'),
        api_key=os.getenv('LLM_API_KEY', 'none'),
    )


def _get_model_name() -> str:
    ingestion = os.getenv('INGESTION_LLM_CHOICE')
    return ingestion or os.getenv('LLM_CHOICE', 'gpt-4o-mini')


# ---------------------------------------------------------------------------
# LLM classification
# ---------------------------------------------------------------------------

async def classify_group(
    group_key: str,
    docs: list[DocumentRow],
) -> ScopeProposal | None:
    """
    Classify a CPG group. Returns ScopeProposal on success, None on failure.
    Retries once on transient / parse errors.
    """
    logger.info("Classifying CPG: %s (%d rows)", group_key, len(docs))
    summary_content = get_summary_content(group_key, docs)
    user_message = f"CPG name: {group_key}\n\nSummary content:\n{summary_content}"

    client = _get_openai_client()
    model_name = _get_model_name()

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=model_name,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw_text = response.choices[0].message.content or ""
            proposal = parse_scope_proposal(raw_text)

            logger.info(
                "  -> icd11=%s  proc=%s",
                proposal.icd11_scope,
                proposal.procedure_scope,
            )
            return proposal

        except (json.JSONDecodeError, ValidationError) as exc:
            if attempt == 0:
                logger.warning("Attempt 1 parse error for %r: %s — retrying", group_key, exc)
                await asyncio.sleep(2)
            else:
                logger.error("Both attempts failed (parse) for %r: %s", group_key, exc)
                return None

        except ValueError as exc:
            logger.error("Rejected proposal for %r: %s", group_key, exc)
            return None

        except openai.APIError as exc:
            if attempt == 0:
                logger.warning("Attempt 1 API error for %r: %s — retrying", group_key, exc)
                await asyncio.sleep(3)
            else:
                logger.error("Both attempts failed (API) for %r: %s", group_key, exc)
                return None

    return None


# ---------------------------------------------------------------------------
# DB update
# ---------------------------------------------------------------------------

async def update_group_scope(
    conn: asyncpg.Connection,
    docs: list[DocumentRow],
    proposal: ScopeProposal,
    dry_run: bool = False,
) -> int:
    """Write scope columns to DB. Returns number of rows touched."""
    ids = [doc.id for doc in docs]

    if dry_run:
        logger.info("  [dry-run] Would update %d rows", len(ids))
        return len(ids)

    await conn.execute(
        """
        UPDATE documents
        SET icd11_scope     = $1,
            procedure_scope = $2,
            scope_rationale = $3,
            classified_at   = NOW(),
            scope_verified  = FALSE
        WHERE id = ANY($4::uuid[])
        """,
        proposal.icd11_scope,
        proposal.procedure_scope,
        proposal.rationale,
        ids,
    )
    return len(ids)


# ---------------------------------------------------------------------------
# Review file
# ---------------------------------------------------------------------------

def generate_review_file(
    results: list[dict[str, Any]],
    errors: list[str],
    unmappable: list[str],
    output_path: Path,
) -> None:
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    lines: list[str] = [
        f"# CPG Scope Review — generated {ts}",
        "",
        "For each CPG below, mark Approve / Edit / Reject. "
        "The verifier script (Step 04) will parse this file.",
        "",
        "---",
        "",
    ]

    for r in results:
        icd_str = ', '.join(f'`{c}`' for c in r['icd11_scope']) or '(none)'
        proc_str = ', '.join(f'`{c}`' for c in r['procedure_scope']) or '(none)'
        lines += [
            f"## {r['group_key']}",
            f"- Rows updated: {r['rows_updated']}",
            f"- Proposed icd11_scope: {icd_str}",
            f"- Proposed procedure_scope: {proc_str}",
            f"- Rationale: {r['rationale']}",
            "",
            "- [ ] Approve",
            "- [ ] Edit (replace lists above; rationale optional)",
            "- [ ] Reject (mark scope_verified false; do nothing)",
            "",
            "---",
            "",
        ]

    if errors or unmappable:
        lines += ["## Errors", ""]
        if errors:
            lines.append("### Classification failures")
            for e in errors:
                lines.append(f"- {e}")
            lines.append("")
        if unmappable:
            lines.append("### Unmappable rows")
            for u in unmappable:
                lines.append(f"- `{u}`")
            lines.append("")

    output_path.write_text('\n'.join(lines), encoding='utf-8')
    logger.info("Review file written: %s", output_path)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run(
    dry_run: bool = False,
    only: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Run the classifier. Returns (results, errors, unmappable)."""
    conn = await get_db_connection()
    try:
        groups, unmappable = await fetch_document_groups(conn)

        if only:
            groups = {k: v for k, v in groups.items() if k in only}
            logger.info("--only filter applied: %s", list(groups.keys()))

        results: list[dict[str, Any]] = []
        errors: list[str] = []

        for group_key, docs in sorted(groups.items()):
            proposal = await classify_group(group_key, docs)

            if proposal is None:
                errors.append(f"{group_key}: classification failed (both attempts exhausted)")
                continue

            rows_updated = await update_group_scope(conn, docs, proposal, dry_run=dry_run)

            results.append({
                'group_key': group_key,
                'rows_updated': rows_updated,
                'icd11_scope': proposal.icd11_scope,
                'procedure_scope': proposal.procedure_scope,
                'rationale': proposal.rationale,
            })

        logger.info(
            "Done: %d classified, %d errors, %d unmappable",
            len(results), len(errors), len(unmappable),
        )

        if not dry_run:
            review_path = PROJECT_ROOT / 'tasks' / 'cpg_scope_review.md'
            generate_review_file(results, errors, unmappable, review_path)

        return results, errors, unmappable
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Classify CPG ICD-11 scope using LLM'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Discovery + LLM calls only; no DB writes, no review file',
    )
    parser.add_argument(
        '--only',
        type=str,
        default=None,
        help='Comma-separated CPG group keys to process (e.g. "Atrial-Fibrillation(2012)")',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    only = [k.strip() for k in args.only.split(',')] if args.only else None
    asyncio.run(run(dry_run=args.dry_run, only=only))


if __name__ == '__main__':
    main()
