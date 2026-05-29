"""
Offline log — three-tier resilience for the clinical pipeline.

1. SSE event log  : every SSE event is appended to a rotating local file
                    before streaming, so a frontend crash loses nothing.
2. Consultation   : a Supabase row is written with status='in_progress'
                    before the LLM pipeline starts (see api.py usage).
3. Failed-job log : when any LLM/API call raises, the patient case + error
                    are appended to failed_jobs.jsonl for manual replay.

All writes are best-effort — they never propagate exceptions to the caller.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────────────
_BASE = Path(os.getenv("OFFLINE_LOG_DIR", Path(__file__).parent.parent / "logs"))
_BASE.mkdir(parents=True, exist_ok=True)

_FAILED_JOBS_PATH = _BASE / "failed_jobs.jsonl"

# ── SSE event logger ─────────────────────────────────────────────────────────
_sse_logger = logging.getLogger("cpg.sse_events")
_sse_logger.setLevel(logging.DEBUG)
_sse_logger.propagate = False  # don't leak into the root handler

_sse_handler = RotatingFileHandler(
    _BASE / "sse_events.log",
    maxBytes=10 * 1024 * 1024,   # 10 MB per file
    backupCount=5,
    encoding="utf-8",
)
_sse_handler.setFormatter(
    logging.Formatter("%(asctime)s\t%(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
)
_sse_logger.addHandler(_sse_handler)


def log_sse_event(consultation_id: str | int | None, event_type: str, data: dict, request_id: str = "") -> None:
    """Append one SSE event to the rotating sse_events.log before it is streamed."""
    try:
        _sse_logger.debug(
            json.dumps(
                {"rid": request_id, "cid": str(consultation_id or ""), "event": event_type, "data": data},
                separators=(",", ":"),
                default=str,
            )
        )
    except Exception:
        pass  # never crash the stream


# ── failed-job log ────────────────────────────────────────────────────────────

def log_failed_job(
    stage: str,
    patient_case: Any,
    error: str,
    extra: dict | None = None,
    request_id: str = "",
) -> None:
    """Append a failed pipeline attempt to failed_jobs.jsonl.

    `patient_case` may be a PatientCase Pydantic model or a plain dict.
    """
    try:
        case_dict: dict
        if hasattr(patient_case, "model_dump"):
            case_dict = patient_case.model_dump()
        elif isinstance(patient_case, dict):
            case_dict = patient_case
        else:
            case_dict = {"raw": str(patient_case)}

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "rid": request_id,
            "stage": stage,
            "error": error,
            "case": case_dict,
            **(extra or {}),
        }
        with _FAILED_JOBS_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")
    except Exception as exc:
        logger.warning("offline_log: failed to write failed_jobs.jsonl: %s", exc)
