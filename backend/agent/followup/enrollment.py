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

WELCOME_TEMPLATE = (
    "Hi {first_name}! I'm ClearPath, your follow-up companion after today's visit. "
    "I'll check in with you over the coming days. "
    "I am NOT an emergency service — if you feel severely unwell, call 999 or go "
    "to the nearest hospital. Reply STOP anytime to end these check-ins."
)
EXPIRED_LINK_REPLY = "This link has expired — please ask your clinic for a new one."
NO_ACTIVE_REPLY = "I don't have an active follow-up plan for you. Please contact your clinic."
STOP_CONFIRM_REPLY = "Okay — I've stopped your check-ins. Take care, and contact your clinic if you need anything."


async def create_enrollment(consultation_id: int, patient_nric: str) -> dict:
    token = secrets.token_urlsafe(24)  # 32 chars
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    async with db_pool.acquire() as conn:
        name_row = await conn.fetchrow(
            "SELECT name FROM patients WHERE nric = $1", patient_nric
        )
        first_name = ((name_row or {}).get("name") or "").split(" ")[0] or None
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
