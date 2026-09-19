from __future__ import annotations

from enum import StrEnum

from django.db import models


class JobType(StrEnum):
    NOTIFICATION = "notification"   # send a queued alert email
    TRACK = "track"                 # scrape one product (scheduled)
    CATALOG_SYNC = "catalog_sync"   # refresh the storefront catalog cache


class Task(models.Model):
    """Durable task queue so scheduled work survives restarts and sleep.

    Scheduled scrapes are written here by the cron tick and claimed by the job
    runner. This mirrors the "cron opens the app, looks up what is due, runs it
    and saves what to run next" model: the process can go away at any point and
    the queue is the source of truth.
    """

    job_id = models.BigAutoField(primary_key=True)
    category = models.CharField(max_length=24, db_index=True)
    run_at = models.DateTimeField(db_index=True)
    payload = models.TextField(default="{}")

    # Lower priority runs first. Scheduled work is low priority; manual scrapes
    # never enter this table (they run on the high-priority lane immediately).
    priority = models.IntegerField(default=100, db_index=True)

    # Product/slot make scheduled tasks idempotent: one scrape per product per
    # slot, no matter how many ticks fire or how many users track it.
    product_id = models.IntegerField(null=True, blank=True, db_index=True)
    slot_at = models.DateTimeField(null=True, blank=True, db_index=True)

    attempts = models.IntegerField(default=0)
    # Claim lease. A worker sets this when it picks the task up; a stale lease
    # (worker died / instance slept) is reclaimed by the next worker.
    locked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks"
        indexes = [
            models.Index(
                fields=["category", "product_id", "slot_at"],
                name="ix_tasks_category_product_slot",
            ),
        ]
