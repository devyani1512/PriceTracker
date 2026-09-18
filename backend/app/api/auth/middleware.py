"""Token extraction helpers (≈ auth/middleware.go).

The DRF authentication class in ``authentication.py`` consumes these; keeping
the extraction separate makes it trivially testable and mirrors the Go layout.
"""

from __future__ import annotations


def extract_token(request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer ") :].strip()
        if token:
            return token
    return request.COOKIES.get("token")
