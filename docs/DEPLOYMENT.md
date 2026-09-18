# Deployment

Targets: **Vercel** (frontend), **Render** (backend), **Supabase** (PostgreSQL),
plus **cron-job.org** to trigger scheduled scrapes because Render's free tier
sleeps.

---

## 1. Supabase (database)

1. Create a project at <https://supabase.com>.
2. Project settings → Database → **Connection string**. Copy the URI.
   - For a long-running Render service, the direct connection (`...:5432`) is fine.
   - If you use the pooler, the URI looks like
     `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`.
3. Tables are created by Django migrations. They run automatically at container
   start (`python manage.py migrate`) and locally via `make migrate`. To inspect
   data, use the Supabase table editor or the Django admin at `/django-admin/`.

> Django accepts the Supabase URI as-is; `postgres://` is normalised to
> `postgresql://` for you.

## 2. Render (backend)

Option A — blueprint:

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. `render.yaml` provisions the
   Docker web service.
3. Fill the `sync: false` env vars: `DATABASE_URL`, `CORS_ORIGINS`,
   `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM`.

Option B — manual:

1. New → **Web Service** → repo → Runtime **Docker**.
2. Dockerfile path `backend/Dockerfile`, context `backend`.
3. Health check path `/health`.
4. Set the same env vars.

Important env vars:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | Supabase URI |
| `JWTKEY` | long random string |
| `CRON_SECRET` | long random string |
| `CORS_ORIGINS` | `https://<your-vercel-app>.vercel.app` |
| `DJANGO_DEBUG` | `false` |
| `ALLOWED_HOSTS` | `.onrender.com` |
| `SELF_TICK` | `false` (external cron drives ticks) |
| `STOREFRONT_BASE` | `https://demo.inelabteamdev.com` |

The Docker image is based on `mcr.microsoft.com/playwright/python`, so Chromium
and its system libraries are already present.

## 3. Vercel (frontend)

1. New Project → import the repo.
2. **Root directory**: `frontend`.
3. Framework preset: Vite. Build `pnpm build`, output `dist`.
4. Env var `VITE_API_URL=https://<your-render-service>.onrender.com`.
5. Deploy. `frontend/vercel.json` rewrites all routes to `index.html` for the SPA.

## 4. cron-job.org (scheduling)

Render free instances sleep, so an external trigger is required.

Create two cron jobs:

1. **Scrape tick** — every 10 minutes:
   - URL: `https://<render>/cron/tick`
   - Method: `POST`
   - Header: `X-Cron-Secret: <CRON_SECRET>`
   - This aligns each tracker to its own cadence (default 2 hours, minimum
     10 minutes) and reuses shared snapshots so a product is scraped once per
     slot no matter how many users track it.

2. **Alert dispatch** (optional) — every 30 minutes:
   - URL: `https://<render>/cron/notify`
   - Header: `X-Cron-Secret: <CRON_SECRET>`

Any scheduler that can send a POST with a custom header works. If the request
exceeds the scheduler's timeout, reduce `cronBatchLimit` / raise the cron
frequency: each tick is idempotent and bounded by `cronBudgetSeconds`.

## 5. Gmail app password (email alerts)

1. Enable 2-step verification on the Google account.
2. Create an **App password** (Google Account → Security → App passwords).
3. Set `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM`.
4. If SMTP is unset the backend logs the email as a dry-run and marks the
   notification sent, so the pipeline can be exercised without credentials.
