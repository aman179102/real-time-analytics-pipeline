# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-08

### Added

#### Core Features
- Event ingestion via REST API (single and batch) with Redis Streams backend
- Async event processing pipeline with consumer groups and backpressure
- Time-series aggregation engine with minute, hourly, and daily windows
- Adaptive sampling for high-volume event streams
- Data retention policies with automatic partition management
- Analytics query API for aggregated metrics and event counts
- Dashboard CRUD with customizable widgets (timeseries, counter, pie chart, table, heatmap)
- Real-time WebSocket dashboard updates with subscription model

#### Authentication & Authorization
- JWT-based authentication with access (15min) and refresh (7d) tokens
- Token rotation and revocation support
- Role-based access control (admin, analyst, viewer)
- Secure password hashing with bcrypt (cost factor 12)

#### Infrastructure
- Multi-stage Docker build (builder + distroless runtime)
- Docker Compose stack with TimescaleDB, Redis, Prometheus, Grafana
- Kubernetes manifests: Deployment (3 replicas), Service, Ingress, ConfigMap, HPA
- Redis and PostgreSQL deployments with persistent volumes
- Horizontal Pod Autoscaler (CPU 70%, memory 80%)

#### Observability
- Structured JSON logging with correlation IDs
- Prometheus metrics: request count, latency histogram, error rate, event throughput
- OpenTelemetry distributed tracing with OTLP HTTP exporter
- Health check endpoint with uptime, version, and service info
- Metrics snapshot and sampling statistics via admin API

#### Testing & Quality
- Unit tests for core business logic (aggregator, sampler, retention)
- Integration tests for all API endpoints
- K6 load testing script for performance benchmarking
- Ruff linter and formatter configuration
- Type hints throughout the codebase

#### Documentation
- Comprehensive README with ASCII architecture diagram
- OpenAPI 3.0 specification with all endpoints documented
- Full API reference with request/response examples
- Development setup guide (CONTRIBUTING.md)
- Environment variable reference (.env.example)
- Deployment guide for Docker Compose and Kubernetes
- Makefile with 20+ commands for common operations
- Database initialization script with TimescaleDB hypertables
- Test data seeding script with realistic event generation

### Infrastructure
- Docker: Multi-stage build, health checks, non-root user
- Docker Compose: TimescaleDB, Redis, Prometheus, Grafana
- Kubernetes: StatefulSet for PostgreSQL, Deployment for Redis
- CI/CD: All Makefile targets for build, test, deploy

### Security
- JWT authentication with short-lived tokens
- bcrypt password hashing
- Rate limiting per user/IP
- CORS configuration
- SQL injection prevention via ORM
- Input validation with Pydantic
- Security headers via middleware
- RBAC authorization
- Secure secret management via environment variables
