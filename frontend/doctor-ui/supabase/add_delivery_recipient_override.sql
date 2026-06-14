-- Allow the clinician to supply the recipient email address from the UI form
-- ("Email to Patient"). When p_recipient is provided, it is used verbatim and
-- the patient-on-file / consent gate is bypassed (the clinician is explicitly
-- directing the send). When p_recipient is NULL the legacy behaviour applies:
-- use the patient's stored email and require both an email and consent.

-- Drop the prior 2-arg signature before extending the parameter list (Postgres
-- treats the 3-arg version as a separate overload otherwise).
DROP FUNCTION IF EXISTS enqueue_delivery_job(INTEGER, TEXT);

CREATE OR REPLACE FUNCTION enqueue_delivery_job(
    p_consultation_id INTEGER,
    p_clinician_name  TEXT DEFAULT NULL,
    p_recipient       TEXT DEFAULT NULL
)
RETURNS TABLE(job_id UUID, status TEXT, recipient TEXT) AS $$
-- The OUT columns `status`/`recipient` shadow delivery_jobs columns of the same
-- name. Without this directive, the `ON CONFLICT ... WHERE status IN (...)` arbiter
-- predicate raises "column reference \"status\" is ambiguous" and EVERY enqueue
-- fails. use_column makes ambiguous identifiers resolve to the table column.
#variable_conflict use_column
DECLARE
    v_patient_nric TEXT;
    v_email        TEXT;
    v_consent      TIMESTAMPTZ;
    v_recipient    TEXT;
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

    IF p_recipient IS NOT NULL AND length(trim(p_recipient)) > 0 THEN
        -- Clinician-supplied address: use it directly.
        v_recipient := trim(p_recipient);
    ELSE
        -- Legacy path: fall back to the patient's stored, consented email.
        IF v_email IS NULL THEN
            RAISE EXCEPTION 'patient has no email on file';
        END IF;
        IF v_consent IS NULL THEN
            RAISE EXCEPTION 'patient has not consented to email delivery';
        END IF;
        v_recipient := v_email;
    END IF;

    INSERT INTO delivery_jobs (consultation_id, patient_nric, channel, recipient, status, clinician_name)
    VALUES (p_consultation_id, v_patient_nric, 'gmail', v_recipient, 'queued', p_clinician_name)
    ON CONFLICT (consultation_id) WHERE status IN ('queued','sending','sent')
    DO UPDATE SET updated_at = now(),
                  clinician_name = EXCLUDED.clinician_name,
                  recipient = EXCLUDED.recipient
    RETURNING delivery_jobs.id INTO v_job_id;

    RETURN QUERY
        SELECT v_job_id, 'queued'::TEXT, v_recipient;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
