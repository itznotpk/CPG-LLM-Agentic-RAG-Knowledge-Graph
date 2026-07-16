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
