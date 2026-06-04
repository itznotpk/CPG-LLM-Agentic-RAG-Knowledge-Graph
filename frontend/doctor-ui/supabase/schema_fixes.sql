-- ============================================================================
-- SUPABASE SCHEMA FIXES & HARDENING MIGRATION
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor:
-- Go to: Supabase Dashboard → SQL Editor → New Query → Paste & Run
-- ============================================================================

-- 1. DROP REDUNDANT TRIGGERS & DATA COLUMNS (normalization)
-- Removes duplicate names in telemetry, triggers, and redundant vitals blobs

-- Drop the redundant sync trigger on live_vitals first to avoid cascade DDL block
DROP TRIGGER IF EXISTS trg_sync_live_vitals ON public.live_vitals;
DROP FUNCTION IF EXISTS public.sync_live_vitals_to_history();

-- Now safe to drop redundant data columns
ALTER TABLE public.live_vitals DROP COLUMN IF EXISTS patient_name;
ALTER TABLE public.patients DROP COLUMN IF EXISTS vitals_history;

-- 2. ENFORCE FOREIGN KEY CONSTRAINTS (referential integrity)
-- Guarantees that vitals metrics cannot contain orphaned patients or consultations

-- Add FK from live_vitals to patients
ALTER TABLE public.live_vitals
  DROP CONSTRAINT IF EXISTS fk_live_vitals_patient,
  ADD CONSTRAINT fk_live_vitals_patient 
  FOREIGN KEY (patient_nric) 
  REFERENCES public.patients(nric) 
  ON DELETE CASCADE;

-- Add FK from live_vitals to consultations
ALTER TABLE public.live_vitals
  DROP CONSTRAINT IF EXISTS fk_live_vitals_consultation,
  ADD CONSTRAINT fk_live_vitals_consultation 
  FOREIGN KEY (consultation_id) 
  REFERENCES public.consultations(id) 
  ON DELETE SET NULL;

-- 3. SECURITY HARDENING: REVOKE ANONYMOUS ACCESS TO BYPASS RPCs
-- Restricts admin bypass operations to authenticated roles or internal API agents only

-- Secure update_patient_status_bypass
REVOKE EXECUTE ON FUNCTION public.update_patient_status_bypass(TEXT, TEXT) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.update_patient_status_bypass(TEXT, TEXT) TO authenticated, service_role;

-- Secure update_prior_visit_summary_bypass
REVOKE EXECUTE ON FUNCTION public.update_prior_visit_summary_bypass(TEXT, INTEGER, JSONB) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.update_prior_visit_summary_bypass(TEXT, INTEGER, JSONB) TO authenticated, service_role;

-- 4. API COMPATIBILITY: REDEFINE search_patient_v2 RPC
-- Overrides the old function to return a mock empty vitals_history JSONB array
-- preventing any client-side queries or Vite mapping logic from breaking.
-- Drop first: the RETURNS TABLE signature changed (added email columns), and
-- CREATE OR REPLACE cannot alter a function's output columns.
DROP FUNCTION IF EXISTS public.search_patient_v2(TEXT);
CREATE OR REPLACE FUNCTION public.search_patient_v2(p_nric TEXT)
RETURNS TABLE (
    nric TEXT,
    full_name TEXT,
    date_of_birth DATE,
    age INTEGER,
    gender public.gender_type,
    race TEXT,
    allergies TEXT,
    comorbidities TEXT[],
    current_medications JSONB,
    risk_level public.risk_level,
    mpis_synced_at TIMESTAMPTZ,
    vitals_history JSONB,
    email TEXT,
    email_consent_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.nric,
        p.full_name,
        p.date_of_birth,
        EXTRACT(YEAR FROM age(CURRENT_DATE, p.date_of_birth))::INTEGER AS age,
        p.gender,
        p.race,
        p.allergies,
        p.comorbidities,
        p.current_medications,
        p.risk_level,
        p.mpis_synced_at,
        '[]'::jsonb AS vitals_history,
        p.email,
        p.email_consent_at
    FROM public.patients p
    WHERE p.nric = p_nric;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.search_patient_v2(TEXT) TO anon, authenticated, service_role;

-- ============================================================================
-- MIGRATION DONE!
-- ============================================================================
