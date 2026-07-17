"""Atomic LLM target resolution and structured-call policy contracts."""

from __future__ import annotations

import pytest

from agent.llm_runtime import (
    LLMConfigurationError,
    POLICIES,
    completion_kwargs,
    configuration_defects,
    resolve_target,
)


GLOBAL = {
    "LLM_BASE_URL": "https://global.test/v1",
    "LLM_API_KEY": "global-secret",
    "LLM_CHOICE": "global-model",
    "LLM_PROVIDER": "openai",
}


def test_referral_target_keeps_prior_summary_tuple_atomic():
    env = {
        **GLOBAL,
        "PRIOR_VISIT_SUMMARISER_BASE_URL": "https://prior.test/v1",
        "PRIOR_VISIT_SUMMARISER_API_KEY": "prior-secret",
        "PRIOR_VISIT_SUMMARISER_MODEL": "prior-model",
        "STAGE5_LLM_BASE_URL": "https://stage5.test/v1",
        "STAGE5_LLM_API_KEY": "stage5-secret",
        "STAGE5_LLM_CHOICE": "stage5-model",
    }

    target = resolve_target("referral_gate", env)

    assert target.alias == "prior_visit_summariser"
    assert (target.base_url, target.api_key, target.model) == (
        "https://prior.test/v1",
        "prior-secret",
        "prior-model",
    )


def test_incomplete_override_falls_back_and_is_a_configuration_defect():
    env = {
        **GLOBAL,
        "PREP_BRIEF_LLM_BASE_URL": "https://partial.test/v1",
        "GEMINI_BASE_URL": "https://gemini.test/v1",
        "GEMINI_API_KEY": "gemini-secret",
        "GEMINI_MODEL": "gemini-2.5-flash",
    }

    target = resolve_target("prep_brief", env)
    defects = configuration_defects(env)

    assert target.alias == "gemini"
    assert any("PREP_BRIEF_LLM" in item for item in defects)
    assert all("gemini-secret" not in item for item in defects)
    assert all("https://partial.test" not in item for item in defects)


def test_prep_brief_complete_override_wins():
    env = {
        **GLOBAL,
        "PREP_BRIEF_LLM_BASE_URL": "https://prep.test/v1",
        "PREP_BRIEF_LLM_API_KEY": "prep-secret",
        "PREP_BRIEF_LLM_MODEL": "prep-model",
        "GEMINI_BASE_URL": "https://gemini.test/v1",
        "GEMINI_API_KEY": "gemini-secret",
        "GEMINI_MODEL": "gemini-2.5-flash",
    }

    assert resolve_target("prep_brief", env).alias == "prep_brief"


def test_safety_target_maps_model_not_choice():
    env = {
        **GLOBAL,
        "SAFETY_CRITIC_LLM_BASE_URL": "https://safety.test/v1",
        "SAFETY_CRITIC_LLM_API_KEY": "safety-secret",
        "SAFETY_CRITIC_MODEL": "safety-model",
    }

    target = resolve_target("safety_critic", env)

    assert target.model == "safety-model"
    assert target.alias == "safety_critic"


def test_missing_all_complete_targets_raises_without_secret_values():
    with pytest.raises(LLMConfigurationError) as exc_info:
        resolve_target("stage5_synthesis", {"LLM_API_KEY": "do-not-leak"})

    message = str(exc_info.value)
    assert "do-not-leak" not in message
    assert "LLM_BASE_URL" in message
    assert "LLM_CHOICE" in message


def test_policy_ceilings_match_approved_design():
    assert POLICIES["stage5_synthesis"].max_tokens == 32000
    assert POLICIES["stage5_refine"].max_tokens == 32000
    assert POLICIES["referral_gate"].max_tokens == 8000
    assert POLICIES["prior_summary"].max_tokens == 8000
    assert POLICIES["prep_brief"].max_tokens == 8000
    assert POLICIES["consultation_summary"].max_tokens == 8000
    assert POLICIES["readiness_probe"].max_tokens == 1024


def test_completion_kwargs_apply_json_and_provider_capabilities():
    mimo = resolve_target(
        "stage5_synthesis",
        {
            "LLM_BASE_URL": "https://mimo.test/v1",
            "LLM_API_KEY": "secret",
            "LLM_CHOICE": "mimo-v2.5-pro",
        },
    )
    gemini = resolve_target(
        "stage5_synthesis",
        {
            "LLM_BASE_URL": "https://gemini.test/v1",
            "LLM_API_KEY": "secret",
            "LLM_CHOICE": "gemini-2.5-flash",
        },
    )

    mimo_kwargs = completion_kwargs("stage5_synthesis", mimo, seed=42)
    gemini_kwargs = completion_kwargs("stage5_synthesis", gemini, seed=42)

    assert mimo_kwargs["response_format"] == {"type": "json_object"}
    assert mimo_kwargs["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert mimo_kwargs["seed"] == 42
    assert "seed" not in gemini_kwargs
    assert "extra_body" not in gemini_kwargs


def test_unknown_operation_is_rejected():
    with pytest.raises(KeyError):
        resolve_target("does_not_exist", GLOBAL)
