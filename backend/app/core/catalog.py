"""Catalog Sync — cache the storefront's 1000 products so search is local.

The store is awkward on purpose here too:

* ``/api/catalog`` ignores ``pageSize`` above 60 and returns a *randomised*
  ordering, so paging through it yields duplicates and only ~620 unique rows.
* Requests are rate limited; bursts get a ``429`` with ``Retry-After``.

So we do two phases, persisting as we go (so an interrupted sync still makes
progress): page through the catalog once to grab the easy majority, then top up
the remaining ids directly via ``/api/product/{id}``. Every request goes through
a shared throttle with 429 backoff. Runs at boot only when we hold fewer than
``Core.catalogTotal`` products.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx
from django.db import close_old_connections

from app.internal.postgresql.module import Database
from app.utils.http import retry_after as _retry_after


class CatalogSync:
    def __init__(self, logger: logging.Logger, cfg: dict, db: Database):
        self.logger = logger
        self.cfg = cfg
        self.db = db
        self.base = str(cfg["Core"]["storefrontBase"]).rstrip("/")
        self.page_size = min(int(cfg["Core"]["catalogPageSize"]), 60)
        self.total = int(cfg["Core"]["catalogTotal"])
        self.min_interval = max(0.1, int(cfg["Core"].get("catalogMinIntervalMs", 600)) / 1000.0)
        self.budget_seconds = float(cfg["Core"].get("catalogBudgetSeconds", 240))
        self._lock = threading.Lock()
        self._throttle = threading.Lock()
        self._last_request = 0.0

    # ------------------------------------------------------------------ transport
    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base,
            timeout=httpx.Timeout(20.0),
            headers={"User-Agent": "PriceTrackerCatalogSync/1.0"},
        )

    def _wait_turn(self) -> None:
        with self._throttle:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _get(self, client: httpx.Client, path: str, params: dict | None = None, retries: int = 6):
        """GET with a global throttle, 429 backoff, and retries. 404 is returned."""
        last: Exception | None = None
        for attempt in range(1, retries + 1):
            self._wait_turn()
            try:
                resp = client.get(path, params=params)
                if resp.status_code == 429:
                    retry_after = _retry_after(resp, attempt)
                    self.logger.warning(
                        "catalog 429 on %s (attempt %d) — sleeping %.1fs",
                        path,
                        attempt,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    continue
                if resp.status_code == 404:
                    return resp
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:  # non-429/404
                last = exc
                time.sleep(min(0.5 * attempt, 4.0))
            except Exception as exc:  # noqa: BLE001
                last = exc
                self.logger.warning("catalog request %s failed (attempt %d): %s", path, attempt, exc)
                time.sleep(min(0.5 * attempt, 4.0))
        raise RuntimeError(f"request {path} failed after {retries} attempts: {last}")

    @staticmethod
    def _normalize_catalog(items: list[dict]) -> list[dict]:
        normalized = []
        for item in items:
            if "id" not in item:
                continue
            normalized.append(
                {
                    "id": int(item["id"]),
                    "slug": item.get("slug"),
                    "name": item.get("name") or f"Product {item['id']}",
                    "brand": item.get("brand"),
                    "category": item.get("category"),
                    "sku": item.get("sku"),
                    "description": item.get("description"),
                }
            )
        return normalized

    # ------------------------------------------------------------------ sync
    def sync(self) -> dict:
        with self._lock:
            return self._sync()

    def _sync(self) -> dict:
        started = time.monotonic()
        deadline = started + self.budget_seconds
        written = 0

        try:
            with self._client() as client:
                first = self._get(client, "/api/catalog", {"page": 1, "pageSize": self.page_size})
                first.raise_for_status()
                meta = first.json()
                pages = int(meta.get("pages") or 1)
                total = int(meta.get("total") or self.total)

                rows = self._normalize_catalog(meta.get("items") or [])
                batch: list[dict] = list(rows)
                for page in range(2, pages + 1):
                    data = self._get(
                        client, "/api/catalog", {"page": page, "pageSize": self.page_size}
                    )
                    if data.status_code == 404:
                        continue
                    batch.extend(self._normalize_catalog(data.json().get("items") or []))
                    if page % 5 == 0:
                        written += self._flush(batch)
                        batch = []
                        self.logger.info("catalog sync: page %d/%d", page, pages)
                written += self._flush(batch)

                # Phase 2 — fill the randomised-page gaps via direct ids.
                if total and time.monotonic() < deadline:
                    known = self.db.products.list_ids()
                    missing = [pid for pid in range(1, total + 1) if pid not in known]
                    self.logger.info(
                        "catalog sync: %d unique after paging, probing %d missing ids",
                        len(known),
                        len(missing),
                    )
                    written += self._probe_ids(client, missing, deadline)
        except Exception:
            self.logger.exception("catalog sync aborted; keeping what we already stored")

        elapsed = round(time.monotonic() - started, 2)
        count = self.db.products.count()
        result = {
            "written": written,
            "inDatabase": count,
            "expected": self.total,
            "complete": count >= self.total,
            "elapsedSeconds": elapsed,
        }
        self.logger.info("catalog sync finished: %s", result)
        return result

    def _flush(self, batch: list[dict]) -> int:
        if not batch:
            return 0
        by_id = {row["id"]: row for row in batch}
        self.db.products.upsert_catalog(list(by_id.values()))
        return len(by_id)

    def _probe_ids(self, client: httpx.Client, missing: list[int], deadline: float) -> int:
        written = 0
        for pid in missing:
            if time.monotonic() >= deadline:
                self.logger.info("catalog top-up budget reached at id %s", pid)
                break
            resp = self._get(client, f"/api/product/{pid}", retries=3)
            if resp.status_code == 404:
                continue
            try:
                detail = resp.json()
            except Exception:
                continue
            self._flush(
                [
                    {
                        "id": int(detail["id"]),
                        "slug": detail.get("slug"),
                        "name": detail.get("name") or f"Product {pid}",
                        "brand": detail.get("brand"),
                        "category": detail.get("category"),
                        "sku": detail.get("sku"),
                        "description": detail.get("description"),
                    }
                ]
            )
            written += 1
        return written

    # ------------------------------------------------------------------ boot
    def ensure_populated(self) -> None:
        try:
            close_old_connections()
            count = self.db.products.count()
            if count >= self.total:
                self.logger.info("catalog already populated (%d products)", count)
                return
            self.logger.info("catalog has %d/%d products — syncing", count, self.total)
            self.sync()
        except Exception:
            self.logger.exception("catalog sync failed at boot (will retry on next start)")

    def start_background(self) -> threading.Thread:
        thread = threading.Thread(
            target=self.ensure_populated, name="catalog-sync", daemon=True
        )
        thread.start()
        return thread
