"""
Tests for CPG scope columns on the documents table (Step 02).

Verifies the seven new columns, GIN index, and array-containment query
patterns that Stage 3 ICD→CPG routing will rely on.
"""

import pytest


# ---------------------------------------------------------------------------
# Schema structure tests
# ---------------------------------------------------------------------------

async def test_scope_columns_exist(db_conn):
    rows = await db_conn.fetch(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'documents'
        ORDER BY ordinal_position
        """
    )
    col_map = {r["column_name"]: r["data_type"] for r in rows}

    assert "icd11_scope" in col_map,     "icd11_scope column missing"
    assert "procedure_scope" in col_map, "procedure_scope column missing"
    assert "scope_rationale" in col_map, "scope_rationale column missing"
    assert "scope_verified" in col_map,  "scope_verified column missing"
    assert "classified_at" in col_map,   "classified_at column missing"
    assert "verified_at" in col_map,     "verified_at column missing"
    assert "verified_by" in col_map,     "verified_by column missing"

    assert col_map["icd11_scope"] == "ARRAY"
    assert col_map["procedure_scope"] == "ARRAY"
    assert col_map["scope_rationale"] == "text"
    assert col_map["scope_verified"] == "boolean"
    assert col_map["classified_at"] == "timestamp with time zone"
    assert col_map["verified_at"] == "timestamp with time zone"
    assert col_map["verified_by"] == "text"


async def test_gin_index_exists(db_conn):
    row = await db_conn.fetchrow(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'documents'
          AND indexname = 'idx_documents_icd_scope'
        """
    )
    assert row is not None, "GIN index idx_documents_icd_scope not found"


# ---------------------------------------------------------------------------
# Data / routing pattern tests
# ---------------------------------------------------------------------------

async def test_insert_and_query_by_scope(db_conn):
    source = "TEST_FIXTURE_AF_scope_query"
    try:
        await db_conn.execute(
            """
            INSERT INTO documents (title, source, content, icd11_scope)
            VALUES ('TEST_FIXTURE_AF', $1, 'fixture content', ARRAY['BC81'])
            """,
            source,
        )
        rows = await db_conn.fetch(
            """
            SELECT id FROM documents
            WHERE 'BC81' = ANY(icd11_scope)
              AND title = 'TEST_FIXTURE_AF'
            """
        )
        assert len(rows) == 1
    finally:
        await db_conn.execute(
            "DELETE FROM documents WHERE source = $1", source
        )


async def test_default_scope_verified_false(db_conn):
    source = "TEST_FIXTURE_default_verified"
    try:
        await db_conn.execute(
            """
            INSERT INTO documents (title, source, content)
            VALUES ('TEST_FIXTURE_DEFAULT', $1, 'fixture content')
            """,
            source,
        )
        row = await db_conn.fetchrow(
            "SELECT scope_verified FROM documents WHERE source = $1", source
        )
        assert row is not None
        assert row["scope_verified"] is False
    finally:
        await db_conn.execute(
            "DELETE FROM documents WHERE source = $1", source
        )


async def test_array_overlap_pattern(db_conn):
    source_af = "TEST_FIXTURE_overlap_BC81"
    source_other = "TEST_FIXTURE_overlap_BA"
    try:
        await db_conn.execute(
            """
            INSERT INTO documents (title, source, content, icd11_scope)
            VALUES ('TEST_FIXTURE_OVERLAP_AF', $1, 'fixture content', ARRAY['BC81'])
            """,
            source_af,
        )
        await db_conn.execute(
            """
            INSERT INTO documents (title, source, content, icd11_scope)
            VALUES ('TEST_FIXTURE_OVERLAP_OTHER', $1, 'fixture content', ARRAY['BA00','BA01'])
            """,
            source_other,
        )
        rows = await db_conn.fetch(
            """
            SELECT id FROM documents
            WHERE icd11_scope && ARRAY['BC81','BC82']::TEXT[]
              AND source = ANY($1::text[])
            """,
            [source_af, source_other],
        )
        assert len(rows) == 1
    finally:
        await db_conn.execute(
            "DELETE FROM documents WHERE source = ANY($1::text[])",
            [source_af, source_other],
        )
