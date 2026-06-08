.PHONY: help install build run run-dev test test-unit test-integration lint format clean docker-build docker-up docker-down migrate seed k8s-deploy k8s-delete

SHELL := /bin/bash
PROJECT := real-time-analytics-pipeline
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DOCKER_IMAGE := $(PROJECT):latest
K8S_NAMESPACE := analytics

help: ## Show this help message
	@echo "$(PROJECT) - Makefile"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies in a virtual environment
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

build: ## Build the package
	$(PYTHON) -m build

run: ## Run the application in production mode
	$(PYTHON) -m src.main

run-dev: ## Run the application in development mode (auto-reload)
	ENVIRONMENT=development DEBUG=true $(PYTHON) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests
	$(PYTHON) -m pytest tests/unit -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80 -q

test-integration: ## Run integration tests
	$(PYTHON) -m pytest tests/integration -v --cov=src --cov-report=term-missing --cov-report=html -q

lint: ## Run linters (ruff)
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

format: ## Format code with ruff
	$(PYTHON) -m ruff format src/ tests/

clean: ## Clean generated files and directories
	rm -rf $(VENV)
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
	rm -rf *.egg-info dist build
	rm -rf htmlcov coverage coverage.xml
	rm -rf .coverage*
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d -delete
	find . -name '.DS_Store' -delete

docker-build: ## Build Docker image
	docker build -t $(DOCKER_IMAGE) -f deploy/Dockerfile .

docker-up: ## Start all services with Docker Compose
	docker compose -f deploy/docker-compose.yml up -d --build

docker-down: ## Stop all services with Docker Compose
	docker compose -f deploy/docker-compose.yml down -v

migrate: ## Run database migrations
	$(PYTHON) -m alembic upgrade head

seed: ## Seed test data into the database
	$(PYTHON) deploy/scripts/seed_data.py

k8s-deploy: ## Deploy to Kubernetes
	@echo "Deploying to Kubernetes namespace: $(K8S_NAMESPACE)"
	kubectl create namespace $(K8S_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -f deploy/kubernetes/configmap.yaml
	kubectl apply -f deploy/kubernetes/redis-deployment.yaml
	kubectl apply -f deploy/kubernetes/postgres-deployment.yaml
	kubectl apply -f deploy/kubernetes/deployment.yaml
	kubectl apply -f deploy/kubernetes/service.yaml
	kubectl apply -f deploy/kubernetes/ingress.yaml
	kubectl apply -f deploy/kubernetes/hpa.yaml
	@echo "Deployment complete. Check status with: kubectl -n $(K8S_NAMESPACE) get pods"

k8s-delete: ## Delete Kubernetes resources
	@echo "Deleting Kubernetes resources in namespace: $(K8S_NAMESPACE)"
	kubectl delete -f deploy/kubernetes/ --ignore-not-found
	kubectl delete namespace $(K8S_NAMESPACE) --ignore-not-found
	@echo "Cleanup complete."
