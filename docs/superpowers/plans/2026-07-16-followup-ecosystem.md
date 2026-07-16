# ClearPath Follow-up Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the post-visit loop: a Telegram Companion agent turns each finalized care plan into scheduled check-ins, and a Triage agent classifies patient replies (REASSURE/ADVISE/ESCALATE), escalating to a realtime doctor-dashboard alert and the next visit's prep brief.

**Architecture:** Two new asyncio workers in the FastAPI lifespan (`scheduler_worker` for due check-ins, `bot_poller` for Telegram long-polling) plus a `backend/agent/followup/` package. Protocol generation is one LLM call at enrollment; the send path is deterministic. Triage runs deterministic tripwires before an LLM classifier and fail-safes to ESCALATE. Four new Supabase tables; frontend adds a QR enrollment card and a realtime Patient Alerts panel.

**Tech Stack:** FastAPI + asyncpg (`supabase_pool`), httpx (Telegram Bot API), Gemini Flash via OpenAI-compat, React 18 + Tailwind + supabase-js, `qrcode.react`.

**Spec:** `docs/superpowers/plans/../specs/2026-07-16-followup-ecosystem-design.md` — read it before starting.

## Global Constraints

- **DO NOT COMMIT ANYTHING.** User preference for this project: no `git add`/`git commit` — user handles version control manually. Every "commit" step normally in this workflow is omitted.
- All paths relative to `CPG LLM/` repo root. PowerShell shell: chain with `;` not `&&`.
- Backend tests: run single files as `pytest backend/tests/test_X.py "--override-ini=addopts="` from repo root (skips the coverage gate during iteration). Full gated suite: `cd backend; pytest`.
- New tables live in **Supabase** (not Neon) → backend access ONLY via `supabase_pool` from `backend/agent/db_utils.py`. Frontend access ONLY via supabase-js (`src/lib/supabase.js`) for Supabase reads/writes and `src/lib/clinicalApi.js` for FastAPI calls. Never mix.
- Never touch the `update_consultation` RPC.
- Schema types: `consultation_id INTEGER`, `patient_nric TEXT` (never UUID).
- Env vars (add to `.env`): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `FOLLOWUP_WORKER_ENABLED` (default true), `FOLLOWUP_TIME_SCALE` (default 1; demo 21600), `FOLLOWUP_LLM_MODEL` (default gemini-2.5-flash, falls back to `GEMINI_*` creds like `PREP_BRIEF_LLM_*` does).
- No LLM in the message-send path. Triage fail-safe = ESCALATE. Enrollment never fails on LLM error (deterministic fallback protocol).
- PHI over Telegram: first name only; never NRIC/full name.
- Frontend: no interpolated Tailwind color classes (purge gotcha); theme via `isDark` ternaries; shared components from `src/components/shared`.

---

### Task 1: Supabase migration `add_followup_ecosystem.sql`

**Files:**
- Create: `frontend/doctor-ui/supabase/add_followup_ecosystem.sql`

**Interfaces:**
- Produces: tables `followup_enrollments`, `followup_checkins`, `patient_messages`, `patient_alerts` — column names/types below are the contract every later task uses.

- [ ] **Step 1: Write the migration**

```sql
-- add_followup_ecosystem.sql — Follow-up ecosystem (Companion + Triage agents).
-- Idempotent. Run manually in the Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS followup_enrollments (
  id BIGSERIAL PRIMARY KEY,
  consultation_id INTEGER NOT NULL,
  patient_nric TEXT NOT NULL,
  patient_first_name TEXT,
  token TEXT UNIQUE NOT NULL,
  token_expires_at TIMESTAMPTZ NOT NULL,
  telegram_chat_id BIGINT,
  status TEXT NOT NULL DEFAULT 'issued',   -- issued|active|stopped|superseded
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_followup_enrollments_chat
  ON followup_enrollments (telegram_chat_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_followup_enrollments_nric
  ON followup_enrollments (patient_nric);

CREATE TABLE IF NOT EXISTS followup_checkins (
  id BIGSERIAL PRIMARY KEY,
  enrollment_id BIGINT NOT NULL REFERENCES followup_enrollments(id),
  kind TEXT NOT NULL,                       -- monitoring|adherence|followup
  question TEXT NOT NULL,
  due_at TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending|sending|sent|failed|cancelled
  attempts INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_followup_checkins_due
  ON followup_checkins (due_at) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS patient_messages (
  id BIGSERIAL PRIMARY KEY,
  enrollment_id BIGINT REFERENCES followup_enrollments(id),
  telegram_chat_id BIGINT,
  direction TEXT NOT NULL,                  -- inbound|outbound
  text TEXT NOT NULL,
  triage_class TEXT,                        -- REASSURE|ADVISE|ESCALATE (inbound only)
  triage_rationale TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS patient_alerts (
  id BIGSERIAL PRIMARY KEY,
  enrollment_id BIGINT REFERENCES followup_enrollments(id),
  consultation_id INTEGER,
  patient_nric TEXT,
  severity TEXT NOT NULL,                   -- critical|major
  summary TEXT NOT NULL,
  patient_reply TEXT,
  status TEXT NOT NULL DEFAULT 'open',      -- open|acked
  acked_by TEXT,
  acked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Realtime for the dashboard alerts panel (idempotent guard).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
     WHERE pubname = 'supabase_realtime' AND tablename = 'patient_alerts'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE patient_alerts;
  END IF;
END $$;
```

- [ ] **Step 2: Ask the user to run it**

Tell the user: "Run `frontend/doctor-ui/supabase/add_followup_ecosystem.sql` in the Supabase SQL Editor now — later tasks' live tests depend on the tables existing." Verify afterwards with: `SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'followup%' OR table_name IN ('patient_messages','patient_alerts');` → expect 4 rows.

---

### Task 2: Telegram client (`telegram_client.py`)

**Files:**
- Create: `backend/agent/followup/__init__.py` (empty)
- Create: `backend/agent/followup/telegram_client.py`
- Test: `backend/tests/test_followup_telegram_client.py`

**Interfaces:**
- Produces: `TelegramClient(token: str | None = None)` with `async send_message(chat_id: int, text: str) -> bool` (3 retries, False on final failure, never raises) and `async get_updates(offset: int, timeout: int = 25) -> list[dict]` (empty list on error, never raises). Module fn `get_client() -> TelegramClient` (cached singleton reading `TELEGRAM_BOT_TOKEN`); `deep_link(token: str) -> str` returning `https://t.me/<TELEGRAM_BOT_USERNAME>?start=<token>`.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for followup Telegram client. Network fully mocked via httpx MockTransport."""
import httpx
import pytest

from agent.followup import telegram_client as tc


def _client_with_transport(handler):
    client = tc.TelegramClient(token="TESTTOKEN")
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_send_message_success():
    async def handler(request):
        assert "sendMessage" in str(request.url)
        return httpx.Response(200, json={"ok": True, "result": {}})
    client = _client_with_transport(handler)
    assert await client.send_message(123, "hello") is True


async def test_send_message_retries_then_false():
    calls = {"n": 0}
    async def handler(request):
        calls["n"] += 1
        return httpx.Response(500, json={"ok": False})
    client = _client_with_transport(handler)
    assert await client.send_message(123, "hello") is False
    assert calls["n"] == 3


async def test_get_updates_returns_list_and_never_raises():
    async def handler(request):
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 7}]})
    client = _client_with_transport(handler)
    assert await client.get_updates(offset=0) == [{"update_id": 7}]

    async def broken(request):
        raise httpx.ConnectError("down")
    client2 = _client_with_transport(broken)
    assert await client2.get_updates(offset=0) == []


def test_deep_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    assert tc.deep_link("abc123") == "https://t.me/ClearPathBot?start=abc123"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_telegram_client.py "--override-ini=addopts="`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.followup'`

- [ ] **Step 3: Implement**

```python
"""Thin httpx wrapper for the Telegram Bot API. No LLM, no DB.

