-- ============================================================================
-- MIGRATION: Add report_pdf_url to consultations + update RPC
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
-- ============================================================================

-- 1. Add the column
ALTER TABLE consultations
  ADD COLUMN IF NOT EXISTS report_pdf_url TEXT;

-- 2. Create Supabase Storage bucket for care plan PDFs (idempotent)
INSERT INTO storage.buckets (id, name, public)
VALUES ('care-plan-reports', 'care-plan-reports', false)
ON CONFLICT (id) DO NOTHING;

-- 3. Storage RLS: authenticated users can upload/read care-plan-reports bucket
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'Authenticated users can upload PDFs'
  ) THEN
    CREATE POLICY "Authenticated users can upload PDFs"
      ON storage.objects FOR INSERT
      TO authenticated
      WITH CHECK (bucket_id = 'care-plan-reports');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'Authenticated users can read PDFs'
  ) THEN
    CREATE POLICY "Authenticated users can read PDFs"
      ON storage.objects FOR SELECT
      TO authenticated
      USING (bucket_id = 'care-plan-reports');
  END IF;
END
$$;

-- 4. Drop & recreate update_consultation to accept p_report_pdf_url
DROP FUNCTION IF EXISTS update_consultation(INTEGER, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB);
DROP FUNCTION IF EXISTS update_consultation(INTEGER, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, TEXT);

CREATE OR REPLACE FUNCTION update_consultation(
    p_consultation_id       INTEGER,
    p_clinical_notes        TEXT        DEFAULT NULL,
    p_next_review           DATE        DEFAULT NULL,
    p_diagnoses             JSONB       DEFAULT NULL,
    p_care_plan_summary     TEXT        DEFAULT NULL,
    p_medication_recommendations JSONB  DEFAULT NULL,
    p_interventions         JSONB       DEFAULT NULL,
    p_monitoring            JSONB       DEFAULT NULL,
    p_patient_education     JSONB       DEFAULT NULL,
    p_referrals             JSONB       DEFAULT NULL,
    p_lifestyle_goals       JSONB       DEFAULT NULL,
    p_cpg_references        JSONB       DEFAULT NULL,
    p_report_pdf_url        TEXT        DEFAULT NULL
)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    UPDATE consultations
    SET
        clinical_notes               = COALESCE(p_clinical_notes,             clinical_notes),
        next_review                  = COALESCE(p_next_review,                next_review),
        diagnoses                    = COALESCE(p_diagnoses,                  diagnoses),
        care_plan_summary            = COALESCE(p_care_plan_summary,          care_plan_summary),
        medication_recommendations   = COALESCE(p_medication_recommendations, medication_recommendations),
        interventions                = COALESCE(p_interventions,              interventions),
        monitoring                   = COALESCE(p_monitoring,                 monitoring),
        patient_education            = COALESCE(p_patient_education,          patient_education),
        referrals                    = COALESCE(p_referrals,                  referrals),
        lifestyle_goals              = COALESCE(p_lifestyle_goals,            lifestyle_goals),
        cpg_references               = COALESCE(p_cpg_references,            cpg_references),
        report_pdf_url               = COALESCE(p_report_pdf_url,             report_pdf_url),
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
