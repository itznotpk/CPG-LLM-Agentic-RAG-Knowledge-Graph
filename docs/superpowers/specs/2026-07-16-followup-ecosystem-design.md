# ClearPath Follow-up Ecosystem — Design Spec

**Date:** 2026-07-16
**Status:** Approved design, pre-implementation
**Goal:** Elevate ClearPath from a point-in-time consultation tool to a multi-agent care ecosystem by closing the post-visit loop: a Telegram **Companion agent** turns the finalized care plan into a scheduled check-in protocol, and a **Triage agent** classifies patient replies against that patient's own plan, escalating red flags back to the doctor dashboard and the next visit's prep brief.
**Constraint:** ~1 week build, live end-to-end demo (judges watch the real system), general health/medicine hackathon track.

---

## 1. Architecture

```
┌─────────────────────┐    finalized plan     ┌──────────────────────────┐
│  Clinical Pipeline   │ ────────────────────▶ │  Companion Agent          │
│  (existing Stage 2–6)│                       │  plan → check-in protocol │
└─────────────────────┘                       │  scheduled Telegram msgs  │
        ▲                                      └───────────┬──────────────┘
        │ prep brief injection                             │ patient replies
        │                                                  ▼
┌───────┴─────────────┐   patient_alerts row   ┌──────────────────────────┐
│  Doctor UI           │ ◀──────────────────── │  Triage Agent             │
│  (realtime alerts)   │                       │  reply → REASSURE/ADVISE/ │
└─────────────────────┘                       │  ESCALATE (fail-safe)     │
                                               └──────────────────────────┘
```

Three agents, one evidence spine:

- **Companion agent** (patient-facing): converts the finalized `TreatmentPlan` into a stored check-in protocol at enrollment time, then delivers pre-generated messages when due. The send path is deterministic — no LLM at send time.
- **Triage agent** (backend): classifies every inbound patient message against the patient's own plan (P7 red flags + monitoring targets). Never freelances general medical advice. Fail-safe default is ESCALATE.
- **Clinical pipeline** (existing Stage 2–6): the upstream producer. Untouched by this work except prep-brief input extension.

Every patient-facing message traces to the safety-critic-vetted plan — preserves the "auditable, not vibes" brand.

### Runtime placement

All new backend code lives in `backend/agent/followup/`:

```
backend/agent/followup/
  __init__.py
  telegram_client.py    # thin httpx wrapper: sendMessage, getUpdates (long-poll)
  bot_poller.py         # asyncio task: getUpdates loop → dispatch inbound messages
  scheduler_worker.py   # asyncio task: poll followup_checkins for due rows → send
  protocol.py           # plan JSON → check-in protocol (one LLM call at enrollment)
  triage.py             # tripwires + LLM classification of patient replies
  enrollment.py         # token issue/bind/expiry, STOP handling
  prompts/
    protocol_generation.txt
    triage_classification.txt
```

Both workers start in the FastAPI lifespan alongside `delivery_worker` (same pattern: env-gated, fail-open, isolated from the clinical pipeline). If either worker dies, Stages 2–6 are unaffected.

**Why long-polling, not webhook:** `getUpdates` needs no public URL or TLS cert, so the whole demo runs off a laptop. Telegram guarantees at-least-once delivery of updates; the poller tracks `offset` to avoid reprocessing.

---

## 2. Enrollment flow (QR deep-link)

1. Clinician finalizes the plan (`finalizePlan` in AppContext succeeds).
2. Frontend calls `POST /followup/enroll` with `{consultation_id, patient_nric}`.
3. Backend inserts a `followup_enrollments` row with a one-time token: 32 chars, `secrets.token_urlsafe`, **expires 48 h** after issue, single-use.
4. `OutputSection` renders a QR card encoding `https://t.me/<BOT_USERNAME>?start=<token>` (QR generated client-side with the `qrcode.react` package — no backend image endpoint).
5. Patient scans → Telegram opens the bot → taps **Start** → bot receives `/start <token>`.
6. Bot validates the token (exists, unexpired, unbound) → binds `telegram_chat_id`, sets `status='active'`, generates the check-in protocol (§3), sends welcome + disclaimer + day-0 check-in.

