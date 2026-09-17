.PHONY: help dev backend frontend test lint format docker-up docker-down logs install

PYTHON ?= python
PIP ?= pip
NPM ?= npm

help:
	@echo "TradeBay development commands"
	@echo "  make install      Install backend and frontend dependencies"
	@echo "  make dev          Run backend + frontend locally (requires MongoDB)"
	@echo "  make backend      Run FastAPI with reload"
	@echo "  make frontend     Run Next.js dev server"
	@echo "  make test         Run backend tests"
	@echo "  make lint         Lint backend and frontend"
	@echo "  make format       Format backend and frontend"
	@echo "  make typecheck    MyPy + TypeScript"
	@echo "  make docker-up    Start Compose stack"
	@echo "  make docker-down  Stop Compose stack"
	@echo "  make logs         Tail Compose logs"

install:
	cd backend && $(PIP) install -e ".[dev]"
	cd frontend && $(NPM) install

dev:
	@echo "Start MongoDB first (docker compose up mongodb -d), then backend + frontend."
	@echo "Use two terminals: make backend  |  make frontend"

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && $(NPM) run dev

test:
	cd backend && pytest

lint:
	cd backend && ruff check .
	cd frontend && $(NPM) run lint

format:
	cd backend && ruff format . && ruff check --fix .
	cd frontend && $(NPM) run lint -- --fix

typecheck:
	cd backend && mypy app
	cd frontend && $(NPM) run typecheck

docker-up:
	docker compose up --build

docker-down:
	docker compose down

logs:
	docker compose logs -f
