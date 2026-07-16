"""
Typed pipeline state + fingerprint-keyed checkpointing — env-gated, fail-open.

PipelineState is the single typed object that flows through the shared stage
runners in clinical_workflow.py (LangGraph's State, without the framework).
Checkpointing gives LangGraph-style resume: the expensive deterministic-ish
stages (2 DDx, 3 routing, 4 retrieval) are snapshotted to disk after each
completes, so when a run dies at Stage 5/6 (LLM outage, process crash) an
IDENTICAL re-submission resumes from the last completed stage instead of
re-running the whole pipeline.

Keying is fully dynamic — no client cooperation needed: the resume key is a
SHA-256 fingerprint of (entrypoint, full PatientCase payload, any extra parts
such as the clinician-selected codes on the resynthesize path). Any change to
the inputs changes the key, so a resume can never serve stage outputs computed
for different inputs. A TTL bounds staleness in time, and the checkpoint is
deleted on successful completion (consumed, LangGraph-style), so a repeat of a
run that already succeeded starts fresh.

Env vars (all read at call time — nothing frozen at import):
    PIPELINE_CHECKPOINT_ENABLED — "true"/"1"/"yes" to enable (default off; when
                                  off, PipelineState still flows but nothing
                                  touches disk and resume never happens)
    PIPELINE_CHECKPOINT_DIR     — snapshot directory (default:
                                  <OFFLINE_LOG_DIR or backend/logs>/checkpoints)
    PIPELINE_CHECKPOINT_TTL_MIN — minutes before a snapshot is stale (default 30)

Every disk operation is fail-open: a checkpoint that cannot be written, read,
or parsed degrades to "no checkpoint" and the pipeline runs normally.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .clinical_stages import DDxResult
from .models import ChunkResult, PatientCase, SafetyReport, TreatmentPlan
from .routing import CPGDocRef

logger = logging.getLogger(__name__)

# Fields snapshotted to disk after their stage completes. Stages 5/6 are the
# LLM outputs — if they succeeded the pipeline succeeded, so they are never
# checkpointed; resume re-runs KG lookup + synthesis + safety on the restored
# evidence. pydantic reconstructs the nested models on load (model_validate),
# so adding a field here is the ONLY change needed to checkpoint a new stage.
_CHECKPOINT_FIELDS = ("ddx", "cpgs", "evidence", "stage4_failed")

_CHECKPOINT_VERSION = 1


def checkpoints_enabled() -> bool:
    return os.getenv("PIPELINE_CHECKPOINT_ENABLED", "false").strip().lower() in ("1", "true", "yes")


def _checkpoint_dir() -> Path:
    configured = os.getenv("PIPELINE_CHECKPOINT_DIR", "").strip()
    if configured:
        return Path(configured)
    base = Path(os.getenv("OFFLINE_LOG_DIR", Path(__file__).parent.parent / "logs"))
    return base / "checkpoints"


def _ttl_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("PIPELINE_CHECKPOINT_TTL_MIN", "30"))) * 60
    except ValueError:
        return 30 * 60


class PipelineState(BaseModel):
    """Typed state threaded through the stage runners of one pipeline run."""
    entrypoint: str
    resume_key: str | None = None
    ddx: list[DDxResult] | None = None
    cpgs: list[CPGDocRef] | None = None
    evidence: list[ChunkResult] | None = None
    stage4_failed: bool | None = None
    treatment_plan: TreatmentPlan | None = None
    safety_report: SafetyReport | None = None
    # Stage fields restored from a checkpoint at begin_state() time — the
    # runners consult this (not mere non-None-ness) to decide to skip a stage.
    resumed_stages: list[str] = Field(default_factory=list)

    def is_resumed(self, field: str) -> bool:
        return field in self.resumed_stages

    def _path(self) -> Path | None:
        if self.resume_key is None:
            return None
        return _checkpoint_dir() / f"{self.resume_key}.json"

    def checkpoint(self) -> None:
        """Snapshot the checkpointable fields. Fail-open no-op when disabled."""
        path = self._path()
        if path is None or not checkpoints_enabled():
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "v": _CHECKPOINT_VERSION,
                "entrypoint": self.entrypoint,
                "fields": self.model_dump(mode="json", include=set(_CHECKPOINT_FIELDS)),
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.warning("Pipeline checkpoint write failed (non-fatal): %s", exc)

    def complete(self) -> None:
        """Consume the checkpoint on successful completion (LangGraph-style)."""
        path = self._path()
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Pipeline checkpoint cleanup failed (non-fatal): %s", exc)


def compute_resume_key(case: PatientCase, entrypoint: str, extra=None) -> str:
    """SHA-256 fingerprint of the full run inputs — identical inputs, same key."""
    material = json.dumps(
        [entrypoint, case.model_dump(mode="json"), extra],
        sort_keys=True, default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _purge_stale(directory: Path, ttl_s: float) -> None:
    cutoff = time.time() - ttl_s
    for f in directory.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        except OSError:
            pass


def begin_state(case: PatientCase, entrypoint: str, extra=None) -> PipelineState:
    """Build the run's PipelineState, restoring a fresh matching checkpoint.

    Always returns a usable state; checkpoint loading is best-effort and any
    failure just yields an un-resumed state.
    """
    state = PipelineState(entrypoint=entrypoint)
    if not checkpoints_enabled():
        return state
    try:
        state.resume_key = compute_resume_key(case, entrypoint, extra)
        directory = _checkpoint_dir()
        if not directory.is_dir():
            return state
        _purge_stale(directory, _ttl_seconds())
        path = directory / f"{state.resume_key}.json"
        if not path.exists():
            return state
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("v") != _CHECKPOINT_VERSION:
            return state
        restored = PipelineState.model_validate({"entrypoint": entrypoint, **payload.get("fields", {})})
        for field in _CHECKPOINT_FIELDS:
            value = getattr(restored, field)
            if value is not None:
                setattr(state, field, value)
                state.resumed_stages.append(field)
        if state.resumed_stages:
            logger.info(
                "Pipeline resume: restored %s from checkpoint %s",
                state.resumed_stages, state.resume_key[:8],
            )
    except Exception as exc:
        logger.warning("Pipeline checkpoint load failed (starting fresh): %s", exc)
        state.resumed_stages = []
    return state
