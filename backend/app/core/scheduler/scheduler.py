"""Local-dev ticker.

The scheduled queue itself lives in ``core/jobs``. This thread is only a
substitute for an external cron service when none is configured: it runs a cron
tick (enqueue + drain inline) on an interval. Production sets ``SELF_TICK=false``
and drives ticks from Render Cron Jobs or an external scheduler.
"""

from __future__ import annotations

import logging
import threading

from django.db import close_old_connections


class SelfTicker(threading.Thread):
    def __init__(self, logger: logging.Logger, cfg: dict, cron) -> None:
        super().__init__(daemon=True, name="self-ticker")
        self.logger = logger
        self.cfg = cfg
        self.cron = cron
        self._stop = threading.Event()
        self.interval = max(30, int(cfg["Core"]["tickSeconds"]))

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        self.logger.info("SelfTicker started (every %ds)", self.interval)
        while not self._stop.is_set():
            close_old_connections()
            try:
                self.cron.tick(drain=True)
            except Exception:
                self.logger.exception("self-tick failed")
            self._stop.wait(self.interval)
        self.logger.info("SelfTicker stopped")
