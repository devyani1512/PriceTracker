import asyncio
import re
import sys
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def clean_price_string(raw: str):
    """
    Converts a concatenated price string like '₹9,452' or '9,452.50'
    into a float. Comma = thousands separator (Indian/US convention).
    A dot is only treated as a decimal point if followed by exactly
    1-2 digits at the very end of the string; otherwise it's dropped
    as noise (defensive against stray characters from split spans).
    """
    if not raw:
        return None

    cleaned = re.sub(r"[^\d.,]", "", raw)  # keep only digits, commas, dots
    cleaned = cleaned.replace(",", "")     # commas are thousands separators — drop them

    decimal_match = re.search(r"\.(\d{1,2})$", cleaned)
    if decimal_match:
        integer_part = cleaned[: decimal_match.start()].replace(".", "")
        return float(f"{integer_part}.{decimal_match.group(1)}")

    # no trailing decimal — any remaining dots are junk, strip them
    digits_only = cleaned.replace(".", "")
    return float(digits_only) if digits_only else None


async def dismiss_cookie_banner(page) -> bool:
    """Dismiss the cookie consent banner if present. Safe to call repeatedly."""
    try:
        accept_btn = page.get_by_role("button", name="Accept cookies")
        await accept_btn.wait_for(state="visible", timeout=3000)
        await accept_btn.click()
        await page.wait_for_timeout(200)
        log("cookie banner: found and dismissed")
        return True
    except PlaywrightTimeoutError:
        return False


async def wait_for_reveal_button(page, timeout_ms: int = 15000):
    """
    Waits for the 'Reveal price' button to become enabled. Tries a real
    stepped mouse move + hover first; if the disabled flag hasn't
    flipped, dispatches raw mouseenter/mouseover events as a fallback,
    re-checking for (and clearing) the cookie banner on every attempt
    since it can silently re-appear and eat pointer events.
    """
    log("waiting for 'Reveal price' button to appear...")
    reveal_btn = page.get_by_role("button", name="Reveal price")
    await reveal_btn.wait_for(state="visible", timeout=timeout_ms)
    log("button visible (still disabled at this point)")

    wrapper = page.locator(".price-block")
    await wrapper.scroll_into_view_if_needed()
    await page.wait_for_timeout(150)

    deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
    attempt = 0

    while True:
        attempt += 1
        dismissed = await dismiss_cookie_banner(page)
        if dismissed:
            log(f"[attempt {attempt}] banner was blocking, cleared it")

        box = await wrapper.bounding_box()
        if not box:
            raise RuntimeError("price-block has no bounding box (not visible/rendered)")
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        log(f"[attempt {attempt}] moving mouse to price-block and hovering...")
        await page.mouse.move(cx - 20, cy - 20)
        await page.mouse.move(cx, cy, steps=10)
        await page.wait_for_timeout(250)

        is_enabled = await reveal_btn.evaluate("(btn) => !btn.disabled")

        if not is_enabled:
            log(f"[attempt {attempt}] still disabled after mouse move, dispatching raw hover events...")
            await wrapper.dispatch_event("mouseenter")
            await wrapper.dispatch_event("mouseover")
            await page.wait_for_timeout(250)
            is_enabled = await reveal_btn.evaluate("(btn) => !btn.disabled")

        if is_enabled:
            log(f"[attempt {attempt}] button enabled")
            return reveal_btn

        log(f"[attempt {attempt}] still disabled")

        if asyncio.get_event_loop().time() >= deadline:
            raise PlaywrightTimeoutError(
                f"Reveal price button never enabled after {attempt} attempt(s)"
            )
        await page.wait_for_timeout(500)


