.PHONY: help install dev-install run format lint test clean ingest build install-frontend build-frontend docker-build docker-run

# Default target
help:
	@echo "Campfire Emergency Helper - Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install      Install production dependencies with uv"
	@echo "  dev-install  Install development dependencies with uv"
	@echo ""
	@echo "Development:"
	@echo "  run          Build frontend and start the complete application server"
	@echo "  format       Format code with black and ruff"
	@echo "  lint         Lint code with ruff and mypy"
	@echo "  test         Run tests with pytest"
	@echo ""
	@echo "Data:"
	@echo "  ingest       Process and ingest corpus documents"
	@echo ""
	@echo "Build:"
	@echo "  build        Build the Python backend"
	@echo "  install-frontend Install frontend dependencies"
	@echo "  build-frontend Build the React frontend"
	@echo "  build-all    Build both backend and frontend"
	@echo "  clean        Clean build artifacts and cache"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run Docker container"
	@echo "  docker-compose-up    Start services with docker-compose"
	@echo "  docker-compose-down  Stop services with docker-compose"
	@echo "  docker-compose-logs  View docker-compose logs"
	@echo "  docker-compose-build Rebuild docker-compose services"
	@echo ""
	@echo "Deployment:"
	@echo "  validate-config      Validate system configuration"
	@echo "  validate-config-json Validate config with JSON output"
	@echo ""
	@echo "Backup & Restore:"
	@echo "  backup               Create timestamped backup"
	@echo "  backup-with-logs     Create backup including log files"
	@echo "  restore BACKUP=file  Restore from backup file"
	@echo "  list-backup BACKUP=file    List backup contents"
	@echo "  verify-backup BACKUP=file  Verify backup integrity"

# Installation
install:
	uv sync --no-dev

dev-install:
	uv sync --all-extras

# Development server
run: build-frontend
	uv run uvicorn campfire.api.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend/src

# Code formatting
format:
	uv run black backend/src backend/tests
	uv run ruff check --fix backend/src backend/tests

# Code linting
lint:
	uv run ruff check backend/src backend/tests
	uv run mypy backend/src
	uv run black --check backend/src backend/tests

# Testing
test:
	uv run pytest backend/tests -v --cov=campfire --cov-report=term-missing

test-fast:
	uv run pytest backend/tests -v -m "not slow"

# Comprehensive testing for task 11
test-comprehensive:
	uv run python backend/tests/run_comprehensive_tests.py

test-comprehensive-fast:
	uv run python backend/tests/run_comprehensive_tests.py --fast

test-comprehensive-verbose:
	uv run python backend/tests/run_comprehensive_tests.py --verbose

test-offline:
	uv run pytest backend/tests/test_offline_validation.py -v

test-emergency-scenarios:
	uv run pytest backend/tests/test_emergency_scenarios.py -v

test-citations:
	uv run pytest backend/tests/test_citation_accuracy.py -v

test-safety-integration:
	uv run pytest backend/tests/test_safety_critic_integration.py -v

test-performance:
	uv run pytest backend/tests/test_performance.py -v -m "not slow"

test-performance-full:
	uv run pytest backend/tests/test_performance.py -v

test-e2e:
	uv run pytest backend/tests/test_end_to_end.py -v

test-frontend:
	cd frontend && npm test -- --coverage --watchAll=false

test-all:
	uv run python backend/tests/run_comprehensive_tests.py --frontend

# Data processing
ingest:
	uv run python scripts/ingest_corpus.py

# Build and clean
build:
	uv build

install-frontend:
	cd frontend && npm install

build-frontend: install-frontend
	cd frontend && npm run build

build-all: build build-frontend

clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf frontend/build/
	rm -rf frontend/node_modules/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Docker commands
docker-build:
	docker build -t campfire:latest .

docker-run:
	docker run -p 8000:8000 campfire:latest

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

docker-compose-logs:
	docker-compose logs -f campfire

docker-compose-build:
	docker-compose build --no-cache

# Deployment and configuration
validate-config:
	uv run python scripts/validate_config.py

validate-config-json:
	uv run python scripts/validate_config.py --json

# Backup and restore
backup:
	uv run python scripts/backup_restore.py backup backups/campfire-$(shell date +%Y%m%d_%H%M%S).tar.gz

backup-with-logs:
	uv run python scripts/backup_restore.py backup backups/campfire-$(shell date +%Y%m%d_%H%M%S).tar.gz --include-logs

restore:
	@echo "Usage: make restore BACKUP=path/to/backup.tar.gz"
	@if [ -z "$(BACKUP)" ]; then echo "Error: BACKUP parameter required"; exit 1; fi
	uv run python scripts/backup_restore.py restore $(BACKUP)

list-backup:
	@echo "Usage: make list-backup BACKUP=path/to/backup.tar.gz"
	@if [ -z "$(BACKUP)" ]; then echo "Error: BACKUP parameter required"; exit 1; fi
	uv run python scripts/backup_restore.py list $(BACKUP)

verify-backup:
	@echo "Usage: make verify-backup BACKUP=path/to/backup.tar.gz"
	@if [ -z "$(BACKUP)" ]; then echo "Error: BACKUP parameter required"; exit 1; fi
	uv run python scripts/backup_restore.py verify $(BACKUP)

# Pre-commit hooks
pre-commit-install:
	uv run pre-commit install

pre-commit-run:
	uv run pre-commit run --all-files

# Development setup (run after cloning)
setup: dev-install pre-commit-install
	@echo "Development environment setup complete!"
	@echo "Run 'make ingest' to process corpus documents"
	@echo "Run 'make run' to start the development server"