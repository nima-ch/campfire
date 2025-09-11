.PHONY: help install dev-install run format lint test clean ingest build docker-build docker-run

# Default target
help:
	@echo "Campfire Emergency Helper - Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install      Install production dependencies with uv"
	@echo "  dev-install  Install development dependencies with uv"
	@echo ""
	@echo "Development:"
	@echo "  run          Start the FastAPI development server"
	@echo "  format       Format code with black and ruff"
	@echo "  lint         Lint code with ruff and mypy"
	@echo "  test         Run tests with pytest"
	@echo ""
	@echo "Data:"
	@echo "  ingest       Process and ingest corpus documents"
	@echo ""
	@echo "Build:"
	@echo "  build        Build the Python backend"
	@echo "  build-frontend Build the React frontend"
	@echo "  build-all    Build both backend and frontend"
	@echo "  clean        Clean build artifacts and cache"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run Docker container"

# Installation
install:
	uv sync --no-dev

dev-install:
	uv sync --all-extras

# Development server
run:
	uv run uvicorn campfire.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend/src

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

build-frontend:
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