"""Consent-gated SMTP email notifications for environmental groups."""
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import getaddresses

logger = logging.getLogger(__name__)


def send_environmental_notification(
    *, species: str, latitude: float, longitude: float,
    created_at: str, sighting_id: int, expires_at: str
) -> dict:
    """Send location only to configured group recipients after explicit opt-in."""
    try:
        raw_recipients = os.getenv("ENVIRONMENTAL_GROUP_EMAILS", "")
        recipients = [
            address for _, address in getaddresses([raw_recipients])
            if address and "@" in address
        ]
        host = os.getenv("SMTP_HOST", "").strip()
        username = os.getenv("SMTP_USERNAME", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        sender = os.getenv("SMTP_FROM_EMAIL", "").strip()
        if not recipients or not host or not sender or not username or not password:
            return {"status": "not_configured", "recipient_count": 0}

        message = EmailMessage()
        message["Subject"] = f"A.I.M. Multiflora Rose sighting #{sighting_id}"
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(
            "A user explicitly authorized environmental-group sharing of this "
            "Multiflora Rose sighting.\n\n"
            f"Species: {species}\n"
            f"Coordinates: {latitude:.6f}, {longitude:.6f}\n"
            f"Submitted (UTC): {created_at}\n"
            f"Consent expires (UTC): {expires_at}\n"
            f"Sighting reference: {sighting_id}\n\n"
            "Please handle these coordinates according to your organization's "
            "privacy and conservation-data policies."
        )

        port = int(os.getenv("SMTP_PORT", "465"))
        use_ssl = os.getenv("SMTP_USE_SSL", "true").lower() in {"1", "true", "yes"}
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "12"))

        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
                smtp.login(username, password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(message)
        return {"status": "sent", "recipient_count": len(recipients)}
    except Exception:
        logger.exception("Environmental-group email delivery failed")
        return {"status": "failed", "recipient_count": 0}
