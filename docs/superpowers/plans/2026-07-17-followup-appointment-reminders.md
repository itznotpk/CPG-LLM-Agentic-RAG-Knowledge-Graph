# Follow-up Appointment Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send each enrolled patient two one-way appointment reminders (3 days and 1 day before their latest `consultations.next_review`) over the existing ClearPath Telegram bot.

**Architecture:** One new module, `reminder_scanner.py`, periodically reconciles `followup_checkins` rows (`kind='reminder'`) from each active patient's latest review date. It sends nothing — the existing `scheduler_worker.process_one_due` sends the rows verbatim, inheriting retries, opt-out, and the audit log. A lifespan hook starts/stops the scanner alongside the other two follow-up workers.

**Tech Stack:** FastAPI lifespan asyncio worker, asyncpg via `supabase_pool` (Supabase, not Neon), pytest with AsyncMock-mocked pool. No LLM, no new dependency.

**Spec:** `docs/superpowers/specs/2026-07-17-followup-appointment-reminders-design.md` — read it before starting.

## Global Constraints

- **DO NOT COMMIT ANYTHING.** User handles git manually for this project. Every "commit" step in the standard workflow is OMITTED here — stop after the tests pass.
- All paths relative to `CPG LLM/` repo root. PowerShell shell: chain with `;` not `&&`.
- Backend tests run single files as `pytest backend/tests/test_X.py "--override-ini=addopts="` from repo root (skips the coverage gate during iteration). Prefix with `OTEL_TRACING_ENABLED=false` to silence Jaeger connection noise. Full gated suite: `cd backend; pytest`.
- New DB access goes ONLY through `supabase_pool` from `backend/agent/db_utils.py` (imported as `db_pool`). Never the Neon `db_pool`.
- The dedup unique index `uq_followup_checkins_dedup ON followup_checkins (enrollment_id, kind, due_at)` is ALREADY APPLIED to the live DB (migration `add_followup_checkins_dedup_index`, repo copy `frontend/doctor-ui/supabase/add_followup_reminder_dedup_index.sql`). Do not re-apply.
- `followup_checkins.question` is `NOT NULL` and the sender sends it verbatim — the rendered reminder text goes into `question`.
- Reminders are ONE-WAY. No reply path, no confirmation, no booking. A patient reply falls through to existing triage unchanged — do not add handling.
- House style for the reminder text (strict): NO emoji, NO exclamation marks, sentence case, speaks as the clinic. First-name-only PHI: no NRIC, no diagnosis, no drug names in a reminder.
- Fail-open: the scanner must log and swallow any exception, never raise into the lifespan or the pipeline.

---

### Task 1: Reminder text + due-time helpers (pure functions)

**Files:**
- Create: `backend/agent/followup/reminder_scanner.py`
- Test: `backend/tests/test_followup_reminder_scanner.py`

**Interfaces:**
- Produces:
  - `REMINDER_OFFSETS_DAYS = (3, 1)` — days-before-appointment for the two reminders.
  - `REMINDER_HOUR = 9` — clinic-local send hour.
  - `def compute_due_at(review_date: date, offset_days: int) -> datetime` — returns a tz-aware UTC datetime for `review_date - offset_days` at `REMINDER_HOUR` local. (Malaysia has a single fixed offset UTC+8, no DST — subtract 8h from the local wall-clock to get UTC.)
  - `def render_reminder(review_date: date, offset_days: int) -> str` — the patient-facing text. `offset_days == 1` → the "tomorrow" variant; otherwise the dated variant.

- [ ] **Step 1: Write the failing tests**

```python
"""Reminder scanner tests. Pure helpers first, then the DB scan (mocked pool)."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import reminder_scanner as rs


def test_compute_due_at_is_utc_for_malaysia_local_9am():
    # 30 Jun 2026, minus 3 days = 27 Jun 09:00 MYT (UTC+8) = 27 Jun 01:00 UTC
    due = rs.compute_due_at(date(2026, 6, 30), 3)
    assert due == datetime(2026, 6, 27, 1, 0, tzinfo=timezone.utc)


def test_compute_due_at_one_day_offset():
    due = rs.compute_due_at(date(2026, 6, 30), 1)
    assert due == datetime(2026, 6, 29, 1, 0, tzinfo=timezone.utc)


def test_render_reminder_t1_says_tomorrow_and_names_date():
    txt = rs.render_reminder(date(2026, 6, 30), 1)
    assert "tomorrow" in txt.lower()
    assert "30" in txt  # names the day


def test_render_reminder_t3_is_dated_not_tomorrow():
    txt = rs.render_reminder(date(2026, 6, 30), 3)
    assert "tomorrow" not in txt.lower()
    assert "30" in txt


@pytest.mark.parametrize("offset", [3, 1])
def test_render_reminder_obeys_house_style(offset):
    txt = rs.render_reminder(date(2026, 6, 30), offset)
    assert "!" not in txt
    # no emoji (any char above the basic multilingual plane / symbol ranges)
    assert all(ord(c) < 0x2190 for c in txt)
    assert "clinic" in txt.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_reminder_scanner.py "--override-ini=addopts=" -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.followup.reminder_scanner'`

