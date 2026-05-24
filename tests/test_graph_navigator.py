"""Tests for the Graph Navigator (Agent 2 v1 — Path A string-evidence preferred-agent rules)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import PatientCase
from agent.clinical_stages import DDxResult
from agent.graph_navigator import get_graph_constraints, _ddx_condition_names


def _case():
    return PatientCase(
        chief_complaint="poorly controlled diabetes",
        age=58, sex="F",
        comorbidities=["Hypertension"],
        current_medications=[],
        allergies=[],
    )


def _ddx():
    return [
        DDxResult(code="5A11", title="Type 2 diabetes mellitus", reason="HbA1c 8.5%", confidence=0.9, similarity=0.9),
        DDxResult(code="BA00", title="Essential hypertension", reason="BP 152/94", confidence=0.7, similarity=0.7),
    ]


def test_ddx_condition_names_takes_top_n_titles():
    names = _ddx_condition_names(_ddx(), limit=2)
    assert names == ["Type 2 diabetes mellitus", "Essential hypertension"]


def test_ddx_condition_names_empty_safe():
    assert _ddx_condition_names([]) == []
    assert _ddx_condition_names(None) == []


@pytest.mark.asyncio
async def test_get_graph_constraints_returns_prefer_flags():
    """Mocked Neo4j returning two FIRST_LINE_FOR edges → two PREFER flags."""
    fake_records = [
        {
            "drug": "Metformin", "cond": "Type 2 diabetes mellitus", "rel": "FIRST_LINE_FOR",
            "evidence": "Metformin remains the preferred first-line agent for T2DM.",
            "evidence_list": ["Metformin remains the preferred first-line agent for T2DM."],
            "source": "T2DM-CPG-6thEd", "chunk_id": "chunk-1", "chunk_ids": ["chunk-1"],
            "trigger": None,
        },
        {
            "drug": "ACE inhibitor", "cond": "Essential hypertension", "rel": "RECOMMENDED_FOR",
            "evidence": "ACEi preferred when diabetes co-exists for renoprotection.",
            "evidence_list": ["ACEi preferred when diabetes co-exists for renoprotection."],
            "source": "HTN-CPG-5thEd", "chunk_id": "chunk-2", "chunk_ids": ["chunk-2"],
            "trigger": "diabetes co-exists",
        },
    ]

    async def _aiter(_self):
        for r in fake_records:
            yield r

    fake_result = MagicMock()
    fake_result.__aiter__ = _aiter

    fake_session = MagicMock()
    fake_session.run = AsyncMock(return_value=fake_result)

    class _Ctx:
        async def __aenter__(self): return fake_session
        async def __aexit__(self, *a): return None

    with patch("agent.graph_navigator._get_neo4j_session",
               new=AsyncMock(return_value=_Ctx())):
        flags = await get_graph_constraints(_case(), _ddx())

    assert len(flags) == 2
    types = {f.flag_type for f in flags}
    assert types == {"PREFER"}
    drugs = sorted(f.subject for f in flags)
    assert drugs == ["ACE inhibitor", "Metformin"]
    # Trigger captured when present, None otherwise
    ace = next(f for f in flags if f.subject == "ACE inhibitor")
    assert ace.trigger == "diabetes co-exists"
    met = next(f for f in flags if f.subject == "Metformin")
    assert met.trigger is None
    # Severity is None for PREFER — must not flip safe_to_proceed downstream
    assert all(f.severity is None for f in flags)


@pytest.mark.asyncio
async def test_get_graph_constraints_short_circuits_on_no_conditions():
    """No DDx + no comorbidities → return [] without touching Neo4j."""
    case = PatientCase(chief_complaint="x", age=30, sex="M",
                       comorbidities=[], current_medications=[], allergies=[])
    with patch("agent.graph_navigator._get_neo4j_session") as session_mock:
        flags = await get_graph_constraints(case, [])
    assert flags == []
    session_mock.assert_not_called()


def test_is_table_row_noise_detects_pipe_separated_garbage():
    from agent.graph_navigator import _is_table_row_noise
    assert _is_table_row_noise("Asthma | + | - | + | + | + | +") is True
    assert _is_table_row_noise("ACEi | - | + | - | - | + | +") is True


def test_is_table_row_noise_passes_real_evidence():
    from agent.graph_navigator import _is_table_row_noise
    assert _is_table_row_noise("Metformin remains first-line for T2DM unless eGFR<30.") is False
    assert _is_table_row_noise("Pre-treatment with amiodarone, sotalol, flecainide.") is False
    assert _is_table_row_noise("") is False


@pytest.mark.asyncio
async def test_get_graph_constraints_drops_table_row_noise():
    """A PREFER edge whose evidence is a comparison-table row should be filtered out."""
    fake_records = [
        {
            "drug": "Metformin", "cond": "Type 2 diabetes mellitus", "rel": "FIRST_LINE_FOR",
            "evidence": "Metformin remains first-line for T2DM unless contraindicated.",
            "evidence_list": ["Metformin remains first-line for T2DM unless contraindicated."],
            "source": "T2DM-CPG", "chunk_id": "good-1", "chunk_ids": ["good-1"],
            "trigger": None,
        },
        {
            "drug": "ACE inhibitor", "cond": "Asthma", "rel": "RECOMMENDED_FOR",
            "evidence": "Asthma | + | - | + | + | + | +",
            "evidence_list": ["Asthma | + | - | + | + | + | +"],
            "source": "HTN-CPG", "chunk_id": "bad-1", "chunk_ids": ["bad-1"],
            "trigger": None,
        },
    ]
    async def _aiter(_self):
        for r in fake_records: yield r
    fake_result = MagicMock(); fake_result.__aiter__ = _aiter
    fake_session = MagicMock(); fake_session.run = AsyncMock(return_value=fake_result)
    class _Ctx:
        async def __aenter__(self): return fake_session
        async def __aexit__(self, *a): return None
    with patch("agent.graph_navigator._get_neo4j_session",
               new=AsyncMock(return_value=_Ctx())):
        flags = await get_graph_constraints(_case(), _ddx())
    assert len(flags) == 1
    assert flags[0].subject == "Metformin"


@pytest.mark.asyncio
async def test_get_graph_constraints_scopes_to_routed_cpgs():
    """When cpgs are provided, PREFER edges whose cpg_chunk_id is not in any
    routed CPG's chunk set must be dropped."""
    fake_records = [
        {
            "drug": "Metformin", "cond": "Type 2 diabetes mellitus", "rel": "FIRST_LINE_FOR",
            "evidence": "Metformin first-line for T2DM.",
            "evidence_list": ["Metformin first-line for T2DM."],
            "source": "T2DM-CPG", "chunk_id": "in-scope-chunk", "chunk_ids": ["in-scope-chunk"],
            "trigger": None,
        },
        {
            "drug": "Beta-Blocker", "cond": "Essential hypertension", "rel": "FIRST_LINE_FOR",
            "evidence": "BB recommended post-MI for HTN secondary prevention.",
            "evidence_list": ["BB recommended post-MI."],
            "source": "AF-CPG", "chunk_id": "out-of-scope-chunk", "chunk_ids": ["out-of-scope-chunk"],
            "trigger": None,
        },
    ]
    async def _aiter(_self):
        for r in fake_records: yield r
    fake_result = MagicMock(); fake_result.__aiter__ = _aiter
    fake_session = MagicMock(); fake_session.run = AsyncMock(return_value=fake_result)
    class _Ctx:
        async def __aenter__(self): return fake_session
        async def __aexit__(self, *a): return None

    class _CPG:
        def __init__(self, doc_ids): self.document_ids = doc_ids

    with patch("agent.graph_navigator._get_neo4j_session",
               new=AsyncMock(return_value=_Ctx())), \
         patch("agent.graph_navigator._fetch_routed_chunk_ids",
               new=AsyncMock(return_value={"in-scope-chunk"})):
        flags = await get_graph_constraints(_case(), _ddx(), cpgs=[_CPG(["doc-T2DM"])])

    assert len(flags) == 1
    assert flags[0].subject == "Metformin"


