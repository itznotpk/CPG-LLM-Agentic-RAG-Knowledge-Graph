"""Gmail delivery for approved care-plan PDFs. Plain async function — no LLM.

Hard invariants:
- Reads clinical artifacts; never writes to consultations.treatment_plan / safety_report.
- Refuses if patient consent missing or email missing.
- Subject line is templated and PHI-validated before send.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
import tempfile
from email.message import EmailMessage
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx

from .db_utils import supabase_pool as db_pool

logger = logging.getLogger(__name__)

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_FROM_NAME    = os.environ.get("GMAIL_FROM_NAME", "Clinic")
SMTP_HOST          = "smtp.gmail.com"
SMTP_PORT          = 465

# Test hook — tests set this to (host, port) of their aiosmtpd instance
_SMTP_OVERRIDE: Optional[tuple[str, int]] = None


def _smtp_target() -> tuple[str, int]:
    return _SMTP_OVERRIDE or (SMTP_HOST, SMTP_PORT)


_BLOCKED_SUBJECT_TOKENS = (
    "diabetes", "diabetic", "hypertension", "cancer", "pregnancy",
    "metformin", "warfarin", "insulin", "hba1c", "ldl",
)


def _validate_subject(subject: str) -> None:
    low = subject.lower()
    for tok in _BLOCKED_SUBJECT_TOKENS:
        if tok in low:
            raise ValueError(f"subject contains PHI/clinical token: {tok!r}")


_COVER_BODY = {
    "en": (
        "Dear {patient_name},\n\n"
        "Please find your care plan from your consultation on {date} attached.\n"
        "If you have questions, contact the clinic. Do not reply to this email.\n\n"
        "— {clinician_name}"
    ),
    "ms": (
        "Salam sejahtera {patient_name},\n\n"
        "Sila lihat pelan rawatan anda daripada konsultasi pada {date} yang dilampirkan.\n"
        "Jika ada soalan, sila hubungi klinik. Jangan balas e-mel ini.\n\n"
        "— {clinician_name}"
    ),
    "zh": (
        "{patient_name} 您好,\n\n"
        "请查阅 {date} 诊询的护理计划附件。\n"
        "如有疑问请联系诊所。请勿回复此邮件。\n\n"
        "— {clinician_name}"
    ),
}


def _cover_body(language: str, patient_name: str, date: str, clinician_name: str) -> str:
    tpl = _COVER_BODY.get(language, _COVER_BODY["en"])
    return tpl.format(patient_name=patient_name, date=date, clinician_name=clinician_name)


async def _load_job(job_id: UUID) -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT dj.consultation_id, dj.patient_nric, dj.recipient,
                   p.full_name AS patient_full_name, p.preferred_language,
                   p.email, p.email_consent_at,
                   c.consultation_time::date AS consultation_date,
                   c.report_pdf_url
              FROM delivery_jobs dj
              JOIN patients p      ON p.nric = dj.patient_nric
              JOIN consultations c ON c.id   = dj.consultation_id
             WHERE dj.id = $1
            """,
            job_id,
        )
        if not row:
            raise RuntimeError(f"job {job_id} not found")
        await conn.execute(
            "UPDATE delivery_jobs SET status='sending', attempts=attempts+1 WHERE id=$1",
            job_id,
        )
        return dict(row)


async def _mark_sent(job_id: UUID, message_id: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE delivery_jobs SET status='sent', message_id=$2, delivered_at=now() WHERE id=$1",
            job_id, message_id,
        )


async def _mark_failed(job_id: UUID, error: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE delivery_jobs SET status='failed', error=$2 WHERE id=$1",
            job_id, error[:500],
        )


async def _fetch_pdf(pdf_url: str) -> Path:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(pdf_url)
        resp.raise_for_status()
    fd = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    fd.write(resp.content)
    fd.close()
    return Path(fd.name)


def _build_message(to: str, subject: str, body: str, attachment: Path) -> EmailMessage:
    _validate_subject(subject)
    msg = EmailMessage()
    msg["From"] = f"{GMAIL_FROM_NAME} <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        attachment.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename="care_plan.pdf",
    )
    return msg


async def _send_email(msg: EmailMessage) -> str:
    host, port = _smtp_target()
    ctx_ssl = ssl.create_default_context()

    def _send() -> str:
        with smtplib.SMTP_SSL(host, port, context=ctx_ssl, timeout=30) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        return msg["Message-ID"] or "unknown"

    return await asyncio.to_thread(_send)


async def deliver_care_plan(job_id: UUID) -> None:
    """Entrypoint called by the worker. Pure deterministic flow."""
    try:
        job = await _load_job(job_id)
        if not (job["email"] and job["email_consent_at"]):
            await _mark_failed(job_id, "no_consent")
            return
        if not job["report_pdf_url"]:
            await _mark_failed(job_id, "no_pdf")
            return

        pdf_path = await _fetch_pdf(job["report_pdf_url"])
        patient_name = (job["patient_full_name"] or "Patient").strip()
        body = _cover_body(
            job["preferred_language"] or "en",
            patient_name=patient_name,
            date=str(job["consultation_date"]),
            clinician_name="Your clinician",
        )
        subject = f"Care Plan — {job['consultation_date']}"
        msg = _build_message(job["recipient"], subject, body, pdf_path)
        message_id = await _send_email(msg)
        await _mark_sent(job_id, message_id)
        logger.info("delivered job=%s message_id=%s", job_id, message_id)
    except Exception as exc:
        logger.exception("delivery failed job=%s", job_id)
        await _mark_failed(job_id, str(exc))
        raise
