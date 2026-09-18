"""DRF authentication: Bearer token or cookie → lightweight principal."""

from __future__ import annotations

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from app.api.auth.jwt import validate_jwt
from app.api.auth.middleware import extract_token


class SimpleUser:
    """Just the user id — services take ``user_id`` strings, not ORM users."""

    def __init__(self, user_id: str):
        self.id = user_id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.id


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = extract_token(request)
        if not token:
            return None  # optional auth: anonymous is allowed on public views
        try:
            return (SimpleUser(validate_jwt(token)), token)
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationFailed("invalid or expired token") from exc
