-- ============================================================================
-- ACTOR AUDIT TRIGGERS — populate created_by / updated_by from auth.uid()
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor.
--
-- Problem: patients.created_by and consultations.created_by/updated_by are
-- never populated, because the RPCs (register_patient, start_consultation,
-- update_consultation) don't pass the actor and the call sites never wire in
-- the logged-in user's id.
--
-- Approach: BEFORE INSERT/UPDATE triggers that stamp the columns from
-- auth.uid() (the authenticated user's profiles.id, via the request JWT).
-- This avoids touching the update_consultation RPC, which has accumulated
-- many overloads and is rebuilt as a full superset elsewhere
-- (add_safety_acknowledgement.sql) — changing its signature here would risk
-- the 42725 "function name is not unique" trap.
--
-- Why auth.uid() works inside SECURITY DEFINER RPCs: it reads the request's
-- JWT claims, not the function owner — so register_patient / start_consultation
-- still resolve the real caller.
--
-- Null-guard rationale: writes made over a direct Postgres connection (e.g.
-- the backend delivery worker / save_pipeline_timings, which connect via
-- SUPABASE_DB_URL as the postgres role with NO JWT) have auth.uid() = NULL.
-- We never overwrite an existing actor with NULL, so those server-side updates
-- leave the original created_by/updated_by intact.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- patients.created_by  (set once, on insert)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_patient_created_by()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.created_by IS NULL THEN
        NEW.created_by := auth.uid();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_patients_set_created_by ON patients;
CREATE TRIGGER trg_patients_set_created_by
    BEFORE INSERT ON patients
    FOR EACH ROW
    EXECUTE FUNCTION set_patient_created_by();

-- ----------------------------------------------------------------------------
-- consultations.created_by  (on insert) + updated_by (on every update)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_consultation_actor()
RETURNS TRIGGER AS $$
DECLARE
    actor uuid := auth.uid();
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.created_by IS NULL THEN
            NEW.created_by := actor;
        END IF;
        -- mirror the creator into updated_by so the first version is attributed
        IF NEW.updated_by IS NULL THEN
            NEW.updated_by := actor;
        END IF;
    ELSIF TG_OP = 'UPDATE' THEN
        -- only stamp when we actually have an authenticated caller, so
        -- backend (no-JWT) updates don't blank out the real editor
        IF actor IS NOT NULL THEN
            NEW.updated_by := actor;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_consultations_set_actor ON consultations;
CREATE TRIGGER trg_consultations_set_actor
    BEFORE INSERT OR UPDATE ON consultations
    FOR EACH ROW
    EXECUTE FUNCTION set_consultation_actor();

-- ============================================================================
-- BACKFILL (optional) — leave existing NULL rows as-is.
-- There is no reliable way to attribute historical rows to a user after the
-- fact, so we intentionally do NOT guess. New rows from here on are stamped.
-- ============================================================================

-- ============================================================================
-- DONE. No frontend or RPC changes required — the triggers fire on the
-- existing register_patient / start_consultation / update_consultation paths.
-- Verify with:
--   SELECT id, created_by, updated_by FROM consultations ORDER BY id DESC LIMIT 5;
-- after creating a consultation while logged in.
-- ============================================================================
