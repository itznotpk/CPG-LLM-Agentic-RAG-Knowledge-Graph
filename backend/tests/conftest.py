"""
Shared pytest fixtures for CPG LLM test suite.
"""

import pytest
import pytest_asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


@pytest_asyncio.fixture
async def db_conn():
    """Per-test asyncpg connection."""
    url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(url)
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
def _no_live_ebm_fetch(monkeypatch):
    """Stub agent.clinical_workflow.fetch_ebm_evidence so the Stage 5.5 EBM
    pass never hits the real Europe PMC HTTP API (or, by extension, the
    refine LLM, since stage_5_5_refine short-circuits on empty evidence).

    Workflow tests (test_clinical_workflow.py, test_streaming.py,
    test_e2e_smoke.py, test_functional_scenarios.py, test_resynthesize.py)
    mock stages 2-5 but previously left _apply_ebm_pass unmocked, so every
    run traversed live network calls. test_ebm_wiring.py tests this seam
    directly and monkeypatches over this stub as needed within each test —
    safe, since monkeypatch.setattr calls layer in call order and both are
    undone at teardown regardless of order.
    """
    try:
        import agent.clinical_workflow as wf
    except ImportError:
        return

    async def _empty_ebm(*args, **kwargs):
        return []

    monkeypatch.setattr(wf, "fetch_ebm_evidence", _empty_ebm, raising=False)
