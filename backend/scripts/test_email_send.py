"""Quick smoke-test: send a dummy care-plan email via Gmail SMTP.

Usage (from CPG LLM/ with venv active):
    python scripts/test_email_send.py --to jiaqi040204@gmail.com
"""
import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_FROM_NAME    = os.environ.get("GMAIL_FROM_NAME", "Clinic")


def send_test(to: str) -> None:
    msg = EmailMessage()
    msg["From"] = f"{GMAIL_FROM_NAME} <{GMAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = "Care Plan — 2026-05-29 [TEST]"
    msg.set_content(
        "Dear Jia Qi,\n\n"
        "This is a test email from the ClearPath Clinic delivery system.\n"
        "In production, your approved care-plan PDF would be attached here.\n\n"
        "— ClearPath Clinic\n"
        "(Do not reply to this email.)"
    )

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    print(f"OK: Test email sent to {to}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", default="jiaqi040204@gmail.com")
    args = parser.parse_args()
    send_test(args.to)
