"""Background sender for due check-ins. Mirrors delivery_worker.py exactly:
started in FastAPI lifespan, env-gated, isolated from the clinical pipeline.
The send path is fully deterministic — rows were pre-generated at enrollment.
"""
from __future__ import annotations

import asyncio
import logging
import os

from ..db_utils import supabase_pool as db_pool
from .enrollment import log_message
from .telegram_client import get_client

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 3
MAX_ATTEMPTS = 3
_stop_event = asyncio.Event()
_task: asyncio.Task | None = None


async def process_one_due() -> bool:
    """Claim one due pending check-in, send it, mark sent/failed. True if processed."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT c.id, c.enrollment_id, c.question, c.attempts, e.telegram_chat_id
                     FROM followup_checkins c
                     JOIN followup_enrollments e ON e.id = c.enrollment_id
                    WHERE c.status = 'pending' AND c.due_at <= now()
                      AND e.status = 'active' AND c.attempts < $1
                    ORDER BY c.due_at LIMIT 1
                      FOR UPDATE SKIP LOCKED""",
                MAX_ATTEMPTS,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE followup_checkins SET status = 'sending', attempts = attempts + 1 WHERE id = $1",
                row["id"],
            )
    ok = await get_client().send_message(row["telegram_chat_id"], row["question"])
    async with db_pool.acquire() as conn:
        if ok:
            await conn.execute(
                "UPDATE followup_checkins SET status = 'sent', sent_at = now() WHERE id = $1", row["id"]
            )
            await log_message(row["enrollment_id"], row["telegram_chat_id"], "outbound", row["question"])
        else:
            await conn.execute(
                """UPDATE followup_checkins
                      SET status = CASE WHEN attempts >= $2 THEN 'failed' ELSE 'pending' END
                    WHERE id = $1""",
                row["id"], MAX_ATTEMPTS,
            )
    return True


async def _loop() -> None:
    while not _stop_event.is_set():
        try:
            processed = await process_one_due()
            if not processed:
                await asyncio.wait_for(_stop_event.wait(), timeout=POLL_INTERVAL_S)
        except asyncio.TimeoutError:
            pass
        except Exception:
            logger.exception("followup scheduler tick failed")
            await asyncio.sleep(POLL_INTERVAL_S)


def start() -> None:
    global _task
    if os.environ.get("FOLLOWUP_WORKER_ENABLED", "true").lower() != "true":
        logger.info("followup scheduler disabled via env")
        return
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("followup scheduler disabled: TELEGRAM_BOT_TOKEN not set")
        return
    if not db_pool.database_url or db_pool.pool is None:
        logger.info("followup scheduler disabled: Supabase pool unavailable")
        return
    _stop_event.clear()
    _task = asyncio.create_task(_loop())
    logger.info("followup scheduler started")


async def stop() -> None:
    _stop_event.set()
    if _task:
        await _task