Long-polling (getUpdates) — no webhook, no public URL, runs off a laptop.
Both methods are fail-open: they log and return a benign value, never raise,
so a Telegram outage can never take down the clinical pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
SEND_RETRIES = 3


class TelegramClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._http = httpx.AsyncClient(timeout=35.0)

    def _url(self, method: str) -> str:
        return _API.format(token=self.token, method=method)

    async def send_message(self, chat_id: int, text: str) -> bool:
        for attempt in range(1, SEND_RETRIES + 1):
            try:
                r = await self._http.post(
                    self._url("sendMessage"),
                    json={"chat_id": chat_id, "text": text},
                )
                if r.status_code == 200 and r.json().get("ok"):
                    return True
                logger.warning("sendMessage attempt %d failed: HTTP %d", attempt, r.status_code)
            except Exception as exc:
                logger.warning("sendMessage attempt %d error: %s", attempt, exc)
            if attempt < SEND_RETRIES:
                await asyncio.sleep(1.5 * attempt)
        return False

    async def get_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        try:
            r = await self._http.get(
                self._url("getUpdates"),
                params={"offset": offset, "timeout": timeout},
            )
            if r.status_code == 200 and r.json().get("ok"):
                return r.json().get("result", [])
        except Exception as exc:
            logger.warning("getUpdates error: %s", exc)
        return []

    async def aclose(self) -> None:
        await self._http.aclose()


_client: TelegramClient | None = None


def get_client() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client


def deep_link(token: str) -> str:
    username = os.getenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    return f"https://t.me/{username}?start={token}"
```

(Create `backend/agent/followup/__init__.py` as an empty file in the same step.)

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_telegram_client.py "--override-ini=addopts="`
Expected: 4 passed

---

### Task 3: Enrollment (`enrollment.py`)

**Files:**
- Create: `backend/agent/followup/enrollment.py`
- Test: `backend/tests/test_followup_enrollment.py`

**Interfaces:**
- Consumes: `supabase_pool` from `agent.db_utils`; `deep_link` from Task 2.
- Produces:
  - `TOKEN_TTL_HOURS = 48`
  - `async create_enrollment(consultation_id: int, patient_nric: str) -> dict` → `{"token", "deep_link", "expires_at"}` (also fetches `patients.name` first token → `patient_first_name`).
  - `async bind_enrollment(token: str, chat_id: int) -> dict | None` — validates token (exists, `status='issued'`, unexpired); on success supersedes any prior `active` enrollment for the same nric (cancelling its pending check-ins), sets `status='active'`, `telegram_chat_id`, `activated_at`; returns the enrollment row as dict. None on any invalid token.
  - `async stop_enrollment(chat_id: int) -> bool` — active enrollment for chat → `status='stopped'` + cancel pending check-ins; False if none.
  - `async active_enrollment_for_chat(chat_id: int) -> dict | None` — most recent `active` enrollment for that chat_id.
  - `async enrollment_status(consultation_id: int) -> dict` → `{"status": "none"|"issued"|"active"|"stopped"|"superseded"}` (latest row for that consultation).
  - `async log_message(enrollment_id: int | None, chat_id: int, direction: str, text: str, triage_class: str | None = None, triage_rationale: str | None = None) -> None` — insert into `patient_messages`, fail-open.
  - Fixed copy constants: `WELCOME_TEMPLATE`, `EXPIRED_LINK_REPLY`, `NO_ACTIVE_REPLY`, `STOP_CONFIRM_REPLY`.

- [ ] **Step 1: Write the failing tests**

Mock the DB with the same AsyncMock-pool style as `backend/tests/test_delivery.py` (read that file first for the fixture idiom). Test code:

```python
"""Enrollment logic tests. DB mocked — no live Supabase needed."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import enrollment as enr


def _mock_pool(fetchrow_results=None, fetch_results=None):
    """Async context-manager pool whose conn returns queued results."""
    conn = AsyncMock()
    if fetchrow_results is not None:
        conn.fetchrow = AsyncMock(side_effect=list(fetchrow_results))
    conn.fetch = AsyncMock(return_value=fetch_results or [])
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    # conn.transaction() used as async CM too
    tctx = MagicMock()
    tctx.__aenter__ = AsyncMock(return_value=None)
    tctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = tctx
    return pool, conn


async def test_create_enrollment_returns_token_and_deep_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    pool, conn = _mock_pool(fetchrow_results=[{"name": "Ahmad bin Ali"}, {"id": 1}])
    with patch.object(enr, "db_pool", pool):
        out = await enr.create_enrollment(101, "900101-14-5555")
    assert out["deep_link"].startswith("https://t.me/ClearPathBot?start=")
    assert len(out["token"]) >= 32


async def test_bind_rejects_expired_token():
    expired = {
        "id": 1, "status": "issued", "patient_nric": "X",
        "token_expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    pool, conn = _mock_pool(fetchrow_results=[expired])
    with patch.object(enr, "db_pool", pool):
        assert await enr.bind_enrollment("tok", 555) is None


async def test_bind_supersedes_prior_active_and_activates():
    fresh = {
        "id": 2, "status": "issued", "patient_nric": "X",
        "consultation_id": 101, "patient_first_name": "Ahmad",
        "token_expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    pool, conn = _mock_pool(fetchrow_results=[fresh])
    with patch.object(enr, "db_pool", pool):
        row = await enr.bind_enrollment("tok", 555)
    assert row["id"] == 2
    executed_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "superseded" in executed_sql          # prior active rows superseded
    assert "cancelled" in executed_sql            # their pending check-ins cancelled
    assert "active" in executed_sql               # this row activated


async def test_stop_enrollment_cancels_pending():
    active = {"id": 3}
    pool, conn = _mock_pool(fetchrow_results=[active])
    with patch.object(enr, "db_pool", pool):
        assert await enr.stop_enrollment(555) is True
    executed_sql = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "stopped" in executed_sql and "cancelled" in executed_sql
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_enrollment.py "--override-ini=addopts="`
Expected: FAIL — `cannot import name 'enrollment'`

- [ ] **Step 3: Implement**

```python
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
                    WHERE id = $1""",
                row["id"], chat_id,
            )
    return dict(row)


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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_enrollment.py "--override-ini=addopts="`
Expected: 4 passed. If the mock's `dict(row)` calls fail, make the fixtures plain dicts (as shown) — the implementation calls `dict(row)` which is a no-op on dicts.

---

### Task 4: Protocol generation (`protocol.py` + prompt)

**Files:**
- Create: `backend/agent/followup/protocol.py`
- Create: `backend/agent/followup/prompts/protocol_generation.txt`
- Test: `backend/tests/test_followup_protocol.py`

**Interfaces:**
- Consumes: `supabase_pool`; env `FOLLOWUP_LLM_MODEL` / `FOLLOWUP_TIME_SCALE`; plan dict (a serialized `TreatmentPlan`: keys `summary`, `recommendations` (each with `intervention`, `recommendation_type`, `action`), `monitoring`, `follow_up`).
- Produces:
  - `class CheckinItem(BaseModel)`: `kind: Literal["monitoring","adherence","followup"]`, `day_offset: int` (clamped 0–30), `question: str` (≤300 chars).
  - `MAX_CHECKINS = 8`, `MAX_PER_DAY = 2`
  - `def fallback_protocol(plan: dict) -> list[CheckinItem]` — deterministic 3 items (day 0 general, day 3 red-flag check naming first red-flag text found in plan, day 7 adherence).
  - `async generate_protocol(plan: dict, patient_first_name: str | None) -> list[CheckinItem]` — LLM call, falls back to `fallback_protocol` on ANY failure; result clamped to caps.
  - `def compute_due_at(enrolled_at: datetime, day_offset: int) -> datetime` — `enrolled_at + timedelta(seconds=day_offset*86400/FOLLOWUP_TIME_SCALE)`.
  - `async schedule_checkins(enrollment_id: int, items: list[CheckinItem], enrolled_at: datetime) -> int` — inserts rows into `followup_checkins`, returns count.

