-- Migration: link live_vitals to consultations + auto-sync to vitals_history
-- Run this in Supabase SQL Editor.

-- 1. Add consultation FK to live_vitals
ALTER TABLE live_vitals
  ADD COLUMN IF NOT EXISTS consultation_id INTEGER REFERENCES consultations(id) ON DELETE SET NULL;

-- =========================================================
-- 2. Trigger function: sync live_vitals → patients.vitals_history
--    Fires on INSERT or UPDATE of live_vitals.
--    Keeps ONE rPPG entry per consultation in vitals_history
--    (or replaces the lone rPPG entry when no consultation linked).
-- =========================================================
CREATE OR REPLACE FUNCTION sync_live_vitals_to_history()
RETURNS TRIGGER LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_entry   JSONB;
  v_history JSONB;
BEGIN
  -- Build the entry to store in vitals_history
  v_entry := jsonb_build_object(
    'date',            NEW.updated_at,
    'source',          'rppg',
    'consultation_id', NEW.consultation_id,
    'hr',              NEW.hr,
    'spo2',            NEW.spo2,
    'bpSystolic',      NEW.sbp,
    'bpDiastolic',     NEW.dbp,
    'rr',              NEW.rr,
    'temp',            NEW.temp,
    'quality',         NEW.quality
  );

  -- Fetch current vitals_history for this patient
  SELECT COALESCE(vitals_history, '[]'::JSONB)
    INTO v_history
    FROM patients
   WHERE nric = NEW.patient_nric;

  -- Append new entry, keep all previous history
  v_history := v_history || jsonb_build_array(v_entry);

  -- Write back to patients table
  UPDATE patients
     SET vitals_history = v_history,
         updated_at     = NOW()
   WHERE nric = NEW.patient_nric;

  RETURN NEW;
END;
$$;

-- 3. Attach trigger
DROP TRIGGER IF EXISTS trg_sync_live_vitals ON live_vitals;
CREATE TRIGGER trg_sync_live_vitals
  AFTER INSERT OR UPDATE ON live_vitals
  FOR EACH ROW
  WHEN (NEW.patient_nric IS NOT NULL)
  EXECUTE FUNCTION sync_live_vitals_to_history();
