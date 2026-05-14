# AI Calling Agent MVP - Development Commands

.PHONY: help install dev test lint format clean docker-build docker-run migrate

help: ## Show this help message
	@echo "AI Calling Agent MVP - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install black isort flake8 mypy pytest pytest-asyncio pytest-mock

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term-missing

lint: ## Run linting
	flake8 app tests
	mypy app

format: ## Format code
	black app tests
	isort app tests

format-check: ## Check code formatting
	black --check app tests
	isort --check-only app tests

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create new migration
	alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade: ## Downgrade database
	alembic downgrade -1

docker-build: ## Build Docker image
	docker build -t ai-calling-agent-mvp .

docker-run: ## Run with Docker Compose
	docker-compose up --build

docker-down: ## Stop Docker Compose
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

run: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run production server
	uvicorn app.main:app --host 0.0.0.0 --port 8000

setup: ## Initial project setup
	cp .env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run: make migrate && make run"

check: format-check lint test ## Run all checks

ci: install check ## Run CI pipeline

deploy-railway: ## Deploy to Railway
	railway up

deploy-render: ## Deploy to Render
	@echo "Push to main branch to trigger Render deployment"

health: ## Check application health
	curl -f http://localhost:8000/health || echo "Application not running"

logs: ## View application logs (if running with systemd)
	journalctl -u ai-calling-agent -f