- [ ] **Step 1: Write the prompt file** `backend/agent/followup/prompts/protocol_generation.txt`

```text
You convert a clinician-approved care plan into short follow-up check-in questions
sent to the patient over Telegram.

RULES:
1. Output STRICT JSON: {"checkins": [{"kind": "...", "day_offset": N, "question": "..."}]}
   kind is one of: monitoring, adherence, followup. day_offset is an integer 0-30.
2. Max 8 check-ins total, max 2 per day. Always include a day 0 item ("How are you
   feeling after today's visit?" style) and at least one adherence item.
3. Each question <= 300 characters, plain patient-friendly language (no medical
   jargon, no drug mechanism talk), and MUST end with a clear reply instruction,
   e.g. "Reply 1 (none) to 5 (severe), or describe in your own words."
4. Base monitoring questions ONLY on the plan's monitoring items and safety-netting
   red flags. Base adherence questions ONLY on medications the plan starts, changes,
   or continues. Do NOT invent symptoms, drugs, doses, or schedules not in the plan.
5. Never include the patient's surname, NRIC, or any identifier in a question.
6. Do not give advice in questions. Questions only.
```

- [ ] **Step 2: Write the failing tests**

```python
"""Protocol generation tests. LLM mocked; caps and fallback exercised."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import protocol as proto

PLAN = {
    "summary": "HFrEF optimisation",
    "recommendations": [
        {"intervention": "[START] Bisoprolol 2.5 mg OD", "recommendation_type": "pharmacological", "action": "start"},
    ],
    "monitoring": [{"parameter": "weight", "schedule": "daily for 2 weeks"}],
    "follow_up": [{"when": "2 weeks", "what": "review symptoms"}],
    "safety_netting": ["Worsening breathlessness at rest", "Ankle swelling"],
}


def test_fallback_protocol_shape():
    items = proto.fallback_protocol(PLAN)
    assert len(items) == 3
    assert items[0].day_offset == 0
    assert any(i.kind == "adherence" for i in items)
    # red-flag text surfaces in the day-3 question
    assert "breathless" in items[1].question.lower() or "swelling" in items[1].question.lower()


async def test_generate_protocol_falls_back_on_llm_error():
    with patch.object(proto, "_call_llm", AsyncMock(side_effect=RuntimeError("down"))):
        items = await proto.generate_protocol(PLAN, "Ahmad")
    assert len(items) == 3  # the fallback


async def test_generate_protocol_clamps_caps():
    raw = {"checkins": [
        {"kind": "monitoring", "day_offset": d, "question": f"Q{d}? Reply 1-5."}
        for d in range(20)
    ]}
    with patch.object(proto, "_call_llm", AsyncMock(return_value=raw)):
        items = await proto.generate_protocol(PLAN, "Ahmad")
    assert len(items) <= proto.MAX_CHECKINS
    assert all(0 <= i.day_offset <= 30 for i in items)


def test_compute_due_at_respects_time_scale(monkeypatch):
    t0 = datetime(2026, 7, 16, tzinfo=timezone.utc)
    monkeypatch.setenv("FOLLOWUP_TIME_SCALE", "1")
    assert (proto.compute_due_at(t0, 3) - t0).total_seconds() == 3 * 86400
    monkeypatch.setenv("FOLLOWUP_TIME_SCALE", "21600")
    assert (proto.compute_due_at(t0, 3) - t0).total_seconds() == pytest.approx(12.0)
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest backend/tests/test_followup_protocol.py "--override-ini=addopts="`
Expected: FAIL — module not found

- [ ] **Step 4: Implement**

```python
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
    scale = float(os.getenv("FOLLOWUP_TIME_SCALE", "1") or "1")
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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_protocol.py "--override-ini=addopts="`
Expected: 4 passed

---

### Task 5: Triage agent (`triage.py` + prompt)

**Files:**
- Create: `backend/agent/followup/triage.py`
- Create: `backend/agent/followup/prompts/triage_classification.txt`
- Test: `backend/tests/test_followup_triage.py`

**Interfaces:**
- Consumes: `supabase_pool`; same LLM env resolution as Task 4.
- Produces:
  - `class TriageResult(BaseModel)`: `classification: Literal["REASSURE","ADVISE","ESCALATE"]`, `rationale: str`, `patient_reply: str`.
  - `def check_tripwires(text: str) -> str | None` — returns tripwire name or None. Intentionally conservative: fires even inside negations ("no chest pain" trips) — documented as intended.
  - `TRIPWIRE_REPLY` (canned, includes "call 999"), `ESCALATE_FALLBACK_REPLY` (canned, no 999 line).
  - `async classify_reply(plan_context: str, checkin_question: str | None, message: str) -> TriageResult` — LLM; ANY failure → `TriageResult(classification="ESCALATE", rationale="triage_llm_failure: <err>", patient_reply=ESCALATE_FALLBACK_REPLY)`.
  - `async create_alert(enrollment: dict, severity: str, summary: str, patient_reply: str) -> None` — inserts `patient_alerts` row, fail-open.

- [ ] **Step 1: Write the prompt file** `backend/agent/followup/prompts/triage_classification.txt`

```text
You are a follow-up triage classifier for a clinic. You receive one patient
message plus the patient's own clinician-approved care plan context. Classify
the message and draft a short reply.

OUTPUT: strict JSON {"classification": "...", "rationale": "...", "patient_reply": "..."}
classification is exactly one of REASSURE, ADVISE, ESCALATE.

RULES (in priority order):
1. ESCALATE if the message plausibly matches any red flag in the plan context,
   describes new/worsening symptoms, mentions medication side effects, or is
   ambiguous but medical. When unsure, ESCALATE. ESCALATE replies must tell the
   patient their clinic has been notified and to call 999 if symptoms are severe.
2. ADVISE only when the answer is fully contained in the plan context. You may
   ONLY restate instructions already in this patient's plan. NEVER suggest a new
   drug, a dose change, a diagnosis, or any probability/prognosis estimate.
3. REASSURE for clearly benign content: numeric scale replies of 1-2, adherence
   confirmations, thanks/acknowledgements, non-medical chit-chat.
4. Numeric scale replies: 1-2 REASSURE; 3 ADVISE (restate the plan's relevant
   instruction and what to watch for); 4-5 ESCALATE.
5. patient_reply <= 400 characters, warm, plain language, no jargon, no patient
   identifiers, and never contradicts the plan.
6. rationale <= 200 characters, for the clinician audit trail.
```

- [ ] **Step 2: Write the failing tests**

```python
"""Triage tests: tripwires, LLM parse, fail-safe ESCALATE, scale routing."""
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import triage as tr


def test_tripwires_hit_and_miss():
    assert tr.check_tripwires("I have chest pain tonight") is not None
    assert tr.check_tripwires("CANT BREATHE properly") is not None
    assert tr.check_tripwires("feeling much better today") is None
    # Conservative by design: negations still trip.
    assert tr.check_tripwires("no chest pain at all") is not None


async def test_classify_reply_parses_valid_json():
    raw = '{"classification": "REASSURE", "rationale": "scale 1", "patient_reply": "Great to hear!"}'
    with patch.object(tr, "_call_llm", AsyncMock(return_value=raw)):
        result = await tr.classify_reply("plan ctx", "How are you?", "1")
    assert result.classification == "REASSURE"


async def test_classify_reply_failsafe_escalates_on_bad_json():
    with patch.object(tr, "_call_llm", AsyncMock(return_value="not json at all")):
        result = await tr.classify_reply("plan ctx", None, "hmm")
    assert result.classification == "ESCALATE"
    assert result.patient_reply == tr.ESCALATE_FALLBACK_REPLY


async def test_classify_reply_failsafe_escalates_on_exception():
    with patch.object(tr, "_call_llm", AsyncMock(side_effect=TimeoutError("slow"))):
        result = await tr.classify_reply("plan ctx", None, "hmm")
    assert result.classification == "ESCALATE"
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest backend/tests/test_followup_triage.py "--override-ini=addopts="`
Expected: FAIL — module not found

