"""Provider-safe configuration and policies for clinical LLM calls.

This module deliberately contains no clinical prompts or fallback decisions. It
only resolves complete provider tuples and exposes provider-aware call kwargs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class LLMConfigurationError(RuntimeError):
    """Raised when an operation has no complete configured provider target."""


@dataclass(frozen=True)
class LLMTarget:
    alias: str
    base_url: str
    api_key: str
    model: str
    provider: str = "openai"


@dataclass(frozen=True)
class TargetTier:
    alias: str
    base_var: str
    key_var: str
    model_var: str
    provider_var: str | None = None

    @property
    def required_vars(self) -> tuple[str, str, str]:
        return (self.base_var, self.key_var, self.model_var)

    def configured(self, environ: Mapping[str, str]) -> bool:
        return any((environ.get(name) or "").strip() for name in self.required_vars)

    def missing(self, environ: Mapping[str, str]) -> tuple[str, ...]:
        return tuple(
            name for name in self.required_vars if not (environ.get(name) or "").strip()
        )

    def resolve(self, environ: Mapping[str, str]) -> LLMTarget | None:
        if self.missing(environ):
            return None
        provider = (
            (environ.get(self.provider_var) or "").strip()
            if self.provider_var
            else ""
        )
        return LLMTarget(
            alias=self.alias,
            base_url=environ[self.base_var].strip(),
            api_key=environ[self.key_var].strip(),
            model=environ[self.model_var].strip(),
            provider=provider or "openai",
        )


@dataclass(frozen=True)
class StructuredCallPolicy:
    operation: str
    max_tokens: int
    json_mode: bool
    version: str


GLOBAL = TargetTier(
    "global", "LLM_BASE_URL", "LLM_API_KEY", "LLM_CHOICE", "LLM_PROVIDER"
)
GEMINI = TargetTier(
    "gemini", "GEMINI_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL"
)
STAGE2 = TargetTier(
    "stage2",
    "STAGE2_LLM_BASE_URL",
    "STAGE2_LLM_API_KEY",
    "STAGE2_LLM_CHOICE",
    "STAGE2_LLM_PROVIDER",
)
STAGE2_RERANK = TargetTier(
    "stage2_rerank",
    "STAGE2_RERANK_LLM_BASE_URL",
    "STAGE2_RERANK_LLM_API_KEY",
    "STAGE2_RERANK_LLM_CHOICE",
    "STAGE2_RERANK_LLM_PROVIDER",
)
STAGE4 = TargetTier(
    "stage4",
    "STAGE4_LLM_BASE_URL",
    "STAGE4_LLM_API_KEY",
    "STAGE4_LLM_CHOICE",
    "STAGE4_LLM_PROVIDER",
)
STAGE5 = TargetTier(
    "stage5",
    "STAGE5_LLM_BASE_URL",
    "STAGE5_LLM_API_KEY",
    "STAGE5_LLM_CHOICE",
    "STAGE5_LLM_PROVIDER",
)
REFERRAL_GATE = TargetTier(
    "referral_gate",
    "REFERRAL_GATE_BASE_URL",
    "REFERRAL_GATE_API_KEY",
    "REFERRAL_GATE_MODEL",
    "REFERRAL_GATE_PROVIDER",
)
PRIOR_SUMMARY = TargetTier(
    "prior_visit_summariser",
    "PRIOR_VISIT_SUMMARISER_BASE_URL",
    "PRIOR_VISIT_SUMMARISER_API_KEY",
    "PRIOR_VISIT_SUMMARISER_MODEL",
    "PRIOR_VISIT_SUMMARISER_PROVIDER",
)
PREP_BRIEF = TargetTier(
    "prep_brief",
    "PREP_BRIEF_LLM_BASE_URL",
    "PREP_BRIEF_LLM_API_KEY",
    "PREP_BRIEF_LLM_MODEL",
    "PREP_BRIEF_LLM_PROVIDER",
)
SAFETY = TargetTier(
    "safety_critic",
    "SAFETY_CRITIC_LLM_BASE_URL",
    "SAFETY_CRITIC_LLM_API_KEY",
    "SAFETY_CRITIC_MODEL",
    "SAFETY_CRITIC_LLM_PROVIDER",
)
FOLLOWUP = TargetTier(
    "followup",
    "FOLLOWUP_LLM_BASE_URL",
    "FOLLOWUP_LLM_API_KEY",
    "FOLLOWUP_LLM_MODEL",
    "FOLLOWUP_LLM_PROVIDER",
)
CONSULTATION_SUMMARY = TargetTier(
    "consultation_summary",
    "GEMINI_BASE_URL",
    "GEMINI_API_KEY",
    "CONSULTATION_SUMMARY_MODEL",
)


TARGET_TIERS: dict[str, tuple[TargetTier, ...]] = {
    "ddx_rerank": (STAGE2_RERANK, STAGE2, GLOBAL),
    "ddx_structured": (STAGE2, GLOBAL),
    "stage4_queries": (STAGE4, GLOBAL),
    "stage5_synthesis": (STAGE5, GLOBAL),
    "stage5_refine": (STAGE5, GLOBAL),
    "referral_gate": (REFERRAL_GATE, PRIOR_SUMMARY, STAGE5, GLOBAL),
    "prior_summary": (PRIOR_SUMMARY, STAGE5, GLOBAL),
    "prep_brief": (PREP_BRIEF, GEMINI, GLOBAL),
    "safety_critic": (SAFETY, STAGE5, GLOBAL),
    "followup_protocol": (FOLLOWUP, GEMINI, GLOBAL),
    "followup_triage": (FOLLOWUP, GEMINI, GLOBAL),
    "consultation_summary": (CONSULTATION_SUMMARY, GLOBAL),
    "readiness_probe": (STAGE5, GLOBAL),
}


POLICIES = {
    "ddx_rerank": StructuredCallPolicy("ddx_rerank", 8000, True, "v1"),
    "ddx_structured": StructuredCallPolicy("ddx_structured", 8000, True, "v1"),
    "stage4_queries": StructuredCallPolicy("stage4_queries", 8000, True, "v1"),
    "stage5_synthesis": StructuredCallPolicy("stage5_synthesis", 32000, True, "v1"),
    "stage5_refine": StructuredCallPolicy("stage5_refine", 32000, True, "v1"),
    "referral_gate": StructuredCallPolicy("referral_gate", 8000, True, "v1"),
    "prior_summary": StructuredCallPolicy("prior_summary", 8000, True, "v1"),
    "prep_brief": StructuredCallPolicy("prep_brief", 8000, True, "v1"),
    "safety_critic": StructuredCallPolicy("safety_critic", 8000, True, "v1"),
    "followup_protocol": StructuredCallPolicy("followup_protocol", 8000, True, "v1"),
    "followup_triage": StructuredCallPolicy("followup_triage", 8000, True, "v1"),
    "consultation_summary": StructuredCallPolicy(
        "consultation_summary", 8000, False, "v1"
    ),
    "readiness_probe": StructuredCallPolicy("readiness_probe", 1024, False, "v1"),
}


def resolve_target(
    operation: str,
    environ: Mapping[str, str] | None = None,
) -> LLMTarget:
    """Resolve the first complete provider tuple configured for *operation*."""
    tiers = TARGET_TIERS[operation]
    env = os.environ if environ is None else environ
    for tier in tiers:
        target = tier.resolve(env)
        if target is not None:
            return target

    configured = [tier for tier in tiers if tier.configured(env)]
    missing = sorted({name for tier in configured or tiers for name in tier.missing(env)})
    raise LLMConfigurationError(
        f"No complete LLM target for {operation}; missing variables: {', '.join(missing)}"
    )


def configuration_defects(environ: Mapping[str, str] | None = None) -> list[str]:
    """Return incomplete configured tiers without exposing configured values."""
    env = os.environ if environ is None else environ
    unique: dict[tuple[str, str, str], TargetTier] = {}
    for tiers in TARGET_TIERS.values():
        for tier in tiers:
            unique[tier.required_vars] = tier

    defects = []
    for tier in unique.values():
        if not tier.configured(env):
            continue
        missing = tier.missing(env)
        if missing:
            defects.append(
                f"Incomplete {tier.alias} LLM tier; missing: {', '.join(missing)}"
            )
    return sorted(defects)


def completion_kwargs(
    operation: str,
    target: LLMTarget,
    *,
    seed: int | None = None,
) -> dict:
    """Return provider-aware completion kwargs for an approved operation policy."""
    policy = POLICIES[operation]
    kwargs: dict = {"max_tokens": policy.max_tokens}
    if policy.json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    model = target.model.lower()
    if "mimo" in model:
        kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": False}
        }
    if seed is not None and "gemini" not in model:
        kwargs["seed"] = seed
    return kwargs
