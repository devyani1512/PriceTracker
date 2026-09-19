"""Boot: initialise logging and load config (tomllib + env overrides)."""

from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.toml"

_TRUE = {"1", "true", "yes", "on"}


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else None


def _as_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in _TRUE


def _apply_env_overrides(cfg: dict) -> dict:
    """Environment beats TOML, exactly like the Go server (PORT, JWTKEY...)."""
    core = cfg.setdefault("Core", {})
    db = cfg.setdefault("DB", {})
    mail = cfg.setdefault("Email", {})
    sec = cfg.setdefault("Security", {})
    cors = cfg.setdefault("CORS", {})

    if v := _env("PORT"):
        core["port"] = v
    if v := _env("STOREFRONT_BASE"):
        core["storefrontBase"] = v
    if v := _env("HEADLESS"):
        core["headless"] = _as_bool(v)
    if v := _env("SELF_TICK"):
        core["selfTick"] = _as_bool(v)
    # MAX_TRACK_THREADS is retired: concurrency is now split across two lanes.
    # It is intentionally ignored so a stale value cannot re-enable high
    # concurrency; set MANUAL_TRACK_THREADS / SCHEDULED_TRACK_THREADS instead.
    if v := _env("MANUAL_TRACK_THREADS"):
        core["manualTrackThreads"] = int(v)
    if v := _env("SCHEDULED_TRACK_THREADS"):
        core["scheduledTrackThreads"] = int(v)
    if v := _env("SCRAPE_MAX_ATTEMPTS"):
        core["scrapeMaxAttempts"] = int(v)
    if v := _env("SCRAPE_TIMEOUT_MS"):
        core["scrapeTimeoutMs"] = int(v)
    if v := _env("CATALOG_BUDGET_SECONDS"):
        core["catalogBudgetSeconds"] = float(v)
    if v := _env("CATALOG_MIN_INTERVAL_MS"):
        core["catalogMinIntervalMs"] = int(v)
    if v := _env("MIN_REFRESH_MINUTES"):
        core["minRefreshMinutes"] = int(v)
    if v := _env("DEFAULT_REFRESH_MINUTES"):
        core["defaultRefreshMinutes"] = int(v)
    if v := _env("ALLOWED_REFRESH_MINUTES"):
        core["allowedRefreshMinutes"] = [int(m.strip()) for m in v.split(",") if m.strip()]
    if v := _env("HISTORY_MAX_POINTS"):
        core["historyMaxPoints"] = int(v)
    if v := _env("CRON_INLINE_BUDGET_SECONDS"):
        core["cronInlineBudgetSeconds"] = float(v)

    if v := _env("DATABASE_URL"):
        db["url"] = v
    if v := _env("DB_HOST"):
        db["host"] = v
    if v := _env("DB_PORT"):
        db["port"] = int(v)
    if v := _env("DB_USER"):
        db["user"] = v
    if v := _env("DB_PASSWORD"):
        db["password"] = v
    if v := _env("DB_NAME"):
        db["dbname"] = v

    if v := _env("EMAIL_PROVIDER"):
        mail["provider"] = v.strip().lower()
    if v := _env("EMAIL_API_KEY"):
        mail["apiKey"] = v
    # Provider-specific key names are accepted too, and infer the provider.
    for key_env, provider in (
        ("BREVO_API_KEY", "brevo"),
        ("SENDGRID_API_KEY", "sendgrid"),
        ("RESEND_API_KEY", "resend"),
    ):
        if v := _env(key_env):
            mail["apiKey"] = v
            if not _env("EMAIL_PROVIDER"):
                mail["provider"] = provider
    if v := _env("SMTP_HOST"):
        mail["host"] = v
    if v := _env("SMTP_PORT"):
        mail["port"] = int(v)
    if v := _env("SMTP_USER"):
        mail["user"] = v
    if v := _env("SMTP_APP_PASSWORD"):
        mail["appPassword"] = v
    if v := _env("SMTP_FROM"):
        mail["fromAddr"] = v
    if v := _env("SMTP_FROM_NAME"):
        mail["fromName"] = v

    if v := _env("JWTKEY"):
        sec["jwtKey"] = v
    if v := _env("CRON_SECRET"):
        sec["cronSecret"] = v
    if v := _env("CORS_ORIGINS"):
        cors["allowOrigins"] = [o.strip() for o in v.split(",") if o.strip()]
    if v := _env("CORS_ORIGIN_REGEXES"):
        cors["allowOriginRegexes"] = [o.strip() for o in v.split(",") if o.strip()]

    return cfg


def _defaults(cfg: dict) -> dict:
    """Fill critical secrets with sane local-dev defaults only when empty."""
    sec = cfg.setdefault("Security", {})
    if not sec.get("jwtKey"):
        logging.getLogger("pricetracker").warning(
            "JWTKEY not set — using insecure development key"
        )
        sec["jwtKey"] = "dev-insecure-jwt-key"
    if not sec.get("cronSecret"):
        sec["cronSecret"] = "dev-cron-secret"
    mail = cfg.setdefault("Email", {})
    if not mail.get("fromAddr"):
        mail["fromAddr"] = mail.get("user") or "noreply@pricetracker.local"
    return cfg


def initialize_app() -> dict:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger("pricetracker")
    logger.info("Logger initialized")

    # Load backend/.env for local dev without overriding real environment
    # variables (Render/Supabase secrets always win).
    if _load_dotenv():
        logger.info("Loaded .env")

    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)
    cfg = _apply_env_overrides(cfg)
    cfg = _defaults(cfg)
    logger.info(
        "Config initialized (storefront=%s, selfTick=%s)",
        cfg["Core"]["storefrontBase"],
        cfg["Core"]["selfTick"],
    )
    return cfg


def _load_dotenv() -> bool:
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent / ".env"
        return bool(load_dotenv(env_path, override=False))
    except Exception:
        return False
