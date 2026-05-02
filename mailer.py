import base64
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from config import settings
from models import EmailRequest

logger = logging.getLogger(__name__)


def send_email(req: EmailRequest) -> None:
    """Baut die MIME-Nachricht auf und sendet sie über Plesk-SMTP."""

    # Äusserer Container: mixed (für Anhänge), sonst alternative (text+html)
    has_attachments = bool(req.attachments)
    if has_attachments:
        outer = MIMEMultipart("mixed")
        body_container = MIMEMultipart("alternative")
        outer.attach(body_container)
    else:
        outer = MIMEMultipart("alternative")
        body_container = outer

    # Header setzen
    sender_display = formataddr((req.from_name or "", settings.smtp_from_email))
    outer["From"] = sender_display
    outer["To"] = ", ".join(req.to)
    outer["Subject"] = req.subject
    if req.cc:
        outer["Cc"] = ", ".join(req.cc)

    # Textkörper anhängen (plain zuerst, dann html – Priorität bei Clients)
    if req.body_text:
        body_container.attach(MIMEText(req.body_text, "plain", "utf-8"))
    if req.body_html:
        body_container.attach(MIMEText(req.body_html, "html", "utf-8"))

    # Anhänge verarbeiten
    for att in req.attachments or []:
        try:
            raw = base64.b64decode(att.data, validate=True)
        except Exception:
            raise ValueError(f"Anhang '{att.filename}': ungültige Base64-Daten")

        main_type, sub_type = att.content_type.split("/", 1)
        part = MIMEBase(main_type, sub_type)
        part.set_payload(raw)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=att.filename,
        )
        outer.attach(part)

    # Alle Empfänger zusammenführen (to + cc + bcc)
    all_recipients = list(req.to) + list(req.cc or []) + list(req.bcc or [])

    logger.info(
        "Sende Mail | An: %s | Betreff: %s | Anhänge: %d",
        all_recipients,
        req.subject,
        len(req.attachments or []),
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.ehlo()
        if settings.smtp_use_tls:
            server.starttls()
            server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, all_recipients, outer.as_string())

    logger.info("Mail erfolgreich gesendet an %s", all_recipients)
