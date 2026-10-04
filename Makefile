.DEFAULT_GOAL := help

COMPOSE := docker compose -f compose.yaml

.PHONY: help setup check-env up down restart logs ps test api-docs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env from the example if it does not exist
	@test -f .env || cp .env.example .env
	@test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
	@echo "Created local env files if needed. Fill in the Supabase settings before running make up."


check-env: ## Check required Supabase settings without printing their values
	@python3 scripts/check-env.py
	@docker info >/dev/null 2>&1 || (echo "Docker Desktop is not running."; exit 1)

up: check-env ## Build and start the API and web app
	$(COMPOSE) up --build -d
	@echo "Web:     http://localhost:5173"
	@echo "API:     http://localhost:8000"
	@echo "API docs: http://localhost:8000/docs"

down: ## Stop the app containers
	$(COMPOSE) down

restart: ## Restart app containers
	$(COMPOSE) restart

logs: ## Follow app logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show app container status
	$(COMPOSE) ps

test: ## Run the backend test suite
	@if test -x backend/.venv/bin/python; then cd backend && .venv/bin/python -m pytest -q; else $(COMPOSE) run --rm api python -m pytest -q; fi

api-docs: ## OpenAPI docs URL
	@echo http://localhost:8000/docs

CONTROL_PY := .control-venv/bin/python
.PHONY: control-setup control-demo control-test control-api control-preflight control-openjev-setup control-openjev

control-setup: ## Install locked control dependencies in a separate Python 3.13 environment (uv required)
	@test -x backend/$(CONTROL_PY) || uv venv --python 3.13 backend/.control-venv
	uv pip sync --python backend/$(CONTROL_PY) backend/requirements-control.txt

control-demo: control-setup ## Judge quick start: all five FICTIONAL cases, no keys/models/Supabase
	cd backend && $(CONTROL_PY) -m app.control_layer.demo --mode fixture --gate jev

control-test: control-setup ## Isolated control tests; no external inference/network
	cd backend && $(CONTROL_PY) -m pytest control_tests -q

control-api: ## Run authenticated local control API on port 8002 (after control-setup)
	cd backend && $(CONTROL_PY) -m uvicorn app.control_layer.api:app --host 127.0.0.1 --port 8002 --workers 1 --no-access-log

control-preflight: ## Check real providers; exit 2 if a required provider is unavailable
	cd backend && $(CONTROL_PY) -m app.control_layer.demo --mode live --preflight --gate $${CONTROL_GATE:-openjev}

control-openjev-setup: ## Install optional pinned OpenJev in its OWN environment
	@test -x backend/.control-openjev-venv/bin/python || uv venv --python 3.13 backend/.control-openjev-venv
	uv pip sync --python backend/.control-openjev-venv/bin/python backend/requirements-control-openjev.txt

control-openjev: ## Start local HF decision scorer on 8003; first use may download the configured weights
	cd backend && .control-openjev-venv/bin/python -m uvicorn app.control_layer.openjev_server:app --host 127.0.0.1 --port 8003 --workers 1 --no-access-log
