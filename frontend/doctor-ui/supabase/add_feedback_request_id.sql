-- ============================================================================
-- MIGRATION: human_signals.request_id — join clinician feedback to its trace
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- WHY: machine_signals already carries the X-Request-ID correlation id, but
-- human_signals (approve/reject/regenerate/manual_diagnosis feedback) did not —
-- so a clinician's judgement could not be clicked through to the OTel trace
-- (Jaeger: search by request_id tag), the SSE event log, or the machine
-- signals of the exact pipeline run it judges. The frontend now stamps the id
-- (read from the API's X-Request-ID response header) on every insert.
--
-- Direct-insert table (no RPC involved), so this is a plain additive column —
-- the update_consultation overload-rebuild trap does not apply.
-- ============================================================================

ALTER TABLE human_signals ADD COLUMN IF NOT EXISTS request_id TEXT;

CREATE INDEX IF NOT EXISTS idx_human_signals_request ON human_signals(request_id);
