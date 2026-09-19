"""TrackCore — wrapper around the Playwright scraper.

Concurrency lives in the :class:`~app.core.jobs.runner.JobRunner`: user actions
run on the high-priority manual lane, scheduled work on the bounded scheduled
lane. TrackCore itself only persists a run: one price snapshot on success, one
scrape-log row per attempt, and the change-detection flag when the page
structure no longer parses.

Browser reuse: when ``Core.scrapeBrowserReuse`` is on, each worker thread keeps a
long-lived :class:`BrowserSession` so consecutive scrapes on that thread don't
pay Chromium startup. The scheduled lane has one worker, so it reuses a single
browser across all of its products. Sessions are recycled after N scrapes and
rebuilt if a crash leaves them unusable.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from datetime import datetime
from functools import partial

from django.db import close_old_connections

from app.core.jobs.runner import JobRunner
from app.core.track.models import ScrapeResult
from app.core.track.scraper import BrowserSession, run_browser_session
from app.entity.price import (
    PriceSnapshot,
    ScrapeErrorKind,
    ScrapeLog,
    ScrapeOutcome,
    SnapshotTrigger,
)
from app.utils.idgen import IDGenerator
from app.utils.timeutil import align_to_interval, utcnow


class _ThreadSession:
    """A persistent event loop + browser owned by one worker thread."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.session: BrowserSession | None = None
        self.headless: bool | None = None


