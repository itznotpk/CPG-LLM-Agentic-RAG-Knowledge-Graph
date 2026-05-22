"""
Tests for agent/routing.py (Deliverable 1) and scoped retrieval in
agent/tools.py + agent/db_utils.py (Deliverable 2).

D1 routing is the six-level structural walk:
    exact -> sibling -> ancestor_d1 -> ancestor_d1_sibling
          -> ancestor_d1_sibling_child -> ancestor_d2 -> none
The retired D2 semantic fallback (_semantic_fallback) no longer exists; these
tests exercise the structural walk only.

All tests are fully mocked — no real DB, no real embeddings, no external calls.
The mock conn simulates the two document-scope queries the router issues
(_scope_code_match and _range_match); the ICD tree helpers
(fetch_icd_siblings / fetch_icd_ancestors / fetch_icd_ancestor_siblings /
fetch_icd_ancestor_sibling_children) are patched per test so each test states
exactly which structural neighbours exist.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

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


@contextmanager
def _routing_env(
    docs,
    *,
    siblings=None,
    ancestors=None,
    anc_siblings=None,
    anc_sibling_children=None,
):
    """
    Set up a mocked routing environment.

    `docs` is the simulated `documents` table (each a _row with id/title/
    icd11_scope/cpg_name). The mock conn.fetch interprets the router's two
    document queries:
      - _scope_code_match: SQL contains "ANY(icd11_scope)", param[0] is the
        scope code -> return docs whose icd11_scope contains that code.
      - _range_match: SQL has no scope param -> return all (verified) docs,
        letting the router's own range logic filter them.

    The four ICD-tree helpers are patched to return the supplied neighbour
    code lists (ancestors as [{"code", "depth"}], the rest as [code, ...]).
    """
    async def _fetch(sql, *params):
        if "ANY(icd11_scope)" in sql:
            scope_code = params[0]
            return [d for d in docs if scope_code in (d["icd11_scope"] or [])]
        return list(docs)  # _range_match: all verified docs

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(side_effect=_fetch)

    with patch("agent.routing.db_pool") as mock_pool, patch(
        "agent.routing.fetch_icd_siblings",
        new=AsyncMock(return_value=siblings or []),
    ), patch(
        "agent.routing.fetch_icd_ancestors",
        new=AsyncMock(return_value=ancestors or []),
    ), patch(
        "agent.routing.fetch_icd_ancestor_siblings",
        new=AsyncMock(return_value=anc_siblings or []),
    ), patch(
        "agent.routing.fetch_icd_ancestor_sibling_children",
        new=AsyncMock(return_value=anc_sibling_children or []),
    ):
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_conn


# ---------------------------------------------------------------------------
# D1 — six-level structural routing (find_cpgs_for_code)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exact_match():
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-1", title="AF CPG", icd11_scope=["BC81.3"], cpg_name="AF CPG")]
    with _routing_env(docs) as conn:
        refs, method = await find_cpgs_for_code("BC81.3", conn)

    assert method == "exact"
    assert len(refs) == 1
    assert refs[0].match_type == "exact"
    assert refs[0].score == 1.0
    assert refs[0].matched_scope == "BC81.3"


@pytest.mark.asyncio
async def test_range_match_is_exact():
    """A code that falls inside a range entry (BC60-BC9Z) routes as exact."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-r", title="Range CPG", icd11_scope=["BC60-BC9Z"], cpg_name="Range CPG")]
    with _routing_env(docs) as conn:
        refs, method = await find_cpgs_for_code("BC81", conn)

    assert method == "exact"
    assert len(refs) == 1
    assert refs[0].matched_scope == "BC60-BC9Z"


@pytest.mark.asyncio
async def test_sibling_match_when_no_exact():
    """Exact miss; a same-parent sibling (BA41.1) is in scope -> sibling."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-sib", title="Sibling CPG", icd11_scope=["BA41.1"], cpg_name="Sibling CPG")]
    with _routing_env(docs, siblings=["BA41.1", "BA41.Z"]) as conn:
        refs, method = await find_cpgs_for_code("BA41.0", conn)

    assert method == "sibling"
    assert refs[0].match_type == "sibling"
    assert refs[0].matched_scope == "BA41.1"


@pytest.mark.asyncio
async def test_ancestor_d1_match():
    """Exact + siblings miss; the direct parent (BC81) is in scope -> ancestor_d1."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-2", title="Some CPG", icd11_scope=["BC81"], cpg_name="Some CPG")]
    with _routing_env(
        docs,
        siblings=[],
        ancestors=[{"code": "BC81", "depth": 1}],
    ) as conn:
        refs, method = await find_cpgs_for_code("BC81.3", conn)

    assert method == "ancestor_d1"
    assert refs[0].matched_scope == "BC81"


