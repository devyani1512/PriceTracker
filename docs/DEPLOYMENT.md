# Deployment

Targets: **Vercel** (frontend), **Render** (backend), **Supabase** (PostgreSQL),
and **cron-job.org** (free) to drive scheduled scrapes because Render's free
tier sleeps. A paid Render Cron Job is documented as an alternative — see
[Scheduling](#4-scheduling).

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
| `MANUAL_TRACK_THREADS` | `1` (user "Refresh" lane) |
| `SCHEDULED_TRACK_THREADS` | `1` (scheduled lane; memory stays flat) |
| `CRON_INLINE_BUDGET_SECONDS` | `25` (under cron-job.org's 30s timeout) |
| `STOREFRONT_BASE` | `https://demo.inelabteamdev.com` |

The Docker image is based on `mcr.microsoft.com/playwright/python`, so Chromium
and its system libraries are already present.

## 3. Vercel (frontend)

1. New Project → import the repo.
2. **Root directory**: `frontend`.
3. Framework preset: Vite. Build `pnpm build`, output `dist`.
4. Env var `VITE_API_URL=https://<your-render-service>.onrender.com`.
5. Deploy. `frontend/vercel.json` rewrites all routes to `index.html` for the SPA.

## 4. Scheduling

Scheduled work is durable (a `tasks` table), so the driver is interchangeable:
a tick enqueues what is due, then drains it for a bounded time. Anything left
over stays queued for the next tick, and a lease reclaims work if the instance
sleeps mid-run. We use **cron-job.org** because it is free.

### cron-job.org (free, recommended)

cron-job.org allows unlimited jobs on fair use, with a **1-minute minimum
interval** and a **30-second request timeout** on the free plan. `render.yaml`
sets `CRON_INLINE_BUDGET_SECONDS=25` so a tick finishes under that timeout.

Create two jobs:

1. **Scrape tick** — every 10 minutes:
   - URL: `https://<your-render-service>.onrender.com/cron/tick`
   - Method: `POST`
   - Header: `X-Cron-Secret: <CRON_SECRET>` (the value Render generated)
   - Enable **Retry on failure** if available. The endpoint enqueues every due
     product and drains the queue inline for up to 25s, then returns. Unfinished
     tasks are picked up by the in-process scheduled workers and the next tick.
2. **Alert dispatch** (optional) — every 30 minutes:
   - URL: `https://<your-render-service>.onrender.com/cron/notify`
   - Method: `POST`
   - Header: `X-Cron-Secret: <CRON_SECRET>`

Notes for the free tier:

- Render spins a free instance down after ~15 minutes without traffic. The cron
  pings it every 10 minutes, which keeps it warm in practice; the first request
  after a cold start can exceed 30s, so treat an occasional timeout as expected
  and rely on the retry/next tick — **no scheduled work is lost**.
- If you want the request to return instantly instead of draining inline, add
  `?drain=false`; the background scheduled workers still process the queue.
- `GET /cron/status` (same header) returns the pending and due task counts, so
  you can confirm the queue is draining. `POST /cron/tick?force=true` bypasses
  snapshot reuse for a debugging re-scrape.

### Alternative — Render Cron Job (paid)

If you would rather keep everything inside Render, add a `type: cron` service
that runs the one-shot drainer instead of `/cron/tick`:

```yaml
- type: cron
  name: price-tracker-jobs
  runtime: docker
  plan: 1c-2g                 # Chromium needs headroom
  region: singapore
  schedule: "*/10 * * * *"
  dockerfilePath: ./backend/Dockerfile
  dockerContext: ./backend
  dockerCommand: sh -c "python manage.py migrate --noinput && python manage.py run_jobs --budget 240"
  envVars:
    - key: DATABASE_URL
      fromService: { name: price-tracker-backend, type: web, envVarKey: DATABASE_URL }
    # ... STOREFRONT_BASE, HEADLESS, SELF_TICK=false, SMTP_*
```

Each run boots a fresh container, drains the queue, and exits. Render Cron Jobs
require a paid plan (prorated, ~$1/month minimum), which is why cron-job.org is
the default here.

### Local dev — in-process ticker

`SELF_TICK=true` (the default outside Render) runs a tick every `tickSeconds`.
Never enable this on the free Render web service.

## 5. Gmail app password (email alerts)

1. Enable 2-step verification on the Google account.
2. Create an **App password** (Google Account → Security → App passwords).
3. Set `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM`.
4. If SMTP is unset the backend logs the email as a dry-run and marks the
   notification sent, so the pipeline can be exercised without credentials.