- [ ] **Step 3: Implement the module skeleton + helpers**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_reminder_scanner.py "--override-ini=addopts=" -q`
Expected: 5 passed

---

### Task 2: The reconcile scan (`scan_due_reminders`)

**Files:**
- Modify: `backend/agent/followup/reminder_scanner.py`
- Test: `backend/tests/test_followup_reminder_scanner.py`

**Interfaces:**
- Consumes: `compute_due_at`, `render_reminder`, `REMINDER_OFFSETS_DAYS` (Task 1); `db_pool`.
- Produces: `async def scan_due_reminders(now: datetime | None = None) -> int` — inserts due reminder rows and cancels superseded ones for every active enrollment; returns the count of rows inserted this pass. `now` defaults to `datetime.now(timezone.utc)` (injectable for tests). Fail-open: logs and returns 0 on any exception.

**Behaviour contract (from the spec):**
- Query active enrollments joined to each patient's latest `next_review` (newest consultation by `id`, `next_review NOT NULL`).
- For each with `review_date >= now.date()`: for each offset in `REMINDER_OFFSETS_DAYS`, compute `due_at`; if `due_at >= now`, `INSERT ... ON CONFLICT (enrollment_id, kind, due_at) DO NOTHING`.
- Per enrollment, cancel pending reminders whose `due_at` is not in the just-computed set (empty set ⇒ cancel all pending reminders for that enrollment — a passed/removed appointment). Only touch `status='pending'`.

- [ ] **Step 1: Write the failing tests**

```python
def _scan_pool(enrollment_rows):
    """Pool whose conn.fetch returns the active-enrollment rows; execute is captured."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=enrollment_rows)
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


_NOW = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)


async def test_scan_inserts_two_reminders_for_future_review():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 30)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        n = await rs.scan_due_reminders(_NOW)
    inserts = [c for c in conn.execute.call_args_list if "INSERT" in str(c.args[0]).upper()]
    assert n == 2 and len(inserts) == 2


async def test_scan_skips_past_review_date():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 10)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        n = await rs.scan_due_reminders(_NOW)
    inserts = [c for c in conn.execute.call_args_list if "INSERT" in str(c.args[0]).upper()]
    assert n == 0 and len(inserts) == 0


async def test_scan_cancels_superseded_pending_reminders():
    rows = [{"enrollment_id": 2, "patient_nric": "X", "review_date": date(2026, 6, 30)}]
    pool, conn = _scan_pool(rows)
    with patch.object(rs, "db_pool", pool):
        await rs.scan_due_reminders(_NOW)
    sql = " ".join(str(c.args[0]).lower() for c in conn.execute.call_args_list)
    assert "cancelled" in sql and "pending" in sql


async def test_scan_is_fail_open_on_db_error():
    pool = MagicMock()
    pool.acquire.side_effect = RuntimeError("db down")
    with patch.object(rs, "db_pool", pool):
        assert await rs.scan_due_reminders(_NOW) == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_reminder_scanner.py -k scan "--override-ini=addopts=" -q`
Expected: FAIL — `AttributeError: module 'agent.followup.reminder_scanner' has no attribute 'scan_due_reminders'`

- [ ] **Step 3: Implement `scan_due_reminders`**

```python
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
    ON CONFLICT (enrollment_id, kind, due_at) DO NOTHING
"""

