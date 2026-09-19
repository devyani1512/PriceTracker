"""Run due scheduled jobs once and exit — for Render Cron Jobs / external cron.

This is the "lambda" entrypoint: boot the app, look up what is due, run it on
the bounded scheduled lane, persist the next slots, then shut down. Nothing is
kept in memory between runs; the durable ``tasks`` table is the source of truth.

Example (Render Cron Job, every 10 minutes):

    python manage.py run_jobs --budget 240
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from app.core.bootstrap import get_core, shutdown_core


class Command(BaseCommand):
    help = "Run due scheduled jobs once, then exit (Render Cron Job friendly)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="ignore reuse and re-scrape")
        parser.add_argument("--no-scrape", action="store_true", help="only reuse existing data")
        parser.add_argument(
            "--budget",
            type=float,
            default=None,
            help="overall wall-clock budget in seconds (defaults to CRON_BUDGET_SECONDS)",
        )

    def handle(self, *args, **options):
        core = get_core()
        budget = (
            float(options["budget"])
            if options["budget"] is not None
            else float(core.cfg["Core"].get("cronBudgetSeconds", 240))
        )
        deadline = time.monotonic() + max(0.0, budget)

        # One tick enqueues everything due, then drains inline so this process
        # actually performs the work before it exits.
        summary = core.cron.tick(
            force=options["force"],
            scrape=not options["no_scrape"],
            budget_seconds=budget,
            drain=True,
        )
        runs = [summary]

        # Keep draining any backlog that did not fit the first pass.
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            drain = core.jobs.drain(budget=remaining)
            runs.append(drain)
            if drain.get("claimed", 0) == 0:
                break

        self.stdout.write(self.style.SUCCESS(str(runs)))
        shutdown_core()
