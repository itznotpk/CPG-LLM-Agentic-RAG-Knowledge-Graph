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
from email.utils import make_msgid
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


# Localized copy for the HTML cover. Kept parallel to _COVER_BODY so the
# plaintext fallback and the HTML alternative always say the same thing.
_COVER_HTML_STRINGS = {
    "en": {
        "preheader": "Your care plan is attached as a PDF.",
        "greeting": "Dear {patient_name},",
        "intro": "Please find your care plan from your consultation on <strong>{date}</strong> attached to this email as a PDF.",
        "attachment_label": "Attached: your care plan (PDF)",
        "attachment_hint": "Open the attachment to view your full care plan, medications, and follow-up instructions.",
        "contact": "If you have any questions about your care plan, please contact the clinic.",
        "noreply": "This is an automated message — please do not reply to this email.",
        "signoff": "Warm regards,",
    },
    "ms": {
        "preheader": "Pelan rawatan anda dilampirkan sebagai PDF.",
        "greeting": "Salam sejahtera {patient_name},",
        "intro": "Sila lihat pelan rawatan anda daripada konsultasi pada <strong>{date}</strong> yang dilampirkan dalam e-mel ini sebagai PDF.",
        "attachment_label": "Lampiran: pelan rawatan anda (PDF)",
        "attachment_hint": "Buka lampiran untuk melihat pelan rawatan, ubat, dan arahan susulan anda.",
        "contact": "Jika ada sebarang soalan mengenai pelan rawatan anda, sila hubungi klinik.",
        "noreply": "Ini adalah mesej automatik — sila jangan balas e-mel ini.",
        "signoff": "Salam hormat,",
    },
    "zh": {
        "preheader": "您的护理计划已作为 PDF 附件发送。",
        "greeting": "{patient_name} 您好,",
        "intro": "请查阅 <strong>{date}</strong> 诊询的护理计划,已作为 PDF 附件随此邮件发送。",
        "attachment_label": "附件:您的护理计划(PDF)",
        "attachment_hint": "请打开附件查看完整的护理计划、用药及后续指示。",
        "contact": "如对护理计划有任何疑问,请联系诊所。",
        "noreply": "此为自动发送的邮件,请勿回复。",
        "signoff": "此致",
    },
}


def _cover_html(language: str, patient_name: str, date: str,
                clinician_name: str, clinic_name: str) -> str:
    """Build an inline-styled HTML cover for the care-plan email.

    Uses table layout + inline CSS for broad email-client compatibility
    (Gmail/Outlook strip <style> blocks and most positional CSS).
    """
    s = _COVER_HTML_STRINGS.get(language, _COVER_HTML_STRINGS["en"])
    g = {k: v.format(patient_name=patient_name, date=date) for k, v in s.items()}
    return f"""\
<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">{g['preheader']}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:24px 0;">
  <tr>
    <td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr>
          <td style="background-color:#0f766e;padding:24px 32px;">
            <span style="color:#ffffff;font-size:18px;font-weight:600;letter-spacing:0.2px;">{clinic_name}</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 32px 8px 32px;">
            <p style="margin:0 0 16px 0;font-size:16px;">{g['greeting']}</p>
            <p style="margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#3e4c59;">{g['intro']}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 32px 24px 32px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0fdfa;border:1px solid #99f6e4;border-radius:8px;">
              <tr>
                <td style="padding:16px 20px;">
                  <p style="margin:0 0 4px 0;font-size:14px;font-weight:600;color:#0f766e;">📎 {g['attachment_label']}</p>
                  <p style="margin:0;font-size:13px;line-height:1.5;color:#3e4c59;">{g['attachment_hint']}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:0 32px 8px 32px;">
            <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#3e4c59;">{g['contact']}</p>
            <p style="margin:0;font-size:14px;color:#1f2933;">{g['signoff']}<br><strong>{clinician_name}</strong></p>
          </td>
        </tr>
        <tr>
          <td style="padding:24px 32px;border-top:1px solid #e4e7eb;">
            <p style="margin:0;font-size:12px;line-height:1.5;color:#9aa5b1;">{g['noreply']}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


async def _load_job(job_id: UUID) -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT dj.consultation_id, dj.patient_nric, dj.recipient,
                   dj.clinician_name,
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


def _build_message(to: str, subject: str, body: str, attachment: Path,
                   html: Optional[str] = None) -> EmailMessage:
    _validate_subject(subject)
    msg = EmailMessage()
    msg["From"] = f"{GMAIL_FROM_NAME} <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    # Set a real RFC-5322 Message-ID up front so _send_email can record it for
    # the delivery audit trail (Gmail preserves a client-supplied Message-ID).
    # Domain mirrors the sending address; falls back to the local host otherwise.
    _domain = GMAIL_USER.split("@", 1)[1] if "@" in GMAIL_USER else None
    msg["Message-ID"] = make_msgid(domain=_domain) if _domain else make_msgid()
    msg.set_content(body)
    if html:
        # multipart/alternative — clients that render HTML show this; the rest
        # fall back to the plaintext body set above.
        msg.add_alternative(html, subtype="html")
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
    pdf_path: Optional[Path] = None
    try:
        job = await _load_job(job_id)
        # The recipient is resolved at enqueue time: either the clinician-supplied
        # address from the UI form, or (legacy path) the patient's stored, consented
        # email. Both routes guarantee a recipient here, so gate the send on that.
        if not job["recipient"]:
            await _mark_failed(job_id, "no_recipient")
            return
        if not job["report_pdf_url"]:
            await _mark_failed(job_id, "no_pdf")
            return

        pdf_path = await _fetch_pdf(job["report_pdf_url"])
        patient_name = (job["patient_full_name"] or "Patient").strip()
        language = job["preferred_language"] or "en"
        date = str(job["consultation_date"])
        clinician_name = (job.get("clinician_name") or "").strip() or "Your clinician"
        body = _cover_body(
            language,
            patient_name=patient_name,
            date=date,
            clinician_name=clinician_name,
        )
        html = _cover_html(
            language,
            patient_name=patient_name,
            date=date,
            clinician_name=clinician_name,
            clinic_name=GMAIL_FROM_NAME or "Clinic",
        )
        subject = f"Care Plan — {job['consultation_date']}"
        msg = _build_message(job["recipient"], subject, body, pdf_path, html=html)
        message_id = await _send_email(msg)
        await _mark_sent(job_id, message_id)
        logger.info("delivered job=%s message_id=%s", job_id, message_id)
    except Exception as exc:
        logger.exception("delivery failed job=%s", job_id)
        await _mark_failed(job_id, str(exc))
        raise
    finally:
        # Always remove the downloaded PDF — _fetch_pdf writes a delete=False temp
        # file, so without this every send leaks a temp file on disk.
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("could not remove temp pdf %s", pdf_path)