@pytest.mark.asyncio
async def test_ancestor_d1_sibling_match():
    """Parent miss; a peer category of the parent (BA01) is in scope."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-as", title="HTN CPG", icd11_scope=["BA01"], cpg_name="HTN CPG")]
    with _routing_env(
        docs,
        ancestors=[{"code": "BA00", "depth": 1}],
        anc_siblings=["BA01", "BA02"],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA00.0", conn)

    assert method == "ancestor_d1_sibling"
    assert refs[0].matched_scope == "BA01"


@pytest.mark.asyncio
async def test_ancestor_d1_sibling_child_match():
    """Parent + its siblings miss; a child of a peer category (BA01.0) is in scope."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-asc", title="HTN CPG", icd11_scope=["BA01.0"], cpg_name="HTN CPG")]
    with _routing_env(
        docs,
        ancestors=[{"code": "BA00", "depth": 1}],
        anc_siblings=["BA01"],
        anc_sibling_children=["BA01.0", "BA01.Z"],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA00.0", conn)

    assert method == "ancestor_d1_sibling_child"
    assert refs[0].matched_scope == "BA01.0"


@pytest.mark.asyncio
async def test_ancestor_d2_match():
    """All nearer levels miss; the grandparent block (depth 2) is in scope."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-d2", title="Block CPG", icd11_scope=["BA00"], cpg_name="Block CPG")]
    with _routing_env(
        docs,
        ancestors=[{"code": "BA00.1", "depth": 1}, {"code": "BA00", "depth": 2}],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA00.10", conn)

    assert method == "ancestor_d2"
    assert refs[0].matched_scope == "BA00"


@pytest.mark.asyncio
async def test_ancestor_walk_stops_at_d2():
    """A depth-3+ code in scope is never reached (ANCESTOR_MAX_DEPTH=2) -> none."""
    from agent.routing import find_cpgs_for_code

    # The only in-scope code would be a depth-3 ancestor, which the helper
    # (capped at max_depth=2) never returns.
    docs = [_row(id="doc-deep", title="Deep CPG", icd11_scope=["BA"], cpg_name="Deep CPG")]
    with _routing_env(
        docs,
        ancestors=[{"code": "BA00.1", "depth": 1}, {"code": "BA00", "depth": 2}],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA00.10", conn)

    assert method == "none"
    assert refs == []


@pytest.mark.asyncio
async def test_out_of_scope_returns_none():
    """Nothing matches at any structural level -> ([], 'none')."""
    from agent.routing import find_cpgs_for_code

    docs = [_row(id="doc-x", title="Unrelated CPG", icd11_scope=["ZZ99"], cpg_name="Unrelated CPG")]
    with _routing_env(
        docs,
        siblings=["BA41.1"],
        ancestors=[{"code": "BA41", "depth": 1}, {"code": "BA4", "depth": 2}],
        anc_siblings=["BA42"],
        anc_sibling_children=["BA42.0"],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA41.0", conn)

    assert method == "none"
    assert refs == []


@pytest.mark.asyncio
async def test_exact_beats_lower_levels():
    """When exact and a sibling both match, exact wins."""
    from agent.routing import find_cpgs_for_code

    docs = [
        _row(id="doc-exact", title="Exact CPG", icd11_scope=["BA41.0"], cpg_name="Exact CPG"),
        _row(id="doc-sib", title="Sibling CPG", icd11_scope=["BA41.1"], cpg_name="Sibling CPG"),
    ]
    with _routing_env(docs, siblings=["BA41.1"]) as conn:
        refs, method = await find_cpgs_for_code("BA41.0", conn)

    assert method == "exact"
    assert refs[0].cpg_name == "Exact CPG"


@pytest.mark.asyncio
async def test_sibling_beats_ancestor():
    """When both a sibling and the parent are in scope, sibling wins (checked first)."""
    from agent.routing import find_cpgs_for_code

    docs = [
        _row(id="doc-sib", title="Sibling CPG", icd11_scope=["BA41.1"], cpg_name="Sibling CPG"),
        _row(id="doc-anc", title="Ancestor CPG", icd11_scope=["BA41"], cpg_name="Ancestor CPG"),
    ]
    with _routing_env(
        docs,
        siblings=["BA41.1"],
        ancestors=[{"code": "BA41", "depth": 1}],
    ) as conn:
        refs, method = await find_cpgs_for_code("BA41.0", conn)

    assert method == "sibling"
    assert refs[0].cpg_name == "Sibling CPG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario_method",
    ["exact", "sibling", "ancestor_d1", "none"],
)
async def test_route_method_always_stamped(scenario_method):
    """Every routing path returns a non-empty route_method string."""
    from agent.routing import find_cpgs_for_code

    if scenario_method == "exact":
        docs = [_row(id="d", title="C", icd11_scope=["BA41.0"], cpg_name="C")]
        env = _routing_env(docs)
    elif scenario_method == "sibling":
        docs = [_row(id="d", title="C", icd11_scope=["BA41.1"], cpg_name="C")]
        env = _routing_env(docs, siblings=["BA41.1"])
    elif scenario_method == "ancestor_d1":
        docs = [_row(id="d", title="C", icd11_scope=["BA41"], cpg_name="C")]
        env = _routing_env(docs, ancestors=[{"code": "BA41", "depth": 1}])
    else:  # none
        docs = [_row(id="d", title="C", icd11_scope=["ZZ99"], cpg_name="C")]
        env = _routing_env(docs)

    with env as conn:
        _, method = await find_cpgs_for_code("BA41.0", conn)

    assert isinstance(method, str) and method
    assert method == scenario_method


# ---------------------------------------------------------------------------
# route_icd_to_cpgs — dedup / top_k / CPG grouping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_code_dedup():
    """A CPG listing both 'BC81' and 'BC81.3' appears once for an exact query."""
    from agent.routing import route_icd_to_cpgs

    docs = [_row(id="doc-5", title="AF CPG", icd11_scope=["BC81", "BC81.3"], cpg_name="AF CPG")]
    with _routing_env(docs):
        results = await route_icd_to_cpgs("BC81.3")

    assert len(results) == 1
    assert results[0].document_id == "doc-5"
    assert results[0].match_type == "exact"


@pytest.mark.asyncio
async def test_cpgdocref_has_document_ids():
    """13 section rows for the same CPG -> one CPGDocRef with 13 document_ids."""
    from agent.routing import route_icd_to_cpgs

    docs = [
        _row(id=f"af-section-{i}", title="AF CPG", icd11_scope=["BC81.3"], cpg_name="AF CPG")
        for i in range(13)
    ]
    with _routing_env(docs):
        results = await route_icd_to_cpgs("BC81.3", top_k=5)

    assert len(results) == 1, "13 section rows should collapse to 1 CPGDocRef"
    assert len(results[0].document_ids) == 13
    assert results[0].cpg_name == "AF CPG"


@pytest.mark.asyncio
async def test_returns_at_most_top_k():
    from agent.routing import route_icd_to_cpgs

    docs = [
        _row(id=f"doc-{i}", title=f"CPG {i}", icd11_scope=["BA00"], cpg_name=f"CPG {i}")
        for i in range(5)
    ]
    with _routing_env(docs):
        results = await route_icd_to_cpgs("BA00", top_k=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_route_top_k_is_cpg_count():
    """2 CPGs with 10 rows each -> top_k=1 returns 1 CPGDocRef with 10 document_ids."""
    from agent.routing import route_icd_to_cpgs

    docs = (
        [_row(id=f"cpg-a-{i}", title="CPG A", icd11_scope=["BA00"], cpg_name="CPG A") for i in range(10)]
        + [_row(id=f"cpg-b-{i}", title="CPG B", icd11_scope=["BA00"], cpg_name="CPG B") for i in range(10)]
    )
    with _routing_env(docs):
        results = await route_icd_to_cpgs("BA00", top_k=1)

    assert len(results) == 1, "top_k=1 should return exactly 1 CPGDocRef"
    assert len(results[0].document_ids) == 10


@pytest.mark.asyncio
async def test_empty_scope_returns_nothing():
    """No verified documents -> no route at any level -> empty list."""
    from agent.routing import route_icd_to_cpgs

    with _routing_env([]):
        results = await route_icd_to_cpgs("BC81.3")

    assert results == []


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
    assert "ANY($6::uuid[])" in args[0]
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
