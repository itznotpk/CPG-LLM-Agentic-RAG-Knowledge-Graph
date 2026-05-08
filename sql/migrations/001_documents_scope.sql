-- Migration 001: add CPG scope columns to documents
-- Idempotent: safe to run on populated DB.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS icd11_scope      TEXT[]                   NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS procedure_scope  TEXT[]                   NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS scope_rationale  TEXT,
  ADD COLUMN IF NOT EXISTS scope_verified   BOOLEAN                  NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS classified_at    TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS verified_at      TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS verified_by      TEXT;

CREATE INDEX IF NOT EXISTS idx_documents_icd_scope
  ON documents USING GIN (icd11_scope);

CREATE INDEX IF NOT EXISTS idx_documents_scope_verified
  ON documents (scope_verified) WHERE scope_verified = TRUE;