async def extract_price_and_discount(page):
    """
    The real current price is split across individual leaf <span>
    elements inside .price-main .pv-k2 (deliberately hard to scrape as
    one text node). Only leaf spans (no span descendants) are read, so
    a digit wrapped in nested spans isn't double-counted. Other
    price-looking elements on this page (.price-value, .amount, .mr-k2)
    are decoys — hidden, struck-through, or not the live current price.
    """
    price_container = page.locator(".price-main .pv-k2")
    await price_container.wait_for(state="visible", timeout=10000)

    raw_price_str = await price_container.evaluate(
        """(el) => Array.from(el.querySelectorAll('span'))
                        .filter(s => s.querySelectorAll('span').length === 0)
                        .map(s => s.textContent.trim())
                        .filter(t => t.length > 0)
                        .join('')"""
    )
    log(f"raw price string from spans: {raw_price_str!r}")
    price = clean_price_string(raw_price_str)

    was_price = None
    was_locator = page.locator(".price-main .mr-k2")
    if await was_locator.count():
        was_text = await was_locator.inner_text()
        log(f"raw was-price string: {was_text!r}")
        was_price = clean_price_string(was_text)

    discount_pct = None
    badge_locator = page.locator(".price-main .bd-k2")
    if await badge_locator.count():
        # Same split-span risk as the price — read leaf spans if any exist,
        # else fall back to inner_text
        raw_badge_str = await badge_locator.evaluate(
            """(el) => {
                const leaves = Array.from(el.querySelectorAll('span'))
                    .filter(s => s.querySelectorAll('span').length === 0)
                    .map(s => s.textContent.trim())
                    .filter(t => t.length > 0);
                return leaves.length > 0 ? leaves.join('') : el.textContent.trim();
            }"""
        )
        log(f"raw discount badge string: {raw_badge_str!r}")
        match = re.search(r"(\d+)\s*%", raw_badge_str)
        discount_pct = int(match.group(1)) if match else None

    return {"price": price, "was_price": was_price, "discount_pct": discount_pct}


async def extract_stock(page):
    """Stock label lives in .stock-badge (e.g. 'HURRY, JUST 64 LEFT')."""
    badge = page.locator(".stock-badge")
    if not await badge.count():
        return {"in_stock": None, "stock_label": None, "stock_count": None}

    label = (await badge.inner_text()).strip()
    label_lower = label.lower()

    stock_count = None
    match = re.search(r"(\d+)\s+left", label_lower)
    if match:
        stock_count = int(match.group(1))

    if "out of stock" in label_lower or "sold out" in label_lower:
        in_stock = False
    else:
        in_stock = True

    return {"in_stock": in_stock, "stock_label": label, "stock_count": stock_count}


async def scrape_product(page, url: str) -> dict:
    """One full scrape attempt. Never returns success=True without a parsed price."""
    result = {
        "price": None, "was_price": None, "discount_pct": None,
        "in_stock": None, "stock_label": None, "stock_count": None,
        "success": False, "error": None,
    }
    try:
        log(f"navigating to {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await dismiss_cookie_banner(page)

        reveal_btn = await wait_for_reveal_button(page)
        await dismiss_cookie_banner(page)

        log("clicking 'Reveal price'...")
        await reveal_btn.click()
        await page.wait_for_timeout(2000)  # let price render + settle

        parsed = await extract_price_and_discount(page)
        if parsed["price"] is None:
            raise ValueError(f"Could not parse price from digit spans")

        stock = await extract_stock(page)

        result.update(parsed)
        result.update(stock)
        result["success"] = True
        log(f"SUCCESS price={result['price']} was={result['was_price']} "
            f"discount={result['discount_pct']}% stock={result['stock_label']}")

    except PlaywrightTimeoutError as e:
        result["error"] = f"Timeout: {e}"
        log(f"FAILED (timeout): {e}")
    except Exception as e:
        result["error"] = f"Error: {e}"
        log(f"FAILED (error): {e}")

    return result


async def single_debug_run(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=150)
        context = await browser.new_context()
        page = await context.new_page()
        data = await scrape_product(page, url)
        log(f"final result: {data}")
        await page.wait_for_timeout(3000)
        await browser.close()


async def poll_loop(url: str, interval_seconds: int = 5, headless: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=100 if not headless else 0)
        context = await browser.new_context()
        page = await context.new_page()

        run_count = 0
        try:
            while True:
                run_count += 1
                started = time.monotonic()
                log(f"--- Run #{run_count} ---")

                data = await scrape_product(page, url)
                elapsed = time.monotonic() - started
                log(f"run #{run_count} took {elapsed:.2f}s")

                sleep_for = max(0, interval_seconds - elapsed)
                await asyncio.sleep(sleep_for)

        except KeyboardInterrupt:
            log("stopped by user")
        finally:
            await browser.close()


if __name__ == "__main__":
    product_url = sys.argv[1] if len(sys.argv) > 1 else "https://demo.inelabteamdev.com/product/138"
    mode = sys.argv[2] if len(sys.argv) > 2 else "single"

    if mode == "loop":
        interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        asyncio.run(poll_loop(product_url, interval_seconds=interval, headless=False))
    else:
        asyncio.run(single_debug_run(product_url))
