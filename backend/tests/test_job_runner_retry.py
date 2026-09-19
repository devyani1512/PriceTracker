"""Job runner retry policy: 0 attempts means keep retrying until it passes."""

from __future__ import annotations

import os
from types import SimpleNamespace

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.core.jobs.runner import JobRunner  # noqa: E402


class _FakeTasks:
    def __init__(self) -> None:
        self.rescheduled: list = []
        self.completed: list = []

    def reschedule(self, job_id, run_at, attempts) -> None:
        self.rescheduled.append((job_id, run_at, attempts))

    def complete(self, job_id) -> None:
        self.completed.append(job_id)


def _runner(max_attempts: int) -> JobRunner:
    runner = JobRunner.__new__(JobRunner)
    runner.max_attempts = max_attempts
    runner.retry_backoff = 30
    runner.retry_max_backoff = 600
    runner.db = SimpleNamespace(tasks=_FakeTasks())
    return runner


def test_zero_attempts_means_retry_forever():
    runner = _runner(0)
    summary = {"failed": 0}

    for _ in range(50):
        runner._schedule_retry(SimpleNamespace(attempts=0, job_id=1), summary)

    assert len(runner.db.tasks.rescheduled) == 50
    assert runner.db.tasks.completed == []
    assert summary["failed"] == 50


def test_positive_cap_stops_after_max_attempts():
    runner = _runner(2)
    summary = {"failed": 0}

    runner._schedule_retry(SimpleNamespace(attempts=0, job_id=1), summary)  # -> retry
    runner._schedule_retry(SimpleNamespace(attempts=1, job_id=1), summary)  # -> drop

    assert len(runner.db.tasks.rescheduled) == 1
    assert runner.db.tasks.completed == [1]


def test_backoff_is_exponential_and_capped():
    runner = _runner(0)

    assert runner._retry_delay(1) == 30
    assert runner._retry_delay(2) == 60
    assert runner._retry_delay(3) == 120
    assert runner._retry_delay(10) == 600  # capped
