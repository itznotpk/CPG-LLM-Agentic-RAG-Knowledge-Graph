"""Plan → check-in protocol. ONE LLM call at enrollment; sends are deterministic.

Enrollment must never fail on LLM error: fallback_protocol() provides a safe
deterministic 3-item protocol. Caps are enforced server-side after parse.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator

from ..db_utils import supabase_pool as db_pool

logger = logging.getLogger(__name__)

MAX_CHECKINS = 8
MAX_PER_DAY = 2

_PROMPT = (Path(__file__).parent / "prompts" / "protocol_generation.txt").read_text(encoding="utf-8")


class CheckinItem(BaseModel):
    kind: Literal["monitoring", "adherence", "followup"]
    day_offset: int
    question: str

    @field_validator("day_offset")
    @classmethod
    def _clamp_day(cls, v: int) -> int:
        return max(0, min(30, v))

    @field_validator("question")
    @classmethod
    def _cap_question(cls, v: str) -> str:
        return v.strip()[:300]


def _first_red_flag(plan: dict) -> str:
    for key in ("safety_netting", "red_flags"):
        vals = plan.get(key) or []
        if vals:
            return str(vals[0])
    for m in plan.get("monitoring") or []:
        if isinstance(m, dict) and m.get("parameter"):
            return str(m["parameter"])
    return "any new or worsening symptoms"


def fallback_protocol(plan: dict) -> list[CheckinItem]:
    flag = _first_red_flag(plan)
    return [
        CheckinItem(kind="followup", day_offset=0,
                    question="How are you feeling after today's visit? Reply 1 (very well) to 5 (unwell), or describe in your own words."),
        CheckinItem(kind="monitoring", day_offset=3,
                    question=f"Have you noticed: {flag}? Reply 1 (none) to 5 (severe), or describe in your own words."),
        CheckinItem(kind="adherence", day_offset=7,
                    question="Have you been able to take your medicines as planned this week? Reply YES, NO, or tell me what got in the way."),
    ]


async def _call_llm(plan: dict, first_name: str | None) -> dict:
    base_url = os.getenv("FOLLOWUP_LLM_BASE_URL") or os.getenv("GEMINI_BASE_URL") or os.getenv("LLM_BASE_URL")
    api_key = os.getenv("FOLLOWUP_LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("FOLLOWUP_LLM_MODEL") or "gemini-2.5-flash"
    client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": json.dumps({"plan": plan, "patient_first_name": first_name}, ensure_ascii=False)},
        ],
        temperature=0.1,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    return json.loads(raw)


def _apply_caps(items: list[CheckinItem]) -> list[CheckinItem]:
    per_day: dict[int, int] = {}
    out: list[CheckinItem] = []
    for item in sorted(items, key=lambda i: i.day_offset):
        if len(out) >= MAX_CHECKINS:
            break
        if per_day.get(item.day_offset, 0) >= MAX_PER_DAY:
            continue
        per_day[item.day_offset] = per_day.get(item.day_offset, 0) + 1
        out.append(item)
    return out


async def generate_protocol(plan: dict, patient_first_name: str | None) -> list[CheckinItem]:
    try:
        data = await _call_llm(plan, patient_first_name)
        items = [CheckinItem(**c) for c in data.get("checkins", [])]
        if not items:
            raise ValueError("LLM returned zero checkins")
        return _apply_caps(items)
    except Exception as exc:
        logger.warning("protocol LLM failed (%s); using deterministic fallback", exc)
        return fallback_protocol(plan)


def compute_due_at(enrolled_at: datetime, day_offset: int) -> datetime:
    try:
        scale = float(os.getenv("FOLLOWUP_TIME_SCALE", "1") or "1")
    except ValueError:
        scale = 1.0
    if scale <= 0:
        scale = 1.0
    return enrolled_at + timedelta(seconds=day_offset * 86400 / scale)


async def schedule_checkins(enrollment_id: int, items: list[CheckinItem], enrolled_at: datetime) -> int:
    async with db_pool.acquire() as conn:
        for item in items:
            await conn.execute(
                """INSERT INTO followup_checkins (enrollment_id, kind, question, due_at)
                   VALUES ($1, $2, $3, $4)""",
                enrollment_id, item.kind, item.question, compute_due_at(enrolled_at, item.day_offset),
            )
    return len(items)
