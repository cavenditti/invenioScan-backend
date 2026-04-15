"""Thin email helpers — no-op when SMTP is not configured."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from invenioscan.settings import Settings

logger = logging.getLogger(__name__)


async def send_email(
    settings: Settings,
    *,
    to: str,
    subject: str,
    body: str,
) -> None:
    """Send a plain-text email. Silently no-ops when smtp_host is None."""
    if not settings.smtp_host:
        logger.debug("SMTP not configured – skipping email to %s", to)
        return

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
        logger.info("Email sent to %s: %s", to, subject)
    except Exception:
        logger.exception("Failed to send email to %s", to)


async def notify_admin_new_registration(settings: Settings, username: str, email: str) -> None:
    """Alert admin that a new user registered and needs approval."""
    to = settings.admin_notification_email
    if not to:
        return
    await send_email(
        settings,
        to=to,
        subject=f"[Shelfscan] New registration: {username}",
        body=(
            f"A new user has registered and is awaiting approval.\n\n"
            f"  Username: {username}\n"
            f"  Email:    {email}\n\n"
            f"Log in to the admin panel to approve or deny this request."
        ),
    )


async def notify_user_approved(settings: Settings, email: str, username: str) -> None:
    """Let user know their account was approved."""
    await send_email(
        settings,
        to=email,
        subject="[Shelfscan] Your account has been approved",
        body=(
            f"Hi {username},\n\n"
            f"Your Shelfscan account has been approved. You can now log in.\n"
        ),
    )


async def notify_user_denied(settings: Settings, email: str, username: str) -> None:
    """Let user know their account was denied."""
    await send_email(
        settings,
        to=email,
        subject="[Shelfscan] Your account request was denied",
        body=(
            f"Hi {username},\n\n"
            f"Unfortunately your Shelfscan account request has been denied.\n"
            f"If you believe this is an error, please contact the administrator.\n"
        ),
    )
