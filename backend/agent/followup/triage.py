"""Triage agent: deterministic tripwires FIRST, then LLM classification.

Fail-safe philosophy mirrors the pipeline's fail-loud contract: any LLM
failure, parse error, or missing field is treated as ESCALATE. Tripwires are
regex-only and fire even when every LLM is down. The tripwire list is
INTENTIONALLY conservative — negated mentions ("no chest pain") still trip;
a false escalation is cheap, a missed one is not.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel

from ..db_utils import supabase_pool as db_pool

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompts" / "triage_classification.txt").read_text(encoding="utf-8")

_TRIPWIRES: list[tuple[str, re.Pattern]] = [
    (name, re.compile(pat, re.IGNORECASE))
    for name, pat in [
        ("chest_pain", r"\bchest (pain|tight)"),
        ("breathless", r"\b(can'?t|cannot|cant) breathe\b|\bbreathless\b|\bdifficulty breathing\b|\bshort(ness)? of breath\b"),
        ("bleeding", r"\bsevere bleed|\bbleeding (a lot|heavily)\b|\bblood in (stool|urine|vomit)\b"),
        ("collapse", r"\bfaint(ed)?\b|\bpassed out\b|\bcollaps"),
        ("stroke_signs", r"\bone[- ]sided weakness\b|\bslurred speech\b|\bface droop"),
        ("self_harm", r"\bsuicid|\bself[- ]harm|\bend my life\b"),
        ("anaphylaxis", r"\bsevere allerg|\bswelling of (face|throat|tongue)\b"),
    ]
]

TRIPWIRE_REPLY = (
    "Thank you for telling me. Your message may describe something serious — "
    "please call 999 or go to the nearest hospital now. I've alerted your clinic."
)
ESCALATE_FALLBACK_REPLY = (
    "Thank you for your message. I've flagged it for your clinic to review. "
    "If your symptoms feel severe, please call 999 or go to the nearest hospital."
)


class TriageResult(BaseModel):
    classification: Literal["REASSURE", "ADVISE", "ESCALATE"]
    rationale: str
    patient_reply: str


def check_tripwires(text: str) -> str | None:
    for name, pattern in _TRIPWIRES:
        if pattern.search(text):
            return name
    return None


async def _call_llm(system: str, user: str) -> str:
    base_url = os.getenv("FOLLOWUP_LLM_BASE_URL") or os.getenv("GEMINI_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("FOLLOWUP_LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("FOLLOWUP_LLM_MODEL") or "gemini-2.5-flash"
    client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    return (resp.choices[0].message.content or "").strip()


async def classify_reply(plan_context: str, checkin_question: str | None, message: str) -> TriageResult:
    user = json.dumps({
        "plan_context": plan_context,
        "checkin_question": checkin_question,
        "patient_message": message,
    }, ensure_ascii=False)
    try:
        raw = await _call_llm(_PROMPT, user)
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        return TriageResult(**json.loads(raw))
    except Exception as exc:
        logger.warning("triage LLM failed (%s); fail-safe ESCALATE", exc)
        return TriageResult(
            classification="ESCALATE",
            rationale=f"triage_llm_failure: {exc}"[:200],
            patient_reply=ESCALATE_FALLBACK_REPLY,
        )


async def create_alert(enrollment: dict, severity: str, summary: str, patient_reply: str) -> None:
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patient_alerts
                     (enrollment_id, consultation_id, patient_nric, severity, summary, patient_reply)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                enrollment["id"], enrollment.get("consultation_id"),
                enrollment.get("patient_nric"), severity, summary[:300], patient_reply[:1000],
            )
    except Exception as exc:
        logger.warning("create_alert failed (fail-open): %s", exc)
