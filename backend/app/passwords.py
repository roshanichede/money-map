"""Email + password accounts. Passwords are hashed with scrypt (Python standard library) and a random salt."""
import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque

N, R, P = 2**14, 8, 1
MIN_LENGTH = 8


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


class Throttle:
    """At most 10 failed sign-ins per email in 15 minutes."""

    def __init__(self, limit: int = 10, window: float = 900):
        self.limit, self.window = limit, window
        self.fails: dict[str, deque] = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        q = self.fails[key]
        while q and q[0] < time.monotonic() - self.window:
            q.popleft()
        return len(q) >= self.limit

    def fail(self, key: str) -> None:
        self.fails[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        self.fails.pop(key, None)


throttle = Throttle()
