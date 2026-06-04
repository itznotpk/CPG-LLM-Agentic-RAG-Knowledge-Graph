-- ============================================================================
-- MIGRATION: machine_signals — pipeline insights emitted by the backend
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- WHY: the Stage 2-6 pipeline already NOTICES recurring problems (referral-gate
-- failures, KG edge gaps, missing-lab data-quality issues, silent stage
-- degradation) but only logs them to disk (logs/, failed_jobs.jsonl). This table
-- is the durable, queryable home for those signals — the "Machine Signals" feed
-- of the Layer-3 feedback ecosystem. Written by the backend (asyncpg via the
-- Supabase pool), never touches the Stage 2-6 outputs, so it needs NO A-D
-- revalidation. Append-only.
-- ============================================================================

CREATE TABLE IF NOT EXISTS machine_signals (
    id               BIGSERIAL PRIMARY KEY,
    -- consultations.id is INTEGER; nullable because some signals fire pre-save
    consultation_id  INTEGER,
    -- correlation id (X-Request-ID) — links to sse_events.log + failed_jobs.jsonl
    request_id       TEXT,
    -- 'gate_failure' | 'kg_gap' | 'data_quality' | 'stage_error' | 'coverage_gap'
    signal_type      TEXT NOT NULL,
    cpg_name         TEXT,
    trigger          TEXT,
    condition        TEXT,
    detail           TEXT,
    -- 'info' | 'warning' | 'critical' — mirrors the log level it was raised at
    severity         TEXT DEFAULT 'info',
    payload          JSONB,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_machine_signals_type       ON machine_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_machine_signals_cpg        ON machine_signals(cpg_name);
CREATE INDEX IF NOT EXISTS idx_machine_signals_request    ON machine_signals(request_id);
CREATE INDEX IF NOT EXISTS idx_machine_signals_created_at ON machine_signals(created_at);
-- aggregation hot-path: count failures by (type, cpg, trigger, condition)
CREATE INDEX IF NOT EXISTS idx_machine_signals_agg
    ON machine_signals(signal_type, cpg_name, trigger, condition);

ALTER TABLE machine_signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS machine_signals_all ON machine_signals;
CREATE POLICY machine_signals_all ON machine_signals
    FOR ALL TO anon, authenticated
    USING (true) WITH CHECK (true);

GRANT ALL ON machine_signals            TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE machine_signals_id_seq TO anon, authenticated;
