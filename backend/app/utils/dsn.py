"""Parse a Postgres DSN into Django DATABASES settings, with clear failures.

Supabase hands out URIs containing a literal ``[YOUR-PASSWORD]`` placeholder and
passwords sometimes contain characters that must be percent-encoded. Bad input
should fail with an actionable message, not a cryptic ``urlparse`` traceback.

Pooler awareness: Supabase's Supavisor pooler in **transaction** mode (port
6543) multiplexes many short-lived clients over a handful of server connections,
so bursts no longer exhaust the small session pool. That only works if the
client doesn't rely on session state, so for pooler hosts we close connections
after each request and disable psycopg's automatic prepared statements. Direct
connections keep the previous (reuse for 60s) behaviour.
"""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

_TRUE = {"1", "true", "yes", "on"}


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_pooler_host(host: str | None, port: str | int | None) -> bool:
    """True for a Supabase/Supavisor pooler host or the transaction-mode port."""
    name = (host or "").lower()
    return "pooler" in name or str(port or "") == "6543"


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

    host = parsed.hostname or ""
    port = str(parsed.port or "")
    pooled = is_pooler_host(host, port)

    # A pooler in transaction mode must not hold idle server sessions, so default
    # to closing each connection after a request. Direct connections can reuse.
    conn_max_age = _env_int("DB_CONN_MAX_AGE")
    if conn_max_age is None:
        conn_max_age = 0 if pooled else 60

    options: dict = {"connect_timeout": 10}
    disable_prepared = pooled or os.getenv(
        "DB_DISABLE_PREPARED_STATEMENTS", ""
    ).lower() in _TRUE
    if disable_prepared:
        # psycopg3 auto-prepares statements after a few executions; a transaction
        # pooler can't guarantee the next execution lands on the same backend.
        options["prepare_threshold"] = None

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/") or "postgres",
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": conn_max_age,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }
