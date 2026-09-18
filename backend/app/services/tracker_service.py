"""Tracker service — add/untrack, cadence changes, history, logs and dashboard."""

from __future__ import annotations

from datetime import timedelta

from app.entity.price import SnapshotTrigger
from app.entity.tracker import Tracker
from app.services.errors import NotFound, ValidationError
from app.utils.timeutil import utcnow


class TrackerServiceMixin:
    # ------------------------------------------------------------------ helpers
    def _min_refresh(self) -> int:
        return int(self.cfg["Core"]["minRefreshMinutes"])

    def _default_refresh(self) -> int:
        return int(self.cfg["Core"]["defaultRefreshMinutes"])

    def _validate_refresh(self, minutes: int | None) -> int:
        if minutes is None:
            return self._default_refresh()
        try:
            minutes = int(minutes)
        except (TypeError, ValueError) as exc:
            raise ValidationError("refreshMinutes must be an integer") from exc
        if minutes < self._min_refresh():
            raise ValidationError(
                f"refreshMinutes must be at least {self._min_refresh()} minutes"
            )
        if minutes > 60 * 24 * 30:
            raise ValidationError("refreshMinutes is unreasonably large")
        return minutes

    def _owned_tracker(self, user_id: str, tracker_id: str) -> Tracker:
        tracker = self.db.trackers.get(tracker_id)
        if tracker is None or tracker.user_id != user_id:
            raise NotFound("tracker not found")
        return tracker

    def _tracker_payload(self, tracker: Tracker, include_latest: bool = True) -> dict:
        product = self.db.products.get(tracker.product_id)
        latest = (
            self.db.prices.latest_for_product(tracker.product_id)
            if include_latest
            else None
        )
        payload = {
            "id": tracker.id,
            "productId": tracker.product_id,
            "product": product.card() if product else None,
            "refreshMinutes": tracker.refresh_minutes,
            "active": tracker.active,
            "alertOnPriceDrop": tracker.alert_on_price_drop,
            "priceDropThresholdPct": tracker.price_drop_threshold_pct,
            "alertOnBackInStock": tracker.alert_on_back_in_stock,
            "lastCoveredSlot": tracker.last_covered_slot.isoformat()
            if tracker.last_covered_slot
            else None,
            "lastScrapedAt": tracker.last_scraped_at.isoformat()
            if tracker.last_scraped_at
            else None,
            "createdAt": tracker.created_at.isoformat() if tracker.created_at else None,
            "latest": latest.point() if latest is not None else None,
            "snapshotCount": self.db.prices.count_for_product(tracker.product_id),
        }
        return payload

    # ------------------------------------------------------------------ CRUD
    def add_tracker(
        self,
        user_id: str,
        product_id: int,
        refresh_minutes: int | None = None,
        alert_on_price_drop: bool = True,
        price_drop_threshold_pct: float | None = None,
        alert_on_back_in_stock: bool = True,
        run_now: bool = True,
    ) -> dict:
        if self.db.products.get(product_id) is None:
            raise NotFound("product not found")
        minutes = self._validate_refresh(refresh_minutes)

        tracker = self.db.trackers.get_by_user_product(user_id, product_id)
        if tracker is not None:
            tracker.active = True
            tracker.refresh_minutes = minutes
            tracker.alert_on_price_drop = bool(alert_on_price_drop)
            tracker.price_drop_threshold_pct = price_drop_threshold_pct
            tracker.alert_on_back_in_stock = bool(alert_on_back_in_stock)
            self.db.trackers.update(tracker)
        else:
            tracker = Tracker(
                id=self.id_gen.new_id(),
                user_id=user_id,
                product_id=product_id,
                refresh_minutes=minutes,
                active=True,
                alert_on_price_drop=bool(alert_on_price_drop),
                price_drop_threshold_pct=price_drop_threshold_pct,
                alert_on_back_in_stock=bool(alert_on_back_in_stock),
            )
            self.db.trackers.create(tracker)

        if run_now:
            # Kick off an immediate scrape so the user sees data without
            # waiting for the next cron slot.
            self.core.track.submit(product_id, SnapshotTrigger.ON_DEMAND.value, tracker.id)

        return self._tracker_payload(tracker)

    def update_tracker(self, user_id: str, tracker_id: str, **fields) -> dict:
        tracker = self._owned_tracker(user_id, tracker_id)

        new_minutes = fields.get("refresh_minutes")
        if new_minutes is not None:
            new_minutes = self._validate_refresh(new_minutes)
            if new_minutes != tracker.refresh_minutes:
                # Spec: changing cadence deletes the user's records captured
                # under the old timing. Shared snapshots stay for other users.
                deleted = self.db.prices.delete_history_for_tracker(tracker.id)
                self.logger.info(
                    "tracker %s cadence %d -> %d; deleted %d history rows",
                    tracker.id,
                    tracker.refresh_minutes,
                    new_minutes,
                    deleted,
                )
                tracker.refresh_minutes = new_minutes
                tracker.last_covered_slot = None

        for attr in ("active", "alert_on_price_drop", "alert_on_back_in_stock"):
            if attr in fields and fields[attr] is not None:
                setattr(tracker, attr, bool(fields[attr]))
        if "price_drop_threshold_pct" in fields:
            threshold = fields["price_drop_threshold_pct"]
            tracker.price_drop_threshold_pct = (
                float(threshold) if threshold is not None else None
            )

        self.db.trackers.update(tracker)
        return self._tracker_payload(tracker)

    def untrack(self, user_id: str, tracker_id: str) -> None:
        tracker = self._owned_tracker(user_id, tracker_id)
        self.db.trackers.delete(tracker.id)
        self.logger.info("untracked %s (cron coverage removed)", tracker.id)

    def list_trackers(self, user_id: str) -> list[dict]:
        return [self._tracker_payload(t) for t in self.db.trackers.list_for_user(user_id)]

    def get_tracker(self, user_id: str, tracker_id: str) -> dict:
        return self._tracker_payload(self._owned_tracker(user_id, tracker_id))

    # ------------------------------------------------------------------ history
    def tracker_history(self, user_id: str, tracker_id: str, days: int | None = None) -> dict:
        self._owned_tracker(user_id, tracker_id)
        since = utcnow() - timedelta(days=days) if days else None
        points = [p.point() for p in self.db.prices.history_for_tracker(tracker_id, since)]
        prices = [p["price"] for p in points if p["price"] is not None]
        stats = {
            "count": len(points),
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "current": prices[-1] if prices else None,
            "first": prices[0] if prices else None,
            "changePct": (
                round((prices[-1] - prices[0]) / prices[0] * 100, 2)
                if len(prices) >= 2 and prices[0]
                else None
            ),
        }
        return {"points": points, "stats": stats}

    def tracker_logs(self, user_id: str, tracker_id: str, limit: int = 50, page: int = 1) -> dict:
        tracker = self._owned_tracker(user_id, tracker_id)
        page = max(1, page)
        limit = min(max(1, limit), 200)
        # The scrape itself is per product (shared across trackers), so show the
        # product's log — every attempt, including ones another tracker paid for.
        rows, total = self.db.prices.logs_for_product(
            tracker.product_id, limit, (page - 1) * limit
        )
        return {"items": [r.entry() for r in rows], "total": total, "page": page, "pageSize": limit}

    def product_logs(self, product_id: int, limit: int = 50, page: int = 1) -> dict:
        page = max(1, page)
        limit = min(max(1, limit), 200)
        rows, total = self.db.prices.logs_for_product(
            product_id, limit, (page - 1) * limit
        )
        return {"items": [r.entry() for r in rows], "total": total, "page": page, "pageSize": limit}

    # ------------------------------------------------------------------ dashboard
    def dashboard(self, user_id: str) -> dict:
        trackers = self.db.trackers.list_for_user(user_id)
        items = [self._tracker_payload(t) for t in trackers]

        structure_changes = sum(
            1
            for t in trackers
            if (p := self.db.products.get(t.product_id)) is not None
            and p.structure_changed_at is not None
        )
        notifications = self.db.notifications.list_for_user(user_id, limit=20)

        recent_logs: list[dict] = []
        for t in trackers:
            rows, _ = self.db.prices.logs_for_product(t.product_id, limit=5)
            recent_logs.extend(r.entry() for r in rows)
        recent_logs.sort(key=lambda r: r["createdAt"] or "", reverse=True)

        return {
            "stats": {
                "trackedProducts": len(trackers),
                "activeTrackers": sum(1 for t in trackers if t.active),
                "structureChanges": structure_changes,
                "pendingAlerts": sum(1 for n in notifications if n.status == "pending"),
                "sentAlerts": sum(1 for n in notifications if n.status == "sent"),
            },
            "trackers": items,
            "notifications": [n.entry() for n in notifications],
            "recentLogs": recent_logs[:20],
        }
