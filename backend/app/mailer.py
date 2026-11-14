"""Sending email (sign-up confirmation, password reset).

Three ways, the first one configured wins:
  - BREVO_API_KEY: Brevo's HTTP API (free: 300 emails a day). Works with a single verified sender address,
    so no domain of your own is needed.
  - RESEND_API_KEY: Resend's HTTP API (free: 3,000 a month). Needs your own domain to email other people.
  - SMTP_HOST (+ SMTP_PORT, SMTP_USER, SMTP_PASSWORD): any SMTP server. Note Render's free plan blocks
    outgoing SMTP ports, so use one of the HTTP APIs there.
MAIL_FROM is the sender, e.g. "MoneyMap <hello@example.com>". Without any of these, sign-up skips the
confirmation email and password reset is unavailable.
"""
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

log = logging.getLogger("moneymap.mail")


def _provider() -> str | None:
    if not os.environ.get("MAIL_FROM"):
        return None
    if os.environ.get("BREVO_API_KEY"):
        return "brevo"
    if os.environ.get("RESEND_API_KEY"):
        return "resend"
    if os.environ.get("SMTP_HOST"):
        return "smtp"
    return None


def configured() -> bool:
    return _provider() is not None


def _post(url: str, headers: dict, body: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", "accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=15) as res:  # noqa: S310 (fixed https URLs)
        res.read()


def _smtp(msg: EmailMessage) -> None:
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    if port == 465:
        smtp = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=15)
    else:
        smtp = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15)
    with smtp:
        if port != 465 and smtp.has_extn("starttls"):
            smtp.starttls()
        if user:
            smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)


def send(to: str, subject: str, text: str) -> bool:
    provider = _provider()
    if provider is None:
        log.warning("Email not set up; not sending %r", subject)
        return False
    sender = os.environ["MAIL_FROM"]
    name, address = parseaddr(sender)
    try:
        if provider == "brevo":
            _post("https://api.brevo.com/v3/smtp/email", {"api-key": os.environ["BREVO_API_KEY"]},
                  {"sender": {"name": name or "MoneyMap", "email": address}, "to": [{"email": to}],
                   "subject": subject, "textContent": text})
        elif provider == "resend":
            _post("https://api.resend.com/emails", {"authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
                  {"from": sender, "to": [to], "subject": subject, "text": text})
        else:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = sender, to, subject
            msg.set_content(text)
            _smtp(msg)
        return True
    except (OSError, smtplib.SMTPException, urllib.error.URLError) as exc:  # never break sign-up because email failed
        log.error("Email to %s via %s failed: %s", to.split("@")[-1], provider, exc)
        return False
