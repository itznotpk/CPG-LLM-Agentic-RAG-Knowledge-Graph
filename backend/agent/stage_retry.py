"""
Per-stage retry policy for the clinical pipeline — env-driven, transient-only.

Mirrors LangGraph's node-level RetryPolicy without the framework: each stage
runner in clinical_workflow.py routes its stage call through run_with_retry().
Only TRANSIENT failures (timeouts, connection drops, rate limits, 5xx) are
retried; deterministic errors (bad input, validation, logic bugs) propagate
immediately so the existing fail-open/fail-loud contracts are untouched — a
stage that fails deterministically behaves exactly as before this module
existed.

Everything is read from the environment AT CALL TIME (no import-time freeze),
so retry behaviour can be tuned per-deploy without code changes:

    STAGE_RETRY_ATTEMPTS      — extra attempts after the first failure
                                (default 2 → up to 3 tries total; 0 disables)
    STAGE_RETRY_BACKOFF_MS    — first backoff delay in ms (default 500),
                                doubled each subsequent attempt
    STAGE_RETRY_STAGES        — comma list of stage names the policy applies
                                to, or "*" for all (default "*")
    STAGE_RETRY_STATUS_CODES  — comma list of retryable HTTP status codes
                                (default "408,429,500,502,503,504")
    STAGE_RETRY_EXC_MARKERS   — comma list of case-insensitive substrings
                                matched against the exception class MRO names
                                (default "timeout,connecterror,connectionerror,
                                connectionreset,ratelimit,serviceunavailable,
                                apiconnection")
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_STATUS_CODES = "408,429,500,502,503,504"
_DEFAULT_EXC_MARKERS = (
    "timeout,connecterror,connectionerror,connectionreset,"
    "ratelimit,serviceunavailable,apiconnection"
)


def _csv_env(name: str, default: str) -> list[str]:
    return [p.strip().lower() for p in os.getenv(name, default).split(",") if p.strip()]


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, "").strip() or default))
    except ValueError:
        return default


def retry_attempts_for(stage_name: str) -> int:
    """Extra attempts configured for this stage (0 = retry disabled)."""
    stages = _csv_env("STAGE_RETRY_STAGES", "*")
    if "*" not in stages and stage_name.lower() not in stages:
        return 0
    return _int_env("STAGE_RETRY_ATTEMPTS", 2)


def is_transient(exc: BaseException) -> bool:
    """Duck-typed transient-error classification — no imports of optional SDKs.

    An exception (or anything in its __cause__/__context__ chain) is transient
    when a class in its MRO matches an STAGE_RETRY_EXC_MARKERS substring, or it
    carries a retryable HTTP status code (status_code / status / code attrs).
    """
    markers = _csv_env("STAGE_RETRY_EXC_MARKERS", _DEFAULT_EXC_MARKERS)
    codes = set(_csv_env("STAGE_RETRY_STATUS_CODES", _DEFAULT_STATUS_CODES))
    seen: set[int] = set()
    node: BaseException | None = exc
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        for klass in type(node).__mro__:
            name = klass.__name__.lower()
            if any(marker in name for marker in markers):
                return True
        for attr in ("status_code", "status", "code"):
            value = getattr(node, attr, None)
            if value is not None and str(value) in codes:
                return True
        node = node.__cause__ or node.__context__
    return False


async def run_with_retry(stage_name: str, factory, *, emit=None, stage: float | None = None):
    """Await factory(); on a TRANSIENT failure, back off and retry.

    factory is a zero-arg callable returning a fresh coroutine per attempt
    (a coroutine object can only be awaited once). Non-transient errors and
    the final exhausted attempt raise unchanged, so callers' except blocks
    see exactly the exception they always did.

    When emit is provided, each retry surfaces as a `sub_step` event
    (badge "retry") in the pipeline trace — never a stage_update, so the
    frontend's terminal-event counting rules are unaffected.
    """
    attempts = retry_attempts_for(stage_name)
    backoff_ms = _int_env("STAGE_RETRY_BACKOFF_MS", 500)
    for attempt in range(attempts + 1):
        try:
            return await factory()
        except Exception as exc:
            if attempt >= attempts or not is_transient(exc):
                raise
            delay_s = (backoff_ms * (2 ** attempt)) / 1000
            logger.warning(
                "%s transient failure (attempt %d/%d), retrying in %.1fs: %s",
                stage_name, attempt + 1, attempts + 1, delay_s, exc,
            )
            if emit is not None:
                try:
                    await emit("sub_step", {
                        "stage": stage,
                        "detail": f"Transient error — retrying ({attempt + 2}/{attempts + 1})",
                        "badge": "retry",
                    })
                except Exception:
                    pass
            await asyncio.sleep(delay_s)
