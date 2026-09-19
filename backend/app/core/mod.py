"""CodeCore container + boot (≈ core/mod.go)."""

from __future__ import annotations

import logging

from app.core.catalog import CatalogSync
from app.core.cron.core import CronCore
from app.core.jobs.runner import JobRunner
from app.core.scheduler.scheduler import SelfTicker
from app.core.track.core import TrackCore
from app.internal.postgresql.module import Database
from app.utils.idgen import IDGenerator


class CodeCore:
    def __init__(
        self,
        logger: logging.Logger,
        cfg: dict,
        db: Database,
        id_gen: IDGenerator,
        track: TrackCore,
        cron: CronCore,
        catalog: CatalogSync,
        jobs: JobRunner,
        self_ticker: SelfTicker | None,
    ):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.id_gen = id_gen
        self.track = track
        self.cron = cron
        self.catalog = catalog
        self.jobs = jobs
        self.self_ticker = self_ticker

    @classmethod
    def create(
        cls, logger: logging.Logger, cfg: dict, db: Database, id_gen: IDGenerator
    ) -> CodeCore:
        jobs = JobRunner(logger, cfg, db)
        track = TrackCore(logger, cfg, db, id_gen, jobs)
        cron = CronCore(logger, cfg, db, track, id_gen, jobs)
        catalog = CatalogSync(logger, cfg, db)
        self_ticker = SelfTicker(logger, cfg, cron) if cfg["Core"]["selfTick"] else None
        return cls(logger, cfg, db, id_gen, track, cron, catalog, jobs, self_ticker)

    def boot(self) -> None:
        """Start background workers once, at app lifespan startup."""
        self.catalog.start_background()
        self.jobs.start()
        if self.self_ticker is not None:
            self.self_ticker.start()

    def shutdown(self) -> None:
        if self.self_ticker is not None:
            self.self_ticker.stop()
        self.jobs.shutdown()
