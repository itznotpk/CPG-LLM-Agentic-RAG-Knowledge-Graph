-- ============================================================================
-- MIGRATION: live_vitals — one row PER CONSULTATION (not per patient)
-- Run in Supabase Dashboard → SQL Editor → New Query → Paste & Run
--
-- Previously live_vitals.patient_nric was UNIQUE (one row per patient), so every
-- new consultation's vitals overwrote the prior visit and only the latest
-- snapshot survived. This migration:
--   1. Drops the patient_nric UNIQUE constraint.
--   2. Adds a UNIQUE constraint on consultation_id so each consultation keeps its
--      own row (and re-applying vitals within a visit upserts in place).
--   3. Fixes the history-sync trigger to pass the real source (manual|rppg)
--      through instead of hardcoding 'rppg'.
-- ============================================================================

-- 1. Drop the per-patient uniqueness (auto-named constraint from the UNIQUE column).
ALTER TABLE live_vitals
  DROP CONSTRAINT IF EXISTS live_vitals_patient_nric_key;

-- 2. One row per consultation. consultation_id may be NULL (Postgres treats NULLs
--    as distinct, so null-consultation rows are not blocked).
ALTER TABLE live_vitals
  ADD CONSTRAINT live_vitals_consultation_id_key UNIQUE (consultation_id);

-- 3. Trigger: sync live_vitals → patients.vitals_history, preserving source.
CREATE OR REPLACE FUNCTION sync_live_vitals_to_history()
RETURNS TRIGGER LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_entry   JSONB;
  v_history JSONB;
BEGIN
  v_entry := jsonb_build_object(
    'date',            NEW.updated_at,
    'source',          COALESCE(NEW.source, 'manual'),
    'consultation_id', NEW.consultation_id,
    'hr',              NEW.hr,
    'spo2',            NEW.spo2,
    'bpSystolic',      NEW.sbp,
    'bpDiastolic',     NEW.dbp,
    'rr',              NEW.rr,
    'temp',            NEW.temp,
    'quality',         NEW.quality
  );

  SELECT COALESCE(vitals_history, '[]'::JSONB)
    INTO v_history
    FROM patients
   WHERE nric = NEW.patient_nric;

  v_history := v_history || jsonb_build_array(v_entry);

  UPDATE patients
     SET vitals_history = v_history,
         updated_at     = NOW()
   WHERE nric = NEW.patient_nric;

  RETURN NEW;
END;
$$;
