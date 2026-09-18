from __future__ import annotations

from app.entity.notification import Notification, NotificationStatus


class NotificationRepo:
    def __init__(self, db):
        self.db = db

    def create(self, notification: Notification) -> None:
        notification.save()

    def get(self, notification_id: str) -> Notification | None:
        return Notification.objects.filter(pk=notification_id).first()

    def list_for_user(self, user_id: str, limit: int = 100) -> list[Notification]:
        return list(
            Notification.objects.filter(user_id=user_id).order_by("-created_at")[:limit]
        )

    def list_pending(self, limit: int = 100) -> list[Notification]:
        return list(
            Notification.objects.filter(status=NotificationStatus.PENDING.value).order_by(
                "created_at"
            )[:limit]
        )

    def has_pending(
        self, user_id: str, product_id: int, ntype: str
    ) -> Notification | None:
        return Notification.objects.filter(
            user_id=user_id,
            product_id=product_id,
            type=ntype,
            status=NotificationStatus.PENDING.value,
        ).first()

    def list_pending_for_product(
        self, product_id: int, ntype: str | None = None, limit: int = 100
    ) -> list[Notification]:
        queryset = Notification.objects.filter(
            product_id=product_id, status=NotificationStatus.PENDING.value
        )
        if ntype is not None:
            queryset = queryset.filter(type=ntype)
        return list(queryset[:limit])

    def update(self, notification: Notification) -> None:
        notification.save()
