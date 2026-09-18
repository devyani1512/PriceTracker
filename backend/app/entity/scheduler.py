from __future__ import annotations

from enum import StrEnum

from django.db import models


class JobType(StrEnum):
    NOTIFICATION = "notification"   # send a queued alert email
    TRACK = "track"                 # scrape one product (internal use)
    CATALOG_SYNC = "catalog_sync"   # refresh the storefront catalog cache


class Task(models.Model):
    """DB-backed task queue so scheduled work survives restarts (≈ Go core Task)."""

    job_id = models.BigAutoField(primary_key=True)
    category = models.CharField(max_length=24, db_index=True)
    run_at = models.DateTimeField(db_index=True)
    payload = models.TextField(default="{}")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tasks"
