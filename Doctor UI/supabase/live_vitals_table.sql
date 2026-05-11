-- Live Vitals table: one row per patient, upserted on Apply click.
-- Run this in Supabase SQL Editor (safe to re-run).

CREATE TABLE IF NOT EXISTS live_vitals (
  id            BIGSERIAL    PRIMARY KEY,
  patient_nric  TEXT         UNIQUE,          -- one row per patient
  patient_name  TEXT,
  source        TEXT         NOT NULL DEFAULT 'rppg',
  hr            FLOAT,
  spo2          FLOAT,
  rr            FLOAT,
  sbp           FLOAT,
  dbp           FLOAT,
  temp          FLOAT,
  quality       FLOAT,
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE live_vitals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_read_live_vitals"   ON live_vitals;
DROP POLICY IF EXISTS "anon_insert_live_vitals"  ON live_vitals;
DROP POLICY IF EXISTS "anon_upsert_live_vitals"  ON live_vitals;

CREATE POLICY "anon_read_live_vitals"
  ON live_vitals FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "anon_upsert_live_vitals"
  ON live_vitals FOR INSERT TO anon, authenticated WITH CHECK (true);

CREATE POLICY "anon_update_live_vitals"
  ON live_vitals FOR UPDATE TO anon, authenticated USING (true);

-- Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE live_vitals;
