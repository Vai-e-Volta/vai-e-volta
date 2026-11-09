.PHONY: up down reset run-backend lint-backend lint-frontend lint test-backend test-frontend test openapi

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build

run-backend:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-frontend:
ifeq ($(wildcard frontend/package.json),)
	@echo "Frontend ainda nao existe; lint-frontend ignorado."
else
	cd frontend && npm run lint && npm run format:check
endif

lint: lint-backend lint-frontend

test-backend:
	uv run --project backend python scripts/run_backend_tests.py

test-frontend:
ifeq ($(wildcard frontend/package.json),)
	@echo "Frontend ainda nao existe; test-frontend ignorado."
else
	cd frontend && npm test -- --coverage
endif

test: test-backend test-frontend

openapi:
	cd backend && uv run python -m app.scripts.export_openapi > ../docs/openapi.json
