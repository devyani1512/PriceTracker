# Deployment

Targets: **Vercel** (frontend), **Render** (backend), **Supabase** (PostgreSQL),
and **cron-job.org** (free) to drive scheduled scrapes because Render's free
tier sleeps. A paid Render Cron Job is documented as an alternative — see
[Scheduling](#4-scheduling).

---

## 1. Supabase (database)

1. Create a project at <https://supabase.com>.
2. Project settings → Database → **Connection string**. Copy two URIs:
   - **`DATABASE_URL` — transaction pooler, port `6543`:**
     `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`
     This is what the app uses. Supavisor multiplexes many short-lived clients
     over a few server connections, so request bursts don't exhaust it.
   - **`DIRECT_DATABASE_URL` (optional) — session pooler or direct, port `5432`:**
     used only for `migrate` at container start. DDL is happiest on a real
     session.
3. Tables are created by Django migrations. They run automatically at container
   start (`python manage.py migrate`) and locally via `make migrate`. To inspect
   data, use the Supabase table editor or the Django admin at `/django-admin/`.

> **Why not the session pooler on `:5432`?** Supavisor session mode pins one
> server connection per client and caps at `pool_size` (15 on the free tier).
> Django opens one connection per database-touching thread, so a few concurrent
> requests plus background workers hit `(EMAXCONNSESSION) max clients reached`.
> The transaction pooler avoids that. For pooler hosts the app sets
> `CONN_MAX_AGE=0` and disables psycopg's prepared statements, both of which are
> required for transaction-mode pooling. Override with `DB_CONN_MAX_AGE` /
> `DB_DISABLE_PREPARED_STATEMENTS` if needed.

> Django accepts the Supabase URI as-is; `postgres://` is normalised to
> `postgresql://` for you.

## 2. Render (backend)

Option A — blueprint:

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. `render.yaml` provisions the
   Docker web service.
3. Fill the `sync: false` env vars: `DATABASE_URL`, `DIRECT_DATABASE_URL`,
   `CORS_ORIGINS`, `EMAIL_API_KEY`, `SMTP_FROM`.

Option B — manual:

1. New → **Web Service** → repo → Runtime **Docker**.
2. Dockerfile path `backend/Dockerfile`, context `backend`.
3. Health check path `/health`.
4. Set the same env vars.

Important env vars:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | Supabase **transaction** pooler URI (`:6543`) |
| `DIRECT_DATABASE_URL` | optional direct/session URI (`:5432`) for migrations |
| `JWTKEY` | long random string |
| `CRON_SECRET` | long random string |
| `CORS_ORIGINS` | `https://<your-vercel-app>.vercel.app` |
| `DJANGO_DEBUG` | `false` |
| `ALLOWED_HOSTS` | `.onrender.com` |
| `SELF_TICK` | `false` (external cron drives ticks) |
| `MANUAL_TRACK_THREADS` | `1` (user "Refresh" lane) |
| `SCHEDULED_TRACK_THREADS` | `1` (scheduled lane; memory stays flat) |
| `CRON_INLINE_BUDGET_SECONDS` | `25` (under cron-job.org's 30s timeout) |
| `EMAIL_PROVIDER` | `brevo` (Render blocks SMTP) |
| `EMAIL_API_KEY` | Brevo/SendGrid/Resend API key |
| `SMTP_FROM` | verified sender address |
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
a tick enqueues what is due, and the background scheduled workers drain it.
Anything left over stays queued for the next tick, and a lease reclaims work if
the instance sleeps mid-run. We use **cron-job.org** because it is free.

### cron-job.org (free, recommended)

cron-job.org allows unlimited jobs on fair use, with a **1-minute minimum
interval** and a **30-second request timeout** on the free plan. `/cron/tick`
is **fire-and-forget**: it enqueues due work, wakes the workers, and returns in
well under a second, so the scheduler never times out. The workers then scrape
in the background while the instance is awake.

Create two jobs:

1. **Scrape tick** — every 10 minutes:
   - URL: `https://<your-render-service>.onrender.com/cron/tick`
   - Method: `POST`
   - Header: `X-Cron-Secret: <CRON_SECRET>` (the value Render generated)
   - The response is a tiny JSON summary of what was enqueued. Work continues
     after the response; unfinished tasks are picked up by the workers or the
     next tick.
2. **Alert dispatch** (optional) — every 30 minutes:
   - URL: `https://<your-render-service>.onrender.com/cron/notify`
   - Method: `POST`
   - Header: `X-Cron-Secret: <CRON_SECRET>`

Notes for the free tier:

- Render spins a free instance down after ~15 minutes without traffic. The cron
  pings it every 10 minutes, which keeps it warm in practice. The first request
  after a cold start can still be slow while the container boots; enable
  **Retry on failure** if available — **no scheduled work is lost** because the
  queue is durable.
- For a synchronous drain (debugging, or a one-shot runner), call
  `/cron/tick?drain=true`; it then waits up to `CRON_INLINE_BUDGET_SECONDS`.
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

## 5. Email alerts

**Render's free plan blocks outbound SMTP** (ports 25, 465, 587), so Gmail SMTP
fails there with `[Errno 101] Network is unreachable`. On Render, send over an
HTTPS email API instead. Locally, plain SMTP still works.

### Render — Brevo (free, single-sender, no domain required)

1. Create a free account at <https://www.brevo.com>.
2. **Senders, Domains & Dedicated IPs → Senders** → add and verify the From
   address you want to send from.
3. **SMTP & API → API Keys** → create a key and copy it.
4. Set these env vars on the web service:
   - `EMAIL_PROVIDER=brevo`
   - `EMAIL_API_KEY=<the API key>`
   - `SMTP_FROM=<the verified sender address>`
   - `SMTP_FROM_NAME=Price Tracker` (optional)

SendGrid (`EMAIL_PROVIDER=sendgrid`) and Resend (`EMAIL_PROVIDER=resend`) are
also supported; they use the same `EMAIL_API_KEY` / `SMTP_FROM` vars.

> Provider-specific key names (`BREVO_API_KEY`, `SENDGRID_API_KEY`,
> `RESEND_API_KEY`) are accepted too, and infer the provider automatically.

### Local development — Gmail SMTP

1. Enable 2-step verification on the Google account.
2. Google Account → Security → **App passwords** → create one.
3. Set `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM`.

If email is unconfigured (or a provider key is missing), the backend logs a
dry-run and marks the notification sent, so the pipeline can be exercised
without credentials.
