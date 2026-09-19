"""ServiceLayer container (≈ service.go). Composes every service mixin."""

from __future__ import annotations

import logging

from app.entity.scheduler import JobType
from app.internal.postgresql.module import Database
from app.services.email_service import EmailService
from app.services.notification_service import NotificationServiceMixin
from app.services.product_service import ProductServiceMixin
from app.services.tracker_service import TrackerServiceMixin
from app.services.user_service import UserServiceMixin
from app.utils.idgen import IDGenerator


class ServiceLayer(
    UserServiceMixin,
    ProductServiceMixin,
    TrackerServiceMixin,
    NotificationServiceMixin,
):
    def __init__(
        self,
        cfg: dict,
        logger: logging.Logger,
        db: Database,
        id_gen: IDGenerator,
        core,
    ):
        self.cfg = cfg
        self.logger = logger
        self.db = db
        self.id_gen = id_gen
        self.core = core
        self.email = EmailService(logger, cfg)

    def wire_core(self) -> None:
        """Connect core hooks to services without core importing services."""
        self.core.cron.snapshot_hook = self.evaluate_snapshot
        self.core.jobs.register(
            JobType.NOTIFICATION, lambda task: self.dispatch_pending()
        )
        self.core.jobs.register(
            JobType.CATALOG_SYNC, lambda task: self.sync_catalog()
        )
        self.core.jobs.register(JobType.TRACK, self.core.cron.run_track_task)
