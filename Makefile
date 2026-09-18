.PHONY: help setup up down install browsers migrate backend frontend dev test lint fmt cron stats push

help:
	@echo "Price Tracker"
	@echo "  make setup     one-time: .env, db, deps, Chromium, migrations"
	@echo "  make dev       run backend (:8080) + frontend (:5173) together"
	@echo "  make up/down   start/stop local Postgres"
	@echo "  make migrate   apply Django migrations"
	@echo "  make cron      run one cron tick from the CLI"
	@echo "  make test      backend tests + frontend build"
	@echo "  make push      commit everything and push (triggers Render + Vercel)"

setup:
	@test -f backend/.env || cp backend/.env.example backend/.env
	docker compose up -d db
	cd backend && uv sync
	cd backend && uv run playwright install chromium
	cd backend && uv run python manage.py migrate
	cd frontend && pnpm install
	@echo "Setup complete. Run 'make dev'."

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
	cd backend && uv run python manage.py migrate
	cd backend && uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8080

frontend:
	cd frontend && pnpm dev

dev:
	cd backend && uv run python manage.py migrate
	@echo "backend :8080  |  frontend :5173  (Ctrl-C stops both)"
	@trap 'kill 0' INT TERM; \
		(cd backend && uv run uvicorn config.asgi:application --port 8080) & \
		(cd frontend && pnpm dev)

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

push:
	git add -A
	git diff --cached --quiet || git commit -m "$${m:-Update}"
	git push
