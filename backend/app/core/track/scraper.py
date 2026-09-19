"""The Playwright scrape flow for one product page.

The storefront is a React SPA whose price is gated behind a browser fingerprint
+ WebAssembly proof-of-work + hover attestation, so this genuinely needs a real
browser. Everything here is defensive: the layout classes are read from
``/api/layout`` (with fallbacks), the reveal button is earned with real mouse
movement, and the terminal success/error state of the price block is awaited
explicitly instead of guessing after a fixed sleep.

``BrowserSession`` starts Playwright + Chromium **once** and opens a fresh
context/page per product, so a batch of scrapes doesn't pay browser startup for
every product. ``run_browser_batch`` can run several pages concurrently inside
that one browser. The browser is recycled after a configurable number of scrapes
to bound memory. Every phase is timed into ``ScrapeResult.timings``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from playwright.async_api import (
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from app.core.track.models import ScrapeAttempt, ScrapeResult
from app.core.track.parsers import (
    clean_price_string,
    detect_currency,
    parse_discount_pct,
    parse_stock_label,
)

DEFAULT_CLASSES = {
    "priceWrap": "pw-k2",
    "priceValue": "pv-k2",
    "mrp": "mr-k2",
    "sale": "sl-k2",
    "badge": "bd-k2",
}

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    # Trim the browser's memory footprint; nothing here needs GPU, extensions,
    # media or background networking.
    "--disable-gpu",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--mute-audio",
    "--no-first-run",
]

_READ_LEAF_TEXT_JS = """
(el) => {
  const leaves = Array.from(el.querySelectorAll('span'))
    .filter(s => s.querySelectorAll('span').length === 0)
    .map(s => s.textContent.trim())
    .filter(t => t.length > 0);
  return leaves.length > 0 ? leaves.join('') : el.textContent.trim();
}
"""

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

LayoutLoader = Callable[[Page, str], Awaitable[tuple[dict, int | None]]]


def _now() -> float:
    return time.monotonic()


def _ms(started: float) -> int:
    return int((_now() - started) * 1000)


class StructureChangedError(Exception):
    """The page rendered but no longer matches the structure we can parse."""


async def dismiss_cookie_banner(page: Page, timeout_ms: int = 1000) -> bool:
    """Dismiss the cookie consent banner if present. Safe to call repeatedly.

    We check ``count()`` first (instant) instead of ``wait_for(visible)``, because
    this runs ~3x per scrape and the banner is usually absent — waiting the full
    timeout each time was the single biggest hidden cost. If the banner renders
    late, the next check catches it. ``timeout_ms`` only bounds the click.
    """
    try:
        accept = page.get_by_role("button", name="Accept cookies")
        if await accept.count() == 0:
            return False
        await accept.first.click(timeout=timeout_ms)
        await page.wait_for_timeout(50)
        return True
    except Exception:
        return False


async def _load_layout(page: Page, base_url: str, logger: logging.Logger) -> tuple[dict, int | None]:
    """Read the storefront's current layout classes + revision for change detection."""
    classes = dict(DEFAULT_CLASSES)
    revision: int | None = None
    try:
        resp = await page.request.get(f"{base_url.rstrip('/')}/api/layout", timeout=10_000)
        if resp.ok:
            data = await resp.json()
            revision = data.get("revision")
            classes.update(data.get("classes") or {})
    except Exception as exc:  # non-fatal: fall back to known defaults
        logger.warning("layout fetch failed, using default classes: %s", exc)
    return classes, revision


