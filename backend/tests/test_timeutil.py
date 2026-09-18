"""Cron grid alignment tests — the heart of the "00:00 + increment" rule."""

from __future__ import annotations

from datetime import UTC, datetime

from app.utils.timeutil import align_to_interval


def test_aligns_to_two_hour_grid():
    dt = datetime(2026, 9, 19, 22, 20, tzinfo=UTC)
    assert align_to_interval(dt, 120) == datetime(2026, 9, 19, 22, 0, tzinfo=UTC)


def test_aligns_to_ten_minute_grid():
    dt = datetime(2026, 9, 19, 22, 23, tzinfo=UTC)
    assert align_to_interval(dt, 10) == datetime(2026, 9, 19, 22, 20, tzinfo=UTC)


def test_alignment_is_stable_at_boundary():
    dt = datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
    assert align_to_interval(dt, 120) == datetime(2026, 9, 19, 22, 0, tzinfo=UTC)


def test_slot_before_midnight():
    dt = datetime(2026, 9, 19, 0, 5, tzinfo=UTC)
    assert align_to_interval(dt, 30) == datetime(2026, 9, 19, 0, 0, tzinfo=UTC)
