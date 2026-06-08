from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_analytics_service,
    get_event_processor,
    get_queue_producer,
    verify_token,
)
from src.api.errors import AuthenticationError
from src.api.routes import auth as auth_routes
from src.api.routes.analytics import router as analytics_router
from src.api.routes.events import router as events_router
from src.config import config
from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    CacheInterface,
    DashboardRepositoryInterface,
    EventRepositoryInterface,
    QueueProducerInterface,
)
from src.domain.models import (
    AggregatedMetric,
    AggregationWindow,
    AnalyticsEvent,
    Dashboard,
    DashboardWidget,
    EventStatus,
    EventType,
    User,
    UserRole,
    WidgetType,
)
from src.domain.value_objects import (
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)


TEST_USER_ID = str(uuid.uuid4())
TEST_USERNAME = "integrationuser"
TEST_EMAIL = "integration@test.com"
TEST_PASSWORD = "testpassword123"


def create_test_token(
    user_id: str = TEST_USER_ID,
    username: str = TEST_USERNAME,
    role: str = "analyst",
    exp_offset_minutes: int = 15,
) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=exp_offset_minutes),
        "type": "access",
    }
    return pyjwt.encode(payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm)


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    repo = AsyncMock(spec=EventRepositoryInterface)
    repo.save.return_value = str(uuid.uuid4())
    repo.save_batch.return_value = [str(uuid.uuid4())]
    repo.get_by_id.side_effect = lambda eid: (
        AnalyticsEvent(
            event_id=eid,
            event_type=EventType.PAGE_VIEW,
            source="web",
            payload={"page": "/home"},
            timestamp=datetime.utcnow(),
            user_id=TEST_USER_ID,
        ) if eid == "known-event-id" else None
    )
    now = datetime.utcnow()
    events = [
        AnalyticsEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PAGE_VIEW,
            source="web",
            payload={"url": "/home"},
            timestamp=now - timedelta(minutes=i),
            user_id=TEST_USER_ID,
            session_id="s1",
        )
        for i in range(5)
    ]
    repo.query.return_value = PaginatedResult(items=events, total=5, page=1, page_size=20)
    repo.count_by_type.return_value = {"page_view": 10, "click": 5, "purchase": 2}
    repo.count_by_source.return_value = {"web": 12, "mobile": 5}
    return repo


@pytest.fixture
def mock_analytics_repo() -> AsyncMock:
    repo = AsyncMock(spec=AnalyticsRepositoryInterface)
    now = datetime.utcnow()
    ws = now.replace(second=0, microsecond=0)
    metric = AggregatedMetric(
        metric_id=str(uuid.uuid4()),
        metric_name="event_count.page_view",
        window=AggregationWindow.MINUTE,
        window_start=ws - timedelta(minutes=5),
        window_end=ws - timedelta(minutes=4),
        value=10.0,
        count=10,
        dimensions={"event_type": "page_view", "source": "web"},
    )
    repo.query_aggregations.return_value = PaginatedResult(
        items=[metric], total=1, page=1, page_size=20,
    )
    repo.get_latest_aggregation.return_value = metric
    repo.save_aggregation.return_value = str(uuid.uuid4())
    return repo


@pytest.fixture
def mock_dashboard_repo() -> AsyncMock:
    repo = AsyncMock(spec=DashboardRepositoryInterface)
    dashboard = Dashboard(
        name="Test Dashboard",
        description="Integration test dashboard",
        widgets=[
            DashboardWidget(
                title="PV", widget_type=WidgetType.TIMESERIES,
                metric_name="event_count.page_view", config={}, position=0,
            ),
        ],
        owner_id=TEST_USER_ID,
    )
    repo.save.return_value = dashboard.dashboard_id
    repo.get_by_id.return_value = dashboard
    repo.list_dashboards.return_value = PaginatedResult(
        items=[dashboard], total=1, page=1, page_size=20,
    )
    return repo


@pytest.fixture
def mock_cache() -> AsyncMock:
    cache = AsyncMock(spec=CacheInterface)
    cache.get.return_value = None
    return cache


@pytest.fixture
def mock_producer() -> AsyncMock:
    producer = AsyncMock(spec=QueueProducerInterface)
    producer.publish.return_value = str(uuid.uuid4())
    producer.publish_batch.return_value = [str(uuid.uuid4()), str(uuid.uuid4())]
    return producer


@pytest.fixture
def mock_analytics_service(
    mock_event_repo: AsyncMock,
    mock_analytics_repo: AsyncMock,
    mock_dashboard_repo: AsyncMock,
    mock_cache: AsyncMock,
):
    from src.core.analytics_service import AnalyticsService
    return AnalyticsService(mock_event_repo, mock_analytics_repo, mock_dashboard_repo, mock_cache)


@pytest.fixture
def test_app(
    mock_analytics_service,
    mock_producer: AsyncMock,
    mock_event_repo: AsyncMock,
) -> FastAPI:
    app = FastAPI()

    from src.api.routes.health import router as health_router
    from src.api.routes.auth import router as auth_router
    from src.api.routes.events import router as events_router
    from src.api.routes.analytics import router as analytics_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(analytics_router)

    async def override_verify_token():
        now = datetime.utcnow()
        return {
            "sub": TEST_USER_ID,
            "username": TEST_USERNAME,
            "role": "analyst",
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "type": "access",
        }

    async def override_get_queue_producer():
        yield mock_producer

    async def override_get_analytics_service():
        return mock_analytics_service

    app.dependency_overrides[verify_token] = override_verify_token
    app.dependency_overrides[get_queue_producer] = override_get_queue_producer
    app.dependency_overrides[get_analytics_service] = override_get_analytics_service

    return app


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_header() -> dict[str, str]:
    token = create_test_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def known_event_id() -> str:
    return "known-event-id"
