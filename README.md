# Real-Time Analytics Pipeline

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.110+-00a86b?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/TimescaleDB-2.16+-2C8EBB?style=for-the-badge&logo=timescale" alt="TimescaleDB">
  <img src="https://img.shields.io/badge/Redis_Streams-7+-DC382D?style=for-the-badge&logo=redis" alt="Redis">
  <img src="https://img.shields.io/badge/Kafka-3.6+-231F20?style=for-the-badge&logo=apachekafka" alt="Kafka">
  <img src="https://img.shields.io/badge/WebSocket-Realtime-010101?style=for-the-badge&logo=socket.io" alt="WebSocket">
  <img src="https://img.shields.io/badge/Prometheus-2.49-E6522C?style=for-the-badge&logo=prometheus" alt="Prometheus">
  <img src="https://img.shields.io/badge/OpenTelemetry-1.22-4B0082?style=for-the-badge&logo=opentelemetry" alt="OpenTelemetry">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/Kubernetes-1.28+-326CE5?style=for-the-badge&logo=kubernetes" alt="Kubernetes">
  <br>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-brightgreen?style=flat-square" alt="Coverage">
  <img src="https://img.shields.io/badge/status-production--ready-00a86b?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/code_style-ruff-000000?style=flat-square" alt="Ruff">
</p>

Enterprise-grade real-time analytics pipeline with async event processing, time-series storage, real-time dashboards via WebSocket, comprehensive observability, and Kubernetes-ready deployment.

## Features

### 🚀 Core

| Feature | Description |
|---------|-------------|
| **Async Event Ingestion** | REST API + batch ingestion with Redis Streams or Kafka backends |
| **Time-Series Storage** | TimescaleDB hypertables with automatic partitioning and compression |
| **Real-Time WebSocket** | Live dashboard updates with auto-reconnect and JWT auth |
| **Adaptive Sampling** | Rate-based sampling with configurable thresholds per event type |
| **Data Retention** | TTL-based policies (raw/hourly/daily) with automatic partition management |

### 🔒 Enterprise Security

| Feature | Description |
|---------|-------------|
| **JWT Authentication** | Access + refresh tokens with bcrypt password hashing |
| **Role-Based Access Control** | Admin, editor, viewer roles with endpoint-level enforcement |
| **Security Headers** | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Permissions-Policy |
| **Correlation IDs** | End-to-end request tracing via `X-Correlation-ID` header propagation |
| **Rate Limiting** | Per-IP request throttling with configurable burst allowances |
| **Request Size Limiting** | Configurable max payload size with 413 rejection |

### 📊 Observability

| Feature | Description |
|---------|-------------|
| **Prometheus Metrics** | Request rate/latency/errors, event throughput, queue depth, active connections |
| **OpenTelemetry Tracing** | Distributed traces across HTTP, queue, DB, and aggregation pipeline |
| **Structured Logging** | JSON-formatted logs with correlation IDs and service context |
| **Grafana Dashboards** | Pre-configured dashboards for metrics visualization and alerting |

### ☁️ Deployment

| Feature | Description |
|---------|-------------|
| **Docker Compose** | One-command full-stack deployment (app, TimescaleDB, Redis, Prometheus, Grafana) |
| **Kubernetes** | Complete K8s manifests with HPA, Ingress, ConfigMaps, health checks |
| **Multi-Stage Build** | Optimized Docker image (Python 3.11-slim, ~200MB) |
| **Health Checks** | Liveness/readiness probes with DB and cache dependency awareness |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Clients / SDKs                                │
│                   (REST API, WebSocket, HTTP Event Stream)                   │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application (uvicorn)                        │
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Health  │  │   Auth   │  │  Events  │  │Analytics │  │  Dashboards  │  │
│  │  Check   │  │  (JWT)   │  │ Ingest   │  │  Queries │  │   CRUD + WS  │  │
│  └──────────┘  └──────────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│                                    │              │               │          │
│  ┌─────────────────────────────────┴──────────────┴───────────────┘          │
│  │                    Core Business Logic Layer                              │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐   │
│  │  │  Aggregator  │  │   Sampler    │  │  Retention   │  │  Analytics │   │
│  │  │  (Time win)  │  │  (Rate-based)│  │  (TTL/Parts) │  │   Service  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘   │
│  └──────────────────────────────────────────────────────────────────────────┘│
└──────────────────┬────────────────────────────────────┬──────────────────────┘
                   │                                    │
                   ▼                                    ▼
