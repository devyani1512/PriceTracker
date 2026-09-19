"""CronCore — the scheduler that decides what to scrape and when.

A tick is now cheap and durable. It aligns every active tracker to the grid
based at 00:00 UTC using its own interval, reuses a shared snapshot captured
inside the current slot window when one exists, and otherwise writes **one**
``task`` per product (deduped by product + slot) into the durable queue. The
job runner's scheduled lane drains that queue at bounded concurrency.

That split is what makes the schedule as reliable as a manual refresh:

* the tick never blocks on a slow scrape, so overlapping ticks are harmless;
* every due product is recorded even if the instance sleeps mid-run;
* a failure is recorded and the slot is marked covered, so we wait for the next
  slot instead of hammering the storefront.

One scrape serves every tracker due for that product. Coverage is computed when
the scrape finishes (not when it was queued), so a task stays correct even if
trackers change between the tick and the run.
"""

from __future__ import annotations

import json
import logging
import threading

from app.core.jobs.runner import JobRunner
from app.core.track.core import TrackCore, TrackRequest
from app.entity.price import SnapshotTrigger
from app.entity.scheduler import JobType
from app.internal.postgresql.module import Database
from app.utils.idgen import IDGenerator
from app.utils.timeutil import align_to_interval, ensure_utc, utcnow

# Scheduled track tasks are the lowest priority in the queue.
TRACK_PRIORITY = 100


