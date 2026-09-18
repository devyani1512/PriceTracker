"""CodeCore container + boot (≈ core/mod.go)."""

from __future__ import annotations

import logging

from app.core.catalog import CatalogSync
from app.core.cron.core import CronCore
from app.core.scheduler.scheduler import Scheduler, SelfTicker
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
        scheduler: Scheduler,
        self_ticker: SelfTicker | None,
    ):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.id_gen = id_gen
        self.track = track
        self.cron = cron
        self.catalog = catalog
        self.scheduler = scheduler
        self.self_ticker = self_ticker

    @classmethod
    def create(
        cls, logger: logging.Logger, cfg: dict, db: Database, id_gen: IDGenerator
    ) -> CodeCore:
        track = TrackCore(logger, cfg, db, id_gen)
        cron = CronCore(logger, cfg, db, track, id_gen)
        catalog = CatalogSync(logger, cfg, db)
        scheduler = Scheduler(logger, db, core=None)
        self_ticker = SelfTicker(logger, cfg, cron) if cfg["Core"]["selfTick"] else None
        core = cls(logger, cfg, db, id_gen, track, cron, catalog, scheduler, self_ticker)
        scheduler.core = core
        return core

    def boot(self) -> None:
        """Start background workers once, at app lifespan startup."""
        self.catalog.start_background()
        self.scheduler.start()
        if self.self_ticker is not None:
            self.self_ticker.start()

    def shutdown(self) -> None:
        if self.self_ticker is not None:
            self.self_ticker.stop()
        self.scheduler.stop()
        self.track.shutdown()
