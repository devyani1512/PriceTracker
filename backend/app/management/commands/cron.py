"""Run one cron pass: enqueue every due tracker and drain the queue."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from app.core.bootstrap import get_core


class Command(BaseCommand):
    help = "Run one cron tick and drain the scheduled queue (used by make cron)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="ignore reuse and re-scrape")
        parser.add_argument("--no-scrape", action="store_true", help="only reuse existing data")
        parser.add_argument("--budget", type=float, default=None, help="drain budget in seconds")

    def handle(self, *args, **options):
        summary = get_core().cron.tick(
            force=options["force"],
            scrape=not options["no_scrape"],
            budget_seconds=options["budget"],
            drain=True,
        )
        self.stdout.write(self.style.SUCCESS(str(summary)))
