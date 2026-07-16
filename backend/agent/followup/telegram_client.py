"""Thin httpx wrapper for the Telegram Bot API. No LLM, no DB.

Long-polling (getUpdates) — no webhook, no public URL, runs off a laptop.
Both methods are fail-open: they log and return a benign value, never raise,
so a Telegram outage can never take down the clinical pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
SEND_RETRIES = 3


class TelegramClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._http = httpx.AsyncClient(timeout=35.0)

    def _url(self, method: str) -> str:
        return _API.format(token=self.token, method=method)

    async def send_message(self, chat_id: int, text: str) -> bool:
        for attempt in range(1, SEND_RETRIES + 1):
            try:
                r = await self._http.post(
                    self._url("sendMessage"),
                    json={"chat_id": chat_id, "text": text},
                )
                if r.status_code == 200 and r.json().get("ok"):
                    return True
                logger.warning("sendMessage attempt %d failed: HTTP %d", attempt, r.status_code)
            except Exception as exc:
                logger.warning("sendMessage attempt %d error: %s", attempt, exc)
            if attempt < SEND_RETRIES:
                await asyncio.sleep(1.5 * attempt)
        return False

    async def get_updates(self, offset: int, timeout: int = 25) -> list[dict]:
        try:
            r = await self._http.get(
                self._url("getUpdates"),
                params={"offset": offset, "timeout": timeout},
            )
            if r.status_code == 200 and r.json().get("ok"):
                return r.json().get("result", [])
        except Exception as exc:
            logger.warning("getUpdates error: %s", exc)
        return []

    async def aclose(self) -> None:
        await self._http.aclose()


_client: TelegramClient | None = None


def get_client() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client


def deep_link(token: str) -> str:
    username = os.getenv("TELEGRAM_BOT_USERNAME", "ClearPathBot")
    return f"https://t.me/{username}?start={token}"