- [ ] **Step 4: Implement**

```python
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

_TRIPWIRES: list[tuple[str, re.Pattern]] = [
    (name, re.compile(pat, re.IGNORECASE))
    for name, pat in [
        ("chest_pain", r"\bchest (pain|tight)"),
        ("breathless", r"\b(can'?t|cannot|cant) breathe\b|\bbreathless\b|\bdifficulty breathing\b|\bshort(ness)? of breath\b"),
        ("bleeding", r"\bsevere bleed|\bbleeding (a lot|heavily)\b|\bblood in (stool|urine|vomit)\b"),
        ("collapse", r"\bfaint(ed)?\b|\bpassed out\b|\bcollaps"),
        ("stroke_signs", r"\bone[- ]sided weakness\b|\bslurred speech\b|\bface droop"),
        ("self_harm", r"\bsuicid|\bself[- ]harm|\bend my life\b"),
        ("anaphylaxis", r"\bsevere allerg|\bswelling of (face|throat|tongue)\b"),
    ]
]

TRIPWIRE_REPLY = (
    "Thank you for telling me. Your message may describe something serious — "
    "please call 999 or go to the nearest hospital now. I've alerted your clinic."
)
ESCALATE_FALLBACK_REPLY = (
    "Thank you for your message. I've flagged it for your clinic to review. "
    "If your symptoms feel severe, please call 999 or go to the nearest hospital."
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
        max_tokens=600,
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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_triage.py "--override-ini=addopts="`
Expected: 4 passed

---

### Task 6: Scheduler worker (`scheduler_worker.py`)

**Files:**
- Create: `backend/agent/followup/scheduler_worker.py`
- Test: `backend/tests/test_followup_scheduler.py`

**Interfaces:**
- Consumes: `supabase_pool`; `get_client().send_message` (Task 2); `log_message` (Task 3).
- Produces: `start() -> None` / `async stop() -> None` (delivery_worker signature, gated on `FOLLOWUP_WORKER_ENABLED` + `TELEGRAM_BOT_TOKEN` + pool health); `async process_one_due() -> bool` (exported for tests + the simulate-due endpoint; claims one due pending check-in, sends it, marks sent/failed; returns True if one was processed).

- [ ] **Step 1: Write the failing tests**

```python
"""Scheduler worker: claim → send → mark. DB and Telegram mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.followup import scheduler_worker as sw


def _pool(due_row):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=due_row)
    conn.execute = AsyncMock()
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    tctx = MagicMock()
    tctx.__aenter__ = AsyncMock(return_value=None)
    tctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = tctx
    return pool, conn


async def test_process_one_due_sends_and_marks_sent():
    due = {"id": 9, "enrollment_id": 2, "question": "How are you? Reply 1-5.",
           "telegram_chat_id": 555, "attempts": 0}
    pool, conn = _pool(due)
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(sw, "db_pool", pool), patch.object(sw, "get_client", lambda: tg), \
         patch.object(sw, "log_message", AsyncMock()):
        assert await sw.process_one_due() is True
    tg.send_message.assert_awaited_once_with(555, "How are you? Reply 1-5.")
    executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "sent" in executed


async def test_process_one_due_marks_failed_after_send_failure():
    due = {"id": 9, "enrollment_id": 2, "question": "Q", "telegram_chat_id": 555, "attempts": 2}
    pool, conn = _pool(due)
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=False)
    with patch.object(sw, "db_pool", pool), patch.object(sw, "get_client", lambda: tg), \
         patch.object(sw, "log_message", AsyncMock()):
        assert await sw.process_one_due() is True
    executed = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "failed" in executed or "attempts" in executed


async def test_process_one_due_noop_when_nothing_due():
    pool, conn = _pool(None)
    with patch.object(sw, "db_pool", pool):
        assert await sw.process_one_due() is False
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_scheduler.py "--override-ini=addopts="`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_scheduler.py "--override-ini=addopts="`
Expected: 3 passed

---

### Task 7: Bot poller (`bot_poller.py`)

**Files:**
- Create: `backend/agent/followup/bot_poller.py`
- Test: `backend/tests/test_followup_bot_poller.py`

**Interfaces:**
- Consumes: everything from Tasks 2–5.
- Produces: `start()`/`async stop()` (same worker signature); `async handle_update(update: dict) -> None` (exported for tests) implementing the full inbound dispatch: `/start <token>` → bind + protocol + welcome; `STOP` → stop; anything else → log + tripwire/triage → reply (+ alert on ESCALATE); `async load_plan(consultation_id: int) -> dict` (reads `consultations.treatment_plan` JSONB via supabase_pool, `{}` on any failure); `def plan_context_text(plan: dict) -> str` (summary + red flags + monitoring, ≤2000 chars, for the triage prompt).

- [ ] **Step 1: Write the failing tests**

```python
"""Bot poller dispatch tests. All collaborators mocked."""
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import bot_poller as bp
from agent.followup.triage import TriageResult

ENROLLMENT = {"id": 2, "consultation_id": 101, "patient_nric": "X",
              "patient_first_name": "Ahmad", "telegram_chat_id": 555}


def _update(text):
    return {"update_id": 1, "message": {"chat": {"id": 555}, "text": text}}


async def test_start_with_valid_token_binds_and_schedules():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "bind_enrollment", AsyncMock(return_value=ENROLLMENT)) as bind, \
         patch.object(bp, "load_plan", AsyncMock(return_value={"summary": "s"})), \
         patch.object(bp, "generate_protocol", AsyncMock(return_value=[])), \
         patch.object(bp, "schedule_checkins", AsyncMock(return_value=0)) as sched, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("/start tok123"))
    bind.assert_awaited_once_with("tok123", 555)
    sched.assert_awaited_once()
    assert tg.send_message.await_count >= 1  # welcome sent


async def test_start_with_bad_token_sends_expired_reply():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "bind_enrollment", AsyncMock(return_value=None)), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("/start nope"))
    sent = tg.send_message.await_args.args[1]
    assert "expired" in sent.lower()


async def test_tripwire_reply_escalates_without_llm():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    classify = AsyncMock()
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=ENROLLMENT)), \
         patch.object(bp, "load_plan", AsyncMock(return_value={})), \
         patch.object(bp, "classify_reply", classify), \
         patch.object(bp, "create_alert", AsyncMock()) as alert, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("I have chest pain"))
    classify.assert_not_awaited()          # tripwire short-circuits the LLM
    alert.assert_awaited_once()
    assert alert.await_args.args[1] == "critical"


async def test_normal_reply_goes_through_triage_and_alerts_on_escalate():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    result = TriageResult(classification="ESCALATE", rationale="worsening", patient_reply="Flagged.")
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=ENROLLMENT)), \
         patch.object(bp, "load_plan", AsyncMock(return_value={"summary": "s"})), \
         patch.object(bp, "classify_reply", AsyncMock(return_value=result)), \
         patch.object(bp, "create_alert", AsyncMock()) as alert, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("feeling more tired and swollen"))
    alert.assert_awaited_once()
    assert alert.await_args.args[1] == "major"


