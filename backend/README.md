# Price Tracker backend

Django 5 + Django REST Framework service, structured like the reference repo
map (`api → services → internal/postgresql`, with `core` running on its own).

## Quick start

```bash
cp .env.example .env
uv sync
uv run playwright install chromium
uv run python manage.py migrate
uv run uvicorn config.asgi:application --reload --port 8080   # http://localhost:8080
```

Local Postgres comes from the repo-level `docker-compose.yml`
(`make up` from the repo root). `backend/.env` is loaded automatically and never
overrides real environment variables.

> Use `uvicorn config.asgi:application` rather than `manage.py runserver` for
> local work: the ASGI lifespan hook starts the background core (catalog sync,
> scheduler, self-tick). `runserver` serves HTTP but not the background workers.

## Commands

```bash
uv run python manage.py migrate                 # apply migrations
uv run python manage.py makemigrations app      # after model changes
uv run python manage.py check                   # Django system checks
uv run python manage.py cron [--force] [--no-scrape]
uv run python manage.py catalog                 # force catalog sync
uv run python manage.py scrape 138 --headed     # observable run
uv run pytest -q && uv run ruff check .         # tests + lint
```

## Key modules

| Path | Role |
| --- | --- |
| `config/settings.py` | Django settings derived from `boot/config.toml` + env |
| `config/asgi.py` | ASGI app + lifespan hook that boots the core once |
| `app/core/track/scraper.py` | Playwright flow: challenge, hover, reveal, parse |
| `app/core/track/core.py` | bounded thread pool + persistence of runs/logs |
| `app/core/cron/core.py` | slot alignment, snapshot reuse, due work |
| `app/core/catalog.py` | throttled, 429-aware catalog sync |
| `app/core/bootstrap.py` | lazy core/services singletons |
| `app/services/*` | user, product, tracker, notification logic |
| `app/internal/postgresql/*` | one query file per entity (Django ORM) |
| `app/api/*` | DRF views + URL routes |

All timestamps are UTC. Cron slots are aligned to 00:00 UTC plus the tracker's
interval. Background threads refresh Django connections with
`close_old_connections()` before doing work.
