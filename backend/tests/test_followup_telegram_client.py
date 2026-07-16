"""Tests for followup Telegram client. Network fully mocked via httpx MockTransport."""
import httpx
import pytest

from agent.followup import telegram_client as tc


def _client_with_transport(handler):
    client = tc.TelegramClient(token="TESTTOKEN")
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


async def test_send_message_success():
    async def handler(request):
        assert "sendMessage" in str(request.url)
        return httpx.Response(200, json={"ok": True, "result": {}})
    client = _client_with_transport(handler)
    assert await client.send_message(123, "hello") is True


async def test_send_message_retries_then_false():
    calls = {"n": 0}
    async def handler(request):
        calls["n"] += 1
        return httpx.Response(500, json={"ok": False})
    client = _client_with_transport(handler)
    assert await client.send_message(123, "hello") is False
    assert calls["n"] == 3


async def test_get_updates_returns_list_and_never_raises():
    async def handler(request):
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 7}]})
    client = _client_with_transport(handler)
    assert await client.get_updates(offset=0) == [{"update_id": 7}]

    async def broken(request):
        raise httpx.ConnectError("down")
    client2 = _client_with_transport(broken)
    assert await client2.get_updates(offset=0) == []


def test_deep_link(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    assert tc.deep_link("abc123") == "https://t.me/ClearPathBot?start=abc123"
