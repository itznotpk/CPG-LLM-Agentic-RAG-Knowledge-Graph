"""Background poller for delivery_jobs. Started by FastAPI lifespan."""
from __future__ import annotations

import asyncio
import logging
import os
from uuid import UUID

from .db_utils import supabase_pool as db_pool
from .delivery import deliver_care_plan

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 5
MAX_ATTEMPTS = 3
_stop = asyncio.Event()
_task: asyncio.Task | None = None


async def _claim_job() -> UUID | None:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id FROM delivery_jobs
                 WHERE status = 'queued' AND attempts < $1
                 ORDER BY created_at
                 LIMIT 1
                 FOR UPDATE SKIP LOCKED
                """,
                MAX_ATTEMPTS,
            )
            if not row:
                return None
            return row["id"]


async def _loop() -> None:
    while not _stop.is_set():
        try:
            job_id = await _claim_job()
            if job_id:
                try:
                    await deliver_care_plan(job_id)
                except Exception:
                    logger.exception("delivery job %s crashed", job_id)
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE delivery_jobs
                                  SET status = CASE WHEN attempts >= $2 THEN 'failed' ELSE 'queued' END,
                                      error  = 'worker_exception'
                                WHERE id = $1""",
                            job_id, MAX_ATTEMPTS,
                        )
            else:
                await asyncio.wait_for(_stop.wait(), timeout=POLL_INTERVAL_S)
        except asyncio.TimeoutError:
            pass
        except Exception:
            logger.exception("delivery worker tick failed")
            await asyncio.sleep(POLL_INTERVAL_S)


def start() -> None:
    global _task
    if os.environ.get("DELIVERY_WORKER_ENABLED", "true").lower() != "true":
        logger.info("delivery worker disabled via env")
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())
    logger.info("delivery worker started")


async def stop() -> None:
    _stop.set()
    if _task:
        await _task
