"""Signed, expiring links for confirming an email address and resetting a password.

Stateless: a link is the email, an expiry and a purpose, signed with the server secret. A reset link also signs
part of the current password hash, so it stops working once the password has been changed (single use)."""
import base64
import hashlib
import hmac
import os
import time


def _key() -> bytes:
    return hashlib.sha256(("moneymap-links:" + os.environ.get("INTERNAL_API_SECRET", "")).encode()).digest()


def make(purpose: str, email: str, extra: str = "", hours: int = 24) -> str:
    expires = int(time.time()) + hours * 3600
    payload = f"{purpose}|{email}|{expires}"
    sig = hmac.new(_key(), f"{payload}|{extra}".encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode().rstrip("=")


def read(token: str, purpose: str, extra_for=lambda email: "") -> str | None:
    """The email the link was made for, or None if it's forged, expired or for another purpose."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        p, email, expires, sig = raw.split("|")
    except (ValueError, UnicodeDecodeError):
        return None
    if p != purpose or int(expires) < time.time():
        return None
    good = hmac.new(_key(), f"{p}|{email}|{expires}|{extra_for(email)}".encode(), hashlib.sha256).hexdigest()[:32]
    return email if hmac.compare_digest(sig, good) else None
