"""Notification service — price-drop and back-in-stock alerts, in-app + email."""

from __future__ import annotations

from app.entity.notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from app.entity.price import PriceSnapshot
from app.services.errors import NotFound
from app.utils.timeutil import utcnow

_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def format_money(value: float | None, currency: str | None = "INR") -> str:
    if value is None:
        return "—"
    symbol = _CURRENCY_SYMBOLS.get(currency or "INR", "")
    return f"{symbol}{value:,.2f}"


class NotificationServiceMixin:
    # ------------------------------------------------------------------ subscribe
    def subscribe_back_in_stock(
        self, user_id: str, product_id: int, tracker_id: str | None = None
    ) -> dict:
        product = self.db.products.get(product_id)
        if product is None:
            raise NotFound("product not found")

        existing = self.db.notifications.has_pending(
            user_id, product_id, NotificationType.BACK_IN_STOCK.value
        )
        if existing is not None:
            return existing.entry()

        latest = self.db.prices.latest_for_product(product_id)
        notification = Notification(
            id=self.id_gen.new_id(),
            user_id=user_id,
            product_id=product_id,
            tracker_id=tracker_id,
            type=NotificationType.BACK_IN_STOCK.value,
            status=NotificationStatus.PENDING.value,
            title=f"Back in stock: {product.name}",
            message=f"We'll email you when {product.name} is back in stock.",
        )
        self.db.notifications.create(notification)

        # If it is already available, don't make the user wait for a scrape.
        if latest is not None and latest.in_stock is True:
            self._deliver(notification)
        return notification.entry()

    def list_notifications(self, user_id: str) -> list[dict]:
        return [n.entry() for n in self.db.notifications.list_for_user(user_id)]

    # ------------------------------------------------------------------ evaluate
    def evaluate_snapshot(self, product_id: int, snapshot: PriceSnapshot) -> None:
        """Cron hook: turn a fresh snapshot into alerts where rules match."""
        if snapshot.price is None and snapshot.in_stock is None:
            return

        previous = self.db.prices.previous_for_product(product_id, snapshot.captured_at)
        trackers = self.db.trackers.list_active_for_product(product_id)

        for tracker in trackers:
            if (
                tracker.alert_on_price_drop
                and previous is not None
                and previous.price
                and snapshot.price is not None
                and snapshot.price < previous.price
            ):
                drop_pct = (previous.price - snapshot.price) / previous.price * 100.0
                threshold = tracker.price_drop_threshold_pct or 0.0
                if drop_pct > 0 and drop_pct >= threshold:
                    self._enqueue(
                        tracker.user_id,
                        product_id,
                        tracker.id,
                        NotificationType.PRICE_DROP,
                        threshold_pct=round(drop_pct, 2),
                        title=None,
                        message=None,
                    )

            if (
                tracker.alert_on_back_in_stock
                and previous is not None
                and previous.in_stock is False
                and snapshot.in_stock is True
            ):
                self._enqueue(
                    tracker.user_id,
                    product_id,
                    tracker.id,
                    NotificationType.BACK_IN_STOCK,
                    threshold_pct=None,
                    title=None,
                    message=None,
                )

        # Standalone "email me when it's back" subscriptions (no tracker needed).
        for notification in self.db.notifications.list_pending_for_product(
            product_id, NotificationType.BACK_IN_STOCK.value
        ):
            if snapshot.in_stock is True:
                self._deliver(notification)

    # ------------------------------------------------------------------ dispatch
    def dispatch_pending(self, limit: int = 50) -> int:
        sent = 0
        for notification in self.db.notifications.list_pending(limit=limit):
            self._deliver(notification)
            sent += 1
        return sent

    # ------------------------------------------------------------------ internals
    def _enqueue(
        self,
        user_id: str,
        product_id: int,
        tracker_id: str | None,
        ntype: NotificationType,
        threshold_pct: float | None,
        title: str | None,
        message: str | None,
    ) -> None:
        notification = Notification(
            id=self.id_gen.new_id(),
            user_id=user_id,
            product_id=product_id,
            tracker_id=tracker_id,
            type=ntype.value,
            status=NotificationStatus.PENDING.value,
            threshold_pct=threshold_pct,
            title=title,
            message=message,
        )
        self.db.notifications.create(notification)
        self._deliver(notification)

    def _deliver(self, notification: Notification) -> None:
        product = self.db.products.get(notification.product_id)
        user = self.db.users.get(notification.user_id)
        if product is None or user is None:
            notification.status = NotificationStatus.FAILED.value
            notification.error = "product or user no longer exists"
            self.db.notifications.update(notification)
            return

        latest = self.db.prices.latest_for_product(notification.product_id)
        currency = latest.currency if latest is not None else "INR"
        price_text = format_money(latest.price if latest is not None else None, currency)
        link = f"{str(self.cfg['Core']['storefrontBase']).rstrip('/')}/product/{product.id}"

        if notification.type == NotificationType.PRICE_DROP.value:
            subject = f"Price drop: {product.name} is now {price_text}"
            body = (
                f"Good news — the price of {product.name} dropped.\n\n"
                f"Current price: {price_text}\n"
                f"Drop: {notification.threshold_pct}%\n"
                f"Stock: {latest.stock_label if latest is not None else 'unknown'}\n\n"
                f"View it: {link}\n"
            )
        else:
            subject = f"Back in stock: {product.name}"
            body = (
                f"{product.name} is back in stock.\n\n"
                f"Price: {price_text}\n"
                f"Stock: {latest.stock_label if latest is not None else 'in stock'}\n\n"
                f"View it: {link}\n"
            )

        ok, detail = self.email.send(user.email, subject, body)
        notification.title = subject
        notification.message = body
        notification.sent_at = utcnow()
        if ok:
            notification.status = NotificationStatus.SENT.value
            notification.error = None if detail == "sent" else detail
        else:
            notification.status = NotificationStatus.FAILED.value
            notification.error = detail
        self.db.notifications.update(notification)
        self.logger.info(
            "notification %s (%s) -> %s (%s)",
            notification.id,
            notification.type,
            user.email,
            notification.status,
        )
