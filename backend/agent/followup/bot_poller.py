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
    EXPIRED_LINK_REPLY, NO_ACTIVE_REPLY, STOP_CONFIRM_REPLY, WELCOME_TEMPLATE,
    active_enrollment_for_chat, bind_enrollment, log_message, stop_enrollment,
)
from .protocol import generate_protocol, schedule_checkins
from .telegram_client import get_client
from .triage import (
    TRIPWIRE_REPLY, TriageResult, check_tripwires, classify_reply, create_alert,
)

logger = logging.getLogger(__name__)

_stop_event = asyncio.Event()
_task: asyncio.Task | None = None


async def load_plan(consultation_id: int) -> dict:
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT treatment_plan FROM consultations WHERE id = $1", consultation_id
            )
        raw = (row or {}).get("treatment_plan")
        if isinstance(raw, str):
            return json.loads(raw)
        return dict(raw) if raw else {}
    except Exception as exc:
        logger.warning("load_plan(%s) failed: %s", consultation_id, exc)
        return {}


def plan_context_text(plan: dict) -> str:
    parts = [f"Plan summary: {plan.get('summary', '')}"]
    flags = plan.get("safety_netting") or plan.get("red_flags") or []
    if flags:
        parts.append("Red flags: " + "; ".join(str(f) for f in flags))
    for m in plan.get("monitoring") or []:
        parts.append(f"Monitoring: {m}")
    return "\n".join(parts)[:2000]


async def _handle_start(chat_id: int, text: str) -> None:
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else None
    enrollment = await bind_enrollment(token, chat_id) if token else None
    if not enrollment:
        await get_client().send_message(chat_id, EXPIRED_LINK_REPLY)
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

    if text.split()[0].upper() == "STOP":
        stopped = await stop_enrollment(chat_id)
        await get_client().send_message(chat_id, STOP_CONFIRM_REPLY if stopped else NO_ACTIVE_REPLY)
        return

    enrollment = await active_enrollment_for_chat(chat_id)
    await log_message(enrollment["id"] if enrollment else None, chat_id, "inbound", text)
    if not enrollment:
        await get_client().send_message(chat_id, NO_ACTIVE_REPLY)
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
