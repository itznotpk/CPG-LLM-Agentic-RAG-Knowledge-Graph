"""Telegram long-poller: getUpdates → dispatch. The Companion agent's inbound half.

Dispatch order per message: /start → STOP → tripwires → LLM triage.
Every message both directions is persisted via log_message (audit trail).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from ..db_utils import supabase_pool as db_pool
from .enrollment import (
    EXPIRED_LINK_REPLY, NO_ACTIVE_REPLY, NO_TOKEN_REPLY, STOP_CONFIRM_REPLY,
    WELCOME_TEMPLATE, active_enrollment_for_chat, bind_enrollment, log_message,
    stop_enrollment,
)
from .protocol import generate_protocol, schedule_checkins
from .telegram_client import get_client
from .triage import (
    TRIPWIRE_REPLY, TriageResult, check_tripwires, classify_reply, create_alert,
)

logger = logging.getLogger(__name__)

_stop_event = asyncio.Event()
_task: asyncio.Task | None = None


def _jsonb(value):
    """asyncpg hands JSONB back as str on some codecs, parsed on others."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _plan_from_row(row) -> dict:
    """Reconstruct the plan dict from the decomposed consultations columns.

    There is no consultations.treatment_plan column — the finalized plan is
    persisted section-by-section (care_plan_summary, medication_recommendations,
    monitoring, ...). Rebuild the shape protocol.py / triage expect from those.
    """
    recs: list[dict] = []
    meds = _jsonb(row.get("medication_recommendations")) or {}
    # medication_recommendations is {action: [med, ...]} keyed by start/stop/continue/...
    for action, items in (meds.items() if isinstance(meds, dict) else []):
        for med in items or []:
            name = (med.get("name") or "").strip()
            if not name:
                continue
            dose = (med.get("dose") or "").strip()
            recs.append({
                "intervention": f"{name} — {dose}" if dose else name,
                "recommendation_type": "pharmacological",
                "action": action,
            })
    for ref in _jsonb(row.get("referrals")) or []:
        spec = (ref.get("specialty") or "").strip()
        if spec:
            recs.append({
                "intervention": f"Refer to {spec}",
                "recommendation_type": "referral",
                "action": ref.get("urgency") or "routine",
            })
    for goal in _jsonb(row.get("lifestyle_goals")) or []:
        text = (goal.get("goal") or "").strip()
        if text:
            recs.append({
                "intervention": text,
                "recommendation_type": "lifestyle",
                "action": "advise",
            })

    # Clinician-facing risk headlines. Deliberately NOT mapped to safety_netting:
    # those are drug-interaction concerns ("Enalapril + Spironolactone -
    # hyperkalaemia"), not patient-facing red flags to ask a patient about.
    safety_flags = [
        (f.get("title") or "").strip()
        for f in (_jsonb(row.get("safety_flags")) or [])
        if (f.get("title") or "").strip()
    ]

    follow_up = []
    if row.get("next_review"):
        follow_up.append({"when": str(row["next_review"]), "what": "scheduled review"})

    monitoring = _jsonb(row.get("monitoring")) or []

    # The backend's plan.red_flags is never persisted (update_consultation has no
    # column for it), but the P7 safety-netting trip-wires live in each monitoring
    # item's `target` — recover the patient-facing red flags from there.
    safety_netting = []
    for m in monitoring:
        if not isinstance(m, dict):
            continue
        target = (m.get("target") or "").strip()
        if not target:
            continue
        parameter = (m.get("parameter") or "").strip()
        safety_netting.append(f"{parameter}: {target}" if parameter else target)

    return {
        "summary": row.get("care_plan_summary") or "",
        "recommendations": recs,
        "monitoring": monitoring,
        "follow_up": follow_up,
        "safety_netting": safety_netting,
        "safety_flags": safety_flags,
    }


