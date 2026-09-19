from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import Q

from app.entity.scheduler import Task


class TaskRepo:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ enqueue
    def enqueue(
        self,
        category,
        run_at,
        payload: str = "{}",
        priority: int = 100,
        product_id: int | None = None,
        slot_at=None,
    ) -> Task:
        """Add a task unless an identical product/slot task is already queued.

        Dedupe ignores the lock so an in-flight scrape does not get queued twice
        by a later tick.
        """
        key = category.value if hasattr(category, "value") else str(category)
        if product_id is not None and slot_at is not None:
            existing = (
                Task.objects.filter(
                    category=key, product_id=product_id, slot_at=slot_at
                )
                .order_by("job_id")
                .first()
            )
            if existing is not None:
                return existing
        return Task.objects.create(
            category=key,
            run_at=run_at,
            payload=payload,
            priority=priority,
            product_id=product_id,
            slot_at=slot_at,
        )

    def new(self, task: Task) -> None:
        task.save()

    def add(self, task: Task) -> Task:
        task.save()
        return task

    # ------------------------------------------------------------------ claim
    def claim_due(self, now, limit: int = 50, lease_seconds: int = 600) -> list[Task]:
        """Atomically claim up to ``limit`` runnable tasks, oldest/highest first.

        ``skip_locked`` lets several workers drain the queue concurrently without
        ever handing the same task to two of them. A task whose lock is older
        than the lease is reclaimed (the previous worker died or the instance
        went to sleep mid-run).
        """
        stale_before = now - timedelta(seconds=max(1, int(lease_seconds)))
        with transaction.atomic():
            queryset = (
                Task.objects.select_for_update(skip_locked=True)
                .filter(run_at__lte=now)
                .filter(Q(locked_at__isnull=True) | Q(locked_at__lt=stale_before))
                .order_by("priority", "run_at")[:limit]
            )
            tasks = list(queryset)
            if tasks:
                ids = [task.job_id for task in tasks]
                Task.objects.filter(job_id__in=ids).update(locked_at=now)
                for task in tasks:
                    task.locked_at = now
            return tasks

    def complete(self, job_id: int) -> None:
        Task.objects.filter(pk=job_id).delete()

    def reschedule(self, job_id: int, run_at, attempts: int) -> None:
        Task.objects.filter(pk=job_id).update(
            run_at=run_at, attempts=attempts, locked_at=None
        )

    def release(self, job_id: int) -> None:
        Task.objects.filter(pk=job_id).update(locked_at=None)

    # ------------------------------------------------------------------ queries
    def peek_recent(self) -> Task | None:
        return Task.objects.order_by("run_at").first()

    def list_all(self, limit: int = 100) -> list[Task]:
        return list(Task.objects.order_by("priority", "run_at")[:limit])

    def delete(self, job_id: int) -> None:
        Task.objects.filter(pk=job_id).delete()

    def pending_count(self) -> int:
        return Task.objects.count()

    def due_count(self, now) -> int:
        return Task.objects.filter(run_at__lte=now).count()
