"""Time helpers. All timestamps are stored in UTC; alignment drives the cron grid."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def align_to_interval(dt: datetime, minutes: int, base_hour: int = 0) -> datetime:
    """Snap ``dt`` down to the cron grid that starts at ``base_hour``:00 UTC.

    A 120-minute tracker set at 22:20 therefore lands on the 22:00 slot, and a
    10-minute tracker lands on the previous 10-minute boundary. This is the
    "take 00:00 as the base and add the increment" rule from the spec.
    """
    minutes = max(1, int(minutes))
    d = ensure_utc(dt) or utcnow()
    midnight = d.replace(hour=base_hour, minute=0, second=0, microsecond=0)
    delta_minutes = (d - midnight).total_seconds() / 60.0
    slot = int(delta_minutes // minutes) * minutes
    return midnight + timedelta(minutes=slot)
