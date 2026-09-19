"""Dataclasses returned by the track core."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScrapeAttempt:
    attempt: int
    success: bool
    duration_ms: int
    error: str | None = None
    error_kind: str | None = None
    price: float | None = None
    in_stock: bool | None = None


@dataclass
class ScrapeResult:
    product_id: int
    url: str
    success: bool = False
    price: float | None = None
    was_price: float | None = None
    discount_pct: int | None = None
    currency: str | None = None
    in_stock: bool | None = None
    stock_label: str | None = None
    stock_count: int | None = None
    layout_revision: int | None = None
    structure_changed: bool = False
    structure_note: str | None = None
    attempts: int = 0
    retried: bool = False
    snapshot_id: str | None = None
    error: str | None = None
    error_kind: str | None = None
    duration_ms: int = 0
    attempts_detail: list[ScrapeAttempt] = field(default_factory=list)
    # Per-phase wall-clock timings in ms, e.g. {"a1.gotoMs": 1200, "a1.hoverMs": 1100}.
    # In-memory only; used by the benchmark command and structured logs.
    timings: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "productId": self.product_id,
            "url": self.url,
            "success": self.success,
            "price": self.price,
            "wasPrice": self.was_price,
            "discountPct": self.discount_pct,
            "currency": self.currency,
            "inStock": self.in_stock,
            "stockLabel": self.stock_label,
            "stockCount": self.stock_count,
            "layoutRevision": self.layout_revision,
            "structureChanged": self.structure_changed,
            "attempts": self.attempts,
            "retried": self.retried,
            "error": self.error,
            "errorKind": self.error_kind,
            "durationMs": self.duration_ms,
            "timings": self.timings,
        }
