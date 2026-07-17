# Follow-up Appointment Reminders — Design

**Date:** 2026-07-17
**Status:** Approved for planning
**Depends on:** the shipped follow-up ecosystem (`backend/agent/followup/`, migration `add_followup_ecosystem.sql`).

## Goal

Send each enrolled patient a one-way reminder before their next review appointment,
driven by `consultations.next_review`. Two reminders per appointment: 3 days before
(time to phone the clinic and rearrange) and 1 day before (the no-show reducer).

**Explicitly one-way.** The reminder expects no reply. If a patient replies anyway,
the message falls through to the existing triage path unchanged — medical content
still escalates, "ok thanks" still reassures. This is deliberately NOT a
confirm/reschedule/booking feature (there is no appointments table, and building one
is out of scope — see Non-Goals).

## Non-Goals

- **No YES/NO confirmation, no reschedule loop, no booking.** Those require an
  appointments table that does not exist. A reminder is a nudge, not a transaction.
- **No new reply path.** Reminders reuse the existing inbound dispatch verbatim.
- **No PDF, no attachments** over Telegram (unencrypted for bots; first-name-only
  PHI rule stands).
- **No change to the send path.** `scheduler_worker.process_one_due` is untouched.

## Architecture

One new unit; everything else is reused.

| Component | Change | Responsibility |
|---|---|---|
| `backend/agent/followup/reminder_scanner.py` | **create** | The only new logic. Periodically joins active enrollments → each patient's latest `next_review`; inserts/cancels `followup_checkins` rows (`kind='reminder'`) so reminder rows exist exactly when they should. Sends nothing, calls no LLM. |
| `backend/agent/followup/scheduler_worker.py` | **none** | Already sends any pending `followup_checkins` row by `question`. Reminder rows ride this unchanged. |
| `backend/agent/api.py` (lifespan) | **1 hook** | Start/stop the scanner loop, gated identically to the other two workers. |
| `frontend/doctor-ui/supabase/add_followup_reminder_dedup_index.sql` | **applied** | Unique index for idempotent inserts. Already applied to the live DB 2026-07-17. |

### Why Approach A (scanner writes rows, existing worker sends them)

The scanner decides *when a reminder row should exist*; the proven `scheduler_worker`
does the sending. This inherits the entire send path for free — retries,
`attempts < 3`, `FOR UPDATE SKIP LOCKED`, the outbound `log_message` audit row, and
crucially the `e.status = 'active'` join, so **STOP and enrollment-supersede both kill
reminders with no extra code**. Rejected alternatives: a separate sender (duplicates
retry/opt-out/logging), and generate-at-enrollment (freezes the date, which
contradicts the "always latest review date" requirement below).

## Data model

Reminders reuse `followup_checkins` (verified live 2026-07-17):

```
id            bigint PK
enrollment_id bigint NOT NULL   -> followup_enrollments(id)
kind          text   NOT NULL   -- 'monitoring'|'adherence'|'followup'|'reminder' (free text, no enum)
question      text   NOT NULL   -- reminder body goes here; sender sends c.question blindly
due_at        timestamptz NOT NULL
sent_at       timestamptz
status        text   NOT NULL DEFAULT 'pending'  -- pending|sending|sent|failed|cancelled
attempts      int    NOT NULL DEFAULT 0
```

- `kind` is free `TEXT` → `'reminder'` needs no schema change.
- `question` is `NOT NULL` and the sender sends it verbatim → the rendered reminder
  text goes straight into `question`. The column name reads oddly for a reminder;
  a one-line code comment notes this rather than adding a parallel `body` column
  and teaching the sender two fields.

**Applied migration** (`add_followup_reminder_dedup_index.sql`, live 2026-07-17):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_followup_checkins_dedup
  ON followup_checkins (enrollment_id, kind, due_at);
```
Makes the scanner's insert idempotent — it can run every scan and only ever create
one row per `(enrollment_id, kind, due_at)`. No duplicate rows existed at build time.

## The scanner

```
async def scan_due_reminders(now: datetime) -> int
    # returns number of reminder rows inserted this pass. Fail-open: any
    # exception is logged and swallowed; returns 0.