┌─────────────────────────────┐       ┌─────────────────────────────────────┐
│   Redis Streams / Kafka     │       │      TimescaleDB (PostgreSQL)       │
│   (Event Queue)             │       │      - events (hypertable)          │
│   - Stream buffering        │       │      - aggregated_metrics           │
│   - Consumer groups         │       │      - dashboards / widgets         │
│   - Backpressure            │       │      - users / refresh_tokens       │
└─────────────────────────────┘       └──────────────┬──────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Observability Stack                                │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────┐  │
│  │  Prometheus  │  │  OpenTelemetry │  │    Grafana     │  │  Loki      │  │
│  │  (Metrics)   │  │  (Tracing)     │  │ (Dashboards)   │  │ (Logs)     │  │
│  └──────────────┘  └────────────────┘  └────────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Middleware Pipeline (per request)

```
Request → CorrelationMiddleware (X-Correlation-ID generation/propagation)
       → AuthMiddleware (JWT verification + RBAC)
       → SecurityHeadersMiddleware (CSP, HSTS, X-Frame-Options, etc.)
       → RateLimitMiddleware (per-IP throttling)
       → SizeLimiterMiddleware (payload size enforcement)
       → Router → ExceptionHandler → Response
```

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Layer** | FastAPI (Python 3.11+) | REST endpoints, WebSocket, request validation |
| **Event Queue** | Redis Streams / Kafka | Async event ingestion, buffering, consumer groups |
| **Time-Series DB** | TimescaleDB (PostgreSQL) | Hypertable storage for events and aggregated metrics |
| **Cache** | Redis | Session cache, rate limiting, real-time counters |
| **Metrics** | Prometheus | Application metrics (latency, throughput, errors) |
| **Tracing** | OpenTelemetry | Distributed trace collection and propagation |
| **Dashboards** | Grafana | Visualization and alerting |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for local stack)
- kubectl (for Kubernetes deployment)

### Local Development

```bash
# Clone and enter the project
cd real-time-analytics-pipeline

# Create virtual environment and install dependencies
make install

# Start infrastructure (PostgreSQL + Redis)
docker compose -f deploy/docker-compose.yml up -d postgres redis

# Run database migrations
make migrate

# Start the application in dev mode
make run-dev

# Seed test data
make seed
```

### Full Stack (Docker Compose)

```bash
# Build and start all services
make docker-up

# View logs
docker compose -f deploy/docker-compose.yml logs -f

# Run tests
make test

# Stop all services
make docker-down
```

### Access Points

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| **API** | http://localhost:8000 | - |
| **API Docs (Swagger)** | http://localhost:8000/docs | - |
| **API Docs (ReDoc)** | http://localhost:8000/redoc | - |
| **Metrics** | http://localhost:9090 | - |
| **Prometheus** | http://localhost:9091 | - |
| **Grafana** | http://localhost:3000 | admin / admin |

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and modify:

```bash
cp .env.example .env
```

Key configuration groups:

- **`ENVIRONMENT`** - `development`, `staging`, or `production`
- **`DATABASE_*`** - TimescaleDB connection and pool settings
- **`REDIS_*`** - Redis connection and stream configuration
- **`JWT_*`** - Authentication tokens and signing
- **`RETENTION_*`** - Data retention policies (raw events, hourly, daily)
- **`SAMPLING_*`** - Adaptive sampling configuration
- **`TRACING_*`** - OpenTelemetry exporter settings
- **`RATE_LIMIT_*`** - Request rate limiting

