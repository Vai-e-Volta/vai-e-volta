.PHONY: up down reset run-backend lint-backend lint-frontend lint test-backend test-frontend test seed backup restore openapi

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v && docker compose up -d --build

run-backend:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-frontend:
	cd frontend && npm run lint && npm run format:check

lint: lint-backend lint-frontend

test-backend:
	cd backend && uv run pytest --cov=app --cov-report=xml

test-frontend:
	cd frontend && npm test -- --coverage

test: test-backend test-frontend

seed:
	docker compose exec backend python -m app.scripts.seed_dev

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh $(DIR)

openapi:
	cd backend && uv run python -m app.scripts.export_openapi > ../docs/openapi.json
