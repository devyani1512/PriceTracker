"""Shared history projection.

A tracker's chart should never hide data just because its cadence changed, and a
brand-new tracker should immediately see whatever the product already has. So we
start from the product's shared snapshots and fold them onto the tracker's
cadence grid: every snapshot belongs to exactly one grid slot, and when several
land in the same slot the most recently captured value wins ("the best value
available at that time"). A coarser grid groups more points; a finer grid exposes
the detail that already exists.
"""

from __future__ import annotations

from datetime import datetime

from app.utils.timeutil import align_to_interval, ensure_utc


def project_history(snapshots, refresh_minutes: int, max_points: int = 0) -> list[dict]:
    """Fold ``snapshots`` onto the ``refresh_minutes`` grid, newest value wins."""
    refresh = max(1, int(refresh_minutes))
    buckets: dict[datetime, object] = {}

    for snapshot in snapshots:
        base = ensure_utc(snapshot.slot_at or snapshot.captured_at)
        if base is None:
            continue
        slot = align_to_interval(base, refresh)
        current = buckets.get(slot)
        if current is None:
            buckets[slot] = snapshot
            continue
        if ensure_utc(snapshot.captured_at) >= ensure_utc(current.captured_at):
            buckets[slot] = snapshot

    ordered = sorted(buckets.items(), key=lambda item: item[0])
    if max_points and len(ordered) > max_points:
        ordered = ordered[-max_points:]

    points: list[dict] = []
    for slot, snapshot in ordered:
        point = snapshot.point()
        # Display on the canonical slot, so a 10:00 value captured at 10:05 is
        # still shown at 10:00.
        point["slotAt"] = slot.isoformat()
        point["bucketAt"] = slot.isoformat()
        points.append(point)
    return points
