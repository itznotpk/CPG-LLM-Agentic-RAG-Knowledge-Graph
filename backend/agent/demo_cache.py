"""
Demo result cache — in-memory, opt-in via DEMO_CACHE_ENABLED.

Purpose: when the same PatientCase is submitted again (e.g. a repeated demo
run), skip every LLM call and replay the previously recorded SSE events +
final WorkflowResult instead. A fingerprint miss (new/different case) always
falls through to the real pipeline; nothing here ever short-circuits a case
that hasn't been seen before.

Cache key deliberately does NOT reuse pipeline_state.compute_resume_key —
that fingerprint includes `prior_visit` (the last consultation's date/plan
summary), which changes every time a new consultation is saved for the same
patient, even when the clinical case being re-demoed is otherwise identical.
Hashing that in would make the cache miss on every "same case, second run"
demo. cache_key_for_case() hashes only the stable clinical-identity fields.

Replay is NOT instant: the real inter-event delays are recorded on the first
(live) run and replayed scaled down (REPLAY_SPEEDUP, default 0.35 = ~30-40%
of original wall time) so a demo re-run visibly steps through the same stage
sequence instead of snapping to a finished plan.

Env vars:
    DEMO_CACHE_ENABLED  — "true"/"1"/"yes" to enable (default off)
    DEMO_CACHE_SPEEDUP  — replay delay as a fraction of the recorded delay
                          (default 0.35)
    DEMO_CACHE_TTL_MIN  — minutes before a cached entry expires (default 120)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return os.getenv("DEMO_CACHE_ENABLED", "false").strip().lower() in ("1", "true", "yes")


# Fields that define "the same clinical case" for demo-cache purposes.
# Excludes prior_visit (churns per consultation) and anything else that isn't
# part of the presenting case itself.
_IDENTITY_FIELDS = (
    "chief_complaint", "history", "age", "sex", "comorbidities",
    "current_medications", "allergies", "vitals", "severity_staging",
    "staged_comorbidities",
)


def cache_key_for_case(case) -> str:
    """SHA-256 fingerprint over stable clinical-identity fields only."""
    dump = case.model_dump(mode="json")
    material = json.dumps(
        {k: dump.get(k) for k in _IDENTITY_FIELDS},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _speedup() -> float:
    try:
        v = float(os.getenv("DEMO_CACHE_SPEEDUP", "0.35"))
    except ValueError:
        v = 0.35
    return min(max(v, 0.05), 1.0)


def _ttl_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("DEMO_CACHE_TTL_MIN", "120"))) * 60
    except ValueError:
        return 120 * 60


@dataclass
class _RecordedEvent:
    event_type: str
    data: dict
    delay_s: float  # time since previous event (or since run start, for the first)


@dataclass
class _CacheEntry:
    events: list[_RecordedEvent]
    result: object  # WorkflowResult
    stored_at: float = field(default_factory=time.monotonic)


_CACHE: dict[str, _CacheEntry] = {}


def get(key: str) -> _CacheEntry | None:
    if not enabled():
        return None
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if time.monotonic() - entry.stored_at > _ttl_seconds():
        _CACHE.pop(key, None)
        return None
    return entry


def store(key: str, events: list[_RecordedEvent], result: object) -> None:
    if not enabled():
        return
    _CACHE[key] = _CacheEntry(events=events, result=result)


class RecordingEmit:
    """Wraps a real `emit` callable, forwarding every call unchanged while
    recording (event_type, data, delay-since-previous) for later replay."""

    def __init__(self, real_emit):
        self._real_emit = real_emit
        self._events: list[_RecordedEvent] = []
        self._last_t = time.monotonic()

    async def __call__(self, event_type: str, data: dict):
        now = time.monotonic()
        self._events.append(_RecordedEvent(event_type, data, now - self._last_t))
        self._last_t = now
        await self._real_emit(event_type, data)

    @property
    def events(self) -> list[_RecordedEvent]:
        return self._events


async def replay(entry: _CacheEntry, emit) -> None:
    """Replay recorded events through `emit`, sleeping a scaled fraction of
    each original inter-event delay so the sequence is visibly stepped
    through rather than dumped instantly."""
    speedup = _speedup()
    for evt in entry.events:
        delay = evt.delay_s * speedup
        if delay > 0:
            await asyncio.sleep(delay)
        await emit(evt.event_type, evt.data)
    logger.info("Demo cache: replayed %d events (speedup=%.2f)", len(entry.events), speedup)


# --- Simple (non-streaming) single-call cache — e.g. prep-brief --------------

@dataclass
class _SimpleCacheEntry:
    result: object
    elapsed_s: float
    stored_at: float = field(default_factory=time.monotonic)


_SIMPLE_CACHE: dict[str, _SimpleCacheEntry] = {}


def key_for_payload(payload: dict) -> str:
    """SHA-256 fingerprint over an arbitrary JSON-able request payload."""
    material = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


async def get_or_call(key: str, call):
    """Cache-through helper for a single non-streaming LLM call.

    Cache miss: awaits `call()`, times it, stores (result, elapsed) and
    returns the fresh result immediately (no artificial delay on the run
    that's paying the real cost).
    Cache hit: sleeps `elapsed * speedup` (visible-but-faster) then returns
    the stored result.
    """
    if not enabled():
        return await call()

    entry = _SIMPLE_CACHE.get(key)
    if entry is not None and time.monotonic() - entry.stored_at <= _ttl_seconds():
        delay = entry.elapsed_s * _speedup()
        if delay > 0:
            await asyncio.sleep(delay)
        logger.info("Demo cache hit (simple, key=%s)", key[:8])
        return entry.result

    t0 = time.monotonic()
    result = await call()
    _SIMPLE_CACHE[key] = _SimpleCacheEntry(result=result, elapsed_s=time.monotonic() - t0)
    return result
