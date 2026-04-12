"""
Email sending service for Saliksik AI.

Uses SMTP when configured (SMTP_HOST is set), otherwise logs the email
content to the application logger (useful in development / testing).
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_verification_email(username: str, verification_url: str) -> MIMEMultipart:
    """Build the email verification MIME message."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your Saliksik AI email address"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"

    plain = (
        f"Hello {username},\n\n"
        f"Please verify your email address by visiting the link below:\n\n"
        f"{verification_url}\n\n"
        f"This link expires in {settings.EMAIL_VERIFY_EXPIRE_HOURS} hour(s).\n\n"
        f"If you did not create a Saliksik AI account, you can safely ignore this email.\n\n"
        f"— The Saliksik AI Team"
    )
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #2563eb;">Verify your email address</h2>
      <p>Hello <strong>{username}</strong>,</p>
      <p>Please click the button below to verify your email address.</p>
      <p style="margin: 24px 0;">
        <a href="{verification_url}"
           style="background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;
                  text-decoration:none;font-weight:bold;">
          Verify Email
        </a>
      </p>
      <p>Or copy and paste this URL into your browser:</p>
      <p style="word-break:break-all;color:#4b5563;">{verification_url}</p>
      <p style="color:#9ca3af;font-size:0.875rem;">
        This link expires in {settings.EMAIL_VERIFY_EXPIRE_HOURS} hour(s).
        If you did not create a Saliksik AI account, you can safely ignore this email.
      </p>
    </body>
    </html>
    """
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_verification_email(to_email: str, username: str, token: str) -> bool:
    """
    Send an email verification message.

    - When SMTP is configured (SMTP_HOST set): sends via SMTP with STARTTLS.
    - Otherwise: logs the verification URL (development / test mode).

    Returns True on success, False on failure.
    """
    verification_url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"

    if not settings.SMTP_HOST:
        logger.info(
            "EMAIL VERIFICATION (dev mode — SMTP not configured): "
            "username=%s email=%s url=%s",
            username,
            to_email,
            verification_url,
        )
        return True

    try:
        msg = _build_verification_email(username, verification_url)
        msg["To"] = to_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())

        logger.info("Verification email sent to %s", to_email)
        return True

    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", to_email, exc)
        return False


def send_verification_email_async_safe(
    to_email: str, username: str, token: str
) -> None:
    """
    Fire-and-forget wrapper: call from an async context via run_in_executor,
    or directly from a Celery task.  Swallows all exceptions so a mail
    failure never breaks registration.
    """
    try:
        send_verification_email(to_email, username, token)
    except Exception as exc:
        logger.error("Unexpected error in email sender: %s", exc)
