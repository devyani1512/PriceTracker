# Playwright's official image already contains Chromium and all system deps,
# which is the reliably reproducible way to run a headless browser on Render.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

# uv for dependency management (matches local dev).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Install deps first for better layer caching.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

# Migrate, then serve the ASGI app (the lifespan hook starts the core).
CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT:-8080}"]