**Welcome/disclaimer message (fixed copy, not LLM):**
> "Hi! I'm ClearPath, your follow-up companion after today's visit to <clinic>. I'll check in with you over the coming days. **I am not an emergency service — if you feel severely unwell, call 999 or go to the nearest hospital.** Reply STOP anytime to end these check-ins."

### Enrollment edge cases

| Case | Behavior |
|---|---|
| Token expired / already used / unknown | Bot replies "This link has expired — please ask your clinic for a new one." No binding. |
| Same patient, new consultation while an enrollment is active | New enrollment **supersedes**: old enrollment `status='superseded'`, its pending check-ins cancelled. One active protocol per patient at a time (mirrors real clinical practice — the newest plan governs). |
| Same chat_id scans a second patient's QR (family shares one phone) | Allowed — enrollments key on `(enrollment_id)`, and inbound messages resolve to the **most recent active enrollment for that chat_id**. Documented limitation for v1. |
| Patient texts the bot with no active enrollment | Fixed reply: "I don't have an active follow-up plan for you. Please contact your clinic." Message still logged (direction=inbound, enrollment_id NULL). |
| Patient texts STOP | Enrollment `status='stopped'`, pending check-ins cancelled, confirmation sent. STOP is matched case-insensitively as a whole-word first token. |
| `/start` with no token | Same reply as unknown token. |

---

## 3. Companion agent — protocol generation and sending

### Protocol generation (one LLM call, at enrollment)

`protocol.py::generate_protocol(plan: TreatmentPlan, patient_first_name: str) -> list[CheckinItem]`

- Input: `plan.monitoring` (time-anchored schedules), `plan.follow_up`, P2 medication recommendations (`action ∈ {start, change, continue}`), P7 safety-netting red flags.
- Output (JSON, validated by Pydantic `CheckinItem`): `{kind: monitoring|adherence|followup, day_offset: int, question: str}` — question ≤ 300 chars, patient-friendly language, each ends with a clear reply instruction ("Reply 1 (none) to 5 (severe), or describe in your own words").
- Model: `FOLLOWUP_LLM_MODEL` (default `gemini-2.5-flash`, GEMINI_* creds fallback — same convention as `PREP_BRIEF_LLM_MODEL`). JSON mode + `max_tokens` set (Gemini truncation gotcha).
- Caps: max 8 check-ins total, max 2 per day, day_offset ∈ [0, 30]. Server-side clamp after parse.
- **Fail-open fallback:** if the LLM call fails, generate a deterministic minimal protocol: day-0 "How are you feeling after today's visit?", day-3 generic symptom check naming the top red flag verbatim from P7, day-7 adherence check. Enrollment never fails because of the LLM.
- Generated rows insert into `followup_checkins` with computed `due_at`.

### Scheduling & demo time

`due_at = enrolled_at + (day_offset * 86400 / FOLLOWUP_TIME_SCALE) seconds`.

- `FOLLOWUP_TIME_SCALE` env var, default `1` (production-honest). Demo: `21600` → 1 day ≈ 4 s.
- `scheduler_worker` polls every 3 s (demo) via `SELECT ... WHERE status='pending' AND due_at <= now()` with `FOR UPDATE SKIP LOCKED` semantics (single worker, but idempotent anyway: mark `sending` before the API call).
- Send failures retry 3× with backoff, then `status='failed'` (delivery_jobs pattern). Check-ins for stopped/superseded enrollments are skipped.

### Message identity & PHI rules

