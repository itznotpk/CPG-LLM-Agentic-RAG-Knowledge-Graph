-- ============================================================================
-- CONSULTATIONS TABLE MIGRATION V2 - MULTIPLE CONSULTATIONS PER PATIENT
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor
-- This migration adds consultation_number column (per-patient sequence)
-- Go to: Supabase Dashboard → SQL Editor → New Query → Paste & Run
-- ============================================================================

-- ============================================================================
-- STEP 1: ADD CONSULTATION_NUMBER COLUMN (Per-Patient Sequence)
-- ============================================================================
-- This column stores the consultation number per patient (1, 2, 3... for each NRIC)
ALTER TABLE consultations ADD COLUMN IF NOT EXISTS consultation_number INTEGER;

-- ============================================================================
-- STEP 2: POPULATE CONSULTATION_NUMBER FOR EXISTING ROWS
-- ============================================================================
-- This calculates the consultation_number for each patient's existing rows
-- Row number is based on consultation_time order
WITH numbered AS (
  SELECT 
    id,
    patient_nric,
    ROW_NUMBER() OVER (PARTITION BY patient_nric ORDER BY consultation_time, id) as row_num
  FROM consultations
)
UPDATE consultations c
SET consultation_number = n.row_num
FROM numbered n
WHERE c.id = n.id AND (c.consultation_number IS NULL OR c.consultation_number != n.row_num);

-- ============================================================================
-- STEP 3: CREATE UNIQUE INDEX (Per-Patient Sequence)
-- ============================================================================
-- Create unique constraint to prevent duplicate consultation numbers per patient
DROP INDEX IF EXISTS idx_consultations_patient_number;
CREATE UNIQUE INDEX idx_consultations_patient_number 
  ON consultations(patient_nric, consultation_number);

-- ============================================================================
-- STEP 4: UPDATE START_CONSULTATION FUNCTION
-- ============================================================================
-- Drop existing function first
DROP FUNCTION IF EXISTS start_consultation(TEXT, TEXT);

-- This function creates a new consultation row and returns the ID
-- Also calculates the consultation_number per patient (1, 2, 3... for each NRIC)
CREATE OR REPLACE FUNCTION start_consultation(
    p_patient_nric TEXT,
    p_clinical_notes TEXT
)
RETURNS JSON AS $$
DECLARE
    new_id INTEGER;
    next_consultation_number INTEGER;
    result JSON;
BEGIN
    -- Validate NRIC format
    IF NOT is_valid_nric(p_patient_nric) THEN
        RAISE EXCEPTION 'Invalid NRIC format. Must be 12 digits (e.g., 580315081234) or with dashes (e.g., 580315-08-1234)';
    END IF;

    -- Verify patient exists
    IF NOT EXISTS (SELECT 1 FROM patients WHERE nric = p_patient_nric) THEN
        RAISE EXCEPTION 'Patient not found with NRIC: %', p_patient_nric;
    END IF;

    -- Calculate the next consultation number for this patient
    SELECT COALESCE(MAX(consultation_number), 0) + 1
    INTO next_consultation_number
    FROM consultations
    WHERE patient_nric = p_patient_nric;

    -- Insert new consultation row with per-patient consultation number
    INSERT INTO consultations (
        patient_nric,
        consultation_number,
        clinical_notes,
        consultation_time,
        created_at,
        updated_at
    )
    VALUES (
        p_patient_nric,
        next_consultation_number,
        p_clinical_notes,
        NOW(),
        NOW(),
        NOW()
    )
    RETURNING id INTO new_id;

    -- Return the new consultation ID and consultation number
    SELECT json_build_object(
        'success', true,
        'consultation_id', new_id,
        'consultation_number', next_consultation_number,
        'patient_nric', p_patient_nric,
        'message', 'Consultation started successfully'
    ) INTO result;

    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION start_consultation(TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION start_consultation(TEXT, TEXT) TO authenticated;

-- ============================================================================
-- DONE! After running this:
--
-- Your table will have:
--   - id (global unique): 1, 2, 3, 4, 5, 6...
--   - consultation_number (per-patient): 1, 2, 3... for EACH patient
--
-- Example:
--   | patient_nric     | consultation_number | id |
--   |------------------|--------------------|----|
--   | 041013-04-0417   | 1                  | 1  |
--   | 810520-10-5678   | 1                  | 2  |
--   | 040204-07-0278   | 1                  | 3  |
--   | 040204-07-0278   | 2                  | 4  |
--   | 041013-04-0417   | 2                  | 5  |
--   | 040204-07-0278   | 3                  | 6  |
--
-- Scroll right in the table view to see "consultation_number" column!
-- ============================================================================
