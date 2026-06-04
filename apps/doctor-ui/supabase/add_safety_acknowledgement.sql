-- ============================================================================
-- MIGRATION: Persist the Stage-6 safety verdict + clinician override audit trail
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- Adds four columns so a blocked plan that the clinician chose to proceed on
-- leaves a durable record of WHO accepted clinical responsibility and WHEN.
--
-- This rebuilds update_consultation as the FULL SUPERSET of every param across
-- prior migrations (add_safety_flags.sql + add_pipeline_timings.sql) PLUS the
-- four new acknowledgement params. It is self-contained and order-independent:
-- all columns it touches are created here with IF NOT EXISTS, so it is safe to
-- run regardless of which earlier migrations were applied. Keep p_pipeline_timings
-- and p_request_id — the backend (db_utils.save_pipeline_timings) calls them by
-- name and will break if they are dropped.
-- ============================================================================

-- 1. Add the columns (safety-ack ones are new; the other two are idempotent
--    re-adds in case add_pipeline_timings.sql was never run)
ALTER TABLE consultations
  ADD COLUMN IF NOT EXISTS safe_to_proceed         BOOLEAN,
  ADD COLUMN IF NOT EXISTS safety_acknowledged     BOOLEAN,
  ADD COLUMN IF NOT EXISTS safety_acknowledged_by  TEXT,
  ADD COLUMN IF NOT EXISTS safety_acknowledged_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS pipeline_timings        JSONB,
  ADD COLUMN IF NOT EXISTS request_id              TEXT;

-- 2. Drop EVERY existing overload of update_consultation. Past migrations left
--    several signatures behind; while more than one exists, the unqualified
--    GRANT at the bottom fails with "function name is not unique" (42725).
--    This loop removes them all so exactly one definition remains afterwards.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT oid::regprocedure AS sig
        FROM pg_proc
        WHERE proname = 'update_consultation'
          AND pronamespace = 'public'::regnamespace
    LOOP
        EXECUTE 'DROP FUNCTION ' || r.sig;
    END LOOP;
END $$;

-- 3. Recreate with the four acknowledgement params appended
CREATE OR REPLACE FUNCTION update_consultation(
    p_consultation_id            INTEGER,
    p_clinical_notes             TEXT        DEFAULT NULL,
    p_next_review                DATE        DEFAULT NULL,
    p_diagnoses                  JSONB       DEFAULT NULL,
    p_care_plan_summary          TEXT        DEFAULT NULL,
    p_medication_recommendations JSONB       DEFAULT NULL,
    p_interventions              JSONB       DEFAULT NULL,
    p_monitoring                 JSONB       DEFAULT NULL,
    p_patient_education          JSONB       DEFAULT NULL,
    p_referrals                  JSONB       DEFAULT NULL,
    p_lifestyle_goals            JSONB       DEFAULT NULL,
    p_cpg_references             JSONB       DEFAULT NULL,
    p_report_pdf_url             TEXT        DEFAULT NULL,
    p_safety_flags               JSONB       DEFAULT NULL,
    p_pipeline_timings           JSONB       DEFAULT NULL,
    p_request_id                 TEXT        DEFAULT NULL,
    p_safe_to_proceed            BOOLEAN     DEFAULT NULL,
    p_safety_acknowledged        BOOLEAN     DEFAULT NULL,
    p_safety_acknowledged_by     TEXT        DEFAULT NULL,
    p_safety_acknowledged_at     TIMESTAMPTZ DEFAULT NULL
)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    UPDATE consultations
    SET
        clinical_notes               = COALESCE(p_clinical_notes,               clinical_notes),
        next_review                  = COALESCE(p_next_review,                  next_review),
        diagnoses                    = COALESCE(p_diagnoses,                    diagnoses),
        care_plan_summary            = COALESCE(p_care_plan_summary,            care_plan_summary),
        medication_recommendations   = COALESCE(p_medication_recommendations,   medication_recommendations),
        interventions                = COALESCE(p_interventions,                interventions),
        monitoring                   = COALESCE(p_monitoring,                   monitoring),
        patient_education            = COALESCE(p_patient_education,            patient_education),
        referrals                    = COALESCE(p_referrals,                    referrals),
        lifestyle_goals              = COALESCE(p_lifestyle_goals,              lifestyle_goals),
        cpg_references               = COALESCE(p_cpg_references,               cpg_references),
        report_pdf_url               = COALESCE(p_report_pdf_url,               report_pdf_url),
        safety_flags                 = COALESCE(p_safety_flags,                 safety_flags),
        pipeline_timings             = COALESCE(p_pipeline_timings,             pipeline_timings),
        request_id                   = COALESCE(p_request_id,                   request_id),
        safe_to_proceed              = COALESCE(p_safe_to_proceed,              safe_to_proceed),
        safety_acknowledged          = COALESCE(p_safety_acknowledged,          safety_acknowledged),
        safety_acknowledged_by       = COALESCE(p_safety_acknowledged_by,       safety_acknowledged_by),
        safety_acknowledged_at       = COALESCE(p_safety_acknowledged_at,       safety_acknowledged_at),
        updated_at                   = NOW()
    WHERE id = p_consultation_id;

    SELECT json_build_object(
        'success', true,
        'consultation_id', p_consultation_id,
        'message', 'Consultation updated successfully'
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION update_consultation TO anon;
GRANT EXECUTE ON FUNCTION update_consultation TO authenticated;
