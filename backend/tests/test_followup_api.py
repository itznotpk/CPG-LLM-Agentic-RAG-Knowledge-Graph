"""Followup API endpoint tests via FastAPI TestClient with mocked internals."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from agent.api import app
    return TestClient(app, raise_server_exceptions=False)


def test_enroll_returns_deep_link(client):
    payload = {"token": "t", "deep_link": "https://t.me/B?start=t", "expires_at": "2026-07-18T00:00:00+00:00"}
    with patch("agent.api.create_followup_enrollment", AsyncMock(return_value=payload)):
        r = client.post("/followup/enroll", json={"consultation_id": 101, "patient_nric": "X"})
    assert r.status_code == 200
    assert r.json()["deep_link"].startswith("https://t.me/")


def test_status_endpoint(client):
    with patch("agent.api.get_followup_status", AsyncMock(return_value={"status": "active"})):
        r = client.get("/followup/status/101")
    assert r.status_code == 200
    assert r.json() == {"status": "active"}


def test_simulate_due_is_gated(client, monkeypatch):
    monkeypatch.delenv("FOLLOWUP_DEMO_MODE", raising=False)
    r = client.post("/followup/simulate-due")
    assert r.status_code == 404
