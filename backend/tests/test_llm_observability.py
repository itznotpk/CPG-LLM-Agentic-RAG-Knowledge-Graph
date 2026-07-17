"""PHI-free degradation and run-manifest harvesting contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agent.api import _harvest_machine_signals
from agent.llm_runtime import begin_llm_run, end_llm_run, record_degradation


@pytest.mark.asyncio
async def test_harvest_emits_one_safe_manifest(monkeypatch):
    monkeypatch.setenv("APP_COMMIT_SHA", "abc123")
    monkeypatch.setenv("CPG_CORPUS_VERSION", "moh-2026-07")
    result = SimpleNamespace(
        treatment_plan=SimpleNamespace(gate_audit=[], unresolved_questions=[]),
        stage_errors=[],
        cpgs=[SimpleNamespace(document_id="cpg-2"), SimpleNamespace(document_id="cpg-1")],
    )
    token = begin_llm_run("req-1", 42)
    try:
        record_degradation("prep_brief", "empty_content")
        writer = AsyncMock()
        with patch("agent.db_utils.log_machine_signal", writer):
            await _harvest_machine_signals(result, 42)
    finally:
        end_llm_run(token)

    manifests = [c for c in writer.await_args_list if c.args[0] == "run_manifest"]
    assert len(manifests) == 1
    payload = manifests[0].kwargs["payload"]
    assert payload["schema_version"] == 1
    assert payload["cpg_documents"] == ["cpg-1", "cpg-2"]
    assert payload["operations"][0]["reason"] == "empty_content"
    serialized = str(payload).lower()
    assert "api_key" not in serialized
    assert "base_url" not in serialized
    assert "patient" not in serialized