- Patient addressed by **first name only** (derived at enrollment from the patients row; stored on the enrollment so no live join at send time).
- Never send: NRIC, full name, other patients' data, raw lab values beyond what the plan's own patient-facing instructions contain.
- Bot messages carry no clinic-identifying PHI beyond the clinic name in the welcome.

---

## 4. Triage agent

Every inbound text (that isn't `/start` or STOP) runs two layers **in order**:

### Layer 1 — deterministic tripwires (no LLM, always on)

Regex list (case-insensitive, word-boundary): chest pain/tightness, can't breathe / breathless / difficulty breathing, severe bleeding, fainted / passed out / collapse, one-sided weakness / slurred speech, suicidal / self-harm, severe allergic / swelling of face or throat. Hit → immediate `ESCALATE`, canned reply:

> "Thank you for telling me. Your message may describe something serious — **please call 999 or go to the nearest hospital now.** I've alerted your clinic."

Tripwires fire even if every LLM is down. The list lives in `triage.py` as a module constant with a comment that it is intentionally conservative.

### Layer 2 — LLM classification

`triage.py::classify_reply(enrollment, plan_context, message) -> TriageResult`

- Context: plan summary, P7 red flags, monitoring targets, the check-in question the patient is answering (if the reply follows one within a window), and the message text.
- Output JSON: `{classification: REASSURE|ADVISE|ESCALATE, rationale: str, patient_reply: str}`.
- Prompt contract (`triage_classification.txt`):
  - ADVISE may **only restate instructions already in this patient's plan** — no new drugs, no dose changes, no new diagnoses, no probability estimates (consistent with Commandment 5's spirit).
  - Numeric scale replies 1–2 → REASSURE; 4–5 → ESCALATE; 3 → ADVISE with plan-grounded guidance.
  - Anything ambiguous, off-topic-but-medical, or outside the plan's scope → ESCALATE.
  - Non-medical chit-chat ("thanks!", "ok") → REASSURE with a short acknowledgment.
- **Fail-safe:** JSON parse error, timeout, refusal, or missing fields → treat as ESCALATE with the canned tripwire reply (minus the 999 line — instead: "I've flagged your message for your clinic to review."). Same fail-loud philosophy as the Stage-4 degraded-evidence contract.
- Model: `FOLLOWUP_LLM_MODEL` (shared with protocol generation).

### Audit trail

Every message both directions persists to `patient_messages` with `triage_class` + `triage_rationale` on inbound rows. Nothing is ephemeral.

---

## 5. Escalation surfaces

### patient_alerts + dashboard

ESCALATE inserts a `patient_alerts` row: `{enrollment_id, consultation_id, patient_nric, severity ('critical' for tripwire, 'major' for LLM escalate), summary (one line, LLM rationale or tripwire name), patient_reply (verbatim), status='open'}`.

Doctor UI gains a **Patient Alerts panel** on the dashboard (`DashboardSection` area), subscribing to `postgres_changes` on `patient_alerts` via the existing `supabase.channel()` pattern. Each alert card: patient first name + NRIC-masked tail, time, severity badge, verbatim reply, summary, and an **Acknowledge** button → direct `supabase.from('patient_alerts').update({status:'acked', acked_by, acked_at})` (direct update, NOT the `update_consultation` RPC — sidesteps the overload trap, same reasoning as `saveConsultationSeverity`).

### Prep-brief injection (closing the loop)

`generate_prep_brief` (existing, `clinical_stages.py`) gains two optional inputs, loaded by the endpoint before the LLM call:

- Open + recently-acked `patient_alerts` for the NRIC (last 30 days).
- A check-in digest: counts + last 3 inbound `patient_messages` with triage class.

The prep-brief prompt gains one line instructing the model to lead `since_last_visit` with any escalation. Fail-open: if the followup tables are empty/missing, the brief behaves exactly as today. **No change to the Stage 2–6 pipeline.**

---

## 6. Data model (Supabase migration `add_followup_ecosystem.sql`)