class CronCore:
    def __init__(
        self,
        logger: logging.Logger,
        cfg: dict,
        db: Database,
        track_core: TrackCore,
        id_gen: IDGenerator,
        jobs: JobRunner,
    ):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.track_core = track_core
        self.id_gen = id_gen
        self.jobs = jobs
        # Set by the service layer; called with (product_id, snapshot) for each
        # freshly captured snapshot so alerts can be evaluated.
        self.snapshot_hook = None
        self._lock = threading.Lock()

    def tick(
        self,
        force: bool = False,
        scrape: bool = True,
        budget_seconds: float | None = None,
        drain: bool = False,
    ) -> dict:
        """One cron pass.

        ``drain=False`` (default) enqueues due work and wakes the scheduled
        workers. ``drain=True`` also runs the queue inline, bounded by
        ``budget_seconds`` — used by the management command and the external cron
        endpoint so the instance stays awake while it works.
        """
        if not self._lock.acquire(blocking=False):
            self.logger.info("cron tick already running — skipping this trigger")
            return {"skipped": True, "reason": "already running"}
        try:
            summary = self._tick(force=force, scrape=scrape)
            if drain:
                summary["drain"] = self.jobs.drain(budget=budget_seconds)
            else:
                self.jobs.wake()
            return summary
        finally:
            self._lock.release()

    def _tick(self, force: bool, scrape: bool) -> dict:
        now = utcnow()

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
            "enqueued": 0,
            "skipped": 0,
        }

        for product_id, items in by_product.items():
            min_interval = min(t.refresh_minutes for t, _ in items)
            slot = align_to_interval(now, min_interval)
            # Reuse only a snapshot captured inside the current slot window — a
            # point from the previous window is stale and must be re-scraped.
            fresh = None if force else self.db.prices.latest_since(product_id, slot)
            if fresh is not None and fresh.price is not None:
                self._cover(items, fresh)
                summary["reused"] += 1
                continue

            if not scrape:
                summary["skipped"] += 1
                continue

            self.db.tasks.enqueue(
                JobType.TRACK,
                run_at=now,
                payload=json.dumps(
                    {"productId": product_id, "minInterval": min_interval}
                ),
                priority=TRACK_PRIORITY,
                product_id=product_id,
                slot_at=slot,
            )
            summary["enqueued"] += 1

        self.logger.info("cron tick: %s", summary)
        return summary

    # ------------------------------------------------------------------ execution
    @staticmethod
    def _product_id(task) -> int | None:
        try:
            payload = json.loads(task.payload or "{}")
        except (TypeError, ValueError):
            payload = {}
        return task.product_id or payload.get("productId")

    def run_track_task(self, task) -> None:
        """Handler for a single queued TRACK task (used outside the batch lane)."""
        product_id = self._product_id(task)
        if product_id is None:
            self.logger.warning("track task %s has no product", task.job_id)
            return

        trackers = self.db.trackers.list_active_for_product(product_id)
        if not trackers:
            return

        slot = ensure_utc(task.slot_at)
        result = self.track_core.scrape_sync(
            product_id,
            SnapshotTrigger.TRACK.value,
            trackers[0].id,  # attribute the log to a representative tracker
            slot_at=slot,
        )

        snapshot = None
        if result is not None and result.success and result.snapshot_id:
            snapshot = self.db.prices.get_snapshot(result.snapshot_id)

        self._cover_due(product_id, slot, snapshot)
        self._notify(product_id, snapshot)

    def run_track_tasks(self, tasks: list, deadline: float | None = None) -> dict:
        """Batch handler: scrape many products in one browser.

        Returns ``{job_id: None}`` for completed products; an exception value
        marks a failure. Products whose ``deadline`` passed stay out of the map
        so the runner releases them for the next drain.
        """
        outcomes: dict[int, Exception | None] = {}
        requests: list[TrackRequest] = []
        owner: dict[int, object] = {}

        for task in tasks:
            product_id = self._product_id(task)
            if product_id is None:
                outcomes[task.job_id] = None
                continue
            trackers = self.db.trackers.list_active_for_product(product_id)
            if not trackers:
                outcomes[task.job_id] = None
                continue
            request = TrackRequest(
                product_id=product_id,
                tracker_id=trackers[0].id,
                slot_at=ensure_utc(task.slot_at),
            )
            requests.append(request)
            owner[id(request)] = task

        if not requests:
            return outcomes

        try:
            results = self.track_core.scrape_many(requests, deadline=deadline)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("track batch failed")
            for request in requests:
                outcomes[owner[id(request)].job_id] = exc
            return outcomes

        for request, result in results:
            task = owner[id(request)]
            snapshot = None
            if result.success and result.snapshot_id:
                snapshot = self.db.prices.get_snapshot(result.snapshot_id)
            self._cover_due(request.product_id, request.slot_at, snapshot)
            self._notify(request.product_id, snapshot)
            outcomes[task.job_id] = None

        return outcomes

    def _notify(self, product_id: int, snapshot) -> None:
        if snapshot is not None and self.snapshot_hook is not None:
            try:
                self.snapshot_hook(product_id, snapshot)
            except Exception:
                self.logger.exception("snapshot hook failed for product %s", product_id)

    # ------------------------------------------------------------------ coverage
    def _cover_due(self, product_id: int, task_slot, snapshot) -> None:
        """Link a fresh snapshot to every tracker that still needs this slot.

        Coverage is recorded for the slot the task was queued for (projected onto
        each tracker's own grid), not "now": a task that runs a few minutes late
        must not mark a newer slot as covered and skip it.
        """
        captured_at = snapshot.captured_at if snapshot is not None else None
        base = task_slot or utcnow()
        for tracker in self.db.trackers.list_active_for_product(product_id):
            slot = align_to_interval(base, tracker.refresh_minutes)
            last = ensure_utc(tracker.last_covered_slot)
            if last is not None and last >= slot:
                continue
            if snapshot is not None:
                self.db.prices.link_history(tracker.id, snapshot, self.id_gen.new_id())
            self.db.trackers.mark_covered(tracker.id, slot, captured_at)

    def _cover(self, items: list[tuple], snapshot) -> None:
        """Link a reused snapshot to the trackers it was queued for."""
        captured_at = snapshot.captured_at if snapshot is not None else None
        for tracker, slot in items:
            if snapshot is not None:
                self.db.prices.link_history(tracker.id, snapshot, self.id_gen.new_id())
            self.db.trackers.mark_covered(tracker.id, slot, captured_at)