@pytest.mark.asyncio
async def test_get_graph_constraints_no_cpgs_skips_scope_filter():
    """Backward-compat: when cpgs is None/empty, scope filter is not applied —
    all (non-noise) rules pass through."""
    fake_records = [
        {
            "drug": "Metformin", "cond": "T2DM", "rel": "FIRST_LINE_FOR",
            "evidence": "good", "evidence_list": ["good"],
            "source": "X", "chunk_id": "any", "chunk_ids": ["any"], "trigger": None,
        },
    ]
    async def _aiter(_self):
        for r in fake_records: yield r
    fake_result = MagicMock(); fake_result.__aiter__ = _aiter
    fake_session = MagicMock(); fake_session.run = AsyncMock(return_value=fake_result)
    class _Ctx:
        async def __aenter__(self): return fake_session
        async def __aexit__(self, *a): return None
    with patch("agent.graph_navigator._get_neo4j_session",
               new=AsyncMock(return_value=_Ctx())):
        flags = await get_graph_constraints(_case(), _ddx(), cpgs=None)
    assert len(flags) == 1


@pytest.mark.asyncio
async def test_get_graph_constraints_fails_open():
    """Neo4j error → [] (never raises)."""
    with patch("agent.graph_navigator._get_neo4j_session",
               new=AsyncMock(side_effect=RuntimeError("neo4j down"))):
        flags = await get_graph_constraints(_case(), _ddx())
    assert flags == []