Idempotent (`CREATE TABLE IF NOT EXISTS`), run manually in the SQL Editor per house convention. Types honor the schema gotcha: `consultation_id INTEGER`, `patient_nric TEXT`.

```sql
followup_enrollments (
  id BIGSERIAL PK,
  consultation_id INTEGER NOT NULL,
  patient_nric TEXT NOT NULL,
  patient_first_name TEXT,
  token TEXT UNIQUE NOT NULL,
  token_expires_at TIMESTAMPTZ NOT NULL,
  telegram_chat_id BIGINT,            -- NULL until bound
  status TEXT NOT NULL DEFAULT 'issued',  -- issued|active|stopped|superseded
  created_at / activated_at TIMESTAMPTZ
)

followup_checkins (
  id BIGSERIAL PK,
  enrollment_id BIGINT REFERENCES followup_enrollments,
  kind TEXT,                          -- monitoring|adherence|followup
  question TEXT,
  due_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',      -- pending|sending|sent|failed|cancelled
  attempts INT DEFAULT 0
)

patient_messages (
  id BIGSERIAL PK,
  enrollment_id BIGINT NULL REFERENCES followup_enrollments,
  telegram_chat_id BIGINT,
  direction TEXT,                     -- inbound|outbound
  text TEXT,
  triage_class TEXT,                  -- REASSURE|ADVISE|ESCALATE (inbound only)
  triage_rationale TEXT,
  created_at TIMESTAMPTZ
)

patient_alerts (
  id BIGSERIAL PK,
  enrollment_id BIGINT,
  consultation_id INTEGER,
  patient_nric TEXT,
  severity TEXT,                      -- critical|major
  summary TEXT,
  patient_reply TEXT,
  status TEXT DEFAULT 'open',         -- open|acked
  acked_by TEXT, acked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)
```

Access split per house rules: backend workers read/write via `supabase_pool` (asyncpg, `SUPABASE_DB_URL`) — these are patient-side tables living in Supabase, not Neon. Frontend reads/writes via supabase-js only (`supabase.js` gains `getPatientAlerts`, `ackPatientAlert`; `clinicalApi.js` gains `enrollFollowup` since `/followup/enroll` is a FastAPI endpoint). No new RPC needed — plain inserts/updates suffice; nothing touches `update_consultation`.

Realtime: enable `patient_alerts` in the Supabase realtime publication (one line in the migration).

---

## 7. API surface (FastAPI)

| Endpoint | Purpose |
|---|---|
| `POST /followup/enroll` | Body `{consultation_id, patient_nric}` → creates enrollment, returns `{token, deep_link, expires_at}` |
| `GET /followup/status/{consultation_id}` | Enrollment state for the OutputSection card (issued/active/stopped) — lets the UI flip the QR card to "Connected ✓" live |
| `POST /followup/simulate-due` *(dev-only, env-gated)* | Force the next pending check-in due now — demo insurance if time-scale math misbehaves on stage |

No inbound webhook — the poller pulls.

---

## 8. Environment variables

```
TELEGRAM_BOT_TOKEN          — from @BotFather; both workers no-op when unset
TELEGRAM_BOT_USERNAME       — for the deep-link URL
FOLLOWUP_WORKER_ENABLED     — default true (mirrors DELIVERY_WORKER_ENABLED)
FOLLOWUP_TIME_SCALE         — default 1; demo 21600 (1 day ≈ 4 s)
FOLLOWUP_LLM_MODEL          — default gemini-2.5-flash (GEMINI_* creds fallback)
```

One-time setup: create the bot via @BotFather (`/newbot`), set its name/description/avatar to ClearPath branding, disable group joins (`/setjoingroups` off), set the command list (`/start`).

---

## 9. Frontend changes

