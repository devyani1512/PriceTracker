"""JWT issue/verify (≈ auth/jwt.go). PyJWT + HS256."""

from __future__ import annotations

import time

import jwt

_ALGORITHM = "HS256"
_KEY: str = ""
_TTL_HOURS: int = 168


def configure(key: str, ttl_hours: int = 168) -> None:
    global _KEY, _TTL_HOURS
    _KEY = key or ""
    _TTL_HOURS = int(ttl_hours or 168)


def generate_jwt(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + _TTL_HOURS * 3600}
    return jwt.encode(payload, _KEY, algorithm=_ALGORITHM)


def validate_jwt(token: str) -> str:
    payload = jwt.decode(token, _KEY, algorithms=[_ALGORITHM])
    subject = payload.get("sub")
    if not subject:
        raise ValueError("token missing subject")
    return str(subject)
