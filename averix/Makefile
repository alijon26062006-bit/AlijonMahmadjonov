# Shortcuts for the commands used often enough to be worth remembering.
#
# Everything here is a thin wrapper over docker compose; nothing is hidden.

COMPOSE ?= docker compose -f docker-compose.production.yml
DEV     ?= docker compose -f docker-compose.yml

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Set up and start everything (first run, and every deployment)
	./install.sh

.PHONY: up
up: ## Start the production stack
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop it, keeping the data
	$(COMPOSE) down

.PHONY: deploy
deploy: ## Pull, rebuild and restart
	git pull
	$(COMPOSE) up -d --build
	$(COMPOSE) ps

.PHONY: ps
ps: ## What is running
	$(COMPOSE) ps

.PHONY: logs
logs: ## Follow the API log
	$(COMPOSE) logs -f api

.PHONY: logs-all
logs-all: ## Follow every log
	$(COMPOSE) logs -f

.PHONY: migrate
migrate: ## Apply pending migrations
	$(COMPOSE) run --rm migrate

.PHONY: admin
admin: ## Grant the admin role (make admin EMAIL=you@averix.dev)
	@test -n "$(EMAIL)" || { echo "usage: make admin EMAIL=you@averix.dev"; exit 1; }
	$(COMPOSE) exec api averixctl create-admin --email $(EMAIL)

.PHONY: psql
psql: ## Database console
	$(COMPOSE) exec postgres psql -U averix -d averix

.PHONY: backup
backup: ## Back up the database and the uploads now
	./scripts/backup.sh

.PHONY: dev
dev: ## Start the development stack on localhost
	$(DEV) up -d --build
	@echo "web  http://localhost:3000"
	@echo "api  http://localhost:8080/health"

.PHONY: seed
seed: ## Fill the development database with demo data
	node scripts/seed-demo.mjs

.PHONY: test
test: ## Run every test suite
	cd services/api-go && go test ./...
	cd services/ai-python && python -m pytest -q
	cd apps/web && npm run typecheck
