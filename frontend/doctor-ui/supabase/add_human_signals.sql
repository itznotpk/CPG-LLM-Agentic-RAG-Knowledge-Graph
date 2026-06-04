-- ============================================================================
-- MIGRATION: human_signals — clinician feedback captured at plan approval/ship
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- WHY: the approval box (ApprovalWorkflow.jsx) collects an approve/reject comment
-- but today it lives only in React state and is discarded on refresh. This table
-- is the durable home for that feedback — the "Human Signals" feed of the
-- Layer-3 feedback ecosystem. Captured via a DIRECT INSERT from supabase.js
-- (NOT the update_consultation RPC) to avoid the RPC overload-rebuild trap.
-- ============================================================================

CREATE TABLE IF NOT EXISTS human_signals (
    id               BIGSERIAL PRIMARY KEY,
    -- consultations.id is INTEGER (not UUID); patients PK is nric TEXT.
    consultation_id  INTEGER REFERENCES consultations(id) ON DELETE CASCADE,
    patient_nric     TEXT    REFERENCES patients(nric)     ON DELETE CASCADE,
    -- 'approved' | 'rejected' | 'regenerate'
    action           TEXT    NOT NULL,
    -- free-text clinician comment from the approval box (the thing we were losing)
    comment          TEXT,
    -- who acted — profiles.id is uuid, mirrors auth.users.id
    clinician_id     UUID    REFERENCES profiles(id) ON DELETE SET NULL,
    clinician_name   TEXT,
    -- true when the clinician shipped a plan the Stage-6 critic had blocked
    safety_overridden BOOLEAN DEFAULT FALSE,
    -- CPGs the plan cited at approval time, so feedback can be attributed per-CPG
    cpg_references   JSONB,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_human_signals_consultation ON human_signals(consultation_id);
CREATE INDEX IF NOT EXISTS idx_human_signals_action       ON human_signals(action);
CREATE INDEX IF NOT EXISTS idx_human_signals_created_at   ON human_signals(created_at);

ALTER TABLE human_signals ENABLE ROW LEVEL SECURITY;

-- Mirror the permissive policy style used elsewhere (anon + authenticated).
DROP POLICY IF EXISTS human_signals_all ON human_signals;
CREATE POLICY human_signals_all ON human_signals
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);

GRANT ALL ON human_signals            TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE human_signals_id_seq TO anon, authenticated;