async def _hover_until_ready(
    page: Page,
    wrapper,
    button,
    min_moves: int,
    min_dwell_ms: int,
    timeout_ms: int,
    logger: logging.Logger,
    banner_timeout_ms: int = 1000,
) -> None:
    """Earn the enabled state of the 'Reveal price' button with real mouse input.

    The page records moves, throttled to one per 40ms, and requires at least
    ``min_moves`` recorded moves plus a dwell of ``min_dwell_ms`` before it will
    let the button be clicked.
    """
    await wrapper.first.scroll_into_view_if_needed()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000.0
    attempt = 0

    while True:
        attempt += 1
        await dismiss_cookie_banner(page, banner_timeout_ms)
        box = await wrapper.first.bounding_box()
        if not box:
            raise RuntimeError("price-block has no bounding box (not rendered)")

        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Space the moves >40ms apart so the throttled tracker actually records them.
        for i in range(min_moves + 2):
            offset = 1 if i % 2 else -1
            dx = offset * min(18 + i * 2, max(12, box["width"] / 3))
            dy = ((i % 3) - 1) * 6
            await page.mouse.move(cx + dx, cy + dy, steps=1)
            await asyncio.sleep(0.055)

        await page.mouse.move(cx, cy, steps=1)
        await asyncio.sleep(min_dwell_ms / 1000.0 + 0.1)

        if await button.evaluate("(b) => !b.disabled"):
            logger.info("reveal button enabled after %d hover attempt(s)", attempt)
            return

        logger.info("reveal button still disabled (hover attempt %d)", attempt)
        if loop.time() >= deadline:
            raise PlaywrightTimeoutError(
                f"Reveal price button never enabled after {attempt} attempt(s)"
            )
        await asyncio.sleep(0.3)


async def _extract_quote(page: Page, classes: dict, logger: logging.Logger) -> dict:
    """Read the real price/stock. Raises StructureChangedError if selectors moved."""
    price_selector = f".price-main .{classes.get('priceValue', DEFAULT_CLASSES['priceValue'])}"
    container = page.locator(price_selector)
    if await container.count() == 0:
        raise StructureChangedError(f"price container {price_selector!r} not found")

    await container.first.wait_for(state="visible", timeout=10_000)
    raw_price = await container.first.evaluate(_READ_LEAF_TEXT_JS)
    price = clean_price_string(raw_price)
    if price is None:
        raise StructureChangedError(f"price spans present but unparseable: {raw_price!r}")
    logger.info("raw price=%r parsed=%s", raw_price, price)

    currency = detect_currency(raw_price)

    was_price = None
    mrp_selector = f".price-main .{classes.get('mrp', DEFAULT_CLASSES['mrp'])}"
    mrp = page.locator(mrp_selector)
    if await mrp.count():
        raw_mrp = await mrp.first.evaluate(_READ_LEAF_TEXT_JS)
        was_price = clean_price_string(raw_mrp)
        currency = currency or detect_currency(raw_mrp)
        if was_price == 0:
            was_price = None

    discount_pct = None
    badge_selector = f".price-main .{classes.get('badge', DEFAULT_CLASSES['badge'])}"
    badge = page.locator(badge_selector)
    if await badge.count():
        discount_pct = parse_discount_pct(await badge.first.inner_text())

    stock_label = None
    in_stock = None
    stock_count = None
    badge_el = page.locator(".stock-badge")
    if await badge_el.count():
        stock_label = (await badge_el.first.inner_text()).strip()
        in_stock, stock_count = parse_stock_label(stock_label)
        class_attr = (await badge_el.first.get_attribute("class")) or ""
        if "out-stock" in class_attr or "out-of-stock" in class_attr:
            in_stock = False

    return {
        "price": price,
        "was_price": was_price,
        "discount_pct": discount_pct,
        "currency": currency or "INR",
        "in_stock": in_stock,
        "stock_label": stock_label,
        "stock_count": stock_count,
    }


