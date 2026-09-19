"""The Playwright scrape flow for one product page.

The storefront is a React SPA whose price is gated behind a browser fingerprint
+ WebAssembly proof-of-work + hover attestation, so this genuinely needs a real
browser. Everything here is defensive: the layout classes are read from
``/api/layout`` (with fallbacks), the reveal button is earned with real mouse
movement, and the terminal success/error state of the price block is awaited
explicitly instead of guessing after a fixed sleep.
"""

from __future__ import annotations

import asyncio
import logging
import time

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


class StructureChangedError(Exception):
    """The page rendered but no longer matches the structure we can parse."""


async def dismiss_cookie_banner(page: Page) -> bool:
    """Dismiss the cookie consent banner if present. Safe to call repeatedly."""
    try:
        accept = page.get_by_role("button", name="Accept cookies")
        await accept.wait_for(state="visible", timeout=2500)
        await accept.click()
        await page.wait_for_timeout(150)
        return True
    except PlaywrightTimeoutError:
        return False
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
        await dismiss_cookie_banner(page)
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


async def _attempt(page: Page, url: str, cfg: dict, logger: logging.Logger) -> dict:
    """One full scrape attempt against an already-open page."""
    timeout = int(cfg["Core"]["scrapeTimeoutMs"])

    await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    await dismiss_cookie_banner(page)

    classes, revision = await _load_layout(page, cfg["Core"]["storefrontBase"], logger)

    reveal = page.get_by_role("button", name="Reveal price")
    await reveal.wait_for(state="visible", timeout=timeout)

    await _hover_until_ready(
        page,
        page.locator(".price-block"),
        reveal,
        int(cfg["Core"]["scrapeMinMoves"]),
        int(cfg["Core"]["scrapeMinDwellMs"]),
        timeout,
        logger,
    )

    await dismiss_cookie_banner(page)
    await reveal.click()

    # Wait for the price block to reach a terminal state (success or error),
    # rather than assuming a fixed render delay. This is where slow/async
    # responses are absorbed.
    await page.wait_for_function(
        "() => document.querySelector('.price-block.price-success')"
        " || document.querySelector('.price-block.price-error')",
        timeout=timeout,
    )

    error_block = page.locator(".price-block.price-error")
    if await error_block.count():
        message = ""
        sub = page.locator(".price-block.price-error .price-substatus")
        if await sub.count():
            message = (await sub.first.inner_text()).strip()
        kind = "rate_limit" if ("429" in message or "rate" in message.lower()) else "unknown"
        return {"error": message or "store returned an error state", "error_kind": kind, "layout_revision": revision}

    quote = await _extract_quote(page, classes, logger)
    quote["layout_revision"] = revision
    return quote


def _classify_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, StructureChangedError):
        return "structure", str(exc)
    if isinstance(exc, PlaywrightTimeoutError):
        return "timeout", f"Timeout: {exc}"
    text = str(exc).lower()
    if "net::" in text or "connection" in text or "err_" in text:
        return "network", f"Network error: {exc}"
    return "unknown", f"Error: {exc}"


async def run_browser_session(
    product_id: int,
    url: str,
    cfg: dict,
    logger: logging.Logger,
    headless: bool,
) -> ScrapeResult:
    """Open a browser, attempt the scrape up to N times, return the full result."""
    result = ScrapeResult(product_id=product_id, url=url)
    max_attempts = max(1, int(cfg["Core"]["scrapeMaxAttempts"]))
    started = time.monotonic()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                # Trim the browser's memory footprint; nothing here needs GPU,
                # extensions, media or background networking.
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--mute-audio",
                "--no-first-run",
            ],
        )
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-IN",
        )
        page = await context.new_page()
        try:
            for attempt in range(1, max_attempts + 1):
                attempt_started = time.monotonic()
                try:
                    data = await _attempt(page, url, cfg, logger)
                    duration = int((time.monotonic() - attempt_started) * 1000)

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
                        logger.warning("attempt %d failed: %s", attempt, data["error"])
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
                        logger.info(
                            "attempt %d success: price=%s stock=%s",
                            attempt,
                            data["price"],
                            data["stock_label"],
                        )
                        break

                except Exception as exc:  # noqa: BLE001 - we classify and record everything
                    duration = int((time.monotonic() - attempt_started) * 1000)
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
                    logger.warning("attempt %d failed (%s): %s", attempt, kind, message)

                # Fresh page for the next attempt so a half-loaded or
                # error-state page never contaminates the retry.
                if attempt < max_attempts:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = await context.new_page()
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 5.0))
        finally:
            await context.close()
            await browser.close()

    # Only call it a structure change if *every* attempt failed structurally —
    # a single missing container is usually a transient partial render.
    structural = [a for a in result.attempts_detail if a.error_kind == "structure"]
    if not result.success and structural and len(structural) == len(result.attempts_detail):
        result.structure_changed = True
        result.structure_note = structural[-1].error

    result.attempts = len(result.attempts_detail) or 1
    result.retried = len(result.attempts_detail) > 1
    result.duration_ms = int((time.monotonic() - started) * 1000)
    if not result.success and result.error_kind is None:
        result.error_kind = "unknown"
    if not result.success and result.error is None:
        result.error = "scrape failed with no recorded error"
    return result
