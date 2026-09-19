"""A failed scrape must keep being retried, never consume the slot."""

from __future__ import annotations

import os
from types import SimpleNamespace

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.core.cron.core import CronCore  # noqa: E402


class _FakePrices:
    def get_snapshot(self, snapshot_id):
        return SimpleNamespace(id=snapshot_id, captured_at=None)


def _cron() -> CronCore:
    cron = CronCore.__new__(CronCore)  # bypass the heavy __init__
    cron.cfg = {"Core": {}}
    cron.db = SimpleNamespace(prices=_FakePrices())
    cron.covered: list = []
    cron.notified: list = []
    cron._cover_due = lambda pid, slot, snap: cron.covered.append((pid, slot, snap))
    # Mirror the real _notify, which is a no-op when there is no snapshot.
    cron._notify = lambda pid, snap: (
        cron.notified.append((pid, snap)) if snap is not None else None
    )
    return cron


def _ok() -> SimpleNamespace:
    return SimpleNamespace(success=True, snapshot_id="snap", error=None)


def _fail() -> SimpleNamespace:
    return SimpleNamespace(success=False, snapshot_id=None, error="Timeout")


def test_failure_requests_retry_and_never_covers_the_slot():
    cron = _cron()
    task = SimpleNamespace(attempts=0, job_id=1)

    outcome = cron._finish_track(task, product_id=7, slot="slot", result=_fail())

    assert isinstance(outcome, RuntimeError)
    assert cron.covered == []  # slot stays open for the next attempt


def test_repeated_failures_keep_retrying():
    cron = _cron()
    task = SimpleNamespace(attempts=99, job_id=1)  # many attempts already

    outcome = cron._finish_track(task, product_id=7, slot="slot", result=_fail())

    assert isinstance(outcome, RuntimeError)
    assert cron.covered == []


def test_success_covers_and_notifies():
    cron = _cron()
    task = SimpleNamespace(attempts=0, job_id=1)

    outcome = cron._finish_track(task, product_id=7, slot="slot", result=_ok())

    assert outcome is None
    assert len(cron.covered) == 1
    assert len(cron.notified) == 1
