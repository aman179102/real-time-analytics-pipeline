# Real-Time Analytics Pipeline

Enterprise-grade real-time analytics pipeline with async event processing, time-series storage, real-time dashboards via WebSocket, and comprehensive observability.

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