async def test_no_active_enrollment_gets_fixed_reply():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=None)), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("hello?"))
    sent = tg.send_message.await_args.args[1]
    assert "active follow-up plan" in sent
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_bot_poller.py "--override-ini=addopts="`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

```python
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
```

Note: `stop()` cancels rather than awaiting, because `get_updates` long-polls for 25 s.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_bot_poller.py "--override-ini=addopts="`
Expected: 5 passed

---

### Task 8: API endpoints + lifespan wiring

**Files:**
- Modify: `backend/agent/api.py` — add 3 endpoints near the delivery endpoints (~line 2180 region) + worker start/stop in `lifespan` (line ~290 `start_delivery_worker()` and ~306 `stop_delivery_worker()`)
- Test: `backend/tests/test_followup_api.py`

**Interfaces:**
- Consumes: `create_enrollment`, `enrollment_status` (Task 3); `process_one_due` (Task 6); worker `start`/`stop` from Tasks 6–7.
- Produces: `POST /followup/enroll` (body `{consultation_id: int, patient_nric: str}` → `{token, deep_link, expires_at}`); `GET /followup/status/{consultation_id}` → `{status}`; `POST /followup/simulate-due` (dev-only: 404 unless `FOLLOWUP_DEMO_MODE=true`; forces the earliest pending check-in due now, then processes it).

- [ ] **Step 1: Write the failing tests**

```python
"""Followup API endpoint tests via FastAPI TestClient with mocked internals."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from agent.api import app
    return TestClient(app, raise_server_exceptions=False)


def test_enroll_returns_deep_link(client):
    payload = {"token": "t", "deep_link": "https://t.me/B?start=t", "expires_at": "2026-07-18T00:00:00+00:00"}
    with patch("agent.api.create_followup_enrollment", AsyncMock(return_value=payload)):
        r = client.post("/followup/enroll", json={"consultation_id": 101, "patient_nric": "X"})
    assert r.status_code == 200
    assert r.json()["deep_link"].startswith("https://t.me/")


def test_status_endpoint(client):
    with patch("agent.api.get_followup_status", AsyncMock(return_value={"status": "active"})):
        r = client.get("/followup/status/101")
    assert r.status_code == 200
    assert r.json() == {"status": "active"}


def test_simulate_due_is_gated(client, monkeypatch):
    monkeypatch.delenv("FOLLOWUP_DEMO_MODE", raising=False)
    r = client.post("/followup/simulate-due")
    assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_api.py "--override-ini=addopts="`
Expected: FAIL — 404 on /followup/enroll (route not defined) or AttributeError patching names

- [ ] **Step 3: Implement in `api.py`**

Imports at the top of `api.py` (aliased so the tests can patch them on the api module):

```python
from .followup.enrollment import create_enrollment as create_followup_enrollment
from .followup.enrollment import enrollment_status as get_followup_status
from .followup import scheduler_worker as followup_scheduler
from .followup import bot_poller as followup_bot_poller
```

Endpoints (place after the delivery endpoints):

```python
class FollowupEnrollRequest(_BaseModel):
    consultation_id: int
    patient_nric: str


@app.post("/followup/enroll")
async def followup_enroll(request: FollowupEnrollRequest):
    """Issue a one-time Telegram deep-link token for post-visit follow-up."""
    try:
        return await create_followup_enrollment(request.consultation_id, request.patient_nric)
    except Exception as e:
        logger.error("followup enroll failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/followup/status/{consultation_id}")
async def followup_status(consultation_id: int):
    try:
        return await get_followup_status(consultation_id)
    except Exception as e:
        logger.error("followup status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/followup/simulate-due")
async def followup_simulate_due():
    """Demo insurance: force the earliest pending check-in due now, then send it.
    Hidden unless FOLLOWUP_DEMO_MODE=true."""
    if os.environ.get("FOLLOWUP_DEMO_MODE", "").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    from .db_utils import supabase_pool as _pool
    async with _pool.acquire() as conn:
        await conn.execute(
            """UPDATE followup_checkins SET due_at = now()
                WHERE id = (SELECT id FROM followup_checkins
                             WHERE status = 'pending' ORDER BY due_at LIMIT 1)"""
        )
    processed = await followup_scheduler.process_one_due()
    return {"processed": processed}
```

Lifespan wiring — immediately after `start_delivery_worker()` (line ~290):

```python
        followup_scheduler.start()
        followup_bot_poller.start()
```

and in the shutdown block, immediately after `await stop_delivery_worker()` (line ~306):

```python
        await followup_scheduler.stop()
        await followup_bot_poller.stop()
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest backend/tests/test_followup_api.py "--override-ini=addopts="`
Expected: 3 passed

- [ ] **Step 5: Smoke the server boots**

Run: `cd backend; python -c "import agent.api"` → no import errors. Then start `python -m agent.api` briefly and confirm log lines `followup scheduler disabled: TELEGRAM_BOT_TOKEN not set` (or `started` if token configured) appear and the app serves `/health`.

---

### Task 9: Prep-brief injection (closing the loop)

**Files:**
- Modify: `backend/agent/clinical_stages.py:6043-6113` (`generate_prep_brief`)
- Modify: `backend/agent/api.py:904-924` (`prep_brief` endpoint)
- Modify: `backend/agent/prompts/prep_brief.txt` (one added rule line)
- Test: `backend/tests/test_followup_prep_brief.py`

**Interfaces:**
- Consumes: `patient_alerts` / `patient_messages` tables; existing `generate_prep_brief` signature.
- Produces: `generate_prep_brief(..., followup_alerts: list | None = None, checkin_digest: str | None = None)` — two NEW optional keyword params appended to the existing signature (existing callers unaffected); new helper in api.py `async _load_followup_context(patient_nric: str) -> tuple[list, str | None]` (fail-open: `([], None)` on any error/empty tables).

- [ ] **Step 1: Write the failing tests**

```python
"""Prep-brief injection: alerts reach the LLM payload; empty tables = today's behavior."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import generate_prep_brief


async def test_alerts_included_in_llm_payload(monkeypatch):
    captured = {}

    class FakeResp:
        class Choice:
            class Msg:
                content = '{"since_last_visit": "ok", "med_flags": null, "ask_today": null}'
            message = Msg()
        choices = [Choice()]

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return FakeResp()

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create
    with patch("agent.clinical_stages._make_openai_client", return_value=fake_client):
        await generate_prep_brief(
            prior_visit={"what_changed": "x"}, current_medications=[],
            patient_age=60, patient_sex="M", comorbidities=[],
            followup_alerts=[{"severity": "critical", "summary": "tripwire: breathless", "created_at": "2026-07-14"}],
            checkin_digest="3 check-ins sent, 2 replies, 1 escalation",
        )
    user_payload = captured["messages"][1]["content"]
    assert "breathless" in user_payload
    assert "escalation" in user_payload


async def test_no_followup_args_behaves_as_today():
    """Omitting the new kwargs must not change the payload shape (regression guard)."""
    captured = {}

    class FakeResp:
        class Choice:
            class Msg:
                content = '{"since_last_visit": "ok", "med_flags": null, "ask_today": null}'
            message = Msg()
        choices = [Choice()]

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return FakeResp()

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create
    with patch("agent.clinical_stages._make_openai_client", return_value=fake_client):
        out = await generate_prep_brief(
            prior_visit={"what_changed": "x"}, current_medications=[],
            patient_age=60, patient_sex="M", comorbidities=[],
        )
    assert "followup" not in captured["messages"][1]["content"]
    assert set(out.keys()) == {"since_last_visit", "med_flags", "ask_today"}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest backend/tests/test_followup_prep_brief.py "--override-ini=addopts="`
