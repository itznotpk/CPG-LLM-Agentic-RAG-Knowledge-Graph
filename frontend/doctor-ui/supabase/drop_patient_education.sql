-- ============================================================================
-- MIGRATION: Drop patient_education from consultations + rebuild update_consultation
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- patient_education was always NULL — the backend never emits an education-type
-- recommendation, the mapper never produced a patientEducation field, and the
-- only "education" content was a hardcoded placeholder in the UI. Nothing reads
-- the column. We drop it and rebuild update_consultation as the full superset of
-- every other param (matching add_safety_acknowledgement.sql) MINUS
-- p_patient_education. Keep p_pipeline_timings/p_request_id — the backend
-- (db_utils.save_pipeline_timings) calls them by name.
-- ============================================================================

-- 1. Drop the column.
ALTER TABLE consultations
  DROP COLUMN IF EXISTS patient_education;

-- 2. Drop EVERY existing overload of update_consultation so exactly one remains
--    (an unqualified GRANT errors with 42725 while >1 signature exists).
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

-- 3. Recreate WITHOUT p_patient_education.
CREATE OR REPLACE FUNCTION update_consultation(
    p_consultation_id            INTEGER,
    p_clinical_notes             TEXT        DEFAULT NULL,
    p_next_review                DATE        DEFAULT NULL,
    p_diagnoses                  JSONB       DEFAULT NULL,
    p_care_plan_summary          TEXT        DEFAULT NULL,
    p_medication_recommendations JSONB       DEFAULT NULL,
    p_interventions              JSONB       DEFAULT NULL,
    p_monitoring                 JSONB       DEFAULT NULL,
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
