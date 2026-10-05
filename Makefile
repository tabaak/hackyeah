.DEFAULT_GOAL := help

COMPOSE := docker compose -f compose.yaml

.PHONY: help setup check-env up down restart logs ps test api-docs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create .env from the example if it does not exist
	@test -f .env || cp .env.example .env
	@test -f frontend/web/.env.local || cp frontend/web/.env.example frontend/web/.env.local
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