Expected: FAIL — `TypeError: generate_prep_brief() got an unexpected keyword argument 'followup_alerts'`

- [ ] **Step 3: Implement**

In `clinical_stages.py`, change the signature (append two optional kwargs):

```python
async def generate_prep_brief(
    prior_visit: dict,
    current_medications: list,
    patient_age: int | None,
    patient_sex: str | None,
    comorbidities: list[str] | None,
    followup_alerts: list | None = None,
    checkin_digest: str | None = None,
) -> dict:
```

And extend the payload construction (the `payload = json.dumps({...})` block):

```python
    payload_dict = {
        "prior_visit": prior_visit,
        "current_medications": current_medications or [],
        "patient": {
            "age": patient_age,
            "sex": patient_sex,
            "comorbidities": comorbidities or [],
        },
    }
    if followup_alerts:
        payload_dict["followup_alerts"] = followup_alerts
    if checkin_digest:
        payload_dict["followup_checkin_digest"] = checkin_digest
    payload = json.dumps(payload_dict, ensure_ascii=False)
```

Append ONE rule line to `backend/agent/prompts/prep_brief.txt` (keep all existing content untouched):

```text
If followup_alerts is present, since_last_visit MUST lead with the most severe alert (e.g. "Reported breathlessness day 3 — escalated").
```

In `api.py`, add the loader helper above the `prep_brief` endpoint and wire it in:

```python
async def _load_followup_context(patient_nric: str) -> tuple[list, str | None]:
    """Open alerts + check-in digest for the prep brief. Fail-open: ([], None)."""
    try:
        from .db_utils import supabase_pool as _pool
        async with _pool.acquire() as conn:
            alerts = await conn.fetch(
                """SELECT severity, summary, patient_reply, status, created_at::text
                     FROM patient_alerts
                    WHERE patient_nric = $1 AND created_at > now() - interval '30 days'
                    ORDER BY created_at DESC LIMIT 5""",
                patient_nric,
            )
            stats = await conn.fetchrow(
                """SELECT count(*) FILTER (WHERE direction = 'outbound') AS sent,
                          count(*) FILTER (WHERE direction = 'inbound') AS replies,
                          count(*) FILTER (WHERE triage_class = 'ESCALATE') AS escalations
                     FROM patient_messages m
                     JOIN followup_enrollments e ON e.id = m.enrollment_id
                    WHERE e.patient_nric = $1 AND m.created_at > now() - interval '30 days'""",
                patient_nric,
            )
        digest = None
        if stats and (stats["sent"] or stats["replies"]):
            digest = (f"{stats['sent']} check-ins sent, {stats['replies']} replies, "
                      f"{stats['escalations']} escalation(s)")
        return [dict(a) for a in alerts], digest
    except Exception as exc:
        logger.warning("followup context load failed (fail-open): %s", exc)
        return [], None
```

In the `prep_brief` endpoint body, before calling `generate_prep_brief`:

```python
        followup_alerts, checkin_digest = await _load_followup_context(request.patient_nric)
        brief = await generate_prep_brief(
            prior_visit=request.prior_visit,
            current_medications=request.current_medications,
            patient_age=request.patient_age,
            patient_sex=request.patient_sex,
            comorbidities=request.comorbidities,
            followup_alerts=followup_alerts,
            checkin_digest=checkin_digest,
        )
```

- [ ] **Step 4: Run new tests + existing prep-brief regression suite**

Run: `pytest backend/tests/test_followup_prep_brief.py backend/tests/test_prep_brief.py "--override-ini=addopts="`
Expected: all pass (the 6 existing prep-brief tests must not break — they call without the new kwargs).

---

### Task 10: Frontend API bindings

**Files:**
- Modify: `frontend/doctor-ui/src/lib/clinicalApi.js` (append after `getDeliveryStatus`, ~line 431)
- Modify: `frontend/doctor-ui/src/lib/supabase.js` (append near other direct-table helpers)
- Test: `frontend/doctor-ui/src/lib/__tests__/followupApi.test.js`

**Interfaces:**
- Produces (clinicalApi.js — FastAPI side): `enrollFollowup(consultationId, patientNric) -> {token, deep_link, expires_at}`; `getFollowupStatus(consultationId) -> {status} | null`.
- Produces (supabase.js — Supabase side): `getPatientAlerts({ openOnly = true, limit = 20 })`; `ackPatientAlert(alertId, ackedBy)`.

- [ ] **Step 1: Write the failing test**

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { enrollFollowup, getFollowupStatus } from '../clinicalApi';

