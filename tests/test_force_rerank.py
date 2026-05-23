"""D6 Smoke-8 deterministic force-rerank harness tests.

The harness lets the smoke runner inject a fixed llm_rank/override_reason order via
FORCE_RERANK_ORDER, bypassing the real LLM so the D6c/D6d path is exercised every
run. It MUST be inert in production config.
"""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.clinical_stages import (
    _force_rerank_enabled,
    _forced_rerank_spec,
    _llm_rerank_ddx,
    DDxResult,
    PatientCase,
)


def _cands():
    return [
        DDxResult(code="AA", title="Cond A", similarity=0.80),
        DDxResult(code="BB", title="Cond B", similarity=0.70),
    ]


# --- gate: inert in production ---------------------------------------------

def test_force_rerank_order_inert_in_prod_config():
    """Even with the flag + order set, production config disables the harness."""
    with patch.dict(os.environ, {
        "APP_ENV": "production",
        "ALLOW_FORCE_RERANK": "1",
        "FORCE_RERANK_ORDER": json.dumps([{"code": "BB"}, {"code": "AA"}]),
    }):
        assert _force_rerank_enabled() is False
        assert _forced_rerank_spec(_cands()) is None


def test_force_rerank_disabled_without_flag():
    """No ALLOW_FORCE_RERANK → harness off even outside production."""
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_FORCE_RERANK", "APP_ENV")}
    env["FORCE_RERANK_ORDER"] = json.dumps([{"code": "BB"}])
    with patch.dict(os.environ, env, clear=True):
        assert _force_rerank_enabled() is False
        assert _forced_rerank_spec(_cands()) is None


def test_force_rerank_enabled_returns_shaped_order():
    with patch.dict(os.environ, {
        "APP_ENV": "staging",
        "ALLOW_FORCE_RERANK": "1",
        "FORCE_RERANK_ORDER": json.dumps([
            {"code": "BB", "override_reason": "BB clinically first"},
            {"code": "AA"},
        ]),
    }):
        assert _force_rerank_enabled() is True
        spec = _forced_rerank_spec(_cands())
    assert [e["code"] for e in spec] == ["BB", "AA"]
    assert spec[0]["override_reason"] == "BB clinically first"


def test_force_rerank_respects_explicit_llm_rank():
    with patch.dict(os.environ, {
        "APP_ENV": "staging", "ALLOW_FORCE_RERANK": "1",
        "FORCE_RERANK_ORDER": json.dumps([
            {"code": "AA", "llm_rank": 2}, {"code": "BB", "llm_rank": 1},
        ]),
    }):
        spec = _forced_rerank_spec(_cands())
    assert [e["code"] for e in spec] == ["BB", "AA"]


def test_force_rerank_ignores_unknown_codes():
    with patch.dict(os.environ, {
        "APP_ENV": "staging", "ALLOW_FORCE_RERANK": "1",
        "FORCE_RERANK_ORDER": json.dumps([{"code": "ZZZ"}, {"code": "BB"}]),
    }):
        spec = _forced_rerank_spec(_cands())
    assert [e["code"] for e in spec] == ["BB"]


# --- integration: LLM bypassed, order + delta applied ----------------------

@pytest.mark.asyncio
async def test_harness_bypasses_llm_and_applies_order():
    case = PatientCase(chief_complaint="x")
    fake_client = MagicMock()
    # If the LLM were called the harness failed — make it explode.
    fake_client.chat.completions.create = AsyncMock(side_effect=AssertionError("LLM must not be called"))

    with patch.dict(os.environ, {
        "APP_ENV": "staging", "ALLOW_FORCE_RERANK": "1",
        "FORCE_RERANK_ORDER": json.dumps([
            {"code": "BB", "override_reason": "BB promoted by harness"},
            {"code": "AA"},
        ]),
    }), patch("agent.clinical_stages.openai.AsyncOpenAI", return_value=fake_client):
        result = await _llm_rerank_ddx(case, _cands())

    # Forced order applied, LLM never called (no AssertionError surfaced).
    assert [r.code for r in result] == ["BB", "AA"]
    bb = result[0]
    assert bb.llm_rank == 1
    assert bb.math_rank == 2          # BB was 2nd by math
    assert bb.rank_delta == 1         # promoted one place
    assert bb.override_reason == "BB promoted by harness"
