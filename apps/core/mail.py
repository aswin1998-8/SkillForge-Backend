"""Outbound email for invites. Render free plans block SMTP; prefer Resend HTTP."""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

_NO_PROVIDER = (
    "Email is not configured on the server. Set RESEND_API_KEY "
    "(recommended on Render) or EMAIL_HOST SMTP credentials. "
    "Console logging is not delivery."
)


def _from_header() -> str:
    raw = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "noreply@honed.app").strip()
    if "<" in raw:
        return raw
    return f"Honed <{raw}>"


def _html_body(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    paragraphs = "".join(
        f"<p style=\"margin:0 0 12px;line-height:1.5\">{p.replace(chr(10), '<br>')}</p>"
        for p in escaped.split("\n\n")
    )
    return (
        "<!DOCTYPE html><html><body style=\"font-family:system-ui,sans-serif;"
        "font-size:16px;color:#111;max-width:560px\">"
        f"{paragraphs}"
        "<p style=\"margin-top:24px;font-size:12px;color:#666\">"
        "Honed · You received this because you joined the waitlist."
        "</p></body></html>"
    )


def _send_via_resend(*, to: str, subject: str, text: str) -> None:
    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    payload = {
        "from": _from_header(),
        "to": [to],
        "subject": subject,
        "text": text,
        "html": _html_body(text),
        "headers": {
            "List-Unsubscribe": f"<mailto:{settings.DEFAULT_FROM_EMAIL}>",
        },
    }
    reply_to = (getattr(settings, "EMAIL_REPLY_TO", "") or "").strip()
    if reply_to:
        payload["reply_to"] = [reply_to]
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend error {response.status_code}: {response.text}")


def _using_locmem() -> bool:
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    return "locmem" in backend


def _can_use_smtp() -> bool:
    return bool(getattr(settings, "EMAIL_HOST", "") or "")


def send_outbound_email(*, to: str, subject: str, text: str) -> None:
    if _using_locmem():
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return

    api_key = getattr(settings, "RESEND_API_KEY", "") or ""
    if api_key:
        _send_via_resend(to=to, subject=subject, text=text)
        return

    if _can_use_smtp():
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return

    if settings.DEBUG:
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return

    raise ValidationError({"email": _NO_PROVIDER})
