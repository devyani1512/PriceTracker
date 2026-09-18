from __future__ import annotations

from django.db import transaction

from app.entity.scheduler import Task


class TaskRepo:
    def __init__(self, db):
        self.db = db

    def new(self, task: Task) -> None:
        task.save()

    def add(self, task: Task) -> Task:
        task.save()
        return task

    def peek_recent(self) -> Task | None:
        return Task.objects.order_by("run_at").first()

    def pop_recent(self) -> Task | None:
        """Atomically pop the earliest task (≈ Go PopRecentTask)."""
        with transaction.atomic():
            task = (
                Task.objects.select_for_update(skip_locked=True).order_by("run_at").first()
            )
            if task is not None:
                task.delete()
            return task

    def list_all(self, limit: int = 100) -> list[Task]:
        return list(Task.objects.order_by("run_at")[:limit])

    def delete(self, job_id: int) -> None:
        Task.objects.filter(pk=job_id).delete()
