# Price Tracker

Track prices and stock for products in INE's hosted mock store. Users search the
storefront, pick a product, and the backend scrapes its current price and stock
on a schedule, storing history and an honest per-product scrape log.

- **Frontend** — React + TypeScript + Vite, Notion-style monochrome UI (`frontend/`)
- **Backend** — Django 5 + Django REST Framework + Playwright (`backend/`)
- **Database** — PostgreSQL locally via Docker, Supabase in production
- **Scheduling** — external cron → `POST /cron/tick` (free tiers sleep)

---

## The awkward storefront (the actual challenge)

`https://demo.inelabteamdev.com` is deliberately hostile to scrapers:

| Obstacle | How we handle it |
| --- | --- |
| It is a React SPA — raw HTML is a 459-byte shell | Playwright drives a real browser for price/stock |
| Price is behind `/api/challenge` + browser fingerprint + **WebAssembly proof-of-work** + hover attestation | Real mouse moves (≥8, spaced >40 ms), ≥700 ms dwell, then a trusted click |
| Price is split across leaf `<span>`s; decoys `.price-value`/`.amount` are hidden | Read leaf spans of `.price-main .pv-k2` only, joined and parsed |
| Layout class names rotate | Read live classes from `/api/layout` (fallback to defaults) |
| Slow / async / transient errors | Wait for an explicit terminal state, fresh page per attempt, exponential backoff, 3 attempts |
| Page structure may change | Only flag `structureChanged` if **all** attempts fail structurally; record the layout revision |
| Catalog is randomised + rate-limited (429) | Throttled fetcher, `Retry-After` backoff, paged collection + direct-id top-up |
| Multiple users, different cadences | One shared snapshot per product per slot; a 2-hour tracker reuses the 10-minute runs |

### Scheduled scraping

Every tracker is aligned to a grid based at **00:00 UTC** using its own interval
(minimum 10 minutes, default 2 hours). On each tick the cron core groups due
trackers by product, reuses a snapshot already captured inside the current slot
window if one exists, and otherwise triggers **one** scrape for that product.
Changing a tracker's cadence deletes that user's history rows (shared snapshots
are untouched).

---

## Features

Core:

- Search by partial/full product name; browse the catalog
- Add/remove trackers; configurable cadence per product
- Scheduled scraping with retries and shared snapshots
- Price & stock history (chart + table)
- Per-product scrape log: every attempt with timestamp, outcome
  (`success` / `retried` / `failed`), duration and error
- Headed (observable) run via the CLI

Bonus:

- Price-drop and back-in-stock alerts, in-app and by email (Gmail SMTP)
- Cross-product dashboard with change flags
- Page-structure change detection via layout revision + selector checks
- Configurable refresh frequency per product
- CI/CD with GitHub Actions

---

## Local setup

```bash
make up          # start Postgres 17 on :5432
make install     # uv sync (backend) + pnpm install (frontend)
make browsers    # download Chromium for Playwright

cp backend/.env.example backend/.env   # then edit if needed
```

Run each side:

```bash
make backend     # http://localhost:8080
make frontend    # http://localhost:5173
```

Open <http://localhost:5173>, register a user, search a product, and track it.

### Observable (headed) run

```bash
cd backend
uv run python manage.py scrape 138 --headed          # watch one scrape
xvfb-run -a uv run python manage.py scrape 138 --headed   # headless Linux box
uv run python manage.py scrape 138 --repeat 3 --interval 15 --headed
```

### Other management commands

```bash
cd backend
uv run python manage.py migrate     # apply migrations
uv run python manage.py cron        # one cron pass
uv run python manage.py catalog     # force a full catalog sync
uv run python manage.py runserver   # plain Django dev server (no background core)
```

> For local development use `uv run uvicorn config.asgi:application --reload`
> (or `make dev`) so the ASGI lifespan hook starts the background core.

---

## Tests

```bash
cd backend && uv run pytest -q && uv run ruff check . && uv run python manage.py check
cd frontend && pnpm build
```

---

## API reference

Public:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/user/register`, `/user/login` | email + password → JWT |
| GET | `/user/me` | current user |
| GET | `/product/search?q=&page=&pageSize=` | search by name/brand/sku |
| GET | `/product/list?page=&pageSize=` | browse the catalog |
| GET | `/product/{id}?ensurePrice=` | detail (+ trigger first scrape) |
| GET | `/product/{id}/logs` | per-product scrape log |
| GET | `/catalog/status` | catalog sync progress |
| GET | `/health` | health + DB + catalog status |

Authenticated (Bearer token):

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/tracker/add` | track a product |
| GET | `/tracker/list`, `/tracker/{id}` | list / fetch trackers |
| PATCH | `/tracker/{id}` | cadence + alert settings |
| DELETE | `/tracker/{id}` | untrack |
| GET | `/tracker/{id}/history` | price & stock history |
| GET | `/tracker/{id}/logs` | scrape log for a tracker |
| GET | `/dashboard` | cross-product dashboard |
| POST | `/notification/subscribe` | "email me when back in stock" |
| GET | `/notification/list` | alert feed |

Cron/admin (header `X-Cron-Secret`):

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/cron/tick` | run due scheduled scrapes |
| POST | `/cron/notify` | dispatch pending alert emails |
| POST | `/admin/catalog/sync` | force a catalog sync |

---

## Project layout

```
price_tracker/
├── backend/                     # Django service (≈ Go repo map)
│   ├── manage.py                # Django entrypoint
│   ├── config/                  # settings / urls / asgi / wsgi
│   ├── boot/                    # logging + config (tomllib + env)
│   └── app/
│       ├── api/                 # DRF views + urls; auth/jwt.py + middleware.py
│       ├── services/            # business logic (user/product/tracker/notification)
│       ├── internal/postgresql/ # one query file per entity (Django ORM)
│       ├── entity/              # Django models
│       ├── core/                # track (Playwright), cron, scheduler, catalog
│       ├── management/          # cron / catalog / scrape commands
│       └── utils/               # idgen, time alignment, security, http
├── frontend/                    # React + Vite + Tailwind (Notion-style)
├── docs/DEPLOYMENT.md           # Vercel + Render + Supabase + cron-job.org
├── docker-compose.yml           # local Postgres 17
├── render.yaml                  # Render blueprint
└── .github/workflows/ci.yml     # CI
```

## Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). In short: Render runs the
Playwright-based Docker image, Vercel serves the SPA, Supabase provides
Postgres, and cron-job.org hits `/cron/tick` every 10 minutes.
