from __future__ import annotations

from enum import StrEnum

from django.db import models


class NotificationType(StrEnum):
    PRICE_DROP = "price_drop"
    BACK_IN_STOCK = "back_in_stock"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(models.Model):
    """An alert subscription/attempt: price drop, or "email me when back"."""

    id = models.CharField(primary_key=True, max_length=36)
    user = models.ForeignKey(
        "app.User", on_delete=models.CASCADE, related_name="notifications"
    )
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="notifications"
    )
    tracker_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)

    type = models.CharField(max_length=24, db_index=True)
    status = models.CharField(max_length=16, default=NotificationStatus.PENDING.value)
    threshold_pct = models.FloatField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"

    def entry(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "productId": self.product_id,
            "trackerId": self.tracker_id,
            "type": self.type,
            "status": self.status,
            "thresholdPct": self.threshold_pct,
            "title": self.title,
            "message": self.message,
            "error": self.error,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "sentAt": self.sent_at.isoformat() if self.sent_at else None,
        }
