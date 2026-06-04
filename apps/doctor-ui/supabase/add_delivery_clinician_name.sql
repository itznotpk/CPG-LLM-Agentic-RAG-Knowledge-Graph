-- Carry the logged-in clinician's name onto the delivery job so the patient
-- email can be signed by the clinician who sent it. consultations.created_by
-- is not populated by start_consultation, so the name is passed from the
-- frontend session (authProfile) through enqueue_delivery_job instead.

ALTER TABLE delivery_jobs ADD COLUMN IF NOT EXISTS clinician_name TEXT;

-- Old 1-arg signature must be dropped before adding the parameter (Postgres
-- treats the 2-arg version as a separate overload otherwise).
DROP FUNCTION IF EXISTS enqueue_delivery_job(INTEGER);

CREATE OR REPLACE FUNCTION enqueue_delivery_job(
    p_consultation_id INTEGER,
    p_clinician_name  TEXT DEFAULT NULL
)
RETURNS TABLE(job_id UUID, status TEXT, recipient TEXT) AS $$
DECLARE
    v_patient_nric TEXT;
    v_email        TEXT;
    v_consent      TIMESTAMPTZ;
    v_job_id       UUID;
BEGIN
    SELECT c.patient_nric, p.email, p.email_consent_at
      INTO v_patient_nric, v_email, v_consent
      FROM consultations c
      JOIN patients p ON p.nric = c.patient_nric
     WHERE c.id = p_consultation_id;

    IF v_patient_nric IS NULL THEN
        RAISE EXCEPTION 'consultation not found: %', p_consultation_id;
    END IF;
    IF v_email IS NULL THEN
        RAISE EXCEPTION 'patient has no email on file';
    END IF;
    IF v_consent IS NULL THEN
        RAISE EXCEPTION 'patient has not consented to email delivery';
    END IF;

    INSERT INTO delivery_jobs (consultation_id, patient_nric, channel, recipient, status, clinician_name)
    VALUES (p_consultation_id, v_patient_nric, 'gmail', v_email, 'queued', p_clinician_name)
    ON CONFLICT (consultation_id) WHERE status IN ('queued','sending','sent')
    DO UPDATE SET updated_at = now(), clinician_name = EXCLUDED.clinician_name
    RETURNING delivery_jobs.id INTO v_job_id;

    RETURN QUERY
        SELECT v_job_id, 'queued'::TEXT, v_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
