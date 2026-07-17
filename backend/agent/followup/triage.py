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

# Patients in Malaysian clinics write English, Malay, Manglish, or a mix, and often
# phonetically (nafas/napas, tak boleh/tak leh). Each hazard carries English AND
# Malay/Manglish alternations under ONE category name, so the clinician-facing
# rationale stays language-neutral. This layer is the only triage that still works
# when every LLM is down — an English-only tripwire set would let "dada saya sakit"
# reach the classifier alone, and reach nothing at all during an outage.
#
# Precision notes (do not "helpfully" broaden these — each was excluded on purpose):
#   - bare "sesak" is congested/crowded ("jalan sesak" = traffic jam); it only means
#     breathless next to nafas/napas, and chest-tight next to dada.
#   - bare "nak mati" is the intensifier idiom "penat nak mati" (tired to death),
#     NOT suicidality. Only explicit "bunuh diri" / "cederakan diri" trip self_harm —
#     a false CRITICAL self-harm alert on an exhausted patient is its own harm.
#   - bare "bengkak" is limb swelling (a routine heart-failure monitoring item);
#     only face/lip/tongue/throat swelling is anaphylaxis.
#   - "got blood" excludes "got blood test/taken/drawn" — a booked blood test is the
#     single most common benign sentence containing the word.
# Malay routinely inserts a possessive or copula between the body part and the
# symptom — "dada saya sakit" (chest my hurts), "dada rasa ketat" (chest feels
# tight) — so body-part patterns tolerate a short, CLOSED filler list. A bare
# `\w+` filler here would start matching across unrelated clauses.
_MS_FILLER = r"(?:\s+(?:saya|aku|ku|dia|rasa|terasa|makin|semakin|dah|sudah|jadi)){0,2}"

_TRIPWIRES: list[tuple[str, re.Pattern]] = [
    (name, re.compile(pat, re.IGNORECASE))
    for name, pat in [
        ("chest_pain",
         r"\bchest (pain|tight)"
         r"|\b(sakit|nyeri|pedih)\s+(di\s+|kat\s+)?dada\b"
         rf"|\bdada{_MS_FILLER}\s+(sakit|nyeri|pedih|sesak|ketat|berat)\b"),
        ("breathless",
         r"\b(can'?t|cannot|cant) breathe\b|\bbreathless\b|\bdifficulty breathing\b|\bshort(ness)? of breath\b"
         r"|\b(sesak|susah|payah|berat)\s+na[fp]as\b"
         rf"|\bna[fp]as{_MS_FILLER}\s+(pendek|berat|sesak)\b"
         r"|\btak\s+(boleh|dapat|le[hk])\s+(berna[fp]as|na[fp]as)\b"
         r"|\btercungap"),
        ("bleeding",
         r"\bsevere bleed|\bbleeding (a lot|heavily)\b|\bblood in (stool|urine|vomit)\b"
         r"|\bgot blood\b(?!\s+(test|tests|taken|drawn|work|sample))"
         r"|\bberdarah\b|\bkeluar darah\b"
         r"|\b(muntah|berak|kencing|batuk)\s+darah\b"),
        ("collapse",
         r"\bfaint(ed)?\b|\bpassed out\b|\bcollaps"
         r"|\bpengsan\b|\bpitam\b|\brebah\b"),
        ("stroke_signs",
         r"\bone[- ]sided weakness\b|\bslurred speech\b|\bface droop"
         r"|\blemah\s+sebelah\b|\bsebelah\s+(badan|kanan|kiri)\s+lemah\b"
         rf"|\b(mulut|muka){_MS_FILLER}\s+senget\b"
         r"|\bcakap\s+(pelat|tak\s+jelas)\b"),
        ("self_harm",
         r"\bsuicid|\bself[- ]harm|\bend my life\b"
         r"|\bbunuh diri\b|\bcedera(kan)?\s+diri\b|\btak\s+(nak|mahu)\s+hidup\b"),
        ("anaphylaxis",
         r"\bsevere allerg|\bswelling of (face|throat|tongue)\b"
         r"|\bbengkak\s+(muka|bibir|lidah|tekak|kerongkong)\b"
         rf"|\b(muka|bibir|lidah|tekak|kerongkong){_MS_FILLER}\s+bengkak\b"
         r"|\balahan\s+(teruk|kuat)\b"),
    ]
]

TRIPWIRE_REPLY = (
    "Thank you for letting us know. Your message may describe something serious. "
    "Please call 999 or go to the nearest hospital now. Your clinic has been alerted."
)
# Deliberately carries NO 999 line: this fires on ANY LLM failure, including for
# plainly benign replies, so a 999 prompt here would over-alarm and desensitise
# patients to TRIPWIRE_REPLY, where it actually means something. Guarded by
# test_reply_constants_differentiate_emergency_guidance — do not "unify" the two.
ESCALATE_FALLBACK_REPLY = (
    "Thank you for your message. It has been flagged for your clinic to review. "
    "If anything feels urgent in the meantime, please contact your clinic directly."
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
        # Gemini 2.5 Flash counts thinking tokens against max_tokens on its
        # OpenAI-compat endpoint; a tight budget truncates the JSON mid-string
        # ("Unterminated string...") and every reply then hits the ESCALATE
        # fail-safe. Same fix as _llm_rerank_ddx. Do not lower.
        max_tokens=8000,
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