class TrackCore:
    def __init__(
        self,
        logger: logging.Logger,
        cfg: dict,
        db,
        id_gen: IDGenerator,
        runner: JobRunner,
    ):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.id_gen = id_gen
        self.runner = runner
        self.reuse_browser = bool(cfg["Core"].get("scrapeBrowserReuse", True))
        self._session_lock = threading.Lock()
        self._thread_sessions: dict[int, _ThreadSession] = {}
        self._all_sessions: list[_ThreadSession] = []
        self.logger.info(
            "TrackCore ready (jobs=%s, reuseBrowser=%s)",
            type(runner).__name__,
            self.reuse_browser,
        )

    # ------------------------------------------------------------------ helpers
    def product_url(self, product_id: int) -> str:
        base = str(self.cfg["Core"]["storefrontBase"]).rstrip("/")
        return f"{base}/product/{product_id}"

    # ------------------------------------------------------------------ public API
    def submit(
        self,
        product_id: int,
        trigger: str = SnapshotTrigger.TRACK.value,
        tracker_id: str | None = None,
        slot_at: datetime | None = None,
        headless: bool | None = None,
    ) -> Future:
        """Queue a scrape on the high-priority (manual) lane.

        Used by user actions: refresh, tracking a product, first-load price.
        Scheduled scrapes never call this — they run on the bounded scheduled
        lane so they cannot starve user requests.
        """
        slot = slot_at or align_to_interval(utcnow(), 1)
        return self.runner.submit_manual(
            partial(self._blocking_run, product_id, trigger, tracker_id, slot, headless)
        )

    def scrape_sync(
        self,
        product_id: int,
        trigger: str = SnapshotTrigger.TRACK.value,
        tracker_id: str | None = None,
        slot_at: datetime | None = None,
        headless: bool | None = None,
        timeout: float | None = None,
    ) -> ScrapeResult:
        """Run a scrape in the calling thread (scheduled workers, CLI, wait=true).

        Running inline keeps the scheduled lane at the configured concurrency and
        avoids a worker waiting on a pool that is itself the scheduled lane.
        """
        slot = slot_at or align_to_interval(utcnow(), 1)
        run = partial(
            self._blocking_run, product_id, trigger, tracker_id, slot, headless
        )
        if timeout is None:
            return run()
        return self.runner.submit_manual(run).result(timeout=timeout)

    def probe(self, product_id: int, headless: bool | None = None) -> ScrapeResult:
        """Scrape without persisting anything — for benchmarks/diagnostics."""
        use_headless = self.cfg["Core"]["headless"] if headless is None else headless
        url = self.product_url(product_id)
        if self.reuse_browser:
            return self._run_reused(product_id, url, use_headless)
        return asyncio.run(
            run_browser_session(product_id, url, self.cfg, self.logger, use_headless)
        )

    # ------------------------------------------------------------------ internals
    def _blocking_run(
        self,
        product_id: int,
        trigger: str,
        tracker_id: str | None,
        slot_at: datetime,
        headless: bool | None,
    ) -> ScrapeResult:
        # Worker threads are long-lived; refresh any stale Django connection.
        close_old_connections()
        use_headless = self.cfg["Core"]["headless"] if headless is None else headless
        url = self.product_url(product_id)
        self.logger.info(
            "scraping product %s (trigger=%s, headless=%s, reuse=%s)",
            product_id,
            trigger,
            use_headless,
            self.reuse_browser,
        )

        if self.reuse_browser:
            result = self._run_reused(product_id, url, use_headless)
        else:
            result = asyncio.run(
                run_browser_session(product_id, url, self.cfg, self.logger, use_headless)
            )

        self._persist_result(product_id, trigger, tracker_id, slot_at, result)
        return result

    # ------------------------------------------------------------------ browser reuse
    def _get_thread_session(self, headless: bool) -> _ThreadSession:
        thread_id = threading.get_ident()
        with self._session_lock:
            session = self._thread_sessions.get(thread_id)
            if session is None:
                session = _ThreadSession()
                self._thread_sessions[thread_id] = session
                self._all_sessions.append(session)
        if session.session is None or session.headless != headless:
            self._rebuild_session(session, headless)
        return session

    def _rebuild_session(self, session: _ThreadSession, headless: bool) -> None:
        if session.session is not None:
            try:
                session.loop.run_until_complete(session.session.close())
            except Exception:
                self.logger.exception("closing reused browser session failed")
        session.session = BrowserSession(self.cfg, self.logger, headless)
        session.headless = headless
        session.loop.run_until_complete(session.session.start())

    def _run_reused(self, product_id: int, url: str, headless: bool) -> ScrapeResult:
        session = self._get_thread_session(headless)
        assert session.session is not None
        try:
            return session.loop.run_until_complete(
                session.session.scrape(product_id, url)
            )
        except Exception:
            # A crashed page/browser can poison the session; rebuild once.
            self.logger.exception(
                "reused browser scrape failed for product %s; rebuilding", product_id
            )
            self._rebuild_session(session, headless)
            return session.loop.run_until_complete(
                session.session.scrape(product_id, url)
            )

    def close_thread_session(self) -> None:
        """Drop the calling thread's session (used between benchmark modes)."""
        thread_id = threading.get_ident()
        with self._session_lock:
            session = self._thread_sessions.pop(thread_id, None)
            if session in self._all_sessions:
                self._all_sessions.remove(session)
        if session is None or session.session is None:
            return
        if not session.loop.is_running():
            try:
                session.loop.run_until_complete(session.session.close())
            except Exception:
                pass
            try:
                session.loop.close()
            except Exception:
                pass

    def shutdown(self) -> None:
        with self._session_lock:
            sessions = list(self._all_sessions)
            self._thread_sessions.clear()
            self._all_sessions.clear()
        for session in sessions:
            if session.session is None or session.loop.is_running():
                # Owned by a worker still mid-scrape; process teardown handles it.
                continue
            try:
                session.loop.run_until_complete(session.session.close())
            except Exception:
                pass
            try:
                session.loop.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ persistence
    def _persist_result(
        self,
        product_id: int,
        trigger: str,
        tracker_id: str | None,
        slot_at: datetime,
        result: ScrapeResult,
    ) -> None:
        now = utcnow()
        if result.success:
            snapshot = self._persist_snapshot(product_id, slot_at, now, trigger, result)
            result.snapshot_id = snapshot.id
            if tracker_id:
                # Attribute the point to the tracker that requested this run
                # (cron runs link every due tracker itself in CronCore._cover).
                self.db.prices.link_history(tracker_id, snapshot, self.id_gen.new_id())
            if result.structure_changed and result.structure_note:
                self.db.products.flag_structure_change(
                    product_id, result.structure_note, now
                )
            else:
                self.db.products.clear_structure_flag(product_id)
        elif result.structure_changed:
            self.db.products.flag_structure_change(
                product_id,
                result.structure_note or "page structure changed",
                now,
            )

        self._persist_logs(product_id, tracker_id, result)

    def _persist_snapshot(
        self,
        product_id: int,
        slot_at: datetime,
        captured_at: datetime,
        trigger: str,
        result: ScrapeResult,
    ) -> PriceSnapshot:
        snapshot = PriceSnapshot(
            id=self.id_gen.new_id(),
            product_id=product_id,
            slot_at=slot_at,
            captured_at=captured_at,
            price=result.price,
            was_price=result.was_price,
            discount_pct=result.discount_pct,
            currency=result.currency,
            in_stock=result.in_stock,
            stock_label=result.stock_label,
            stock_count=result.stock_count,
            layout_revision=result.layout_revision,
            structure_changed=result.structure_changed,
            trigger=trigger,
        )
        self.db.prices.add_snapshot(snapshot)
        return snapshot

    def _persist_logs(
        self, product_id: int, tracker_id: str | None, result: ScrapeResult
    ) -> None:
        total = len(result.attempts_detail)
        for att in result.attempts_detail:
            if att.success:
                outcome = ScrapeOutcome.SUCCESS.value
            elif att.attempt < total:
                outcome = ScrapeOutcome.RETRIED.value
            else:
                outcome = ScrapeOutcome.FAILED.value

            kind = att.error_kind
            if kind is not None and kind not in {k.value for k in ScrapeErrorKind}:
                kind = ScrapeErrorKind.UNKNOWN.value

            self.db.prices.add_log(
                ScrapeLog(
                    id=self.id_gen.new_id(),
                    product_id=product_id,
                    tracker_id=tracker_id,
                    attempt=att.attempt,
                    outcome=outcome,
                    error_kind=kind,
                    message=att.error,
                    duration_ms=att.duration_ms,
                    price=att.price,
                    in_stock=att.in_stock,
                )
            )
