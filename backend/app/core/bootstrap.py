"""Lazy singletons for the core and service layers.

Django settings/urls import cheaply; the heavy objects (DB facade, scheduler,
scraper pool) are built on first use so management commands like
``makemigrations`` never touch them.
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings

from app.core.mod import CodeCore
from app.internal.postgresql.module import Database
from app.services.service import ServiceLayer
from app.utils.idgen import IDGenerator

_lock = threading.Lock()
_core: CodeCore | None = None
_services: ServiceLayer | None = None


def get_cfg() -> dict:
    return settings.PRICE_TRACKER


def get_core() -> CodeCore:
    global _core, _services
    if _core is None:
        with _lock:
            if _core is None:
                cfg = get_cfg()
                logger = logging.getLogger("pricetracker")
                db = Database(cfg, logger)
                id_gen = IDGenerator(cfg)
                core = CodeCore.create(logger, cfg, db, id_gen)
                services = ServiceLayer(cfg, logger, db, id_gen, core)
                services.wire_core()
                _core, _services = core, services
    return _core


def get_services() -> ServiceLayer:
    get_core()
    assert _services is not None
    return _services


def boot_core() -> None:
    get_core().boot()


def shutdown_core() -> None:
    if _core is not None:
        _core.shutdown()
