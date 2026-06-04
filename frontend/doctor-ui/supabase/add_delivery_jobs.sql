-- Patient delivery preferences
ALTER TABLE patients ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS email_consent_at TIMESTAMPTZ;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS preferred_language TEXT
    NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en','ms','zh'));

-- Delivery audit log
-- consultations.id is INTEGER; patients PK is nric TEXT
CREATE TABLE IF NOT EXISTS delivery_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id INTEGER  NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_nric    TEXT     NOT NULL REFERENCES patients(nric)    ON DELETE CASCADE,
    channel         TEXT     NOT NULL DEFAULT 'gmail' CHECK (channel = 'gmail'),
    recipient       TEXT     NOT NULL,
    status          TEXT     NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','sending','sent','failed')),
    message_id      TEXT,
    error           TEXT,
    attempts        INT      NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_delivery_jobs_status_created
    ON delivery_jobs(status, created_at)
    WHERE status IN ('queued','sending');

CREATE INDEX IF NOT EXISTS idx_delivery_jobs_consultation
    ON delivery_jobs(consultation_id, created_at DESC);

-- Idempotency: at most one non-failed job per consultation
CREATE UNIQUE INDEX IF NOT EXISTS uniq_delivery_active_per_consultation
    ON delivery_jobs(consultation_id)
    WHERE status IN ('queued','sending','sent');

-- updated_at trigger
CREATE OR REPLACE FUNCTION set_delivery_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_delivery_jobs_updated ON delivery_jobs;
CREATE TRIGGER trg_delivery_jobs_updated
    BEFORE UPDATE ON delivery_jobs
    FOR EACH ROW EXECUTE FUNCTION set_delivery_jobs_updated_at();

-- RLS (match consultations posture)
ALTER TABLE delivery_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS delivery_jobs_all ON delivery_jobs;
CREATE POLICY delivery_jobs_all ON delivery_jobs FOR ALL USING (true) WITH CHECK (true);

-- RPC the FastAPI endpoint calls
CREATE OR REPLACE FUNCTION enqueue_delivery_job(p_consultation_id INTEGER)
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

    INSERT INTO delivery_jobs (consultation_id, patient_nric, channel, recipient, status)
    VALUES (p_consultation_id, v_patient_nric, 'gmail', v_email, 'queued')
    ON CONFLICT (consultation_id) WHERE status IN ('queued','sending','sent')
    DO UPDATE SET updated_at = now()
    RETURNING delivery_jobs.id INTO v_job_id;

    RETURN QUERY
        SELECT v_job_id, 'queued'::TEXT, v_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
