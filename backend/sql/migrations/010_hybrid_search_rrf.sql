-- Migration 010: Replace linear weighted fusion with Reciprocal Rank Fusion (RRF).
-- Fixes hybrid Recall@10 < vector Recall@10: linear fusion penalised chunks with
-- no keyword match (text_sim=0 subtracted from combined_score). RRF avoids this —
-- a keyword miss contributes 0 rather than actively dragging the score down.
-- k=60 is the standard RRF constant (Robertson 2009); raise it to reduce the
-- influence of top ranks, lower it to amplify rank differences.

DROP FUNCTION IF EXISTS hybrid_search(vector, TEXT, INT, FLOAT);

CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text TEXT,
    match_count INT DEFAULT 10,
    rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    combined_score FLOAT,
    vector_similarity FLOAT,
    text_similarity FLOAT,
    metadata JSONB,
    document_title TEXT,
    document_source TEXT,
    chunk_level TEXT,
    start_char INTEGER,
    end_char INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS vector_sim,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS vector_rank,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source,
            c.chunk_level,
            c.start_char,
            c.end_char
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
    ),
    text_results AS (
        SELECT
            c.id AS chunk_id,
            ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) AS text_sim,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) DESC
            ) AS text_rank
        FROM chunks c
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
          AND c.embedding IS NOT NULL
    )
    SELECT
        v.chunk_id,
        v.document_id,
        v.content,
        -- RRF: keyword miss contributes 0, never subtracts from vector score
        (1.0 / (rrf_k + v.vector_rank) + COALESCE(1.0 / (rrf_k + t.text_rank), 0)) AS combined_score,
        v.vector_sim AS vector_similarity,
        COALESCE(t.text_sim, 0) AS text_similarity,
        v.metadata,
        v.doc_title AS document_title,
        v.doc_source AS document_source,
        v.chunk_level,
        v.start_char,
        v.end_char
    FROM vector_results v
    LEFT JOIN text_results t ON v.chunk_id = t.chunk_id
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;
