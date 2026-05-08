-- ============================================================================
-- CONSULTATIONS TABLE - WITH RPC BYPASS FOR DEMO
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor
-- This adds next_review column and the bypass function for demo purposes
-- Go to: Supabase Dashboard → SQL Editor → New Query → Paste & Run
-- ============================================================================

-- ============================================================================
-- SET TIMEZONE TO UTC+08:00 (Malaysia/Singapore)
-- ============================================================================
-- Set the database timezone to Asia/Singapore (UTC+08:00)
-- This ensures all NOW() calls use the correct timezone
ALTER DATABASE postgres SET timezone TO 'Asia/Singapore';

-- For immediate effect in current session
SET timezone TO 'Asia/Singapore';

-- Add next_review column if it doesn't exist
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS next_review DATE;

-- Add care_plan_summary column if it doesn't exist
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS care_plan_summary TEXT;

-- Add medication_recommendations column if it doesn't exist (JSONB for stop/start/change/continue)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS medication_recommendations JSONB;

-- Add interventions column if it doesn't exist (JSONB for procedures)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS interventions JSONB;

-- Add monitoring column if it doesn't exist (JSONB for monitoring tasks)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS monitoring JSONB;

-- Add patient_education column if it doesn't exist (JSONB for education/counselling)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS patient_education JSONB;

-- Add referrals column if it doesn't exist (JSONB for specialist referrals)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS referrals JSONB;

-- Add lifestyle_goals column if it doesn't exist (JSONB for lifestyle recommendations)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS lifestyle_goals JSONB;

-- Add cpg_references column if it doesn't exist (JSONB for clinical practice guideline references)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS cpg_references JSONB;

-- ============================================================================
-- NRIC VALIDATION FUNCTION
-- Accepts: 12 digits (e.g., 580315081234) OR with dashes (e.g., 580315-08-1234)
-- ============================================================================
CREATE OR REPLACE FUNCTION is_valid_nric(nric TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if NRIC matches either:
    -- 1. 12 consecutive digits: 580315081234
    -- 2. Format with dashes: 580315-08-1234 (6 digits - 2 digits - 4 digits)
    RETURN nric ~ '^[0-9]{12}$' OR nric ~ '^[0-9]{6}-[0-9]{2}-[0-9]{4}$';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Drop existing functions (all signatures)
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB);
DROP FUNCTION IF EXISTS save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB, JSONB);

-- Create SECURITY DEFINER function to bypass RLS (for demo purposes)
-- This function APPENDS new diagnoses to existing ones (preserves original timestamps)
CREATE OR REPLACE FUNCTION save_consultation_bypass(
    p_patient_nric TEXT,
    p_clinical_notes TEXT,
    p_next_review DATE DEFAULT NULL,
    p_diagnoses JSONB DEFAULT '[]'::JSONB,
    p_care_plan_summary TEXT DEFAULT NULL,
    p_medication_recommendations JSONB DEFAULT NULL,
    p_interventions JSONB DEFAULT NULL,
    p_monitoring JSONB DEFAULT NULL,
    p_patient_education JSONB DEFAULT NULL,
    p_referrals JSONB DEFAULT NULL,
    p_lifestyle_goals JSONB DEFAULT NULL,
    p_cpg_references JSONB DEFAULT NULL
)
RETURNS JSON AS $$
DECLARE
    result JSON;
    existing_diagnoses JSONB;
    merged_diagnoses JSONB;
    existing_count INT;
    new_count INT;
