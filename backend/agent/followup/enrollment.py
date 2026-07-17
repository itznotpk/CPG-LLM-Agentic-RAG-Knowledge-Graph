"""Enrollment lifecycle: token issue → QR scan bind → active protocol → STOP.

One active protocol per patient: binding a new enrollment supersedes any prior
active one for the same NRIC and cancels its pending check-ins (newest plan
governs). All DB writes go through supabase_pool (Supabase, not Neon).
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from ..db_utils import supabase_pool as db_pool
from .telegram_client import deep_link

logger = logging.getLogger(__name__)

TOKEN_TTL_HOURS = 48

# Patient-facing copy. Follows the MHNexus voice: plain English, respectful, no
# decorative emoji, no exclamation marks, no marketing tone. Written as the clinic's
# service ("your care team"), not as a chatty persona.
#
# SAFETY: every message that could be read as "someone is watching" must state the
# opposite. This service is polled, not monitored — a patient who waits for a reply
# instead of calling 999 is the failure mode that matters most.
WELCOME_TEMPLATE = (
    "Hello {first_name}. This is ClearPath, the follow-up service from your clinic.\n\n"
    "Over the next few weeks you will receive a small number of short check-in "
    "questions — about how you are feeling, your medicines, and anything your care "
    "team asked you to watch for. Most take a few seconds to answer, and you can "
    "always reply in your own words.\n\n"
    "Your answers are saved to your clinic record and reviewed by your care team "
    "during clinic hours.\n\n"
    "Please note: these messages are not monitored around the clock, and this is "
    "not an emergency service. If you feel severely unwell, call 999 or go to the "
    "nearest hospital.\n\n"
    "Reply STOP at any time to end these check-ins."
)
# A bare "/start" (Telegram's Start button) carries no token — that is NOT an
# expired link. Telling the patient it expired sends them back to the clinic for
# nothing, so the two cases get different copy.
NO_TOKEN_REPLY = (
    "To begin your check-ins, please scan the QR code provided by your clinic. "
    "That link is what connects this service to your care plan. If you no longer "
    "have it, please ask your clinic for a new one."
)
EXPIRED_LINK_REPLY = (
    "This link has expired or has already been used. Please ask your clinic for a "
    "new QR code."
)
NO_ACTIVE_REPLY = (
    "There is no active follow-up plan linked to this chat, so these messages are "
    "not being reviewed by anyone. Please contact your clinic directly."
)
STOP_CONFIRM_REPLY = (
    "Your check-ins have been stopped and no further messages will be sent. "
    "Please contact your clinic whenever you need them."
)


async def create_enrollment(consultation_id: int, patient_nric: str) -> dict:
    token = secrets.token_urlsafe(24)  # 32 chars
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    async with db_pool.acquire() as conn:
        name_row = await conn.fetchrow(
            "SELECT full_name FROM patients WHERE nric = $1", patient_nric
        )
        first_name = ((name_row or {}).get("full_name") or "").split(" ")[0] or None
        await conn.fetchrow(
            """INSERT INTO followup_enrollments
                 (consultation_id, patient_nric, patient_first_name, token, token_expires_at)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            consultation_id, patient_nric, first_name, token, expires_at,
        )
    return {"token": token, "deep_link": deep_link(token), "expires_at": expires_at.isoformat()}


async def bind_enrollment(token: str, chat_id: int) -> dict | None:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM followup_enrollments WHERE token = $1", token
            )
            if not row or row["status"] != "issued":
                return None
            expires = row["token_expires_at"]
            if expires < datetime.now(timezone.utc):
                return None
            # Supersede prior active enrollments for this patient.
            await conn.execute(
                """UPDATE followup_checkins SET status = 'cancelled'
                    WHERE status = 'pending' AND enrollment_id IN (
                      SELECT id FROM followup_enrollments
                       WHERE patient_nric = $1 AND status = 'active')""",
                row["patient_nric"],
            )
            await conn.execute(
                """UPDATE followup_enrollments SET status = 'superseded'
                    WHERE patient_nric = $1 AND status = 'active'""",
                row["patient_nric"],
            )
            await conn.execute(
                """UPDATE followup_enrollments
                      SET status = 'active', telegram_chat_id = $2, activated_at = now()
                    WHERE id = $1 AND status = 'issued'""",
                row["id"], chat_id,
            )
    result = dict(row)
    result["status"] = "active"
    result["telegram_chat_id"] = chat_id
    result["activated_at"] = datetime.now(timezone.utc)
    return result


async def stop_enrollment(chat_id: int) -> bool:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id FROM followup_enrollments
                WHERE telegram_chat_id = $1 AND status = 'active'
                ORDER BY activated_at DESC LIMIT 1""",
            chat_id,
        )
        if not row:
            return False
        await conn.execute(
            "UPDATE followup_enrollments SET status = 'stopped' WHERE id = $1", row["id"]
        )
        await conn.execute(
            "UPDATE followup_checkins SET status = 'cancelled' WHERE enrollment_id = $1 AND status = 'pending'",
            row["id"],
        )
    return True


async def active_enrollment_for_chat(chat_id: int) -> dict | None:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM followup_enrollments
                WHERE telegram_chat_id = $1 AND status = 'active'
                ORDER BY activated_at DESC LIMIT 1""",
            chat_id,
        )
    return dict(row) if row else None


async def enrollment_status(consultation_id: int) -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT status FROM followup_enrollments
                WHERE consultation_id = $1 ORDER BY created_at DESC LIMIT 1""",
            consultation_id,
        )
    return {"status": row["status"] if row else "none"}


async def log_message(
    enrollment_id: int | None, chat_id: int, direction: str, text: str,
    triage_class: str | None = None, triage_rationale: str | None = None,
) -> None:
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patient_messages
                     (enrollment_id, telegram_chat_id, direction, text, triage_class, triage_rationale)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                enrollment_id, chat_id, direction, text, triage_class, triage_rationale,
            )
    except Exception as exc:
        logger.warning("log_message failed (fail-open): %s", exc)
