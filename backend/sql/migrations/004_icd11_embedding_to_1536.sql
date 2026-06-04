-- Migration 004: align icd11_codes.embedding with chunks.embedding at 1536 dimensions.
--
-- Background:
--   The original Chapter 17 ingest (47 rows) used Bedrock Titan v1 with a
--   `[:dimension]` truncation when VECTOR_DIMENSION=768. Today VECTOR_DIMENSION
--   is 1536 and CPG chunks live in vector(1536) space. Two embedding spaces
--   creates dimension juggling for downstream cross-table operations
--   (semantic CPG fallback in Step 06). Truncation of Titan embeddings is also
--   lossy — those dimensions aren't ordered by importance, so chopping the
--   latter half degrades semantic geometry.
--
-- This migration:
--   1. Changes icd11_codes.embedding type from vector(768) to vector(1536),
--      setting all existing values to NULL.
--   2. Re-embedding the 47 Chapter-17 rows is done OUTSIDE this migration by
--      re-running `python -m ddx.ingest_icd11` (the existing markdown ingester
--      is idempotent via ON CONFLICT (code) DO UPDATE).
--
-- Run order:
--   1. Apply this migration (clears 768-dim embeddings).
--   2. Run `python -m ddx.ingest_icd11` to re-populate Chapter 17 at 1536-dim.
--   3. Run Step 05 (`python -m ddx.ingest_icd11_full --chapters 02,05,08,11,16`).
--
-- Notes:
--   - inclusion_embeddings (JSONB) is left alone. If you use it for inclusion
--     similarity search, re-run `ddx/migrate_inclusion_embeddings.py` after
--     step 2 to regenerate at 1536-dim — separate concern.
--   - No index drop needed: there is no ivfflat/hnsw index on this column
--     today.

BEGIN;

-- 1. Confirm the table exists and capture pre-migration state for the audit log.
DO $$
DECLARE
    n INTEGER;
BEGIN
    SELECT COUNT(*) INTO n FROM icd11_codes;
    RAISE NOTICE 'icd11_codes pre-migration row count: %', n;

    SELECT COUNT(*) INTO n FROM icd11_codes WHERE embedding IS NOT NULL;
    RAISE NOTICE 'icd11_codes rows with non-null embedding (will be cleared): %', n;
END $$;

-- 2. Change the column type. USING NULL clears all existing values — we'll
--    re-embed in the next manual step. Postgres will validate the new
--    dimension on subsequent inserts.
ALTER TABLE icd11_codes
    ALTER COLUMN embedding TYPE vector(1536)
    USING NULL;

-- 3. Sanity check: column is now vector(1536) and all rows have NULL embedding.
DO $$
DECLARE
    typmod  INTEGER;
    expected_typmod CONSTANT INTEGER := 1536;
    null_count INTEGER;
    total INTEGER;
BEGIN
    SELECT atttypmod INTO typmod
    FROM pg_attribute
    WHERE attrelid = 'icd11_codes'::regclass
      AND attname = 'embedding';

    -- pgvector stores the dimension directly in atttypmod
    IF typmod <> expected_typmod THEN
        RAISE EXCEPTION 'icd11_codes.embedding dim is %, expected %', typmod, expected_typmod;
    END IF;

    SELECT COUNT(*) INTO total FROM icd11_codes;
    SELECT COUNT(*) INTO null_count FROM icd11_codes WHERE embedding IS NULL;

    IF null_count <> total THEN
        RAISE EXCEPTION 'After migration, expected all % rows to have NULL embedding; found % NULL', total, null_count;
    END IF;

    RAISE NOTICE 'icd11_codes.embedding is now vector(1536), all % rows have NULL embedding (re-ingest required).', total;
END $$;

COMMIT;
