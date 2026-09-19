from __future__ import annotations

from app.entity.price import PriceSnapshot, ScrapeLog, TrackerHistory


class PriceRepo:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------ snapshots
    def add_snapshot(self, snapshot: PriceSnapshot) -> PriceSnapshot:
        snapshot.save()
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> PriceSnapshot | None:
        return PriceSnapshot.objects.filter(pk=snapshot_id).first()

    def exists_for_slot(self, product_id: int, slot) -> PriceSnapshot | None:
        return (
            PriceSnapshot.objects.filter(
                product_id=product_id, slot_at=slot, price__isnull=False
            )
            .order_by("-captured_at")
            .first()
        )

    def latest_since(self, product_id: int, since) -> PriceSnapshot | None:
        """A successful snapshot captured at/after ``since`` — reusable by cron."""
        return (
            PriceSnapshot.objects.filter(
                product_id=product_id, captured_at__gte=since, price__isnull=False
            )
            .order_by("-captured_at")
            .first()
        )

    def latest_for_product(self, product_id: int) -> PriceSnapshot | None:
        return (
            PriceSnapshot.objects.filter(product_id=product_id, price__isnull=False)
            .order_by("-captured_at")
            .first()
        )

    def previous_for_product(self, product_id: int, before) -> PriceSnapshot | None:
        return (
            PriceSnapshot.objects.filter(
                product_id=product_id, captured_at__lt=before, price__isnull=False
            )
            .order_by("-captured_at")
            .first()
        )

    def count_for_product(self, product_id: int) -> int:
        return PriceSnapshot.objects.filter(product_id=product_id).count()

    def latest_per_product(self) -> dict[int, PriceSnapshot]:
        """Newest successful snapshot for each product (dashboards)."""
        rows = PriceSnapshot.objects.filter(price__isnull=False).order_by(
            "product_id", "-captured_at"
        )
        latest: dict[int, PriceSnapshot] = {}
        for row in rows:
            latest.setdefault(row.product_id, row)
        return latest

    # ------------------------------------------------------------------ history links
    def link_history(self, tracker_id: str, snapshot: PriceSnapshot, entry_id: str) -> bool:
        """Link a snapshot to a tracker unless it is already linked."""
        _, created = TrackerHistory.objects.get_or_create(
            tracker_id=tracker_id,
            snapshot_id=snapshot.id,
            defaults={
                "id": entry_id,
                "product_id": snapshot.product_id,
                "captured_at": snapshot.captured_at,
            },
        )
        return created

    def history_for_tracker(self, tracker_id: str, since=None, limit: int = 2000):
        queryset = PriceSnapshot.objects.filter(history_links__tracker_id=tracker_id)
        if since is not None:
            queryset = queryset.filter(captured_at__gte=since)
        return list(queryset.order_by("captured_at")[:limit])

    def history_for_product(self, product_id: int, since=None, limit: int = 2000):
        """Most recent ``limit`` shared snapshots, returned oldest-first.

        Newest-first selection matters now that a tracker charts the product's
        full shared history: we would rather keep the latest window than the
        oldest when a long range exceeds the cap.
        """
        queryset = PriceSnapshot.objects.filter(product_id=product_id)
        if since is not None:
            queryset = queryset.filter(captured_at__gte=since)
        rows = list(queryset.order_by("-captured_at")[:limit])
        rows.reverse()
        return rows

    def delete_history_for_tracker(self, tracker_id: str) -> int:
        deleted, _ = TrackerHistory.objects.filter(tracker_id=tracker_id).delete()
        return int(deleted or 0)

    # ------------------------------------------------------------------ scrape log
    def add_log(self, log: ScrapeLog) -> None:
        log.save()

    def logs_for_product(
        self, product_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[list[ScrapeLog], int]:
        queryset = ScrapeLog.objects.filter(product_id=product_id).order_by("-created_at")
        return list(queryset[offset : offset + limit]), queryset.count()

    def logs_for_tracker(
        self, tracker_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[ScrapeLog], int]:
        queryset = ScrapeLog.objects.filter(tracker_id=tracker_id).order_by("-created_at")
        return list(queryset[offset : offset + limit]), queryset.count()

    def recent_logs(self, limit: int = 50) -> list[ScrapeLog]:
        return list(ScrapeLog.objects.order_by("-created_at")[:limit])