1. **`OutputSection`** — "Patient Follow-up" card: explains the companion, renders the QR (`qrcode.react`), polls `GET /followup/status` every 3 s until `active`, then shows "Connected — first check-in sent ✓". Card only renders when the plan was finalized and delivery consent exists.
2. **Dashboard Patient Alerts panel** — realtime list of open alerts (see §5), badge count in the panel header, Acknowledge button. Styled with existing `GlassCard`/`Badge` shared components; theme-aware per `ThemeContext` rules; no interpolated Tailwind color classes (purge gotcha).
3. **`PrepBriefCard`** — no component change needed; the escalation arrives inside the existing 3 fields from the backend.

---

## 10. Demo choreography (3-minute script)

1. Finalize a seeded demo patient's plan → QR card appears.
2. Scan with a phone (judge's or yours) → welcome + day-0 check-in arrive within seconds.
3. `FOLLOWUP_TIME_SCALE=21600` → "day 3" check-in lands ~30 s later, while you narrate the architecture.
4. Reply: "my ankles are swollen and I woke up breathless" → tripwire + triage ESCALATE → canned safety reply on the phone.
5. Doctor dashboard: alert card pops in live (realtime), you hit Acknowledge.
6. Start a new consultation for that NRIC → prep brief opens with "Patient reported nocturnal breathlessness, escalated day 3."
7. Close: "The plan didn't die in a PDF — it lived, watched, and reported back."

Rehearsal insurance: `/followup/simulate-due` endpoint; a pre-bound second enrollment on your own phone as backup; the tripwire layer guarantees the escalation moment even if Gemini is down on stage.

Demo seeding: one script `backend/scripts/seed_followup_demo.py` that creates the demo patient + consultation if absent (idempotent).

---

## 11. Error handling summary

| Failure | Behavior |
|---|---|
| `TELEGRAM_BOT_TOKEN` unset | Workers log one line and no-op; everything else normal |
| Telegram API down | Sends retry 3× then `failed`; poller backs off exponentially (max 60 s) |
| Protocol LLM fails at enrollment | Deterministic fallback protocol (§3); enrollment succeeds |
| Triage LLM fails on a reply | ESCALATE + safe canned reply (§4) |
| Supabase pool unavailable | Workers no-op with warning (matches delivery worker); bot replies generic "try later" to inbound |
| Duplicate Telegram update delivery | Poller offset tracking + `sending` status guard make sends idempotent |
| Patient replies to an old (superseded) enrollment's thread | Resolved to most-recent active enrollment; if none, "no active plan" reply |

---

## 12. Testing

**Pytest (`backend/tests/test_followup_*.py`, Telegram fully mocked with AsyncMock/respx — same approach as `test_delivery.py`):**
- Protocol generation: fixture `TreatmentPlan` → valid CheckinItems, caps enforced, LLM-failure fallback protocol.
- Tripwires: hit/miss table across the regex list, including negations kept conservative (a "no chest pain" reply DOES trip — conservatism documented as intended).
- Triage: valid JSON parse; malformed JSON → ESCALATE; scale replies 1/3/5 routing.
- Enrollment: token bind, expiry, reuse rejection, supersede cancels pending check-ins, STOP.
- Time-scale math: offset → due_at at scale 1 and 21600.
- Prep-brief injection: alerts present → digest reaches prompt inputs; tables empty → identical to today.

**Vitest:** QR card render + status flip; alerts panel renders rows + ack call.

**End-to-end:** the rehearsed demo script against the real bot, twice, before demo day.

Coverage gate: new modules included in the existing `--cov-fail-under=80` run.

---

## 13. Deliberately out of scope (v1)

Multi-language (en only; ms/zh strings can extend later), WhatsApp/SMS channels, medication photo confirmation, doctor-side Telegram notifications, patient-initiated symptom triage outside an active enrollment, inline keyboards beyond plain-text replies, per-item reschedule/snooze, any LLM in the send path, RLS policies on the new tables (service-role access only for v1 — noted as a production TODO).