async def _attempt(
    page: Page,
    url: str,
    cfg: dict,
    logger: logging.Logger,
    load_classes: LayoutLoader,
    deadline: float | None = None,
) -> tuple[dict, dict[str, float]]:
    """One full scrape attempt against an already-open page.

    ``deadline`` is a monotonic per-product budget: every wait is capped to the
    time remaining, so a single slow step can't blow past it. Returns
    ``(data, timings)``; ``data`` either has an ``error`` key or quote fields.
    """
    timeout = int(cfg["Core"]["scrapeTimeoutMs"])
    reveal_timeout = int(cfg["Core"].get("scrapeRevealTimeoutMs", 300000))
    banner_timeout = int(cfg["Core"].get("cookieBannerTimeoutMs", 1000))
    timings: dict[str, float] = {}

    def cap(default_ms: int) -> int:
        if deadline is None:
            return default_ms
        remaining_ms = int((deadline - _now()) * 1000)
        if remaining_ms <= 0:
            raise PlaywrightTimeoutError("scrape product budget exceeded")
        return max(250, min(default_ms, remaining_ms))

    started = _now()
    await page.goto(url, wait_until="domcontentloaded", timeout=cap(timeout))
    timings["gotoMs"] = _ms(started)

    started = _now()
    await dismiss_cookie_banner(page, cap(banner_timeout))
    timings["bannerAfterGotoMs"] = _ms(started)

    started = _now()
    classes, revision = await load_classes(page, cfg["Core"]["storefrontBase"])
    timings["layoutMs"] = _ms(started)

    reveal = page.get_by_role("button", name="Reveal price")
    started = _now()
    await reveal.wait_for(state="visible", timeout=cap(timeout))
    timings["revealButtonMs"] = _ms(started)

    started = _now()
    await _hover_until_ready(
        page,
        page.locator(".price-block"),
        reveal,
        int(cfg["Core"]["scrapeMinMoves"]),
        int(cfg["Core"]["scrapeMinDwellMs"]),
        cap(timeout),
        logger,
        cap(banner_timeout),
    )
    timings["hoverMs"] = _ms(started)

    started = _now()
    await dismiss_cookie_banner(page, cap(banner_timeout))
    timings["bannerBeforeClickMs"] = _ms(started)

    started = _now()
    await reveal.click()
    # Wait for the price block to reach a terminal state (success or error),
    # rather than assuming a fixed render delay. This is where slow/async
    # responses are absorbed, so it gets its own (long) budget — the storefront
    # can take minutes. Navigation/hover still use the shorter scrape timeout.
    await page.wait_for_function(
        "() => document.querySelector('.price-block.price-success')"
        " || document.querySelector('.price-block.price-error')",
        timeout=cap(reveal_timeout),
    )
    timings["revealWaitMs"] = _ms(started)

    error_block = page.locator(".price-block.price-error")
    if await error_block.count():
        message = ""
        sub = page.locator(".price-block.price-error .price-substatus")
        if await sub.count():
            message = (await sub.first.inner_text()).strip()
        kind = "rate_limit" if ("429" in message or "rate" in message.lower()) else "unknown"
        return {
            "error": message or "store returned an error state",
            "error_kind": kind,
            "layout_revision": revision,
        }, timings

    started = _now()
    quote = await _extract_quote(page, classes, logger)
    timings["extractMs"] = _ms(started)
    quote["layout_revision"] = revision
    return quote, timings


def _classify_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, StructureChangedError):
        return "structure", str(exc)
    if isinstance(exc, PlaywrightTimeoutError):
        return "timeout", f"Timeout: {exc}"
    text = str(exc).lower()
    if "net::" in text or "connection" in text or "err_" in text:
        return "network", f"Network error: {exc}"
    return "unknown", f"Error: {exc}"


