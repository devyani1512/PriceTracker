"""Parse a Postgres DSN into Django DATABASES settings, with clear failures.

Supabase hands out URIs containing a literal ``[YOUR-PASSWORD]`` placeholder and
passwords sometimes contain characters that must be percent-encoded. Bad input
should fail with an actionable message, not a cryptic ``urlparse`` traceback.
"""

from __future__ import annotations

from urllib.parse import unquote, urlparse


def parse_database_url(raw: str) -> dict:
    url = (raw or "").strip().strip('"').strip("'")
    if not url:
        raise ValueError("DATABASE_URL is empty")

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if "[YOUR-PASSWORD]" in url.upper():
        raise ValueError(
            "DATABASE_URL still contains the [YOUR-PASSWORD] placeholder. Replace it "
            "with the real Supabase database password."
        )

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError(
            "Could not parse DATABASE_URL. Special characters in the password must be "
            "percent-encoded (@ -> %40, [ -> %5B, ] -> %5D, # -> %23, / -> %2F)."
        ) from exc

    if not parsed.hostname:
        raise ValueError(
            "DATABASE_URL has no host. Expected "
            "postgresql://user:password@host:port/dbname"
        )

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/") or "postgres",
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 10},
    }
