import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def send_invite_email(to_email: str, inviter_name: str, register_url: str) -> bool:
    """Send invitation email. Returns True if sent, False if SMTP not configured or failed."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{inviter_name} har invitert deg til Yields"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = to_email

    text = f"""Hei!

{inviter_name} har invitert deg til å se eiendommene sine i Yields – en app for å holde oversikt over eiendomsøkonomi.

Registrer deg her for å få tilgang:
{register_url}

Med vennlig hilsen,
Yields
"""

    html = f"""<!DOCTYPE html>
<html lang="no">
<body style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:2rem;color:#1a202c">
  <h2 style="color:#1a365d">Du er invitert til Yields</h2>
  <p><strong>{inviter_name}</strong> har invitert deg til å se eiendommene sine i <strong>Yields</strong>.</p>
  <p style="margin:1.5rem 0">
    <a href="{register_url}"
       style="background:#1a365d;color:white;padding:0.75rem 1.5rem;border-radius:6px;text-decoration:none;font-weight:600">
      Registrer deg
    </a>
  </p>
  <p style="color:#718096;font-size:0.85rem">Eller kopier denne lenken: {register_url}</p>
</body>
</html>"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(msg["From"], to_email, msg.as_string())
        return True
    except Exception:
        return False
