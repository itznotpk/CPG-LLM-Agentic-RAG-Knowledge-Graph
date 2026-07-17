-- add_followup_reminder_dedup_index.sql — Follow-up appointment reminders.
-- Idempotent. Applied to the live DB 2026-07-17 via the Supabase MCP as
-- migration `add_followup_checkins_dedup_index`; kept here as the repo
-- source-of-truth (this project runs migrations manually, no runner).
--
-- Reminder rows ride the existing followup_checkins table (kind='reminder').
-- This unique index makes the reminder scanner's insert idempotent: the scanner
-- can run every few seconds and only ever create one row per
-- (enrollment_id, kind, due_at). Verified no pre-existing duplicates before build.

CREATE UNIQUE INDEX IF NOT EXISTS uq_followup_checkins_dedup
  ON followup_checkins (enrollment_id, kind, due_at);
