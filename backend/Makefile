.PHONY: install sync browsers migrate makemigrations run dev cron catalog scrape test lint fmt stats docker

install:
	uv sync

sync:
	uv sync

browsers:
	uv run playwright install chromium

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

run:
	uv run uvicorn config.asgi:application --host 0.0.0.0 --port 8080

dev:
	uv run uvicorn config.asgi:application --reload --port 8080

cron:
	uv run python manage.py cron

catalog:
	uv run python manage.py catalog

scrape:
	uv run python manage.py scrape 138 --headed

test:
	uv run pytest -v

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

checkmigrations:
	uv run python manage.py makemigrations --check --dry-run

stats:
	find . -name '*.py' -not -path './.venv/*' | xargs wc -l

docker:
	docker build -t price-tracker-backend .
