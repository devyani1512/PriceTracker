from __future__ import annotations

from enum import StrEnum

from django.db import models
from django.utils import timezone


class ScrapeOutcome(StrEnum):
    SUCCESS = "success"
    RETRIED = "retried"
    FAILED = "failed"


class ScrapeErrorKind(StrEnum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    PARSE = "parse"
    STRUCTURE = "structure"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class SnapshotTrigger(StrEnum):
    TRACK = "track"          # scheduled cron tick
    MANUAL = "manual"        # user pressed "refresh"
    ON_DEMAND = "on_demand"  # product page opened and no data existed


class PriceSnapshot(models.Model):
    """The shared, timescale-ish lookup table.

    One row per scrape. Multiple users tracking the same product at different
    cadences share the same snapshot — if a value already exists for the slot,
    the cron core reuses it instead of scraping again.
    """

    id = models.CharField(primary_key=True, max_length=36)
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="snapshots"
    )
    slot_at = models.DateTimeField(db_index=True)
    captured_at = models.DateTimeField(default=timezone.now, db_index=True)

    price = models.FloatField(null=True, blank=True)
    was_price = models.FloatField(null=True, blank=True)
    discount_pct = models.IntegerField(null=True, blank=True)
    currency = models.CharField(max_length=8, null=True, blank=True)

    in_stock = models.BooleanField(null=True, blank=True)
    stock_label = models.CharField(max_length=120, null=True, blank=True)
    stock_count = models.IntegerField(null=True, blank=True)

    layout_revision = models.IntegerField(null=True, blank=True)
    structure_changed = models.BooleanField(default=False)
    trigger = models.CharField(max_length=16, default=SnapshotTrigger.TRACK.value)

    class Meta:
        db_table = "price_snapshots"

    def point(self) -> dict:
        return {
            "id": self.id,
            "productId": self.product_id,
            "slotAt": self.slot_at.isoformat() if self.slot_at else None,
            "capturedAt": self.captured_at.isoformat() if self.captured_at else None,
            "price": self.price,
            "wasPrice": self.was_price,
            "discountPct": self.discount_pct,
            "currency": self.currency,
            "inStock": self.in_stock,
            "stockLabel": self.stock_label,
            "stockCount": self.stock_count,
            "trigger": self.trigger,
            "structureChanged": self.structure_changed,
        }


class TrackerHistory(models.Model):
    """A tracker's own view of the shared snapshots (its "records").

    Kept as links so that changing a tracker's refresh rate can delete the
    user's history without touching the shared snapshots other trackers rely on.
    """

    id = models.CharField(primary_key=True, max_length=36)
    tracker = models.ForeignKey(
        "app.Tracker", on_delete=models.CASCADE, related_name="history_links"
    )
    snapshot = models.ForeignKey(
        "app.PriceSnapshot", on_delete=models.CASCADE, related_name="history_links"
    )
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="history_links"
    )
    captured_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tracker_history"
        constraints = [
            models.UniqueConstraint(
                fields=["tracker", "snapshot"], name="uq_history_tracker_snapshot"
            )
        ]


class ScrapeLog(models.Model):
    """Every scrape attempt, honestly recorded: success, retried or failed."""

    id = models.CharField(primary_key=True, max_length=36)
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="scrape_logs"
    )
    tracker_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)

    attempt = models.IntegerField(default=1)
    outcome = models.CharField(max_length=16, db_index=True)
    error_kind = models.CharField(max_length=16, null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(default=0)

    price = models.FloatField(null=True, blank=True)
    in_stock = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "scrape_logs"

    def entry(self) -> dict:
        product = getattr(self, "product", None)
        return {
            "id": self.id,
            "productId": self.product_id,
            "productName": product.name if product is not None else None,
            "trackerId": self.tracker_id,
            "attempt": self.attempt,
            "outcome": self.outcome,
            "errorKind": self.error_kind,
            "message": self.message,
            "durationMs": self.duration_ms,
            "price": self.price,
            "inStock": self.in_stock,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
