"""Pure parsing helpers for storefront text. No I/O, easy to unit test."""

from __future__ import annotations

import re

_CURRENCY_SYMBOLS = {
    "₹": "INR",
    "Rs.": "INR",
    "INR": "INR",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}


def clean_price_string(raw: str | None) -> float | None:
    """Convert a concatenated price string ('₹9,452', '9,452.50') to float.

    Comma = thousands separator (Indian/US convention). A dot is only a decimal
    point if followed by exactly 1-2 digits at the very end; anything else is
    treated as noise from split spans.
    """
    if not raw:
        return None

    cleaned = re.sub(r"[^\d.,]", "", raw)
    cleaned = cleaned.replace(",", "")

    decimal_match = re.search(r"\.(\d{1,2})$", cleaned)
    if decimal_match:
        integer_part = cleaned[: decimal_match.start()].replace(".", "")
        if not integer_part:
            return None
        return float(f"{integer_part}.{decimal_match.group(1)}")

    digits_only = cleaned.replace(".", "")
    return float(digits_only) if digits_only else None


def detect_currency(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        for symbol, code in _CURRENCY_SYMBOLS.items():
            if symbol in text:
                return code
    return None


def parse_discount_pct(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d+)\s*%", raw)
    return int(match.group(1)) if match else None


def parse_stock_label(label: str | None) -> tuple[bool | None, int | None]:
    """Return (in_stock, stock_count) from a label like 'HURRY, JUST 64 LEFT'."""
    if label is None:
        return None, None
    label = label.strip()
    if not label:
        return None, None

    lowered = label.lower()
    count_match = re.search(r"(\d+)\s+(left|in stock)", lowered)
    stock_count = int(count_match.group(1)) if count_match else None

    if "out of stock" in lowered or "sold out" in lowered:
        return False, stock_count
    return True, stock_count
