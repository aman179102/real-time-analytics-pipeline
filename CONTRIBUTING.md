# Contributing to Real-Time Analytics Pipeline

Thank you for considering contributing! We welcome contributions of all kinds: bug fixes, new features, documentation improvements, and more.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 16+ (or use Docker)
- Redis 7+ (or use Docker)

### Local Environment

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/real-time-analytics-pipeline.git
cd real-time-analytics-pipeline

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
make install

# Copy environment configuration
cp .env.example .env

# Start infrastructure services
docker compose -f deploy/docker-compose.yml up -d postgres redis

# Run migrations
make migrate

# Run the application
make run-dev
```

### Verify Setup

```bash
# Health check
curl http://localhost:8000/health

# Register a test user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"testpassword123!"}'

# Run tests
make test
```

## Coding Standards

### Python Style

- **Formatting**: Ruff with default settings (`make format`)
- **Linting**: Ruff (`make lint`) - no warnings allowed
- **Type Hints**: Required for all public functions and methods
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants
- **Imports**: Group in order: standard library, third-party, application. Use absolute imports.
- **Line Length**: 100 characters max
- **Docstrings**: Google-style for all public APIs

### Architecture Guidelines

1. **Clean Architecture**: Domain models in `src/domain/`, business logic in `src/core/`, infrastructure in `src/infrastructure/`
2. **Dependency Injection**: Use FastAPI's `Depends()` for service injection
3. **Repository Pattern**: All database access through repositories
4. **Error Handling**: Use custom `AppError` subclasses with proper error codes
5. **Configuration**: All configurable values via environment variables in `config.py`
6. **Async-First**: All I/O operations must be async

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add event batch ingestion endpoint
fix: resolve race condition in aggregator
docs: update API documentation for dashboards
refactor: simplify retention policy logic
test: add unit tests for sampler
chore: update dependencies
```

### Branch Naming

```
feature/description     - New features
fix/description         - Bug fixes
docs/description        - Documentation
refactor/description    - Code refactoring
test/description        - Test additions/changes
chore/description       - Maintenance
```

## Pull Request Process

1. **Create an issue** for the change you want to make (unless it's a minor fix)
2. **Fork the repo** and create a branch from `main`
3. **Write code** following the coding standards above
4. **Add tests** for new functionality. Coverage should remain above 80%.
5. **Run all tests** locally: `make test`
6. **Run linter**: `make lint`
7. **Update documentation** if needed (README, API docs, docstrings)
8. **Create a pull request** with a clear description of changes
9. **Address review feedback** promptly

### PR Requirements

- [ ] Code follows coding standards
- [ ] Tests pass and coverage >= 80%
- [ ] Linter passes with no warnings
- [ ] Documentation updated
- [ ] Commit messages follow Conventional Commits
- [ ] No unnecessary dependencies added
- [ ] Security best practices followed

## Testing Guidelines

### Test Structure

```
tests/
├── unit/                   # Test individual functions/classes in isolation
│   ├── test_aggregator.py
│   ├── test_sampler.py
│   └── test_retention.py
├── integration/            # Test API endpoints with real dependencies
│   ├── test_health.py
│   ├── test_auth.py
│   ├── test_events.py
│   ├── test_analytics.py
│   └── test_dashboards.py
└── e2e/                    # End-to-end user journeys
    └── test_full_flow.py
```

### Writing Tests

- Use `pytest` with `pytest-asyncio` for async tests
- Use fixtures for common setup (DB session, auth tokens, test data)
- Mock external services (Redis, Kafka) in unit tests
- Use test containers or a real database for integration tests
- Each test should be independent and idempotent

```python
# Example unit test
async def test_event_aggregation():
    aggregator = Aggregator()
    events = [create_test_event() for _ in range(10)]
    result = await aggregator.aggregate(events, window="minute")
    assert result.count == 10
    assert result.value > 0
```

## Security

- Never commit secrets or credentials to the repository
- Always use parameterized queries (SQLAlchemy ORM)
- Validate and sanitize all user inputs
- Use proper authentication and authorization checks
- Report security vulnerabilities privately

## Questions?

Open a [GitHub Discussion](https://github.com/yourusername/real-time-analytics-pipeline/discussions) or issue.
