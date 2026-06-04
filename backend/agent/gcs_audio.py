"""
Temporary GCS upload/delete helpers for consultation audio.

Audio is uploaded immediately before STT and deleted in a finally block
after transcription completes — no PHI persists beyond the operation.
A 1-day bucket lifecycle rule (configured in GCS) acts as a safety net
for crashes between upload and delete.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy singleton — avoids importing google.cloud.storage at module load
# (heavy dependency; only needed when the consultation endpoint is called).
_storage_client = None

# MIME type → file extension for the GCS object name + content_type header.
# This is separate from the STT encoding map; the extension does not affect
# how Google STT decodes the audio.
_MIME_TO_EXT: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg":  "ogg",
    "audio/wav":  "wav",
    "audio/x-wav": "wav",
    "audio/mp4":  "m4a",
    "audio/mpeg": "mp3",
}


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        from google.cloud import storage  # noqa: PLC0415
        # Uses Application Default Credentials — same auth path as
        # providers.py:get_vertex_token (gcloud auth application-default login).
        _storage_client = storage.Client()
    return _storage_client


def mime_to_ext(content_type: str, default: str = "webm") -> str:
    """Return the file extension for a browser audio MIME type."""
    ct = content_type.lower()
    for mime, ext in _MIME_TO_EXT.items():
        if mime in ct:
            return ext
    return default


def upload_consultation_audio(audio_bytes: bytes, content_type: str = "audio/webm") -> tuple[str, str]:
    """Upload audio bytes to GCS.

    Returns:
        (gs_uri, object_key) — e.g.
        ("gs://cpg-consultation-audio-temp/consultations/abc123.webm",
         "consultations/abc123.webm")

    Raises:
        RuntimeError if GCS_CONSULTATION_BUCKET is not set.
        google.cloud.exceptions.GoogleCloudError on upload failure.
    """
    bucket_name = os.getenv("GCS_CONSULTATION_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_CONSULTATION_BUCKET not configured")

    ext = mime_to_ext(content_type)
    object_key = f"consultations/{uuid.uuid4()}.{ext}"
    bucket = _get_storage_client().bucket(bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_string(audio_bytes, content_type=f"audio/{ext}")
    gs_uri = f"gs://{bucket_name}/{object_key}"
    logger.info("Uploaded consultation audio: %s (%d bytes)", gs_uri, len(audio_bytes))
    return gs_uri, object_key


def delete_consultation_audio(object_key: str) -> None:
    """Delete the temporary GCS object. Logs a warning on failure — never raises."""
    try:
        bucket_name = os.getenv("GCS_CONSULTATION_BUCKET")
        if not bucket_name:
            return
        bucket = _get_storage_client().bucket(bucket_name)
        bucket.blob(object_key).delete()
        logger.info("Deleted consultation audio: %s", object_key)
    except Exception as e:
        logger.warning("Failed to delete GCS blob %s: %s", object_key, e)