async def load_plan(consultation_id: int) -> dict:
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT care_plan_summary, medication_recommendations, monitoring,
                          referrals, lifestyle_goals, safety_flags, next_review
                     FROM consultations WHERE id = $1""",
                consultation_id,
            )
        return _plan_from_row(dict(row)) if row else {}
    except Exception as exc:
        logger.warning("load_plan(%s) failed: %s", consultation_id, exc)
        return {}


def plan_context_text(plan: dict) -> str:
    parts = [f"Plan summary: {plan.get('summary', '')}"]
    flags = plan.get("safety_netting") or plan.get("red_flags") or []
    if flags:
        parts.append("Red flags: " + "; ".join(str(f) for f in flags))
    for risk in plan.get("safety_flags") or []:
        parts.append(f"Known risk on this plan: {risk}")
    for m in plan.get("monitoring") or []:
        parts.append(f"Monitoring: {m}")
    return "\n".join(parts)[:2000]


async def _handle_start(chat_id: int, text: str) -> None:
    await log_message(None, chat_id, "inbound", "[/start command]")
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else None
    if not token:
        # Telegram's Start button, not the QR deep link — no token to bind.
        await get_client().send_message(chat_id, NO_TOKEN_REPLY)
        await log_message(None, chat_id, "outbound", NO_TOKEN_REPLY)
        return
    enrollment = await bind_enrollment(token, chat_id)
    if not enrollment:
        await get_client().send_message(chat_id, EXPIRED_LINK_REPLY)
        await log_message(None, chat_id, "outbound", EXPIRED_LINK_REPLY)
        return
    plan = await load_plan(enrollment["consultation_id"])
    items = await generate_protocol(plan, enrollment.get("patient_first_name"))
    from datetime import datetime, timezone
    await schedule_checkins(enrollment["id"], items, datetime.now(timezone.utc))
    welcome = WELCOME_TEMPLATE.format(first_name=enrollment.get("patient_first_name") or "there")
    await get_client().send_message(chat_id, welcome)
    await log_message(enrollment["id"], chat_id, "outbound", welcome)


async def handle_update(update: dict) -> None:
    msg = update.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return

    if text.startswith("/start"):
        await _handle_start(chat_id, text)
        return

    # Accept both the typed word and the /stop command (Telegram's command menu
    # sends the latter). Missing a form routes an opt-out to the LLM as if it
    # were a symptom report, and the patient stays enrolled.
    if text.split()[0].upper().lstrip("/") == "STOP":
        await log_message(None, chat_id, "inbound", text)
        stopped = await stop_enrollment(chat_id)
        reply = STOP_CONFIRM_REPLY if stopped else NO_ACTIVE_REPLY
        await get_client().send_message(chat_id, reply)
        await log_message(None, chat_id, "outbound", reply)
        return

    enrollment = await active_enrollment_for_chat(chat_id)
    await log_message(enrollment["id"] if enrollment else None, chat_id, "inbound", text)
    if not enrollment:
        await get_client().send_message(chat_id, NO_ACTIVE_REPLY)
        await log_message(None, chat_id, "outbound", NO_ACTIVE_REPLY)
        return

    tripwire = check_tripwires(text)
    if tripwire:
        result = TriageResult(
            classification="ESCALATE", rationale=f"tripwire: {tripwire}", patient_reply=TRIPWIRE_REPLY,
        )
        severity = "critical"
    else:
        plan = await load_plan(enrollment["consultation_id"])
        result = await classify_reply(plan_context_text(plan), None, text)
        severity = "major"

    await log_message(enrollment["id"], chat_id, "inbound",
                      f"[triage] {result.classification}", result.classification, result.rationale)
    if result.classification == "ESCALATE":
        await create_alert(enrollment, severity, result.rationale, text)
    await get_client().send_message(chat_id, result.patient_reply)
    await log_message(enrollment["id"], chat_id, "outbound", result.patient_reply)


async def _loop() -> None:
    offset = 0
    backoff = 1
    while not _stop_event.is_set():
        try:
            updates = await get_client().get_updates(offset=offset, timeout=25)
            backoff = 1
            for update in updates:
                offset = max(offset, update.get("update_id", 0) + 1)
                try:
                    await handle_update(update)
                except Exception:
                    logger.exception("handle_update crashed for update %s", update.get("update_id"))
        except Exception:
            logger.exception("bot poller tick failed")
            await asyncio.sleep(min(backoff, 60))
            backoff *= 2


def start() -> None:
    global _task
    if os.environ.get("FOLLOWUP_WORKER_ENABLED", "true").lower() != "true":
        logger.info("bot poller disabled via env")
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("bot poller disabled: TELEGRAM_BOT_TOKEN not set")
        return
    if not db_pool.database_url or db_pool.pool is None:
        logger.info("bot poller disabled: Supabase pool unavailable")
        return
    _stop_event.clear()
    _task = asyncio.create_task(_loop())
    logger.info("bot poller started")


async def stop() -> None:
    _stop_event.set()
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
