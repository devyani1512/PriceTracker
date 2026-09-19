"""Email policy: only the out-of-stock -> in-stock transition emails by default."""

from __future__ import annotations

import logging
import os
from types import SimpleNamespace

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.entity.notification import NotificationType  # noqa: E402
from app.services.notification_service import NotificationServiceMixin  # noqa: E402


class _Svc(NotificationServiceMixin):
    def __init__(self, cfg, previous, trackers):
        self.cfg = cfg
        self.db = SimpleNamespace(
            prices=SimpleNamespace(previous_for_product=lambda pid, before: previous),
            trackers=SimpleNamespace(list_active_for_product=lambda pid: trackers),
            notifications=SimpleNamespace(list_pending_for_product=lambda pid, ntype: []),
        )
        self.logger = logging.getLogger("test.notification")
        self.enqueued: list[str] = []

    def _enqueue(self, user_id, product_id, tracker_id, ntype, threshold_pct, title, message):
        self.enqueued.append(ntype.value)


def _tracker(**overrides) -> SimpleNamespace:
    values = {
        "id": "t1",
        "user_id": "u1",
        "alert_on_price_drop": True,
        "price_drop_threshold_pct": 0.0,
        "alert_on_back_in_stock": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _snapshot(price: float | None = None, in_stock: bool | None = None) -> SimpleNamespace:
    return SimpleNamespace(price=price, in_stock=in_stock, captured_at=None)


def _cfg(only_stock: bool = True) -> dict:
    return {
        "Email": {"backInStockOnly": only_stock},
        "Core": {"storefrontBase": "https://example.test"},
    }


def test_back_in_stock_only_emails_restock_not_price_drop():
    previous = SimpleNamespace(price=100.0, in_stock=False)
    svc = _Svc(_cfg(True), previous, [_tracker()])

    svc.evaluate_snapshot(1, _snapshot(price=50.0, in_stock=True))

    assert svc.enqueued == [NotificationType.BACK_IN_STOCK.value]


def test_back_in_stock_only_suppresses_price_drop_without_restock():
    previous = SimpleNamespace(price=100.0, in_stock=True)
    svc = _Svc(_cfg(True), previous, [_tracker()])

    svc.evaluate_snapshot(1, _snapshot(price=50.0, in_stock=True))

    assert svc.enqueued == []


def test_price_drop_emails_when_policy_disabled():
    previous = SimpleNamespace(price=100.0, in_stock=True)
    svc = _Svc(_cfg(False), previous, [_tracker()])

    svc.evaluate_snapshot(1, _snapshot(price=50.0, in_stock=True))

    assert svc.enqueued == [NotificationType.PRICE_DROP.value]