## API Overview

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| **GET** | `/health` | Health check |
| **POST** | `/api/v1/auth/register` | User registration |
| **POST** | `/api/v1/auth/login` | User login |
| **POST** | `/api/v1/auth/refresh` | Refresh access token |
| **GET** | `/api/v1/auth/me` | Current user info |
| **POST** | `/api/v1/events/ingest` | Ingest a single event |
| **POST** | `/api/v1/events/ingest/batch` | Batch ingest events |
| **GET** | `/api/v1/events` | List events with filters |
| **GET** | `/api/v1/events/{id}` | Get event by ID |
| **GET** | `/api/v1/analytics/aggregations/{name}` | Get aggregated metrics |
| **GET** | `/api/v1/analytics/aggregations/{name}/latest` | Latest aggregation |
| **GET** | `/api/v1/analytics/counts/types` | Event type counts |
| **GET** | `/api/v1/analytics/counts/sources` | Event source counts |
| **GET** | `/api/v1/analytics/realtime` | Real-time metrics snapshot |
| **POST** | `/api/v1/dashboards` | Create dashboard |
| **GET** | `/api/v1/dashboards` | List dashboards |
| **GET** | `/api/v1/dashboards/{id}` | Get dashboard |
| **PUT** | `/api/v1/dashboards/{id}` | Update dashboard |
| **DELETE** | `/api/v1/dashboards/{id}` | Delete dashboard |
| **POST** | `/api/v1/admin/retention/apply` | Apply retention policy |
| **GET** | `/api/v1/admin/retention/summary` | Retention summary |
| **GET** | `/api/v1/admin/metrics/snapshot` | Metrics snapshot |
| **GET** | `/api/v1/admin/sampling/stats` | Sampling statistics |
| **WS** | `/ws/dashboard/{id}` | Real-time dashboard updates |

### Authentication

All endpoints except `/health` and `/api/v1/auth/*` require a Bearer JWT token:

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"securepass123!"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"securepass123!"}'

# Use token
curl http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json"
```

## Deployment

### Docker Compose (Full Stack)

```bash
make docker-build
make docker-up
```

### Kubernetes

```bash
# Deploy all manifests
make k8s-deploy

# Check status
kubectl -n analytics get pods,svc,ingress

# Delete
make k8s-delete
```

### Production Checklist

- [ ] Change all default passwords and secrets
- [ ] Set `ENVIRONMENT=production` and `DEBUG=false`
- [ ] Configure TLS certificates for Ingress
- [ ] Set `JWT_SECRET` to a strong random value
- [ ] Configure proper resource limits
- [ ] Set up database backups and point-in-time recovery
- [ ] Configure Prometheus alerting rules
- [ ] Set up log aggregation (Loki, ELK, or similar)
- [ ] Enable database connection pooling (PgBouncer)
- [ ] Configure pod autoscaling thresholds

## Testing

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Load testing (k6)
k6 run tests/load/k6-script.js
```

## Project Structure

```
src/                          # Main source code
├── api/                      # API layer (routes, middleware, websocket)
├── core/                     # Business logic (aggregator, retention, etc.)
├── domain/                   # Domain models, interfaces, value objects
├── infrastructure/           # Database, cache, queue, logging, metrics
├── config.py                 # Typed configuration
└── main.py                   # Application entry point

tests/
├── unit/                     # Unit tests
├── integration/              # Integration tests
├── e2e/                      # End-to-end tests
└── load/                     # K6 load testing scripts

deploy/
├── Dockerfile                # Multi-stage build
├── docker-compose.yml        # Full local stack
├── kubernetes/               # K8s manifests
└── scripts/                  # DB init, data seeding

docs/
└── api/                      # API documentation
```

## Observability

### Metrics (Prometheus)

- `http_requests_total` - Request count by method, path, status
- `http_request_duration_seconds` - Request latency histogram
- `events_ingested_total` - Event ingestion rate
- `events_processed_total` - Event processing rate
- `active_connections` - Active WebSocket connections
- `queue_depth` - Event queue depth

### Tracing (OpenTelemetry)

Distributed traces with span context propagation across:
- HTTP requests (incoming/outgoing)
- Queue operations (publish/consume)
- Database queries
- Aggregation pipelines

### Logging (Structured JSON)

All logs formatted as JSON with:
- Correlation ID (trace_id/span_id)
- Service name and version
- Log level
- Timestamp with timezone
- Request path and method

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

[MIT](LICENSE)
