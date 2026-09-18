"""Run the scraper for one product — optionally headed, for a screen recording.

Examples
--------
    uv run python manage.py scrape 138 --headed
    xvfb-run -a uv run python manage.py scrape 138 --headed   # headless Linux box
    uv run python manage.py scrape 138 --repeat 3 --interval 15 --headed
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from app.core.bootstrap import get_core
from app.entity.price import SnapshotTrigger


class Command(BaseCommand):
    help = "Scrape a single product by id (headed mode supported)."

    def add_arguments(self, parser):
        parser.add_argument("product_id", type=int)
        parser.add_argument("--headed", action="store_true", help="show the browser")
        parser.add_argument("--repeat", type=int, default=1)
        parser.add_argument("--interval", type=int, default=15)

    def handle(self, *args, **options):
        core = get_core()
        headless = not options["headed"]
        for run in range(1, options["repeat"] + 1):
            self.stdout.write(f"--- run #{run} (headless={headless}) ---")
            result = core.track.scrape_sync(
                options["product_id"],
                SnapshotTrigger.MANUAL.value,
                headless=headless,
            )
            self.stdout.write(str(result.as_dict()))
            if run < options["repeat"]:
                time.sleep(max(0, options["interval"]))
