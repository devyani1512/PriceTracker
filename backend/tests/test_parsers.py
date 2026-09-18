"""Pure-function tests for the parsers (no DB / browser needed)."""

from __future__ import annotations

from app.core.track.parsers import (
    clean_price_string,
    detect_currency,
    parse_discount_pct,
    parse_stock_label,
)


def test_clean_price_with_symbol_and_commas():
    assert clean_price_string("₹9,452") == 9452.0


def test_clean_price_with_decimals():
    assert clean_price_string("9,452.50") == 9452.5


def test_clean_price_with_single_decimal():
    assert clean_price_string("₹1,299.9") == 1299.9


def test_clean_price_strips_junk_dots():
    # A dot followed by 3+ digits is not a decimal point; it is dropped.
    assert clean_price_string("9.452") == 9452.0
    assert clean_price_string("1.2.3,456") == 123456.0


def test_clean_price_none_and_empty():
    assert clean_price_string(None) is None
    assert clean_price_string("") is None
    assert clean_price_string("₹") is None


def test_detect_currency():
    assert detect_currency("₹9,452") == "INR"
    assert detect_currency(None, "$10") == "USD"
    assert detect_currency("nothing") is None


def test_parse_discount_pct():
    assert parse_discount_pct("23% off") == 23
    assert parse_discount_pct("no discount") is None


def test_parse_stock_label():
    assert parse_stock_label("HURRY, JUST 64 LEFT") == (True, 64)
    assert parse_stock_label("Out of stock") == (False, None)
    assert parse_stock_label("Only 3 left") == (True, 3)
    assert parse_stock_label("Selling fast — 12 left") == (True, 12)
