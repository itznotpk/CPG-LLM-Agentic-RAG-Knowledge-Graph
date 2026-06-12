-- Add weight + height to live_vitals so BMI can be derived per consultation.
-- Step-1 intake already captures weight & height (state.vitals), but they were
-- dropped on save because the columns did not exist. Both are needed to compute
-- BMI = weight(kg) / (height(m))^2. No weight TREND graph is shown — BMI is
-- surfaced on the patient cards instead. Safe to re-run.

ALTER TABLE live_vitals ADD COLUMN IF NOT EXISTS weight FLOAT;  -- kg
ALTER TABLE live_vitals ADD COLUMN IF NOT EXISTS height FLOAT;  -- cm