_CANCEL_SQL = """
    UPDATE followup_checkins SET status = 'cancelled'
     WHERE kind = 'reminder' AND status = 'pending'
       AND enrollment_id = $1
       AND due_at <> ALL($2::timestamptz[])
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
                await conn.execute(_CANCEL_SQL, row["enrollment_id"], due_ats)
    except Exception as exc:
        logger.warning("scan_due_reminders failed (fail-open): %s", exc)
        return 0
    return inserted
```

Note: `conn.execute` returns a status string like `"INSERT 0 1"`; `.endswith("1")` counts a real insert vs an `ON CONFLICT` no-op (`"INSERT 0 0"`). The `test_scan_inserts_two_reminders` mock returns an `AsyncMock` (truthy, not a str), so `isinstance(res, str)` is False and `inserted` stays 0 there — **fix the test to make execute return the real string** (see Step 4).

- [ ] **Step 4: Make the insert mock return realistic status strings**

In `_scan_pool`, replace `conn.execute = AsyncMock()` with a side effect that returns the Postgres-style tag so the insert counter works:

```python
    async def _exec(sql, *args):
        return "INSERT 0 1" if "INSERT" in str(sql).upper() else "UPDATE 0"
    conn.execute = AsyncMock(side_effect=_exec)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_reminder_scanner.py "--override-ini=addopts=" -q`
Expected: 9 passed (5 from Task 1 + 4 here)

---

### Task 3: Worker loop + lifespan wiring

**Files:**
- Modify: `backend/agent/followup/reminder_scanner.py` (add `start`/`stop`/`_loop`)
- Modify: `backend/agent/api.py` — imports near line 28, start near line 295, stop near line 313
- Test: `backend/tests/test_followup_reminder_scanner.py`

**Interfaces:**
- Consumes: `scan_due_reminders` (Task 2).
- Produces: `def start() -> None` and `async def stop() -> None` — same signature and env-gating as `scheduler_worker.start`/`stop` (gated on `FOLLOWUP_WORKER_ENABLED != "true"`, `TELEGRAM_BOT_TOKEN` unset, or `db_pool.pool is None` → no-op with an INFO log). `_loop` scans every `POLL_INTERVAL_S`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_start_is_noop_when_worker_disabled(monkeypatch):
    monkeypatch.setenv("FOLLOWUP_WORKER_ENABLED", "false")
    rs._task = None
    rs.start()
    assert rs._task is None


async def test_start_is_noop_without_bot_token(monkeypatch):
    monkeypatch.setenv("FOLLOWUP_WORKER_ENABLED", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rs._task = None
    rs.start()
    assert rs._task is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_reminder_scanner.py -k start "--override-ini=addopts=" -q`
Expected: FAIL — `AttributeError: ... has no attribute 'start'`

- [ ] **Step 3: Implement the loop + start/stop**

Append to `reminder_scanner.py` (mirror `scheduler_worker.py` exactly):

```python
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
    _stop_event.set()
    if _task:
        await _task
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_reminder_scanner.py "--override-ini=addopts=" -q`
Expected: 11 passed

- [ ] **Step 5: Wire into the FastAPI lifespan**

In `backend/agent/api.py`, add the import next to the existing follow-up imports (~line 29):

```python
from .followup import reminder_scanner as followup_reminders
```

In the lifespan startup block, right after `followup_bot_poller.start()` (~line 296):

```python
        followup_reminders.start()
```

In the lifespan shutdown block, right after `await followup_bot_poller.stop()` (~line 314):

```python
        await followup_reminders.stop()
```

- [ ] **Step 6: Smoke that the app imports and the worker gates cleanly**

Run: `cd backend; OTEL_TRACING_ENABLED=false python -c "from agent import api; print('import ok')"`
Expected: prints `import ok` with no traceback.

---

### Task 4: Full-suite gate + docs

**Files:**
- Modify: `CPG LLM/CLAUDE.md` — one line under the "Follow-up ecosystem" section.

- [ ] **Step 1: Run the whole follow-up suite + the new file**

Run:
```
cd backend; OTEL_TRACING_ENABLED=false python -m pytest tests/test_followup_api.py tests/test_followup_bot_poller.py tests/test_followup_enrollment.py tests/test_followup_prep_brief.py tests/test_followup_protocol.py tests/test_followup_scheduler.py tests/test_followup_telegram_client.py tests/test_followup_triage.py tests/test_followup_reminder_scanner.py "--override-ini=addopts=" -q
```
Expected: all pass (the prior 45 + 11 new = 56).

- [ ] **Step 2: Document the reminder scanner in CLAUDE.md**

Under the "Follow-up ecosystem (Telegram companion + triage)" section, add one line noting the third lifespan worker:

```
`reminder_scanner.py` is a THIRD lifespan worker (same env gates): every 60s it reconciles `followup_checkins` rows (`kind='reminder'`) from each active patient's LATEST `consultations.next_review` — two one-way reminders at 3 days and 1 day before, sent by `scheduler_worker` like any check-in (so STOP kills them for free). Real-calendar based, so `FOLLOWUP_TIME_SCALE` cannot compress it; dedup via `uq_followup_checkins_dedup`. `question` column carries the reminder text.
```

- [ ] **Step 3: Confirm the CLAUDE.md gotcha note about `treatment_plan` is still accurate**

No change needed — just verify no reminder claim contradicts existing docs. Done.

---

## Self-review notes

- **Spec coverage:** architecture/scanner → Tasks 1–2; wiring (own module + lifespan, 60s) → Task 3; error/fail-open → Task 2 Step 3 + test; edge cases (past date, superseded, empty set) → Task 2 tests; house style + PHI → Task 1 tests; testing list (6 spec tests) → covered across Tasks 1–2 (date-out, idempotent-via-ON-CONFLICT, moved-date-cancel, past-date, inactive-excluded-by-`WHERE status='active'`, house-style); demo caveat + `question` reuse → documented in CLAUDE.md (Task 4).
- **Idempotent-insert test note:** the `ON CONFLICT` no-op is enforced by the live unique index, not reproducible against the mock; the `.endswith("1")` counter + `_exec` mock exercise the count logic. True idempotency is verified in the live rehearsal, not the unit test — acceptable, matches how the send path is tested.
- **Type consistency:** `scan_due_reminders(now)`, `compute_due_at(review_date, offset_days)`, `render_reminder(review_date, offset_days)`, `REMINDER_OFFSETS_DAYS`, `start`/`stop`/`_loop`/`_stop_event`/`_task`/`POLL_INTERVAL_S` used identically across tasks and mirror `scheduler_worker`'s names.
- **Deferred consciously:** T-3/T-1 both fired same-sitting in a demo needs a manual second insert (spec demo caveat) — not automated.
