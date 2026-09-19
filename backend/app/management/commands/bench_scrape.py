"""Benchmark the scraper's phase timings with and without browser reuse.

No data is persisted: this uses ``TrackCore.probe`` so it only measures the
browser work. Run it locally against real products, e.g.

    uv run python manage.py bench_scrape 1 138 --repeat 2
    uv run python manage.py bench_scrape 1 --no-reuse
    uv run python manage.py bench_scrape 1 --reuse
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from app.core.bootstrap import get_core

_PHASES = (
    "browserStartMs",
    "contextMs",
    "gotoMs",
    "bannerAfterGotoMs",
    "layoutMs",
    "revealButtonMs",
    "hoverMs",
    "bannerBeforeClickMs",
    "revealWaitMs",
    "extractMs",
)


def _phase(timings: dict, suffix: str) -> int:
    return int(sum(value for key, value in timings.items() if key.endswith(suffix)))


def _avg(values: list[int]) -> int:
    return int(sum(values) / len(values)) if values else 0


class Command(BaseCommand):
    help = "Probe scrape timings with/without browser reuse (no DB writes)."

    def add_arguments(self, parser):
        parser.add_argument("product_id", type=int, nargs="+")
        parser.add_argument("--repeat", type=int, default=1)
        parser.add_argument("--headed", action="store_true")
        parser.add_argument("--no-reuse", action="store_true", help="only the no-reuse path")
        parser.add_argument("--reuse", action="store_true", help="only the reuse path")

    def handle(self, *args, **options):
        core = get_core()
        headless = not options["headed"]
        if options["reuse"]:
            modes = [True]
        elif options["no_reuse"]:
            modes = [False]
        else:
            modes = [False, True]

        results: dict[str, list[tuple[int, int, object, int]]] = {}
        for reuse in modes:
            core.track.close_thread_session()
            core.track.reuse_browser = reuse
            label = "reuse" if reuse else "no-reuse"
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {label} ==="))
            rows: list[tuple[int, int, object, int]] = []
            for repeat in range(1, options["repeat"] + 1):
                for product_id in options["product_id"]:
                    wall_started = time.monotonic()
                    result = core.track.probe(product_id, headless=headless)
                    wall = int((time.monotonic() - wall_started) * 1000)
                    rows.append((product_id, repeat, result, wall))
                    self._print_row(product_id, repeat, result, wall)
            results[label] = rows
            self._print_summary(rows, label)

        if len(results) == 2:
            self._compare(results["no-reuse"], results["reuse"])
        core.track.close_thread_session()

    def _print_row(self, product_id: int, repeat: int, result, wall: int) -> None:
        status = "ok" if result.success else "FAIL"
        phases = "  ".join(
            f"{name[:-2]}={_phase(result.timings, name)}" for name in _PHASES
        )
        self.stdout.write(
            f"  #{repeat} product {product_id}: {status} wall={wall}ms "
            f"total={result.duration_ms}ms\n      {phases}"
        )
        if not result.success and result.error:
            self.stdout.write(f"      error: {result.error}")

    def _print_summary(self, rows, label: str) -> None:
        if not rows:
            return
        successes = [row for row in rows if row[2].success]
        self.stdout.write(
            f"  {label}: {len(successes)}/{len(rows)} ok, "
            f"avg total={_avg([row[2].duration_ms for row in rows])}ms, "
            f"avg wall={_avg([row[3] for row in rows])}ms"
        )
        for name in _PHASES:
            self.stdout.write(
                f"      avg {name[:-2]}={_avg([_phase(row[2].timings, name) for row in rows])}ms"
            )

    def _compare(self, no_reuse, reuse) -> None:
        before = _avg([row[2].duration_ms for row in no_reuse])
        after = _avg([row[2].duration_ms for row in reuse])
        if not before or not after:
            return
        saved = before - after
        pct = round(saved / before * 100, 1)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nreuse vs no-reuse: {before}ms -> {after}ms "
                f"(saved {saved}ms, {pct}%)"
            )
        )
