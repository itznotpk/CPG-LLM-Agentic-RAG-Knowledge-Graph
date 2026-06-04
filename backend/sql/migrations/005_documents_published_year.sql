-- Migration 005: add published_year to documents + backfill from title.
-- Idempotent: safe to run on populated DB.
--
-- Rationale: CPG currency is a clinical trust signal. A 2011 PAH CPG predates
-- the 2022 ESC/ERS guideline that fundamentally changed PAH management (upfront
-- combination therapy, selexipag, REVEAL 2.0 risk stratification). Surfacing
-- published_year lets the synthesis stage flag stale evidence and the UI show
-- an amber chip on old citations.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS published_year SMALLINT;

-- Backfill from metadata.cpg_name: rows in `documents` are CPG sections, not
-- top-level CPGs. The CPG name with its year lives in metadata->>'cpg_name',
-- e.g. "Pulmonary-Arterial-Hypertension(2011)" → 2011.
-- Only updates rows where published_year IS NULL so re-running is safe.
UPDATE documents
SET published_year = (
    substring(metadata->>'cpg_name' FROM '\((\d{4})\)')
)::SMALLINT
WHERE published_year IS NULL
  AND metadata->>'cpg_name' IS NOT NULL
  AND metadata->>'cpg_name' ~ '\(\d{4}\)';

-- Secondary backfill from metadata.file_path (catches edge cases where cpg_name
-- uses "Nth Edition" without year but file_path includes the year).
UPDATE documents
SET published_year = (
    substring(metadata->>'file_path' FROM '\((\d{4})\)')
)::SMALLINT
WHERE published_year IS NULL
  AND metadata->>'file_path' IS NOT NULL
  AND metadata->>'file_path' ~ '\(\d{4}\)';

-- Tertiary fallback — title or source if metadata is sparse.
UPDATE documents
SET published_year = (
    substring(title FROM '\((\d{4})\)')
)::SMALLINT
WHERE published_year IS NULL
  AND title ~ '\(\d{4}\)';

CREATE INDEX IF NOT EXISTS idx_documents_published_year
  ON documents (published_year)
  WHERE published_year IS NOT NULL;
