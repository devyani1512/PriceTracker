"""ScrapeResult serialization (phase timings are surfaced to the bench command)."""

from __future__ import annotations

from app.core.track.models import ScrapeAttempt, ScrapeResult


def test_as_dict_includes_timings_and_attempts():
    result = ScrapeResult(product_id=7, url="https://example.test/product/7")
    result.timings["a1.gotoMs"] = 120.0
    result.timings["browserStartMs"] = 480.0

    payload = result.as_dict()

    assert payload["productId"] == 7
    assert payload["timings"]["a1.gotoMs"] == 120.0
    assert payload["timings"]["browserStartMs"] == 480.0


def test_attempts_detail_is_not_serialized_but_kept():
    result = ScrapeResult(product_id=1, url="u")
    result.attempts_detail.append(ScrapeAttempt(attempt=1, success=True, duration_ms=5))

    assert "attemptsDetail" not in result.as_dict()
    assert result.attempts_detail[0].success is True