BEGIN
    -- Validate NRIC format
    IF NOT is_valid_nric(p_patient_nric) THEN
        RAISE EXCEPTION 'Invalid NRIC format. Must be 12 digits (e.g., 580315081234) or with dashes (e.g., 580315-08-1234)';
    END IF;

    -- Get existing diagnoses for this patient (if any)
    SELECT COALESCE(diagnoses, '[]'::JSONB) INTO existing_diagnoses
    FROM consultations
    WHERE patient_nric = p_patient_nric;

    -- If no existing record found, start with empty array
    IF existing_diagnoses IS NULL THEN
        existing_diagnoses := '[]'::JSONB;
    END IF;

    -- Get counts for debugging
    existing_count := jsonb_array_length(existing_diagnoses);
    new_count := jsonb_array_length(COALESCE(p_diagnoses, '[]'::JSONB));

    -- Build merged array by combining existing (with their original timestamps) + new diagnoses
    -- Using jsonb_agg to explicitly rebuild the array preserving all data
    WITH existing_items AS (
        SELECT jsonb_array_elements(existing_diagnoses) AS item
    ),
    new_items AS (
        SELECT jsonb_array_elements(COALESCE(p_diagnoses, '[]'::JSONB)) AS item
    ),
    all_items AS (
        SELECT item FROM existing_items
        UNION ALL
        SELECT item FROM new_items
    )
    SELECT COALESCE(jsonb_agg(item), '[]'::JSONB) INTO merged_diagnoses FROM all_items;

    -- Log for debugging (visible in Supabase logs)
    RAISE NOTICE 'Merging diagnoses: % existing + % new = % total', 
        existing_count, new_count, jsonb_array_length(merged_diagnoses);

    INSERT INTO consultations (
        patient_nric, 
        clinical_notes, 
        next_review,
        diagnoses,
        care_plan_summary,
        medication_recommendations,
        interventions,
        monitoring,
        patient_education,
        referrals,
        lifestyle_goals,
        cpg_references,
        consultation_time,
        created_at,
        updated_at
    )
    VALUES (
        p_patient_nric, 
        p_clinical_notes, 
        p_next_review,
        merged_diagnoses,
        p_care_plan_summary,
        p_medication_recommendations,
        p_interventions,
        p_monitoring,
        p_patient_education,
        p_referrals,
        p_lifestyle_goals,
        p_cpg_references,
        NOW(),
        NOW(),
        NOW()
    )
    ON CONFLICT (patient_nric) 
    DO UPDATE SET 
        clinical_notes = EXCLUDED.clinical_notes,
        next_review = EXCLUDED.next_review,
        diagnoses = merged_diagnoses,
        care_plan_summary = COALESCE(p_care_plan_summary, consultations.care_plan_summary),
        medication_recommendations = COALESCE(p_medication_recommendations, consultations.medication_recommendations),
        interventions = COALESCE(p_interventions, consultations.interventions),
        monitoring = COALESCE(p_monitoring, consultations.monitoring),
        patient_education = COALESCE(p_patient_education, consultations.patient_education),
        referrals = COALESCE(p_referrals, consultations.referrals),
        lifestyle_goals = COALESCE(p_lifestyle_goals, consultations.lifestyle_goals),
        cpg_references = COALESCE(p_cpg_references, consultations.cpg_references),
        consultation_time = NOW(),
        updated_at = NOW()
    RETURNING json_build_object(
        'patient_nric', patient_nric,
        'clinical_notes', clinical_notes,
        'next_review', next_review,
        'diagnoses', diagnoses,
        'diagnoses_count', jsonb_array_length(diagnoses),
        'care_plan_summary', care_plan_summary,
        'consultation_time', consultation_time
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Grant execute to everyone (including anon) for demo
GRANT EXECUTE ON FUNCTION save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION save_consultation_bypass(TEXT, TEXT, DATE, JSONB, TEXT) TO authenticated;

-- ============================================================================
-- DONE! Consultations table now has:
--   - patient_nric (PK)
--   - clinical_notes
--   - next_review (DATE)
--   - diagnoses (JSONB array - ACCUMULATES across consultations)
--   - care_plan_summary (TEXT) - AI-generated clinical summary from step 3
--   - consultation_time
--   - created_by, updated_by, created_at, updated_at
--
-- DIAGNOSES FEATURE:
--   - New diagnoses are APPENDED to existing ones (not replaced)
--   - Each diagnosis has a recordedAt timestamp for date/time display
--   - Sorted newest to oldest in the UI
--
-- RPC bypass function enabled for demo (no authentication required)
-- ============================================================================

-- ============================================================================
-- UPDATE PATIENT STATUS BYPASS FUNCTION
-- ============================================================================
-- This function updates patient status bypassing RLS for demo purposes
-- Drop existing function if exists
DROP FUNCTION IF EXISTS update_patient_status_bypass(TEXT, TEXT);

CREATE OR REPLACE FUNCTION update_patient_status_bypass(
    p_patient_nric TEXT,
    p_status TEXT
)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    -- Validate NRIC format
    IF NOT is_valid_nric(p_patient_nric) THEN
        RAISE EXCEPTION 'Invalid NRIC format';
    END IF;

    -- Validate status value
    IF p_status NOT IN ('active', 'follow-up', 'discharged') THEN
        RAISE EXCEPTION 'Invalid status. Must be: active, follow-up, or discharged';
    END IF;

    -- Update patient status
    UPDATE patients
    SET 
        status = p_status::patient_status,
        updated_at = NOW()
    WHERE nric = p_patient_nric;

    -- Check if update was successful
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Patient not found with NRIC: %', p_patient_nric;
    END IF;

    -- Return success
    SELECT json_build_object(
        'success', true,
        'nric', p_patient_nric,
        'status', p_status
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to anon and authenticated roles
GRANT EXECUTE ON FUNCTION update_patient_status_bypass(TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION update_patient_status_bypass(TEXT, TEXT) TO authenticated;
