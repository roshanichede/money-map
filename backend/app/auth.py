"""Who is making this request.

Local mode (INTERNAL_API_SECRET unset): one built-in user, no login. This is how ./start.sh runs by default.

Login mode (INTERNAL_API_SECRET set): the browser never talks to this API directly. The Next.js server
signs the user in with Google, then forwards each request with X-User-Email / X-User-Name and the shared
X-Internal-Secret. Requests without the right secret are rejected, so the headers can't be forged.
"""
import hmac
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_session
from .models import Transaction, User

LOCAL_EMAIL = "local@moneymap"


def login_mode() -> bool:
    return bool(os.environ.get("INTERNAL_API_SECRET"))


def _get_or_create(session: Session, email: str, name: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user:
        if name and user.name != name:
            user.name = name
            session.commit()
        return user
    # First person to sign in inherits anything imported while the app ran in local mode.
    local = session.scalar(select(User).where(User.email == LOCAL_EMAIL))
    others = session.scalar(select(func.count()).select_from(User).where(User.email != LOCAL_EMAIL))
    if local and not others:
        has_data = session.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == local.id))
        if has_data:
            local.email, local.name = email, name
            session.commit()
            return local
    user = User(email=email, name=name)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:  # a parallel first request created this user a moment ago
        session.rollback()
        user = session.scalar(select(User).where(User.email == email))
    return user


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    secret = os.environ.get("INTERNAL_API_SECRET")
    if not secret:
        return _get_or_create(session, LOCAL_EMAIL, "You")
    sent = request.headers.get("x-internal-secret", "")
    if not hmac.compare_digest(sent.encode(), secret.encode()):
        raise HTTPException(401, "Not signed in.")
    email = request.headers.get("x-user-email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(401, "Not signed in.")
    provider = request.headers.get("x-user-provider", "")
    if provider == "credentials":
        # Password accounts are created at sign-up, never here: a session for a deleted account stops working.
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            raise HTTPException(401, "This account no longer exists. Sign in again.")
    else:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is None and os.environ.get("SIGNUP_MODE", "invite") != "open" and _has_accounts(session):
            raise HTTPException(403, "Sign-up is by invitation for now.")  # a new Google user while invite-only
        user = _get_or_create(session, email, unquote(request.headers.get("x-user-name", ""))[:255])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.last_seen is None or now - user.last_seen > timedelta(hours=1):
        user.last_seen = now
        session.commit()
    return user


def _has_accounts(session: Session) -> bool:
    return bool(session.scalar(select(func.count()).select_from(User).where(User.email != LOCAL_EMAIL)))


def owner_emails(session: Session) -> set[str]:
    """OWNER_EMAILS if set; otherwise the first account ever created (the person who deployed it)."""
    configured = {e.strip().lower() for e in os.environ.get("OWNER_EMAILS", "").split(",") if e.strip()}
    if configured:
        return configured
    first = session.scalar(select(User).where(User.email != LOCAL_EMAIL).order_by(User.id))
    return {first.email} if first else set()


def is_owner(session: Session, user: User) -> bool:
    return login_mode() and user.email in owner_emails(session)


def owner_only(user: User = Depends(current_user), session: Session = Depends(get_session)) -> User:
    if not is_owner(session, user):
        raise HTTPException(404, "Not found.")
    return user


def internal_only(request: Request) -> None:
    """Sign-up and password checks may only come from the Next.js server, never straight from a browser."""
    secret = os.environ.get("INTERNAL_API_SECRET")
    sent = request.headers.get("x-internal-secret", "")
    if not secret or not hmac.compare_digest(sent.encode(), secret.encode()):
        raise HTTPException(403, "Not allowed.")


def find_or_create(session: Session, email: str, name: str) -> User:
    return _get_or_create(session, email, name)
