"""CronCore — the scheduler that decides what to scrape and when.

This is the "run job for all, but look up the shared DB first" core. It aligns
every tracker to a grid based at 00:00 UTC using its own refresh interval, then
for each due product either reuses a snapshot already captured inside the
current slot window (another tracker paid for it) or triggers TrackCore once.
One scrape serves every tracker due for that product.
"""

from __future__ import annotations

import logging
import threading
import time

from app.core.track.core import TrackCore
from app.entity.price import SnapshotTrigger
from app.internal.postgresql.module import Database
from app.utils.idgen import IDGenerator
from app.utils.timeutil import align_to_interval, ensure_utc, utcnow


class CronCore:
    def __init__(
        self,
        logger: logging.Logger,
        cfg: dict,
        db: Database,
        track_core: TrackCore,
        id_gen: IDGenerator,
    ):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.track_core = track_core
        self.id_gen = id_gen
        # Set by the service layer; called with (product_id, snapshot) for each
        # freshly captured snapshot so alerts can be evaluated.
        self.snapshot_hook = None
        self._lock = threading.Lock()

    def tick(
        self,
        force: bool = False,
        scrape: bool = True,
        budget_seconds: float | None = None,
    ) -> dict:
        """One cron pass. Idempotent and safe to call from an external cron.

        A second concurrent call (e.g. an overlapping scheduler trigger) is
        skipped rather than queued, so a slow pass never stacks up.
        """
        if not self._lock.acquire(blocking=False):
            self.logger.info("cron tick already running — skipping this trigger")
            return {"skipped": True, "reason": "already running"}
        try:
            return self._tick(force=force, scrape=scrape, budget_seconds=budget_seconds)
        finally:
            self._lock.release()

    def _tick(self, force: bool, scrape: bool, budget_seconds: float | None) -> dict:
        now = utcnow()
        batch_limit = int(self.cfg["Core"]["cronBatchLimit"])
        budget = float(budget_seconds or self.cfg["Core"].get("cronBudgetSeconds", 240))
        deadline = time.monotonic() + budget

        trackers = self.db.trackers.list_active()
        due: list[tuple] = []
        for tracker in trackers:
            slot = align_to_interval(now, tracker.refresh_minutes)
            last = ensure_utc(tracker.last_covered_slot)
            if force or last is None or last < slot:
                due.append((tracker, slot))

        by_product: dict[int, list[tuple]] = {}
        for tracker, slot in due:
            by_product.setdefault(tracker.product_id, []).append((tracker, slot))

        summary = {
            "at": now.isoformat(),
            "activeTrackers": len(trackers),
            "dueTrackers": len(due),
            "products": len(by_product),
            "reused": 0,
            "scraped": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "budgetExceeded": False,
        }

        pending: list[tuple[int, list[tuple], object]] = []
        processed = 0

        for product_id, items in by_product.items():
            min_interval = min(t.refresh_minutes for t, _ in items)
            slot = align_to_interval(now, min_interval)
            # Reuse only if a snapshot was captured inside the current slot
            # window — a point from the previous window is stale and must be
            # re-scraped.
            fresh = None if force else self.db.prices.latest_since(product_id, slot)
            if fresh is not None and fresh.price is not None:
                self._cover(items, fresh)
                summary["reused"] += 1
                continue

            if not scrape:
                summary["skipped"] += 1
                continue

            if processed >= batch_limit or time.monotonic() >= deadline:
                summary["skipped"] += 1
                continue

            future = self.track_core.submit(
                product_id,
                SnapshotTrigger.TRACK.value,
                items[0][0].id,  # attribute logs to a representative tracker
                slot,
            )
            pending.append((product_id, items, future))
            processed += 1

        for product_id, items, future in pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                summary["skipped"] += 1
                summary["budgetExceeded"] = True
                # Mark covered so the same slot isn't retried forever; next
                # tick will pick up the following slot.
                self._cover(items, None)
                continue
            try:
                result = future.result(timeout=remaining)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("track future crashed: %s", exc)
                result = None

            summary["scraped"] += 1
            if result is not None and result.success and result.snapshot_id:
                snapshot = self.db.prices.get_snapshot(result.snapshot_id)
                self._cover(items, snapshot)
                summary["succeeded"] += 1
                if snapshot is not None and self.snapshot_hook is not None:
                    try:
                        self.snapshot_hook(product_id, snapshot)
                    except Exception:
                        self.logger.exception("snapshot hook failed for product %s", product_id)
            else:
                summary["failed"] += 1
                # Honest failure: log it, and wait for the next slot rather than
                # hammering the store on every tick.
                self._cover(items, None)

        self.logger.info("cron tick: %s", summary)
        return summary

    def _cover(self, items: list[tuple], snapshot) -> None:
        """Link the snapshot to each due tracker and mark the slot covered."""
        for tracker, slot in items:
            if snapshot is not None:
                self.db.prices.link_history(
                    tracker.id, snapshot, self.id_gen.new_id()
                )
            self.db.trackers.mark_covered(
                tracker.id, slot, snapshot.captured_at if snapshot is not None else None
            )
