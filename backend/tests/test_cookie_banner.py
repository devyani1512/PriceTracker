"""The consent overlay needs 1-3 Accept clicks; one click leaves it blocking."""

from __future__ import annotations

import asyncio

from app.core.track.scraper import dismiss_cookie_banner


class _Locator:
    def __init__(self, page, key: str):
        self.page = page
        self.key = key

    async def count(self) -> int:
        if self.key in {"overlay", "accept"}:
            return 1 if self.page.counter > 0 else 0
        return 0

    @property
    def first(self):
        return self

    async def click(self, timeout: int | None = None) -> None:
        if self.key != "accept":
            raise RuntimeError("only the accept button is clickable")
        self.page.clicks += 1
        self.page.counter -= 1

    async def evaluate_all(self, script: str) -> None:
        self.page.neutralized = True


class _Page:
    def __init__(self, counter: int):
        self.counter = counter
        self.clicks = 0
        self.neutralized = False

    def locator(self, selector: str) -> _Locator:
        return _Locator(self, "overlay" if selector == ".cookie-overlay" else "fallback")

    def get_by_role(self, role: str, name: str | None = None) -> _Locator:
        return _Locator(self, "accept")

    async def wait_for_timeout(self, ms: int) -> None:
        return None


def test_absent_banner_returns_immediately():
    page = _Page(counter=0)

    assert asyncio.run(dismiss_cookie_banner(page)) is False
    assert page.clicks == 0


def test_single_click_banner_is_dismissed():
    page = _Page(counter=1)

    assert asyncio.run(dismiss_cookie_banner(page)) is True
    assert page.clicks == 1
    assert page.counter == 0


def test_multi_click_banner_keeps_clicking_until_gone():
    page = _Page(counter=3)

    assert asyncio.run(dismiss_cookie_banner(page)) is True
    assert page.clicks == 3
    assert page.counter == 0


def test_overlay_that_wont_unmount_is_neutralised():
    page = _Page(counter=99)  # more clicks than the loop budget

    assert asyncio.run(dismiss_cookie_banner(page)) is True
    assert page.clicks == 5  # bounded
    assert page.neutralized is True  # pointer events disabled so clicks pass through
