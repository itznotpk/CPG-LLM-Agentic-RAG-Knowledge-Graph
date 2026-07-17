-- ============================================================================
-- MIGRATION: Persist clinician decisions from the curated international-guidance
-- comparison. Run this in the Supabase SQL Editor after the previous
-- consultations migrations.
-- ============================================================================

ALTER TABLE consultations
  ADD COLUMN IF NOT EXISTS international_guidance_audit JSONB;

-- Avoid the PostgREST RPC overload trap: remove every prior overload before
-- adding the new parameter.
DO $$
DECLARE r RECORD;
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

CREATE OR REPLACE FUNCTION update_consultation(
    p_consultation_id                 INTEGER,
    p_clinical_notes                  TEXT        DEFAULT NULL,
    p_next_review                     DATE        DEFAULT NULL,
    p_diagnoses                       JSONB       DEFAULT NULL,
    p_care_plan_summary               TEXT        DEFAULT NULL,
    p_medication_recommendations      JSONB       DEFAULT NULL,
    p_interventions                   JSONB       DEFAULT NULL,
    p_monitoring                      JSONB       DEFAULT NULL,
    p_referrals                       JSONB       DEFAULT NULL,
    p_lifestyle_goals                 JSONB       DEFAULT NULL,
    p_cpg_references                  JSONB       DEFAULT NULL,
    p_report_pdf_url                  TEXT        DEFAULT NULL,
    p_safety_flags                    JSONB       DEFAULT NULL,
    p_pipeline_timings                JSONB       DEFAULT NULL,
    p_request_id                      TEXT        DEFAULT NULL,
    p_safe_to_proceed                 BOOLEAN     DEFAULT NULL,
    p_safety_acknowledged             BOOLEAN     DEFAULT NULL,
    p_safety_acknowledged_by          TEXT        DEFAULT NULL,
    p_safety_acknowledged_at          TIMESTAMPTZ DEFAULT NULL,
    p_international_guidance_audit    JSONB       DEFAULT NULL
)
RETURNS JSON AS $$
DECLARE result JSON;
BEGIN
  UPDATE consultations SET
    clinical_notes                 = COALESCE(p_clinical_notes, clinical_notes),
    next_review                    = COALESCE(p_next_review, next_review),
    diagnoses                      = COALESCE(p_diagnoses, diagnoses),
    care_plan_summary              = COALESCE(p_care_plan_summary, care_plan_summary),
    medication_recommendations     = COALESCE(p_medication_recommendations, medication_recommendations),
    interventions                  = COALESCE(p_interventions, interventions),
    monitoring                     = COALESCE(p_monitoring, monitoring),
    referrals                      = COALESCE(p_referrals, referrals),
    lifestyle_goals                = COALESCE(p_lifestyle_goals, lifestyle_goals),
    cpg_references                 = COALESCE(p_cpg_references, cpg_references),
    report_pdf_url                 = COALESCE(p_report_pdf_url, report_pdf_url),
    safety_flags                   = COALESCE(p_safety_flags, safety_flags),
    pipeline_timings               = COALESCE(p_pipeline_timings, pipeline_timings),
    request_id                     = COALESCE(p_request_id, request_id),
    safe_to_proceed                = COALESCE(p_safe_to_proceed, safe_to_proceed),
    safety_acknowledged            = COALESCE(p_safety_acknowledged, safety_acknowledged),
    safety_acknowledged_by         = COALESCE(p_safety_acknowledged_by, safety_acknowledged_by),
    safety_acknowledged_at         = COALESCE(p_safety_acknowledged_at, safety_acknowledged_at),
    international_guidance_audit   = COALESCE(p_international_guidance_audit, international_guidance_audit),
    updated_at                     = NOW()
  WHERE id = p_consultation_id;

  SELECT json_build_object('success', true, 'consultation_id', p_consultation_id,
    'message', 'Consultation updated successfully') INTO result;
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION update_consultation TO anon;
GRANT EXECUTE ON FUNCTION update_consultation TO authenticated;
