"""DB-backed background scheduler (≈ core/scheduler/scheduler.go).

Peek the earliest Task, sleep until it is due (woken early when a new task is
pushed), then dispatch it. Keeping tasks in the DB means scheduled work survives
restarts. A separate optional SelfTicker drives the track cron locally when no
external cron is available.
"""

from __future__ import annotations

import logging
import threading

from django.db import close_old_connections

from app.entity.scheduler import JobType, Task
from app.internal.postgresql.module import Database
from app.utils.timeutil import ensure_utc, utcnow


class Scheduler(threading.Thread):
    def __init__(self, logger: logging.Logger, db: Database, core):
        super().__init__(daemon=True, name="scheduler")
        self.logger = logger
        self.db = db
        self.core = core
        self._wake = threading.Event()
        self._stop = threading.Event()
        self.handlers: dict[str, callable] = {}

    def new_task(self, task: Task, persist: bool = True) -> None:
        """Push a task and wake the loop (≈ Scheduler.NewTask)."""
        if persist:
            self.db.tasks.new(task)
        self._wake.set()

    def register(self, category: JobType | str, handler) -> None:
        key = category.value if isinstance(category, JobType) else str(category)
        self.handlers[key] = handler

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def run(self) -> None:
        self.logger.info("Scheduler started")
        while not self._stop.is_set():
            close_old_connections()
            task = self.db.tasks.peek_recent()
            if task is None:
                self._wake.wait(timeout=60.0)
                self._wake.clear()
                continue

            delay = (ensure_utc(task.run_at) - utcnow()).total_seconds()
            if delay > 0:
                self._wake.wait(timeout=min(delay, 60.0))
                self._wake.clear()
                continue

            self.db.tasks.delete(task.job_id)
            self._dispatch(task)
        self.logger.info("Scheduler stopped")

    def _dispatch(self, task: Task) -> None:
        handler = self.handlers.get(task.category)
        if handler is None:
            self.logger.warning("no handler for task category %s", task.category)
            return
        try:
            handler(task)
        except Exception:
            self.logger.exception("task %s (%s) failed", task.job_id, task.category)


class SelfTicker(threading.Thread):
    """Local-dev substitute for an external cron service."""

    def __init__(self, logger: logging.Logger, cfg: dict, cron) -> None:
        super().__init__(daemon=True, name="self-ticker")
        self.logger = logger
        self.cfg = cfg
        self.cron = cron
        self._stop = threading.Event()
        self.interval = max(30, int(cfg["Core"]["tickSeconds"]))

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self.logger.info("SelfTicker started (every %ds)", self.interval)
        while not self._stop.is_set():
            close_old_connections()
            try:
                self.cron.tick()
            except Exception:
                self.logger.exception("self-tick failed")
            self._stop.wait(self.interval)
        self.logger.info("SelfTicker stopped")
