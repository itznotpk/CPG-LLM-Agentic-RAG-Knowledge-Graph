"""Provider-safe configuration and policies for clinical LLM calls.

This module deliberately contains no clinical prompts or fallback decisions. It
only resolves complete provider tuples and exposes provider-aware call kwargs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Mapping


class LLMConfigurationError(RuntimeError):
    """Raised when an operation has no complete configured provider target."""


class LLMResponseError(RuntimeError):
    """A provider response could not satisfy a structured-call contract."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


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


@dataclass
class LLMCallRecord:
    request_id: str
    consultation_id: int | None
    operation: str
    provider: str = ""
    model: str = ""
    policy_version: str = "v1"
    prompt_sha256: str = ""
    max_tokens: int = 0
    attempts: int = 1
    latency_ms: float = 0.0
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    outcome: str = "ok"
    reason: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize an explicit safe allowlist; never include prompts or targets."""
        return {
            "request_id": self.request_id,
            "consultation_id": self.consultation_id,
            "operation": self.operation,
            "provider": self.provider,
            "model": self.model,
            "policy_version": self.policy_version,
            "prompt_sha256": self.prompt_sha256,
            "max_tokens": self.max_tokens,
            "attempts": self.attempts,
            "latency_ms": round(self.latency_ms, 2),
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "outcome": self.outcome,
            "reason": self.reason,
        }


@dataclass
class LLMRunContext:
    request_id: str
    consultation_id: int | None = None
    records: list[LLMCallRecord] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredCallResult:
    data: dict
    raw_content: str
    response: Any


_RUN_CONTEXT: ContextVar[LLMRunContext | None] = ContextVar(
    "llm_run_context", default=None
)


def begin_llm_run(
    request_id: str,
    consultation_id: int | None = None,
) -> Token:
    """Open an isolated run context and return the token required to restore it."""
    return _RUN_CONTEXT.set(LLMRunContext(request_id, consultation_id))


def end_llm_run(token: Token) -> list[LLMCallRecord]:
    """Return completed records and restore the parent context."""
    context = _RUN_CONTEXT.get()
    completed = list(context.records) if context is not None else []
    _RUN_CONTEXT.reset(token)
    return completed


def current_llm_records() -> list[LLMCallRecord]:
    context = _RUN_CONTEXT.get()
    return list(context.records) if context is not None else []


def _append_record(record: LLMCallRecord) -> LLMCallRecord:
    context = _RUN_CONTEXT.get()
    if context is not None:
        context.records.append(record)
    return record


def _record(
    operation: str,
    *,
    target: LLMTarget | None = None,
    prompt_template: str = "",
    attempts: int = 1,
    latency_ms: float = 0.0,
    finish_reason: str | None = None,
    usage: dict[str, int] | None = None,
    outcome: str = "ok",
    reason: str | None = None,
) -> LLMCallRecord:
    context = _RUN_CONTEXT.get()
    policy = POLICIES[operation]
    return _append_record(
        LLMCallRecord(
            request_id=context.request_id if context is not None else "",
            consultation_id=context.consultation_id if context is not None else None,
            operation=operation,
            provider=target.provider if target is not None else "",
            model=target.model if target is not None else "",
            policy_version=policy.version,
            prompt_sha256=(
                hashlib.sha256(prompt_template.encode("utf-8")).hexdigest()
                if prompt_template
                else ""
            ),
            max_tokens=policy.max_tokens,
            attempts=attempts,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            usage=usage or {},
            outcome=outcome,
            reason=reason,
        )
    )


def record_degradation(
    operation: str,
    reason: str,
    *,
    target: LLMTarget | None = None,
    prompt_template: str = "",
    attempts: int = 1,
    latency_ms: float = 0.0,
    finish_reason: str | None = None,
) -> LLMCallRecord:
    return _record(
        operation,
        target=target,
        prompt_template=prompt_template,
        attempts=attempts,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        outcome="degraded",
        reason=reason,
    )


def _usage_payload(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    names = ("prompt_tokens", "completion_tokens", "total_tokens")
    if isinstance(usage, Mapping):
        return {name: int(usage[name]) for name in names if usage.get(name) is not None}
    return {
        name: int(value)
        for name in names
        if (value := getattr(usage, name, None)) is not None
    }


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("timeout", "timed out", "connection", "rate limit", "overloaded")
    )


def _clean_json_content(content: str) -> str:
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    return raw


async def call_structured(
    client,
    *,
    operation: str,
    target: LLMTarget,
    messages: list[dict],
    prompt_template: str,
    temperature: float = 0.1,
    seed: int | None = None,
    retry_delays: tuple[float, ...] = (0.25, 0.5),
) -> StructuredCallResult:
    """Execute one structured call, recording one success or terminal degradation."""
    started = time.perf_counter()
    attempts = 0
    for attempt in range(len(retry_delays) + 1):
        attempts = attempt + 1
        try:
            response = await client.chat.completions.create(
                model=target.model,
                messages=messages,
                temperature=temperature,
                **completion_kwargs(operation, target, seed=seed),
            )
            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)
            content = (getattr(choice.message, "content", None) or "").strip()
            if finish_reason == "length":
                raise LLMResponseError("length_truncated")
            if not content:
                raise LLMResponseError("empty_content")
            try:
                data = json.loads(_clean_json_content(content))
            except json.JSONDecodeError as exc:
                raise LLMResponseError("invalid_json") from exc
            if not isinstance(data, dict):
                raise LLMResponseError("invalid_json")

            _record(
                operation,
                target=target,
                prompt_template=prompt_template,
                attempts=attempts,
                latency_ms=(time.perf_counter() - started) * 1000,
                finish_reason=finish_reason,
                usage=_usage_payload(getattr(response, "usage", None)),
            )
            return StructuredCallResult(data=data, raw_content=content, response=response)
        except LLMResponseError as exc:
            record_degradation(
                operation,
                exc.reason,
                target=target,
                prompt_template=prompt_template,
                attempts=attempts,
                latency_ms=(time.perf_counter() - started) * 1000,
                finish_reason=(
                    getattr(response.choices[0], "finish_reason", None)
                    if "response" in locals()
                    else None
                ),
            )
            raise
        except Exception as exc:
            if attempt < len(retry_delays) and _is_transient(exc):
                await asyncio.sleep(retry_delays[attempt])
                continue
            record_degradation(
                operation,
                "provider_error",
                target=target,
                prompt_template=prompt_template,
                attempts=attempts,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            raise

    raise AssertionError("unreachable")


def record_stream_completion(
    operation: str,
    *,
    target: LLMTarget,
    prompt_template: str,
    attempts: int,
    latency_ms: float,
    finish_reason: str | None,
    outcome: str = "ok",
    reason: str | None = None,
) -> LLMCallRecord:
    return _record(
        operation,
        target=target,
        prompt_template=prompt_template,
        attempts=attempts,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        outcome=outcome,
        reason=reason,
    )