describe('followup clinical API', () => {
  beforeEach(() => { global.fetch = vi.fn(); });

  it('enrollFollowup POSTs consultation_id + patient_nric', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ deep_link: 'https://t.me/B?start=t' }) });
    const out = await enrollFollowup(101, '900101-14-5555');
    expect(out.deep_link).toContain('t.me');
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain('/followup/enroll');
    expect(JSON.parse(opts.body)).toEqual({ consultation_id: 101, patient_nric: '900101-14-5555' });
  });

  it('getFollowupStatus returns null on non-2xx', async () => {
    fetch.mockResolvedValue({ ok: false });
    expect(await getFollowupStatus(101)).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/lib/__tests__/followupApi.test.js`
Expected: FAIL — enrollFollowup is not exported

- [ ] **Step 3: Implement**

Append to `clinicalApi.js`:

```javascript
// --- Follow-up ecosystem (Telegram companion) ---
export async function enrollFollowup(consultationId, patientNric) {
  const r = await fetch(`${CLINICAL_API_BASE}/followup/enroll`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ consultation_id: consultationId, patient_nric: patientNric }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getFollowupStatus(consultationId) {
  const r = await fetch(`${CLINICAL_API_BASE}/followup/status/${consultationId}`);
  return r.ok ? r.json() : null;
}
```

Append to `supabase.js` (follow the file's existing export style):

```javascript
// --- Patient alerts (follow-up ecosystem) ---
export async function getPatientAlerts({ openOnly = true, limit = 20 } = {}) {
  let q = supabase.from('patient_alerts').select('*').order('created_at', { ascending: false }).limit(limit);
  if (openOnly) q = q.eq('status', 'open');
  const { data, error } = await q;
  if (error) throw error;
  return data || [];
}

export async function ackPatientAlert(alertId, ackedBy) {
  const { error } = await supabase
    .from('patient_alerts')
    .update({ status: 'acked', acked_by: ackedBy || null, acked_at: new Date().toISOString() })
    .eq('id', alertId);
  if (error) throw error;
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/lib/__tests__/followupApi.test.js`
Expected: 2 passed

---

### Task 11: Follow-up QR card in OutputSection

**Files:**
- Create: `frontend/doctor-ui/src/components/sections/FollowupQRCard.jsx`
- Modify: `frontend/doctor-ui/src/components/sections/OutputSection.jsx` (render the card near the Send-to-patient block, ~line 230 region)
- Modify: `frontend/doctor-ui/package.json` (add `qrcode.react`)
- Test: `frontend/doctor-ui/src/components/sections/__tests__/FollowupQRCard.test.jsx`

**Interfaces:**
- Consumes: `enrollFollowup`, `getFollowupStatus` (Task 10); `consultationId` + `patientNric` props from OutputSection (OutputSection already has `consultationId` in scope — see its `enqueueDelivery` call at line ~177; patient NRIC comes from AppContext patient state the same way other cards read it).
- Produces: `<FollowupQRCard consultationId patientNric isDark />`.

- [ ] **Step 1: Install the QR dependency**

Run: `cd "frontend/doctor-ui"; npm install qrcode.react`
Expected: added to package.json dependencies.

- [ ] **Step 2: Write the failing test**

```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../../../lib/clinicalApi', () => ({
  enrollFollowup: vi.fn().mockResolvedValue({ deep_link: 'https://t.me/B?start=tok', expires_at: 'x' }),
  getFollowupStatus: vi.fn().mockResolvedValue({ status: 'issued' }),
}));

import FollowupQRCard from '../FollowupQRCard';
import { getFollowupStatus } from '../../../lib/clinicalApi';

describe('FollowupQRCard', () => {
  it('renders QR after enrolling', async () => {
    render(<FollowupQRCard consultationId={101} patientNric="X" isDark={false} />);
    await waitFor(() => expect(document.querySelector('svg, canvas')).toBeTruthy());
    expect(screen.getByText(/scan/i)).toBeInTheDocument();
  });

  it('flips to connected when status becomes active', async () => {
    getFollowupStatus.mockResolvedValue({ status: 'active' });
    render(<FollowupQRCard consultationId={101} patientNric="X" isDark={false} />);
    await waitFor(() => expect(screen.getByText(/connected/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/components/sections/__tests__/FollowupQRCard.test.jsx`
Expected: FAIL — module not found

- [ ] **Step 4: Implement `FollowupQRCard.jsx`**

```jsx
import { useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { MessageCircle, CheckCircle2 } from 'lucide-react';
import { GlassCard } from '../shared';
import { enrollFollowup, getFollowupStatus } from '../../lib/clinicalApi';

/**
 * Post-visit follow-up enrollment card. Enrolls once on mount, shows the
 * t.me deep-link QR, then polls status every 3 s until the patient scans
 * (status flips to 'active') and shows "Connected".
 */
export default function FollowupQRCard({ consultationId, patientNric, isDark }) {
  const [deepLink, setDeepLink] = useState(null);
  const [status, setStatus] = useState('none');
  const [error, setError] = useState(null);
  const enrolled = useRef(false);

  useEffect(() => {
    if (!consultationId || !patientNric || enrolled.current) return;
    enrolled.current = true;
    enrollFollowup(consultationId, patientNric)
      .then((r) => { setDeepLink(r.deep_link); setStatus('issued'); })
      .catch((e) => setError(String(e.message || e)));
  }, [consultationId, patientNric]);

  useEffect(() => {
    if (status !== 'issued') return undefined;
    const t = setInterval(async () => {
      const s = await getFollowupStatus(consultationId);
      if (s?.status === 'active') setStatus('active');
    }, 3000);
    return () => clearInterval(t);
  }, [status, consultationId]);

  if (error) return null; // follow-up is optional — never block the output step

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <MessageCircle size={18} className="text-teal-500" />
        <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>Patient Follow-up</h3>
      </div>
      {status === 'active' ? (
        <div className="flex items-center gap-2 text-teal-500">
          <CheckCircle2 size={18} />
          <span className="text-sm font-medium">Connected — first check-in sent</span>
        </div>
      ) : deepLink ? (
        <div className="flex items-center gap-4">
          <div className="bg-white p-2 rounded-lg">
            <QRCodeSVG value={deepLink} size={120} />
          </div>
          <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
            Ask the patient to scan this with their phone to receive follow-up
            check-ins on Telegram. Link expires in 48 hours.
          </p>
        </div>
      ) : (
        <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Preparing follow-up link…</p>
      )}
    </GlassCard>
  );
}
```

- [ ] **Step 5: Wire into OutputSection**

In `OutputSection.jsx`: import `FollowupQRCard` and render it below the delivery card (find the component rendered around line 230 with `deliveryStatus={delivery}` and place the card as a sibling after it), passing the `consultationId` the file already has in scope, the patient NRIC from the same state source the delivery block uses, and `isDark` from the theme context already imported in that file. Read the surrounding JSX first and match its layout wrappers exactly.

- [ ] **Step 6: Run tests + build**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/components/sections/__tests__/FollowupQRCard.test.jsx; npx vite build`
Expected: 2 passed; build succeeds.

---

### Task 12: Patient Alerts panel on the dashboard

**Files:**
- Create: `frontend/doctor-ui/src/components/sections/PatientAlertsPanel.jsx`
- Modify: `frontend/doctor-ui/src/components/sections/DashboardSection.jsx` (render panel; add realtime subscription alongside the existing one at line ~368)
- Test: `frontend/doctor-ui/src/components/sections/__tests__/PatientAlertsPanel.test.jsx`

**Interfaces:**
- Consumes: `getPatientAlerts`, `ackPatientAlert` (Task 10); `supabase` client for the realtime channel.
- Produces: `<PatientAlertsPanel isDark />` — self-contained (fetches + subscribes internally).

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const ALERT = {
  id: 1, patient_nric: '900101-14-5555', severity: 'critical',
  summary: 'tripwire: breathless', patient_reply: 'woke up breathless',
  status: 'open', created_at: '2026-07-16T10:00:00Z',
};

vi.mock('../../../lib/supabase', () => ({
  getPatientAlerts: vi.fn().mockResolvedValue([ALERT]),
  ackPatientAlert: vi.fn().mockResolvedValue(undefined),
  supabase: { channel: () => ({ on: vi.fn().mockReturnThis(), subscribe: vi.fn().mockReturnThis() }), removeChannel: vi.fn() },
}));

import PatientAlertsPanel from '../PatientAlertsPanel';
import { ackPatientAlert } from '../../../lib/supabase';

describe('PatientAlertsPanel', () => {
  it('renders open alerts with masked NRIC and verbatim reply', async () => {
    render(<PatientAlertsPanel isDark={false} />);
    await waitFor(() => expect(screen.getByText(/breathless/i)).toBeInTheDocument());
    expect(screen.queryByText('900101-14-5555')).toBeNull();  // full NRIC never shown
    expect(screen.getByText(/5555/)).toBeInTheDocument();      // masked tail shown
  });

  it('acknowledge button calls ackPatientAlert', async () => {
    render(<PatientAlertsPanel isDark={false} />);
    await waitFor(() => screen.getByRole('button', { name: /acknowledge/i }));
    fireEvent.click(screen.getByRole('button', { name: /acknowledge/i }));
    await waitFor(() => expect(ackPatientAlert).toHaveBeenCalledWith(1, expect.anything()));
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/components/sections/__tests__/PatientAlertsPanel.test.jsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `PatientAlertsPanel.jsx`**

```jsx
import { useCallback, useEffect, useState } from 'react';
import { BellRing } from 'lucide-react';
import { GlassCard, Badge } from '../shared';
import { supabase, getPatientAlerts, ackPatientAlert } from '../../lib/supabase';

const maskNric = (nric) => (nric ? `•••• ${String(nric).slice(-4)}` : 'unknown');

/** Realtime list of open follow-up escalations from the Triage agent. */
export default function PatientAlertsPanel({ isDark }) {
  const [alerts, setAlerts] = useState([]);

  const load = useCallback(async () => {
    try { setAlerts(await getPatientAlerts({ openOnly: true })); }
    catch { /* panel is non-critical — swallow */ }
  }, []);

  useEffect(() => {
    load();
    const ch = supabase
      .channel('patient-alerts')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'patient_alerts' }, load)
      .subscribe();
    return () => supabase.removeChannel(ch);
  }, [load]);

  const ack = async (id) => {
    await ackPatientAlert(id, 'clinician');
    load();
  };

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <BellRing size={18} className="text-red-500" />
        <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Patient Alerts {alerts.length > 0 && <span className="text-red-500">({alerts.length})</span>}
        </h3>
      </div>
      {alerts.length === 0 ? (
        <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>No open alerts from follow-up.</p>
      ) : (
        <ul className="space-y-3">
          {alerts.map((a) => (
            <li key={a.id} className={`rounded-lg border p-3 ${isDark ? 'border-red-900/50 bg-red-950/20' : 'border-red-200 bg-red-50'}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant={a.severity === 'critical' ? 'danger' : 'warning'}>{a.severity}</Badge>
                  <span className={`text-sm font-medium ${isDark ? 'text-gray-200' : 'text-gray-800'}`}>
                    Patient {maskNric(a.patient_nric)}
                  </span>
                </div>
                <button
                  onClick={() => ack(a.id)}
                  className="text-xs font-medium px-2 py-1 rounded bg-teal-600 text-white hover:bg-teal-700"
                >
                  Acknowledge
                </button>
              </div>
              <p className={`mt-2 text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>“{a.patient_reply}”</p>
              <p className={`mt-1 text-xs ${isDark ? 'text-gray-500' : 'text-gray-500'}`}>
                {a.summary} · {new Date(a.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}
```

If the shared `Badge` component doesn't accept a `variant` prop with `danger`/`warning`, read `src/components/shared/Badge.jsx` first and use its actual API (fall back to inline classes if needed — but static class strings only, never interpolated colors).

- [ ] **Step 4: Wire into DashboardSection**

In `DashboardSection.jsx`: import `PatientAlertsPanel` and render it near the top of the dashboard grid (above or beside the safety-flags block) as `<PatientAlertsPanel isDark={isDark} />`. The panel manages its own data + realtime; do NOT add `patient_alerts` to DashboardSection's own subscription.

- [ ] **Step 5: Run tests + build**

Run: `cd "frontend/doctor-ui"; npm run test -- --run src/components/sections/__tests__/PatientAlertsPanel.test.jsx; npx vite build`
Expected: 2 passed; build succeeds.

---

### Task 13: Demo seed script, env docs, and full-suite gate

**Files:**
- Create: `backend/scripts/seed_followup_demo.py`
- Modify: `.env` (user adds real values; you add the keys commented)
- Modify: `CPG LLM/CLAUDE.md` — add a short "Follow-up ecosystem" section documenting the package, workers, env vars, and the no-LLM-in-send-path invariant

**Interfaces:**
- Consumes: everything.
- Produces: a rehearsable demo.

- [ ] **Step 1: Write the seed script**

```python
"""Idempotent demo seed for the follow-up ecosystem rehearsal.

Ensures a demo patient + a finalized consultation with a treatment_plan exist,
then prints the enroll curl. Run with the backend up.

Usage: python backend/scripts/seed_followup_demo.py [--url http://localhost:8058]
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DEMO_NRIC = "990101-14-1234"
DEMO_PLAN = {
    "summary": "HFrEF optimisation: start bisoprolol, daily weights, review 2 weeks.",
    "recommendations": [
        {"intervention": "[START] Bisoprolol 2.5 mg OD", "recommendation_type": "pharmacological", "action": "start"},
    ],
    "monitoring": [{"parameter": "daily weight", "schedule": "daily for 2 weeks"}],
    "follow_up": [{"when": "2 weeks", "what": "symptom + weight review"}],
    "safety_netting": ["Worsening breathlessness at rest", "Ankle swelling", "Weight gain >2 kg in 3 days"],
}


async def main():
    conn = await asyncpg.connect(os.environ["SUPABASE_DB_URL"])
    try:
        await conn.execute(
            """INSERT INTO patients (nric, name) VALUES ($1, 'Demo Ahmad bin Ali')
               ON CONFLICT (nric) DO NOTHING""",
            DEMO_NRIC,
        )
        row = await conn.fetchrow(
            "SELECT id FROM consultations WHERE patient_nric = $1 ORDER BY id DESC LIMIT 1", DEMO_NRIC
        )
        if row:
            cid = row["id"]
            await conn.execute(
                "UPDATE consultations SET treatment_plan = $2 WHERE id = $1",
                cid, json.dumps(DEMO_PLAN),
            )
        else:
            cid = (await conn.fetchrow(
                """INSERT INTO consultations (patient_nric, treatment_plan)
                   VALUES ($1, $2) RETURNING id""",
                DEMO_NRIC, json.dumps(DEMO_PLAN),
            ))["id"]
        print(f"Demo consultation id: {cid}")
        print(f'Enroll: curl -X POST http://localhost:8058/followup/enroll '
              f'-H "Content-Type: application/json" '
              f'-d "{{\\"consultation_id\\": {cid}, \\"patient_nric\\": \\"{DEMO_NRIC}\\"}}"')
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
```

NOTE: verify the real `patients` / `consultations` NOT NULL columns before running — if inserts fail, read the table definitions (`information_schema.columns`) and supply the missing required fields rather than weakening constraints.

- [ ] **Step 2: Add env keys**

Append to `.env` (values left for the user to fill from @BotFather):

```
# --- Follow-up ecosystem (Telegram companion + triage) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
FOLLOWUP_WORKER_ENABLED=true
FOLLOWUP_TIME_SCALE=1
FOLLOWUP_LLM_MODEL=gemini-2.5-flash
FOLLOWUP_DEMO_MODE=false
```

Tell the user: create the bot via @BotFather (`/newbot`), disable group joins (`/setjoingroups` → Disable), then fill `TELEGRAM_BOT_TOKEN` + `TELEGRAM_BOT_USERNAME`.

- [ ] **Step 3: Document in `CLAUDE.md`**

Add a concise section under the architecture area of `CPG LLM/CLAUDE.md` covering: `backend/agent/followup/` package map, the two lifespan workers and their env gates, the four Supabase tables, the "no LLM in the send path / triage fail-safe = ESCALATE / tripwires fire even on negations" invariants, and `FOLLOWUP_TIME_SCALE` demo semantics. Keep it under ~25 lines, matching the file's existing density.

- [ ] **Step 4: Full gated suites**

Run: `cd backend; pytest` → all pass including the ≥80% coverage gate (new modules are covered by Tasks 2–9 tests).
Run: `cd "frontend/doctor-ui"; npm run test; npx vite build` → all pass, build clean.

- [ ] **Step 5: Live rehearsal (manual, with the user)**

1. Migration run (Task 1), `.env` filled, backend on 8058, frontend dev server up, `FOLLOWUP_TIME_SCALE=21600`, `FOLLOWUP_DEMO_MODE=true`.
2. `python backend/scripts/seed_followup_demo.py` → enroll via the printed curl OR through the UI QR card.
3. Scan QR on a real phone → welcome + day-0 check-in arrive.
4. Wait ~15 s → day-3 check-in arrives (time scale).
5. Reply "my ankles are swollen and I woke up breathless" → tripwire reply on the phone; alert pops on the dashboard.
6. Acknowledge on the dashboard; open a prep brief for the demo NRIC → escalation leads `since_last_visit`.
7. If step 4 stalls: `curl -X POST http://localhost:8058/followup/simulate-due`.

---

## Self-review notes

- **Spec coverage:** §1 architecture → Tasks 2–8; §2 enrollment + edge cases → Task 3 (supersede/STOP/expired) + Task 7 (no-active, /start without token handled by bind returning None); §3 protocol/caps/fallback/time-scale → Task 4; §4 triage layers + fail-safe → Task 5 + Task 7 dispatch order; §5 alerts + prep brief → Tasks 5, 9, 12; §6 tables → Task 1; §7 endpoints → Task 8; §8 env → Tasks 8/13; §9 frontend → Tasks 10–12; §10 demo → Task 13; §12 testing → per-task TDD + Task 13 gates.
- **Deferred consciously (spec §13):** multi-language, RLS, WhatsApp — out of scope, do not add.
- **Type consistency check:** `bind_enrollment(token, chat_id) -> dict|None` used identically in Tasks 3/7; `process_one_due() -> bool` in Tasks 6/8; `CheckinItem` fields in Tasks 4/7; `create_alert(enrollment, severity, summary, patient_reply)` in Tasks 5/7; `generate_prep_brief` new kwargs in Task 9 only.
