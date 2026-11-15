"""Outbound notifications: email (SMTP) and Telegram. Both are optional and fail silently (logged)."""

import logging
import smtplib
from email.message import EmailMessage

import httpx

from .config import settings

log = logging.getLogger("sepa.notify")


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def telegram_configured() -> bool:
    return bool(settings.telegram_bot_token)


def send_email(to: str, subject: str, body: str) -> bool:
    if not email_configured():
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("Email to %s failed", to)
        return False


def send_telegram(chat_id: str, text: str) -> bool:
    if not telegram_configured() or not chat_id:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code != 200:
            log.warning("Telegram send failed: %s %s", r.status_code, r.text[:200])
        return r.status_code == 200
    except Exception:
        log.exception("Telegram send failed")
        return False
