-- D3: Exclusion-aware DDx re-ranking support.
--
-- Stores one embedding per WHO ICD-11 exclusion phrase, keyed by the raw
-- exclusion text. Shape mirrors inclusion_embeddings, but is exclusion-term-only.

ALTER TABLE icd11_codes
  ADD COLUMN IF NOT EXISTS exclusion_embeddings JSONB DEFAULT '{}';
