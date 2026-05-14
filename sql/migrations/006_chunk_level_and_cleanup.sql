-- Migration 006: add chunk_level / start_char / end_char; drop 5 dead columns.
-- Idempotent: safe to re-run on a populated DB.
--
-- Rationale: Phase A Step 2 introduces H1-parent / H2-child hierarchy.
-- chunk_level discriminates the two tiers so retrieval can filter to H2 only.
-- start_char/end_char record child position inside the parent for window slicing.
-- The five dropped columns were written only by an old PDF parser that is no
-- longer used; the markdown ingestion path never populated them.

-- 1. New columns
ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS chunk_level TEXT NOT NULL DEFAULT 'h1_leaf';

ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS start_char INTEGER;

ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS end_char INTEGER;

-- 2. Index for chunk_level filtering (retrieval hot path)
CREATE INDEX IF NOT EXISTS idx_chunks_level ON chunks (chunk_level);

-- 3. Drop dead indexes before dropping columns (Postgres requires this order)
DROP INDEX IF EXISTS idx_chunks_recommendations;
DROP INDEX IF EXISTS idx_chunks_tables;
DROP INDEX IF EXISTS idx_chunks_algorithms;

-- 4. Drop dead columns
ALTER TABLE chunks DROP COLUMN IF EXISTS is_recommendation;
ALTER TABLE chunks DROP COLUMN IF EXISTS is_table;
ALTER TABLE chunks DROP COLUMN IF EXISTS is_algorithm;
ALTER TABLE chunks DROP COLUMN IF EXISTS structured_content;
ALTER TABLE chunks DROP COLUMN IF EXISTS section_hierarchy;
