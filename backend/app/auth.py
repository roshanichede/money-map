"""Who is making this request.

Local mode (INTERNAL_API_SECRET unset): one built-in user, no login. This is how ./start.sh runs by default.

Login mode (INTERNAL_API_SECRET set): the browser never talks to this API directly. The Next.js server
signs the user in with Google, then forwards each request with X-User-Email / X-User-Name and the shared
X-Internal-Secret. Requests without the right secret are rejected, so the headers can't be forged.
"""
import hmac
import os
from urllib.parse import unquote

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
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
    session.commit()
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
    return _get_or_create(session, email, unquote(request.headers.get("x-user-name", ""))[:255])
