"""Priority job lanes for the scraper.

Two lanes keep user-facing work fast without letting scheduled work pile up:

* **manual** — a small ``ThreadPoolExecutor``. A user pressing "Refresh" is
  submitted here and starts immediately; it never waits behind a cron batch.
* **scheduled** — worker threads that drain the durable ``tasks`` table a bounded
  number at a time (default 1). This is the low-priority lane and the reason a
  single instance can run for hours without ballooning memory.

Everything scheduled is persisted before it runs, so the process is free to be
killed / sleep at any moment: unclaimed and leased-but-unfinished tasks are
picked up on the next tick.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import timedelta

from django.db import close_old_connections

from app.internal.postgresql.module import Database
from app.utils.timeutil import ensure_utc, utcnow

MANUAL = "manual"
SCHEDULED = "scheduled"


class JobRunner:
    def __init__(self, logger: logging.Logger, cfg: dict, db: Database):
        core = cfg["Core"]
        self.logger = logger
        self.db = db

        self.manual_threads = max(1, int(core.get("manualTrackThreads", 1)))
        self.scheduled_threads = max(1, int(core.get("scheduledTrackThreads", 1)))
        self.poll_seconds = max(1.0, float(core.get("scheduledPollSeconds", 15)))
        self.lease_seconds = max(30, int(core.get("scheduledLeaseSeconds", 600)))
        self.batch_limit = max(1, int(core.get("cronBatchLimit", 50)))
        self.budget_seconds = max(1.0, float(core.get("cronBudgetSeconds", 240)))
        self.max_attempts = max(1, int(core.get("jobMaxAttempts", 2)))
        self.retry_backoff = max(1, int(core.get("jobRetryBackoffSeconds", 30)))
        self.max_task_age = max(0, int(core.get("maxTaskAgeSeconds", 7200)))

        self._manual = ThreadPoolExecutor(
            max_workers=self.manual_threads, thread_name_prefix="pt-manual"
        )
        self._handlers: dict[str, callable] = {}
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._started = False

    # ------------------------------------------------------------------ registry
    def register(self, category, handler) -> None:
        key = category.value if hasattr(category, "value") else str(category)
        self._handlers[key] = handler

    # ------------------------------------------------------------------ manual lane
    def submit_manual(self, fn) -> Future:
        """Run ``fn`` on the high-priority lane, bypassing the queue entirely."""
        return self._manual.submit(self._guard, fn)

    @staticmethod
    def _guard(fn):
        close_old_connections()
        return fn()

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self.scheduled_threads):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"pt-scheduled-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        self.logger.info(
            "JobRunner started (manual=%d, scheduled=%d)",
            self.manual_threads,
            self.scheduled_threads,
        )

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def shutdown(self) -> None:
        self.stop()
        self._manual.shutdown(wait=False, cancel_futures=True)

    def wake(self) -> None:
        self._wake.set()

    def pending_count(self) -> int:
        return self.db.tasks.pending_count()

    # ------------------------------------------------------------------ scheduled lane
    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            close_old_connections()
            try:
                summary = self.drain(
                    budget=self.budget_seconds, limit=self.batch_limit
                )
            except Exception:
                self.logger.exception("scheduled drain failed")
                summary = {"claimed": 0}
            if summary.get("claimed", 0) == 0:
                self._wake.wait(self.poll_seconds)
                self._wake.clear()

    def drain(self, budget: float | None = None, limit: int | None = None, now=None) -> dict:
        """Claim and run due tasks once. Safe to call from any thread/process."""
        now = now or utcnow()
        budget = self.budget_seconds if budget is None else float(budget)
        limit = self.batch_limit if limit is None else int(limit)
        deadline = time.monotonic() + max(0.0, budget)

        claimed = self.db.tasks.claim_due(now, limit, self.lease_seconds)
        summary = {
            "claimed": len(claimed),
            "done": 0,
            "failed": 0,
            "stale": 0,
            "missingHandler": 0,
            "budgetExceeded": False,
        }

        for task in claimed:
            if time.monotonic() >= deadline:
                self.db.tasks.release(task.job_id)
                summary["budgetExceeded"] = True
                continue
            if self._is_stale(task, now):
                self.db.tasks.complete(task.job_id)
                summary["stale"] += 1
                continue
            handler = self._handlers.get(task.category)
            if handler is None:
                self.logger.warning("no handler for task category %s", task.category)
                self.db.tasks.complete(task.job_id)
                summary["missingHandler"] += 1
                continue
            try:
                handler(task)
            except Exception:
                self.logger.exception(
                    "task %s (%s) failed", task.job_id, task.category
                )
                attempts = int(task.attempts or 0) + 1
                if attempts < self.max_attempts:
                    self.db.tasks.reschedule(
                        task.job_id,
                        utcnow() + timedelta(seconds=self.retry_backoff),
                        attempts,
                    )
                else:
                    self.db.tasks.complete(task.job_id)
                summary["failed"] += 1
            else:
                self.db.tasks.complete(task.job_id)
                summary["done"] += 1

        if summary["claimed"]:
            self.logger.info("scheduled drain: %s", summary)
        return summary

    def _is_stale(self, task, now) -> bool:
        """Drop slots that are so old a fresher one must already be due."""
        if self.max_task_age <= 0 or task.slot_at is None:
            return False
        slot = ensure_utc(task.slot_at)
        if slot is None:
            return False
        return (now - slot).total_seconds() > self.max_task_age
