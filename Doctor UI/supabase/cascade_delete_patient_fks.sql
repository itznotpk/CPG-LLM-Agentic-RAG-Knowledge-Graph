-- ============================================================================
-- CASCADE DELETE: patients → consultations (+ live_vitals)
-- ----------------------------------------------------------------------------
-- Run in Supabase Dashboard → SQL Editor → New Query → Run
-- Re-runnable: drops whatever FK currently points at patients(nric) and
-- recreates it with ON DELETE CASCADE.
-- ============================================================================

DO $$
DECLARE
    fk_name TEXT;
BEGIN
    -- consultations.patient_nric  →  patients.nric
    SELECT conname INTO fk_name
    FROM pg_constraint
    WHERE conrelid = 'public.consultations'::regclass
      AND contype  = 'f'
      AND confrelid = 'public.patients'::regclass;

    IF fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.consultations DROP CONSTRAINT %I', fk_name);
    END IF;

    ALTER TABLE public.consultations
        ADD CONSTRAINT consultations_patient_nric_fkey
        FOREIGN KEY (patient_nric) REFERENCES public.patients(nric)
        ON DELETE CASCADE;

    -- live_vitals.patient_nric → patients.nric (only if table exists)
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema='public' AND table_name='live_vitals') THEN

        SELECT conname INTO fk_name
        FROM pg_constraint
        WHERE conrelid = 'public.live_vitals'::regclass
          AND contype  = 'f'
          AND confrelid = 'public.patients'::regclass;

        IF fk_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.live_vitals DROP CONSTRAINT %I', fk_name);
        END IF;

        -- Re-add only if the column already exists & references patients
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='live_vitals'
                     AND column_name='patient_nric') THEN
            ALTER TABLE public.live_vitals
                ADD CONSTRAINT live_vitals_patient_nric_fkey
                FOREIGN KEY (patient_nric) REFERENCES public.patients(nric)
                ON DELETE CASCADE;
        END IF;
    END IF;
END $$;

-- Clean up any orphans left from earlier non-cascading deletes
DELETE FROM public.consultations
WHERE patient_nric NOT IN (SELECT nric FROM public.patients);
