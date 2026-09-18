"""Small HTTP helpers shared by the fetchers."""

from __future__ import annotations


def retry_after(response, attempt: int, default_cap: float = 8.0) -> float:
    """Seconds to wait after a 429: honour Retry-After, else exponential-ish."""
    header = response.headers.get("Retry-After") if response is not None else None
    if header:
        try:
            return max(0.2, float(header))
        except ValueError:
            pass
    return min(1.0 * attempt, default_cap)
