"""History folding tests — cadence changes must never lose earlier points."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.history import project_history


def _snap(slot: datetime, captured: datetime, price: float, sid: str = "s"):
    return SimpleNamespace(
        id=sid,
        slot_at=slot,
        captured_at=captured,
        point=lambda: {
            "id": sid,
            "slotAt": slot.isoformat(),
            "capturedAt": captured.isoformat(),
            "price": price,
        },
    )


def test_coarse_cadence_groups_finer_points_keeping_latest_value():
    points = [
        _snap(datetime(2026, 9, 19, 10, 0, tzinfo=UTC), datetime(2026, 9, 19, 10, 0, tzinfo=UTC), 100.0, "a"),
        _snap(datetime(2026, 9, 19, 10, 30, tzinfo=UTC), datetime(2026, 9, 19, 10, 31, tzinfo=UTC), 90.0, "b"),
        _snap(datetime(2026, 9, 19, 11, 0, tzinfo=UTC), datetime(2026, 9, 19, 11, 0, tzinfo=UTC), 95.0, "c"),
    ]

    folded = project_history(points, refresh_minutes=60)

    assert [p["price"] for p in folded] == [90.0, 95.0]
    assert [p["slotAt"] for p in folded] == [
        "2026-09-19T10:00:00+00:00",
        "2026-09-19T11:00:00+00:00",
    ]


def test_finer_cadence_reveals_every_point():
    points = [
        _snap(datetime(2026, 9, 19, 10, 0, tzinfo=UTC), datetime(2026, 9, 19, 10, 0, tzinfo=UTC), 100.0, "a"),
        _snap(datetime(2026, 9, 19, 10, 30, tzinfo=UTC), datetime(2026, 9, 19, 10, 31, tzinfo=UTC), 90.0, "b"),
        _snap(datetime(2026, 9, 19, 11, 0, tzinfo=UTC), datetime(2026, 9, 19, 11, 0, tzinfo=UTC), 95.0, "c"),
    ]

    folded = project_history(points, refresh_minutes=30)

    assert [p["price"] for p in folded] == [100.0, 90.0, 95.0]


def test_value_captured_late_is_labelled_with_its_slot():
    captured_late = _snap(
        datetime(2026, 9, 19, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 19, 10, 5, tzinfo=UTC),
        42.0,
    )

    folded = project_history([captured_late], refresh_minutes=10)

    assert folded[0]["slotAt"] == "2026-09-19T10:00:00+00:00"


def test_max_points_keeps_the_most_recent():
    points = [
        _snap(
            datetime(2026, 9, 19, 10, minute, tzinfo=UTC),
            datetime(2026, 9, 19, 10, minute, tzinfo=UTC),
            float(minute),
            f"s{minute}",
        )
        for minute in (0, 10, 20, 30)
    ]

    folded = project_history(points, refresh_minutes=10, max_points=2)

    assert [p["price"] for p in folded] == [20.0, 30.0]
