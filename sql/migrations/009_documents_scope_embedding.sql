-- D2: semantic CPG fallback support.
--
-- Embeds each document's clinical scope summary so Stage 3 can fall back to
-- semantically related CPGs only after exact/ancestor/sibling ICD routing miss.

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS scope_embedding vector(1536);

CREATE INDEX IF NOT EXISTS idx_documents_scope_embedding
  ON documents USING ivfflat (scope_embedding vector_cosine_ops) WITH (lists = 16);
