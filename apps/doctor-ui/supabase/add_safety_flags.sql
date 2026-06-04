-- ============================================================================
-- MIGRATION: Add safety_flags to consultations + update RPC
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
-- ============================================================================

-- 1. Add the column
ALTER TABLE consultations
  ADD COLUMN IF NOT EXISTS safety_flags JSONB;

-- 2. Drop old signatures so we can add the new param
DROP FUNCTION IF EXISTS update_consultation(INTEGER, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, TEXT);
DROP FUNCTION IF EXISTS update_consultation(INTEGER, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, TEXT, JSONB);

-- 3. Recreate with p_safety_flags
CREATE OR REPLACE FUNCTION update_consultation(
    p_consultation_id            INTEGER,
    p_clinical_notes             TEXT    DEFAULT NULL,
    p_next_review                DATE    DEFAULT NULL,
    p_diagnoses                  JSONB   DEFAULT NULL,
    p_care_plan_summary          TEXT    DEFAULT NULL,
    p_medication_recommendations JSONB   DEFAULT NULL,
    p_interventions              JSONB   DEFAULT NULL,
    p_monitoring                 JSONB   DEFAULT NULL,
    p_patient_education          JSONB   DEFAULT NULL,
    p_referrals                  JSONB   DEFAULT NULL,
    p_lifestyle_goals            JSONB   DEFAULT NULL,
    p_cpg_references             JSONB   DEFAULT NULL,
    p_report_pdf_url             TEXT    DEFAULT NULL,
    p_safety_flags               JSONB   DEFAULT NULL
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
