"""Manual/nightly live-provider contract; never selected by ordinary CI."""

import os

import pytest
from openai import AsyncOpenAI

from agent.llm_runtime import call_structured, resolve_target


pytestmark = pytest.mark.live_provider


@pytest.mark.asyncio
async def test_gemini_json_contract():
    if os.getenv("RUN_LIVE_PROVIDER_TESTS") != "1" or not os.getenv("GEMINI_API_KEY"):
        pytest.skip("live provider tests require explicit opt-in and GEMINI_API_KEY")
    target = resolve_target("prep_brief")
    client = AsyncOpenAI(base_url=target.base_url, api_key=target.api_key, max_retries=0)
    result = await call_structured(
        client,
        operation="prep_brief",
        target=target,
        messages=[{"role": "user", "content": 'Return exactly {"ok": true} as JSON.'}],
        prompt_template="provider-smoke-v1",
        temperature=0,
    )
    assert result.data == {"ok": True}
