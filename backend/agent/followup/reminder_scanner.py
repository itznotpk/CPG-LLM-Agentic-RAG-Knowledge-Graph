"""Appointment-reminder scanner. Reconciles followup_checkins reminder rows from
each active patient's latest consultations.next_review; the existing
scheduler_worker sends them. No LLM, no Telegram calls here — this module only
decides WHEN a reminder row should exist. Fail-open throughout.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, time, timedelta, timezone

from ..db_utils import supabase_pool as db_pool

logger = logging.getLogger(__name__)

REMINDER_OFFSETS_DAYS = (3, 1)     # 3 days before, then 1 day before
REMINDER_HOUR = 9                  # clinic-local send hour
_MYT = timezone(timedelta(hours=8))  # Malaysia, fixed offset, no DST
POLL_INTERVAL_S = 60
_stop_event = asyncio.Event()
_task: "asyncio.Task | None" = None


def compute_due_at(review_date: date, offset_days: int) -> datetime:
    local = datetime.combine(review_date - timedelta(days=offset_days),
                             time(hour=REMINDER_HOUR), tzinfo=_MYT)
    return local.astimezone(timezone.utc)


def render_reminder(review_date: date, offset_days: int) -> str:
    when = review_date.strftime("%a %d %b")
    if offset_days == 1:
        return (f"Reminder: your review appointment at the clinic is tomorrow, "
                f"{when}. Please contact the clinic if you cannot attend.")
    return (f"Your review appointment at the clinic is on {when}. "
            f"Please contact the clinic if you need to change it.")


_ACTIVE_ENROLLMENTS_SQL = """
    SELECT e.id AS enrollment_id, e.patient_nric,
           (SELECT c.next_review FROM consultations c
             WHERE c.patient_nric = e.patient_nric
               AND c.next_review IS NOT NULL
             ORDER BY c.id DESC LIMIT 1) AS review_date
      FROM followup_enrollments e
     WHERE e.status = 'active'
"""

_INSERT_SQL = """
    INSERT INTO followup_checkins (enrollment_id, kind, question, due_at)
    VALUES ($1, 'reminder', $2, $3)
    ON CONFLICT (enrollment_id, kind, due_at) DO UPDATE
       SET status = 'pending', question = EXCLUDED.question
     WHERE followup_checkins.status = 'cancelled'
"""

_CANCEL_SQL = """
    UPDATE followup_checkins SET status = 'cancelled'
     WHERE kind = 'reminder' AND status = 'pending'
       AND enrollment_id = $1
       AND due_at > $2
       AND due_at <> ALL($3::timestamptz[])
"""


async def scan_due_reminders(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    inserted = 0
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(_ACTIVE_ENROLLMENTS_SQL)
            for row in rows:
                review_date = row["review_date"]
                due_ats: list[datetime] = []
                if review_date and review_date >= now.date():
                    for offset in REMINDER_OFFSETS_DAYS:
                        due_at = compute_due_at(review_date, offset)
                        if due_at >= now:
                            due_ats.append(due_at)
                            res = await conn.execute(
                                _INSERT_SQL, row["enrollment_id"],
                                render_reminder(review_date, offset), due_at,
                            )
                            if isinstance(res, str) and res.endswith("1"):
                                inserted += 1
                await conn.execute(_CANCEL_SQL, row["enrollment_id"], now, due_ats)
    except Exception as exc:
        logger.warning("scan_due_reminders failed (fail-open): %s", exc)
        return 0
    return inserted


async def _loop() -> None:
    while not _stop_event.is_set():
        try:
            await scan_due_reminders()
        except Exception:
            logger.exception("reminder scan tick failed")
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=POLL_INTERVAL_S)
        except asyncio.TimeoutError:
            pass


def start() -> None:
    global _task
    if os.environ.get("FOLLOWUP_WORKER_ENABLED", "true").lower() != "true":
        logger.info("reminder scanner disabled via env")
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("reminder scanner disabled: TELEGRAM_BOT_TOKEN not set")
        return
    if not db_pool.database_url or db_pool.pool is None:
        logger.info("reminder scanner disabled: Supabase pool unavailable")
        return
    _stop_event.clear()
    _task = asyncio.create_task(_loop())
    logger.info("reminder scanner started")


async def stop() -> None:
    global _task
    _stop_event.set()
    if _task:
        await _task
        _task = None
