"""Product service — search, catalog browsing, detail loading and on-demand scrape."""

from __future__ import annotations

import math
import time

import httpx

from app.entity.price import SnapshotTrigger
from app.services.errors import NotFound
from app.utils.http import retry_after as _retry_after
from app.utils.timeutil import utcnow

DETAIL_TTL_SECONDS = 6 * 60 * 60


class ProductServiceMixin:
    # ------------------------------------------------------------------ helpers
    def _storefront_base(self) -> str:
        return str(self.cfg["Core"]["storefrontBase"]).rstrip("/")

    def _fetch_detail(self, product_id: int, retries: int = 4) -> dict:
        url = f"{self._storefront_base()}/api/product/{product_id}"
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                resp = httpx.get(url, timeout=20.0, headers={"User-Agent": "PriceTracker/1.0"})
                if resp.status_code == 429:
                    retry_after = _retry_after(resp, attempt)
                    self.logger.warning(
                        "detail %s rate limited (attempt %d) — sleeping %.1fs",
                        product_id,
                        attempt,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self.logger.warning("product detail %s failed (attempt %d): %s", product_id, attempt, exc)
                time.sleep(0.4 * attempt)
        raise RuntimeError(f"could not load product detail {product_id}: {last_error}")

    def _ensure_detail(self, product_id: int):
        product = self.db.products.get(product_id)
        if product is None:
            raise NotFound("product not found")
        loaded = product.detail_loaded_at
        stale = (
            loaded is None
            or (utcnow() - loaded).total_seconds() > DETAIL_TTL_SECONDS
        )
        if stale:
            try:
                detail = self._fetch_detail(product_id)
                self.db.products.update_detail(
                    product_id,
                    detail.get("specs") or {},
                    detail.get("reviews") or [],
                    utcnow(),
                )
                product = self.db.products.get(product_id)
            except Exception:
                # Detail is nice-to-have; the page still works from catalog data.
                self.logger.exception("detail load failed for product %s", product_id)
        return product

    def _product_payload(self, product, latest, pending: bool = False) -> dict:
        return {
            "id": product.id,
            "slug": product.slug,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "sku": product.sku,
            "description": product.description,
            "specs": product.specs or {},
            "reviews": product.reviews or [],
            "detailLoaded": product.detail_loaded_at is not None,
            "structureChanged": product.structure_changed_at is not None,
            "structureNote": product.structure_note,
            "latest": latest.point() if latest is not None else None,
            "snapshotCount": self.db.prices.count_for_product(product.id),
            "pending": pending,
        }

    @staticmethod
    def _paginate(total: int, page: int, page_size: int) -> dict:
        return {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "pages": max(1, math.ceil(total / page_size)) if total else 0,
        }

    # ------------------------------------------------------------------ public
    def search_products(self, query: str, page: int = 1, page_size: int = 20) -> dict:
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 20)), 60)
        items, total = self.db.products.search(query or "", page_size, (page - 1) * page_size)
        return {
            "items": [p.card() for p in items],
            **self._paginate(total, page, page_size),
        }

    def list_products(self, page: int = 1, page_size: int = 20) -> dict:
        page = max(1, int(page or 1))
        page_size = min(max(1, int(page_size or 20)), 60)
        items, total = self.db.products.list_page(page_size, (page - 1) * page_size)
        return {
            "items": [p.card() for p in items],
            **self._paginate(total, page, page_size),
        }

    def get_product(self, product_id: int, ensure_price: bool = False) -> dict:
        product = self._ensure_detail(product_id)
        latest = self.db.prices.latest_for_product(product_id)

        pending = False
        if ensure_price and latest is None:
            # "If item data is not available, load that by triggering a track core."
            self.core.track.submit(product_id, SnapshotTrigger.ON_DEMAND.value)
            pending = True

        return self._product_payload(product, latest, pending)

    def refresh_product(self, product_id: int, wait: bool = False, headless: bool | None = None) -> dict:
        if self.db.products.get(product_id) is None:
            raise NotFound("product not found")
        if wait:
            result = self.core.track.scrape_sync(
                product_id, SnapshotTrigger.MANUAL.value, headless=headless
            )
            return {"status": "done", "result": result.as_dict()}
        future = self.core.track.submit(
            product_id, SnapshotTrigger.MANUAL.value, headless=headless
        )
        del future  # fire-and-forget; the client polls the product
        return {"status": "queued"}

    # ------------------------------------------------------------------ catalog
    def sync_catalog(self) -> dict:
        return self.core.catalog.sync()

    def catalog_status(self) -> dict:
        count = self.db.products.count()
        expected = int(self.cfg["Core"]["catalogTotal"])
        return {
            "count": count,
            "expected": expected,
            "complete": count >= expected,
        }