class BrowserSession:
    """A long-lived Playwright + Chromium, reused across many product scrapes.

    A fresh context (and page) is opened per product to keep cookies/fingerprint
    state isolated. The browser is recycled after ``scrapeBrowserRecycle``
    scrapes to bound memory growth.
    """

    def __init__(self, cfg: dict, logger: logging.Logger, headless: bool):
        self.cfg = cfg
        self.logger = logger
        self.headless = headless
        self.recycle_after = max(1, int(cfg["Core"].get("scrapeBrowserRecycle", 25)))
        self.layout_ttl = max(0.0, float(cfg["Core"].get("scrapeLayoutTtlSeconds", 300)))
        self._pw = None
        self._browser = None
        self._uses = 0
        self._active = 0
        self._recycle_lock: asyncio.Lock | None = None
        self.start_ms = 0
        self._layout: dict | None = None
        self._layout_revision: int | None = None
        self._layout_at = 0.0

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        started = _now()
        self._pw = await async_playwright().start()
        await self._launch()
        self._recycle_lock = asyncio.Lock()
        self.start_ms = _ms(started)
        self.logger.info("browser started in %dms", self.start_ms)

    async def _launch(self) -> None:
        self._browser = await self._pw.chromium.launch(
            headless=self.headless, args=_LAUNCH_ARGS
        )
        self._uses = 0

    async def _recycle(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                self.logger.exception("closing recycled browser failed")
            self._browser = None
        await self._launch()

    async def _maybe_recycle(self) -> None:
        # Only recycle when no scrape is in flight, so concurrent pages aren't
        # torn down under each other. Deferred recycle happens on the next start.
        if self._uses < self.recycle_after:
            return
        if self._active > 0 or self._recycle_lock is None:
            return
        async with self._recycle_lock:
            if self._uses >= self.recycle_after and self._active == 0:
                self.logger.info("recycling browser after %d scrapes", self._uses)
                await self._recycle()

    async def close(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None

    # ------------------------------------------------------------------ layout cache
    async def _load_classes(self, page: Page, base_url: str) -> tuple[dict, int | None]:
        now = _now()
        if self._layout is not None and (now - self._layout_at) < self.layout_ttl:
            return self._layout, self._layout_revision
        classes, revision = await _load_layout(page, base_url, self.logger)
        self._layout = classes
        self._layout_revision = revision
        self._layout_at = now
        return classes, revision

    # ------------------------------------------------------------------ scrape
    async def _new_context(self):
        params = {
            "user_agent": _USER_AGENT,
            "viewport": {"width": 1366, "height": 900},
            "locale": "en-IN",
        }
        try:
            return await self._browser.new_context(**params)
        except Exception:
            self.logger.exception("new_context failed; recycling browser")
            await self._recycle()
            return await self._browser.new_context(**params)

    async def scrape(self, product_id: int, url: str) -> ScrapeResult:
        await self._maybe_recycle()
        self._active += 1
        try:
            result = ScrapeResult(product_id=product_id, url=url)
            started = _now()

            context_started = _now()
            context = await self._new_context()
            result.timings["contextMs"] = _ms(context_started)
            result.timings["browserStartMs"] = self.start_ms

            page = await context.new_page()
            try:
                await self._run_attempts(result, page, context, url)
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

            self._uses += 1
            result.duration_ms = _ms(started)
            return result
        finally:
            self._active -= 1

    async def _run_attempts(self, result: ScrapeResult, page: Page, context, url: str) -> None:
        cfg = self.cfg
        max_attempts = max(1, int(cfg["Core"]["scrapeMaxAttempts"]))
        budget_ms = int(cfg["Core"].get("scrapeProductBudgetMs", 120000))
        product_deadline = (_now() + budget_ms / 1000.0) if budget_ms > 0 else None

        for attempt in range(1, max_attempts + 1):
            if product_deadline is not None and _now() >= product_deadline:
                self._mark_budget_exceeded(result, attempt)
                break

            attempt_started = _now()
            try:
                data, timings = await _attempt(
                    page, url, cfg, self.logger, self._load_classes, product_deadline
                )
                for key, value in timings.items():
                    result.timings[f"a{attempt}.{key}"] = value
                duration = _ms(attempt_started)

                if "error" in data:
                    result.attempts_detail.append(
                        ScrapeAttempt(
                            attempt=attempt,
                            success=False,
                            duration_ms=duration,
                            error=data["error"],
                            error_kind=data.get("error_kind", "unknown"),
                        )
                    )
                    result.error = data["error"]
                    result.error_kind = data.get("error_kind", "unknown")
                    result.layout_revision = data.get("layout_revision")
                    self.logger.warning("attempt %d failed: %s", attempt, data["error"])
                else:
                    result.success = True
                    result.price = data["price"]
                    result.was_price = data["was_price"]
                    result.discount_pct = data["discount_pct"]
                    result.currency = data["currency"]
                    result.in_stock = data["in_stock"]
                    result.stock_label = data["stock_label"]
                    result.stock_count = data["stock_count"]
                    result.layout_revision = data["layout_revision"]
                    result.attempts_detail.append(
                        ScrapeAttempt(
                            attempt=attempt,
                            success=True,
                            duration_ms=duration,
                            price=data["price"],
                            in_stock=data["in_stock"],
                        )
                    )
                    self.logger.info(
                        "attempt %d success: price=%s stock=%s",
                        attempt,
                        data["price"],
                        data["stock_label"],
                    )
                    break

            except Exception as exc:  # noqa: BLE001 - classify and record everything
                duration = _ms(attempt_started)
                kind, message = _classify_exception(exc)
                result.attempts_detail.append(
                    ScrapeAttempt(
                        attempt=attempt,
                        success=False,
                        duration_ms=duration,
                        error=message,
                        error_kind=kind,
                    )
                )
                result.error = message
                result.error_kind = kind
                self.logger.warning("attempt %d failed (%s): %s", attempt, kind, message)

            # Fresh page for the next attempt so a half-loaded or error-state
            # page never contaminates the retry.
            if attempt < max_attempts:
                backoff = min(0.5 * (2 ** (attempt - 1)), 5.0)
                if product_deadline is not None and _now() + backoff >= product_deadline:
                    self._mark_budget_exceeded(result, attempt)
                    break
                try:
                    await page.close()
                except Exception:
                    pass
                page = await context.new_page()
                await asyncio.sleep(backoff)

        # Only call it a structure change if *every* attempt failed structurally.
        structural = [a for a in result.attempts_detail if a.error_kind == "structure"]
        if not result.success and structural and len(structural) == len(result.attempts_detail):
            result.structure_changed = True
            result.structure_note = structural[-1].error

        result.attempts = len(result.attempts_detail) or 1
        result.retried = len(result.attempts_detail) > 1
        if not result.success and result.error_kind is None:
            result.error_kind = "unknown"
        if not result.success and result.error is None:
            result.error = "scrape failed with no recorded error"

    def _mark_budget_exceeded(self, result: ScrapeResult, attempt: int) -> None:
        if not result.attempts_detail:
            result.attempts_detail.append(
                ScrapeAttempt(
                    attempt=attempt,
                    success=False,
                    duration_ms=0,
                    error="scrape product budget exceeded",
                    error_kind="timeout",
                )
            )
        if result.error is None:
            result.error = "scrape product budget exceeded"
        if result.error_kind is None:
            result.error_kind = "timeout"


async def run_browser_session(
    product_id: int,
    url: str,
    cfg: dict,
    logger: logging.Logger,
    headless: bool,
) -> ScrapeResult:
    """One-shot scrape: open a browser, attempt the scrape, close it again."""
    session = BrowserSession(cfg, logger, headless)
    await session.start()
    try:
        return await session.scrape(product_id, url)
    finally:
        await session.close()


async def run_browser_batch(
    pairs: list[tuple[int, str]],
    cfg: dict,
    logger: logging.Logger,
    headless: bool,
    concurrency: int = 1,
    deadline: float | None = None,
) -> list[ScrapeResult | None]:
    """Scrape many products in one browser, up to ``concurrency`` pages at once.

    Returns a list aligned with ``pairs``; an entry is ``None`` when the overall
    ``deadline`` (monotonic) passed before it could run.
    """
    session = BrowserSession(cfg, logger, headless)
    await session.start()
    semaphore = asyncio.Semaphore(max(1, int(concurrency)))
    results: list[ScrapeResult | None] = [None] * len(pairs)

    async def scrape_one(index: int, product_id: int, url: str) -> None:
        async with semaphore:
            if deadline is not None and time.monotonic() >= deadline:
                return
            try:
                results[index] = await session.scrape(product_id, url)
            except Exception as exc:  # noqa: BLE001
                kind, message = _classify_exception(exc)
                failed = ScrapeResult(product_id=product_id, url=url)
                failed.error = message
                failed.error_kind = kind
                failed.attempts = 1
                failed.attempts_detail.append(
                    ScrapeAttempt(
                        attempt=1,
                        success=False,
                        duration_ms=0,
                        error=message,
                        error_kind=kind,
                    )
                )
                results[index] = failed

    try:
        await asyncio.gather(
            *(scrape_one(i, product_id, url) for i, (product_id, url) in enumerate(pairs))
        )
    finally:
        await session.close()
    return results
