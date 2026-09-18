from __future__ import annotations

from app.entity.user import User


class UserRepo:
    def __init__(self, db):
        self.db = db

    def create(self, user: User) -> None:
        user.save()

    def get(self, user_id: str) -> User | None:
        return User.objects.filter(pk=user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return User.objects.filter(email=email).first()

    def list_all(self) -> list[User]:
        return list(User.objects.order_by("-created_at"))

    def update(self, user: User) -> None:
        user.save()
