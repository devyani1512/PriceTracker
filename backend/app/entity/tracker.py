from __future__ import annotations

from django.db import models


class Tracker(models.Model):
    """A user's decision to track a product at their own cadence."""

    id = models.CharField(primary_key=True, max_length=36)
    user = models.ForeignKey(
        "app.User", on_delete=models.CASCADE, related_name="trackers"
    )
    product = models.ForeignKey(
        "app.Product", on_delete=models.CASCADE, related_name="trackers"
    )

    refresh_minutes = models.IntegerField(default=120)
    active = models.BooleanField(default=True)

    alert_on_price_drop = models.BooleanField(default=True)
    price_drop_threshold_pct = models.FloatField(null=True, blank=True)
    alert_on_back_in_stock = models.BooleanField(default=True)

    # Last cron slot this tracker has been covered for. Lets the cron core
    # decide "already have data at this timestamp" without a per-tracker scan.
    last_covered_slot = models.DateTimeField(null=True, blank=True)
    last_scraped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "trackers"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="uq_tracker_user_product"
            )
        ]
