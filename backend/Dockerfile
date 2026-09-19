# Playwright's official image already contains Chromium and all system deps,
# which is the reliably reproducible way to run a headless browser on Render.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

# uv for dependency management (matches local dev).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=3.13 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Install deps first for better layer caching. Copy .python-version too so uv
# builds the venv on 3.13 (the version the lockfile was resolved for) rather
# than whatever Python happens to ship in the base image.
COPY pyproject.toml uv.lock* .python-version ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

# Migrate, then serve the ASGI app (the lifespan hook starts the core).
# Migrations run against DIRECT_DATABASE_URL when set (a direct/Supabase session
# connection), because DDL is happier on a real session than a transaction
# pooler. The app itself always uses DATABASE_URL.
CMD ["sh", "-c", "(DATABASE_URL=\"${DIRECT_DATABASE_URL:-$DATABASE_URL}\" python manage.py migrate --noinput) && uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT:-8080}"]
