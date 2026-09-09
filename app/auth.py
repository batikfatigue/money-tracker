"""Single-user password login with an HMAC-signed session cookie.

Set MONEY_TRACKER_PASSWORD to enable. When unset, the app is open (local dev).
"""

import hashlib
import hmac
import os
import secrets
import time

COOKIE_NAME = "mt_session"
SESSION_TTL = 30 * 24 * 3600


def password() -> str | None:
    return os.environ.get("MONEY_TRACKER_PASSWORD") or None


def enabled() -> bool:
    return password() is not None


def _key() -> bytes:
    secret = os.environ.get("MONEY_TRACKER_SECRET") or f"mt-secret:{password()}"
    return hashlib.sha256(secret.encode()).digest()


def _sign(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def check_password(candidate: str) -> bool:
    expected = password()
    return expected is not None and hmac.compare_digest(candidate.encode(), expected.encode())


def issue_token() -> str:
    payload = f"{int(time.time()) + SESSION_TTL}.{secrets.token_hex(8)}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    payload, _, sig = token.rpartition(".")
    if not payload or not hmac.compare_digest(sig, _sign(payload)):
        return False
    expires, _, _ = payload.partition(".")
    return expires.isdigit() and int(expires) > time.time()
