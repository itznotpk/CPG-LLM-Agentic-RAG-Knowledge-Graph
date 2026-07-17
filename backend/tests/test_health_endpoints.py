"""Contracts for liveness, readiness, and strict provider probes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import JSONResponse

from agent.api import health_check, live_check, readiness_check
from agent.llm_runtime import LLMTarget


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "content", "expected"),
    [(200, "pong", True), (200, "", False), (400, "pong", False),
     (401, "pong", False), (404, "pong", False), (429, "pong", False),
     (500, "pong", False)],
)
async def test_probe_requires_2xx_and_nonempty_content(status, content, expected):
    from agent import api

    response = SimpleNamespace(
        status_code=status,
        json=lambda: {"choices": [{"message": {"content": content}}]},
    )
    client = AsyncMock()
    client.post.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    target = LLMTarget("test", "https://provider.test/v1", "secret", "model")

    api._LLM_PROBE_CACHE.clear()
    with patch("httpx.AsyncClient", return_value=client):
        assert await api._probe_llm(target) is expected


@pytest.mark.asyncio
async def test_liveness_has_no_dependency_calls():
    with patch("agent.api.test_connection", new=AsyncMock()) as db:
        body = await live_check()
    assert body["status"] == "alive"
    db.assert_not_awaited()


@pytest.mark.asyncio
async def test_ready_returns_503_when_configuration_is_incomplete():
    healthy = SimpleNamespace(
        model_dump=lambda **_: {
            "status": "degraded", "database": True, "graph_database": True,
            "llm_connection": True, "llm_synthesis": "ok", "llm_safety": "ok",
            "version": "0.1.0", "timestamp": "2026-07-17T00:00:00",
        }
    )
    with patch("agent.api._build_health_status", new=AsyncMock(return_value=healthy)), \
         patch("agent.api.configuration_defects", return_value=["Incomplete prep_brief tier"]):
        response = await readiness_check()
    assert isinstance(response, JSONResponse)
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_health_remains_compatible_when_degraded():
    status = SimpleNamespace(status="degraded")
    with patch("agent.api._build_health_status", new=AsyncMock(return_value=status)):
        assert await health_check() is status
