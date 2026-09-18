.PHONY: help up down backend frontend dev install browsers test lint fmt cron stats

help:
	@echo "Price Tracker"
	@echo "  make up        start local Postgres (docker compose)"
	@echo "  make install   install backend + frontend dependencies"
	@echo "  make browsers  install the Playwright Chromium used by the scraper"
	@echo "  make backend   run the API on :8080"
	@echo "  make frontend  run the Vite dev server on :5173"
	@echo "  make migrate   apply Django migrations"
	@echo "  make cron      run one cron tick from the CLI"
	@echo "  make test      run backend tests + frontend typecheck/build"

up:
	docker compose up -d db

down:
	docker compose down

install:
	cd backend && uv sync
	cd frontend && pnpm install

browsers:
	cd backend && uv run playwright install chromium

migrate:
	cd backend && uv run python manage.py migrate

backend:
	cd backend && uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8080

frontend:
	cd frontend && pnpm dev

dev:
	@echo "Run 'make backend' and 'make frontend' in two terminals."

test:
	cd backend && uv run pytest -q
	cd frontend && pnpm build

lint:
	cd backend && uv run ruff check .

fmt:
	cd backend && uv run ruff format .

cron:
	cd backend && uv run python manage.py cron

stats:
	cd backend && find . -name '*.py' -not -path './.venv/*' | xargs wc -l
