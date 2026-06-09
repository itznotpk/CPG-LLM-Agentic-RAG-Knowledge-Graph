"""
Tests for agent/routing.py (Deliverable 1) and scoped retrieval in
agent/tools.py + agent/db_utils.py (Deliverable 2).

All tests are fully mocked — no real DB, no real embeddings, no external calls.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to build fake asyncpg Row-like objects
# ---------------------------------------------------------------------------

def _row(**kwargs):
    """Return a dict that also supports attribute-style access (like asyncpg.Record)."""
    class _Record(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)
    return _Record(kwargs)


# ---------------------------------------------------------------------------
# Routing — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exact_match():
    doc = _row(id="doc-1", title="AF CPG", icd11_scope=["BC81.3"], cpg_name="AF CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[doc])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BC81.3")

    assert len(results) == 1
    assert results[0].match_type == "exact"
    assert results[0].score == 1.0
    assert results[0].matched_scope == "BC81.3"


@pytest.mark.asyncio
async def test_ancestor_d1_match():
    doc = _row(id="doc-2", title="Some CPG", icd11_scope=["BC81"], cpg_name="Some CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=[
        [],                         # exact
        [],                         # range
        [],                         # siblings
        [_row(code="BC81", depth=1)],  # ancestors
        [doc],                      # ancestor scope match
    ])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BC81.3")

    assert len(results) == 1
    assert results[0].match_type == "ancestor_d1"
    assert results[0].matched_scope == "BC81"


@pytest.mark.asyncio
async def test_ancestor_d1_4char_match():
    doc = _row(id="doc-3", title="STEMI CPG", icd11_scope=["BA41"], cpg_name="STEMI CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=[
        [],
        [],
        [],
        [_row(code="BA41", depth=1)],
        [doc],
    ])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BA41.0")

    assert len(results) == 1
    assert results[0].match_type == "ancestor_d1"
    assert results[0].matched_scope == "BA41"


@pytest.mark.asyncio
async def test_range_match():
    # structural returns nothing; _range_match should find it
    doc = _row(id="doc-4", title="Range CPG", icd11_scope=["BC60-BC9Z"], cpg_name="Range CPG")

    mock_conn = AsyncMock()
    # first call: _structural_match (returns empty)
    # second call: _range_match (returns all docs)
    mock_conn.fetch = AsyncMock(side_effect=[[], [doc], [], []])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BC81")

    assert len(results) == 1
    assert results[0].matched_scope == "BC60-BC9Z"


@pytest.mark.asyncio
async def test_range_no_match():
    doc = _row(id="doc-4", title="Range CPG", icd11_scope=["BC60-BC9Z"], cpg_name="Range CPG")

    mock_conn = AsyncMock()
    # exact empty, range fetch returns doc but BA00 is outside BC60-BC9Z,
    # then structural fallbacks all miss.
    mock_conn.fetch = AsyncMock(side_effect=[[], [doc], [], [], [], []])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        # semantic scope fallback is also mocked to return empty
        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[])):
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("BA00")

    assert len(results) == 0


@pytest.mark.asyncio
async def test_multi_code_dedup():
    # Document has both 'BC81' and 'BC81.3'; querying BC81.3 should match exact
    # but the CPG should appear only once.
    doc = _row(id="doc-5", title="AF CPG", icd11_scope=["BC81", "BC81.3"], cpg_name="AF CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[doc])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BC81.3")

    assert len(results) == 1
    assert results[0].document_id == "doc-5"
    assert results[0].match_type == "exact"


@pytest.mark.asyncio
async def test_semantic_fallback_fires_on_no_structural():
    mock_conn = AsyncMock()
    # exact, range, siblings, ancestors, ancestor siblings, sibling children all miss
    mock_conn.fetch = AsyncMock(side_effect=[[], [], [], [], [], []])

    semantic_result = MagicMock()
    semantic_result.document_id = "doc-sem"
    semantic_result.cpg_name = "Sem CPG"
    semantic_result.match_type = "semantic_scope"

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[semantic_result])) as mock_sem:
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("ZZ99")

    mock_sem.assert_awaited_once()
    assert results[0].document_id == "doc-sem"


@pytest.mark.asyncio
async def test_sibling_fallback_after_ancestor_misses():
    doc = _row(id="doc-sib", title="Sibling CPG", icd11_scope=["BA41.1"], cpg_name="Sibling CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=[
        [],                              # exact
        [],                              # range
        [_row(code="BA41.1")],           # siblings
        [doc],                           # sibling scope match
    ])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BA41.0")

    assert len(results) == 1
    assert results[0].match_type == "sibling"
    assert results[0].matched_scope == "BA41.1"


@pytest.mark.asyncio
async def test_semantic_fallback_threshold():
    """Results below threshold must be excluded by _semantic_scope_match."""
    from agent.routing import _semantic_scope_match

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=[0.1] * 1536)
    candidate_above = _row(id="doc-above", cpg_name="CPG A", title="CPG A", similarity=0.75)
    candidate_below = _row(id="doc-below", cpg_name="CPG B", title="CPG B", similarity=0.40)
    mock_conn.fetch = AsyncMock(return_value=[candidate_above, candidate_below])

    results = await _semantic_scope_match(mock_conn, "ZZ00")

    doc_ids = [r.document_id for r in results]
    assert "doc-above" in doc_ids
    assert "doc-below" not in doc_ids


@pytest.mark.asyncio
async def test_semantic_fallback_skipped_when_structural_matches():
    doc = _row(id="doc-7", title="HTN CPG", icd11_scope=["BA00"], cpg_name="HTN CPG")

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[doc])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock()) as mock_sem:
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("BA00")

    mock_sem.assert_not_awaited()
    assert len(results) == 1


@pytest.mark.asyncio
async def test_unknown_icd_code_returns_empty():
    """When the code is not in icd11_codes, semantic scope matching yields no CPG.

    _semantic_scope_match now compares server-side via a single join (no Python
    round-trip of the embedding), so an unknown code simply produces no join rows.
    """
    from agent.routing import _semantic_scope_match

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])  # join yields nothing (no embedding / no match)

    results = await _semantic_scope_match(mock_conn, "XX99ZZ")

    assert results == []


@pytest.mark.asyncio
async def test_returns_at_most_top_k():
    # 5 rows with distinct cpg_names so they don't collapse into one CPG
    docs = [
        _row(id=f"doc-{i}", title=f"CPG {i}", icd11_scope=["BA00"], cpg_name=f"CPG {i}")
        for i in range(5)
    ]

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=docs)

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BA00", top_k=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_empty_scope_verified_false():
    """Documents with scope_verified=FALSE must not be returned (SQL WHERE filters them)."""
    mock_conn = AsyncMock()
    # The SQL already filters scope_verified=TRUE; simulate DB returning nothing
    mock_conn.fetch = AsyncMock(side_effect=[[], [], [], [], [], []])

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("agent.routing._semantic_scope_match", new=AsyncMock(return_value=[])):
            from agent.routing import route_icd_to_cpgs
            results = await route_icd_to_cpgs("BC81.3")

    assert results == []


# ---------------------------------------------------------------------------
# CPGDocRef grouping tests (new for Step 07)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cpgdocref_has_document_ids():
    """13 section rows for the same CPG → one CPGDocRef with 13 document_ids."""
    docs = [
        _row(id=f"af-section-{i}", title="AF CPG", icd11_scope=["BC81.3"], cpg_name="AF CPG")
        for i in range(13)
    ]

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=docs)

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BC81.3", top_k=5)

    assert len(results) == 1, "13 section rows should collapse to 1 CPGDocRef"
    assert len(results[0].document_ids) == 13
    assert results[0].cpg_name == "AF CPG"


@pytest.mark.asyncio
async def test_route_top_k_is_cpg_count():
    """2 CPGs with 10 rows each → top_k=1 returns 1 CPGDocRef with 10 document_ids."""
    cpg_a_rows = [
        _row(id=f"cpg-a-{i}", title="CPG A", icd11_scope=["BA00"], cpg_name="CPG A")
        for i in range(10)
    ]
    cpg_b_rows = [
        _row(id=f"cpg-b-{i}", title="CPG B", icd11_scope=["BA00"], cpg_name="CPG B")
        for i in range(10)
    ]
    all_docs = cpg_a_rows + cpg_b_rows

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=all_docs)

    with patch("agent.routing.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        from agent.routing import route_icd_to_cpgs
        results = await route_icd_to_cpgs("BA00", top_k=1)

    assert len(results) == 1, "top_k=1 should return exactly 1 CPGDocRef"
    assert len(results[0].document_ids) == 10


# ---------------------------------------------------------------------------
# Scoped retrieval — db_utils unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vector_search_with_filter():
    """With document_id_filter, the inline SQL with ANY($3::uuid[]) must be used."""
    from agent.db_utils import vector_search

    fake_row = _row(
        chunk_id="cid-1",
        document_id="doc-uuid-1",
        content="chunk text",
        similarity=0.9,
        metadata="{}",
        document_title="Some CPG",
        document_source="http://example.com",
    )

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[fake_row])

    with patch("agent.db_utils.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await vector_search(
            embedding=[0.1] * 1536,
            limit=5,
            document_id_filter=["doc-uuid-1"],
        )

    args, kwargs = mock_conn.fetch.call_args
    assert len(args) == 4  # query, embedding_str, limit, id_list
    assert "match_chunks" not in args[0]
    assert "ANY($3::uuid[])" in args[0]
    assert results[0]["document_id"] == "doc-uuid-1"


@pytest.mark.asyncio
async def test_vector_search_without_filter():
    """Without document_id_filter, match_chunks SQL function must be called."""
    from agent.db_utils import vector_search

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    with patch("agent.db_utils.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        await vector_search(embedding=[0.1] * 1536, limit=5)

    args, _ = mock_conn.fetch.call_args
    assert "match_chunks" in args[0]


@pytest.mark.asyncio
async def test_hybrid_search_with_filter():
    """With document_id_filter, hybrid search must use inline SQL, not the DB function."""
    from agent.db_utils import hybrid_search

    fake_row = _row(
        chunk_id="cid-2",
        document_id="doc-uuid-2",
        content="hybrid text",
        combined_score=0.85,
        vector_similarity=0.8,
        text_similarity=0.7,
        metadata="{}",
        document_title="Some CPG",
        document_source="http://example.com",
    )

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[fake_row])

    with patch("agent.db_utils.db_pool") as mock_pool:
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await hybrid_search(
            embedding=[0.1] * 1536,
            query_text="some query",
            limit=5,
            document_id_filter=["doc-uuid-2"],
        )

    args, _ = mock_conn.fetch.call_args
    assert "hybrid_search" not in args[0]
    assert "ANY($5::uuid[])" in args[0]
    assert results[0]["document_id"] == "doc-uuid-2"


@pytest.mark.asyncio
async def test_graph_search_filter_logs_warning(caplog):
    """Passing document_id_filter to graph_search_tool must log a warning."""
    from agent.tools import GraphSearchInput, graph_search_tool

    with patch("agent.tools.search_knowledge_graph", new=AsyncMock(return_value=[])):
        with caplog.at_level(logging.WARNING, logger="agent.tools"):
            await graph_search_tool(
                GraphSearchInput(query="test", document_id_filter=["some-id"])
            )

    assert any("document_id_filter" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Integration smoke (mocked DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_route_then_filter_roundtrip():
    """
    Simulate the full routing → scoped retrieval flow.
    route_icd_to_cpgs returns one CPGDocRef; vector_search_tool is then
    called with that document_id as filter and must use the filtered path.
    """
    from agent.routing import CPGDocRef
    from agent.tools import VectorSearchInput, vector_search_tool

    routed_ref = CPGDocRef(
        cpg_name="AF CPG",
        document_id="abc-doc-uuid",
        document_ids=["abc-doc-uuid"],
        title="AF CPG",
        match_type="exact",
        score=1.0,
        matched_scope="BC81.3",
    )

    with patch("agent.routing.route_icd_to_cpgs", new=AsyncMock(return_value=[routed_ref])):
        fake_row = _row(
            chunk_id="cid-rt",
            document_id="abc-doc-uuid",
            content="content",
            similarity=0.88,
            metadata="{}",
            document_title="AF CPG",
            document_source="http://example.com",
        )
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[fake_row])

        with patch("agent.db_utils.db_pool") as mock_pool:
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("agent.tools.generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)):
                results = await vector_search_tool(
                    VectorSearchInput(
                        query="atrial fibrillation treatment",
                        limit=5,
                        document_id_filter=["abc-doc-uuid"],
                    )
                )

    args, _ = mock_conn.fetch.call_args
    assert "ANY($3::uuid[])" in args[0]
    assert results[0].document_id == "abc-doc-uuid"