```

Each pass:

1. **Resolve latest review date per active patient.** For every `active`
   enrollment, take that patient's most recent `next_review` (newest consultation
   by `id`, `next_review NOT NULL`):
   ```sql
   SELECT e.id AS enrollment_id, e.patient_nric,
          (SELECT next_review FROM consultations c
            WHERE c.patient_nric = e.patient_nric
              AND c.next_review IS NOT NULL
            ORDER BY c.id DESC LIMIT 1) AS review_date
     FROM followup_enrollments e
    WHERE e.status = 'active';
   ```
   This is why reminders track the patient's **latest** review date, not the one
   frozen at enrollment: a later consultation (or an edited TCA) changes the
   sub-select result on the next pass.

2. **Compute due timestamps and insert.** For each row with `review_date >= today`,
   compute two `due_at`s: `review_date - 3 days` and `review_date - 1 day`, each
   anchored to 09:00 clinic-local time. For each `due_at` still in the future (or
   today), insert:
   ```sql
   INSERT INTO followup_checkins (enrollment_id, kind, question, due_at)
   VALUES ($1, 'reminder', $2, $3)
   ON CONFLICT (enrollment_id, kind, due_at) DO NOTHING;
   ```

3. **Cancel superseded reminders.** If the date moved, old pending reminder rows no
   longer match a computed `due_at`:
   ```sql
   UPDATE followup_checkins SET status = 'cancelled'
    WHERE kind = 'reminder' AND status = 'pending'
      AND enrollment_id = $1
      AND due_at <> ALL($2::timestamptz[]);   -- the T-3, T-1 we just computed
   ```

Step 3 runs every pass, not only when a date moved. When the computed due-set for an
enrollment is **empty** (the review date is now in the past, or no `next_review`
exists), `due_at <> ALL('{}')` is TRUE for every row, so all that enrollment's pending
reminders are cancelled — the correct outcome: never remind about a passed or removed
appointment. Only `status='pending'` rows are touched, so a reminder already `sending`
or `sent` is never retroactively cancelled.

Self-correcting: `due_at` is a pure function of `next_review`, so a moved date yields
new rows + cancelled stale ones automatically. No frozen state, no reconciler.

### Reminder text (deterministic, no LLM)

Rendered in Python from the date. Obeys the package house style (no emoji, no
exclamation marks, sentence case, speaks as the clinic). First-name-only PHI rule
holds — no NRIC, no diagnosis, no drug names. Shape:

- T-3: `"Your review appointment at the clinic is on <Day DD Mon>. Please contact the clinic if you need to change it."`
- T-1: `"Reminder: your review appointment at the clinic is tomorrow, <Day DD Mon>. Please contact the clinic if you cannot attend."`

## Wiring

The scanner runs as its own `start()` / `async stop()` in `api.py` lifespan,
gated on the same three conditions as the other workers (`FOLLOWUP_WORKER_ENABLED`
== true, `TELEGRAM_BOT_TOKEN` set, Supabase pool live). Keeping it a separate module
leaves `scheduler_worker` a pure sender. Scan interval: **60s** — reminders are
date-based, not second-sensitive, so the 3s send poll is unnecessary here.

## Error handling / edge cases

Fail-open throughout, matching the package:

| Case | Behaviour |
|---|---|
| Scanner raises mid-pass | Logged, returns 0, never propagates. Sender just has fewer/older rows. |
| `next_review` in the past | Filtered by `review_date >= today`. No reminder. |
| `next_review` today / <1 day at first scan | T-3 already past → not inserted (only future `due_at`s insert). T-1 may fire same-day. |
| Doctor moves the date later | New `due_at`s inserted; old pending reminders cancelled (step 3). |
| Patient sends STOP | Enrollment → `stopped`; sender's `e.status='active'` join skips their reminders; scanner stops matching them. |
| Enrollment superseded by a newer one | Same `active`-join mechanism skips the old enrollment's reminders. |
| Patient replies to a reminder | Falls through to existing triage. Medical → escalate, benign → reassure. No new path. |
| No `next_review` on any consultation | Sub-select is NULL → row skipped. |
| Duplicate concurrent scan | `ON CONFLICT DO NOTHING` → harmless. |

## Testing

Pure-logic unit tests against a mocked pool (idiom of `test_followup_scheduler.py`),
no Telegram, no live DB:

1. Review date 10 days out → inserts exactly 2 rows (T-3, T-1) with correct `due_at`s.
2. Second scan of identical state → inserts 0 (idempotent).
3. Date moved later → new rows inserted AND stale pending reminders cancelled.
4. `next_review` in the past → 0 rows.
5. Enrollment not `active` → patient excluded.
6. Rendered reminder text: no emoji, no `!`, names the date, no NRIC/diagnosis/drug.

## Demo caveat

Reminders key off the real calendar, so `FOLLOWUP_TIME_SCALE` cannot compress them
(an absolute date does not move when elapsed time is scaled). To demo: set a
consultation's `next_review` to tomorrow → T-1 fires on the next 60s scan. Showing
both T-3 and T-1 in one sitting is not naturally possible; insert the second row
manually or use `/followup/simulate-due`.

## Files

- **create** `backend/agent/followup/reminder_scanner.py`
- **create** `backend/tests/test_followup_reminder_scanner.py`
- **modify** `backend/agent/api.py` — lifespan start/stop hook
- **applied** `frontend/doctor-ui/supabase/add_followup_reminder_dedup_index.sql` (live)
- **modify** `CPG LLM/CLAUDE.md` — one line under the follow-up ecosystem section
