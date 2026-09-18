"""User service — registration, login and lookup (email + password + JWT)."""

from __future__ import annotations

from app.entity.user import User
from app.services.errors import Conflict, Unauthorized, ValidationError
from app.utils.security import hash_password, normalize_email, verify_password


class UserServiceMixin:
    def register_user(self, email: str, password: str, display_name: str | None = None) -> User:
        email = normalize_email(email or "")
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValidationError("a valid email is required")
        if len(password or "") < 8:
            raise ValidationError("password must be at least 8 characters")
        if self.db.users.get_by_email(email) is not None:
            raise Conflict("an account with that email already exists")

        user = User(
            id=self.id_gen.new_id(),
            email=email,
            password_hash=hash_password(password),
            display_name=(display_name or email.split("@")[0])[:80],
        )
        self.db.users.create(user)
        self.logger.info("registered user %s", email)
        return user

    def login_user(self, email: str, password: str) -> User:
        user = self.db.users.get_by_email(normalize_email(email or ""))
        if user is None or not verify_password(password or "", user.password_hash):
            raise Unauthorized("invalid email or password")
        return user

    def get_user(self, user_id: str) -> User | None:
        return self.db.users.get(user_id)
