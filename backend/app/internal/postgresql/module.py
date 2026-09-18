"""Database access facade (≈ module.go).

Django owns the connection and migrations. This module keeps the same
``db.<entity>.<method>`` surface the core and services were written against, so
only this layer needed to change when we moved off SQLAlchemy.
"""

from __future__ import annotations

import logging

from django.db import connection

from app.internal.postgresql.notification_db import NotificationRepo
from app.internal.postgresql.price_db import PriceRepo
from app.internal.postgresql.product_db import ProductRepo
from app.internal.postgresql.task_db import TaskRepo
from app.internal.postgresql.tracker_db import TrackerRepo
from app.internal.postgresql.user_db import UserRepo


class Database:
    def __init__(self, cfg: dict, logger: logging.Logger | None = None):
        self.cfg = cfg
        self.logger = logger or logging.getLogger("pricetracker.db")
        # one repo attribute per entity file
        self.users = UserRepo(self)
        self.products = ProductRepo(self)
        self.trackers = TrackerRepo(self)
        self.prices = PriceRepo(self)
        self.notifications = NotificationRepo(self)
        self.tasks = TaskRepo(self)

    def ping(self) -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:  # pragma: no cover - surfaced through /health
            self.logger.exception("database ping failed")
            return False
