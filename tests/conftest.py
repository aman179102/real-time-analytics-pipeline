from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    CacheInterface,
    DashboardRepositoryInterface,
    EventRepositoryInterface,
    QueueConsumerInterface,
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
    EventPayload,
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)
from src.core.aggregator import AggregationEngine
from src.core.analytics_service import AnalyticsService
from src.core.event_processor import EventProcessor
from src.core.retention import RetentionManager
from src.core.sampling import Sampler


@pytest.fixture
def sample_timestamp() -> datetime:
    return datetime(2025, 6, 1, 12, 30, 0)


@pytest.fixture
def sample_time_range(sample_timestamp: datetime) -> TimeRange:
    return TimeRange(
        start=sample_timestamp - timedelta(hours=1),
        end=sample_timestamp,
    )


@pytest.fixture
def sample_pagination() -> PaginationParams:
    return PaginationParams(page=1, page_size=20)


@pytest.fixture
def sample_payload() -> dict[str, Any]:
    return {"url": "/home", "referrer": "/login", "duration_ms": 1500}


@pytest.fixture
def page_view_event(sample_timestamp: datetime, sample_payload: dict[str, Any]) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.PAGE_VIEW,
        source="web-app",
        payload=sample_payload,
        timestamp=sample_timestamp,
        user_id="user-1",
        session_id="session-abc",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        status=EventStatus.RECEIVED,
    )


@pytest.fixture
def click_event(sample_timestamp: datetime) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.CLICK,
        source="web-app",
        payload={"element": "button-submit", "page": "/checkout"},
        timestamp=sample_timestamp + timedelta(seconds=5),
        user_id="user-1",
        session_id="session-abc",
        status=EventStatus.RECEIVED,
    )


@pytest.fixture
def purchase_event(sample_timestamp: datetime) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.PURCHASE,
        source="mobile-app",
        payload={"amount": 49.99, "currency": "USD", "item": "premium-plan"},
        timestamp=sample_timestamp + timedelta(seconds=30),
        user_id="user-2",
        session_id="session-xyz",
        status=EventStatus.RECEIVED,
    )


@pytest.fixture
def signup_event(sample_timestamp: datetime) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.SIGNUP,
        source="web-app",
        payload={"email": "test@example.com"},
        timestamp=sample_timestamp + timedelta(minutes=1),
        status=EventStatus.RECEIVED,
    )


@pytest.fixture
def error_event(sample_timestamp: datetime) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=str(uuid.uuid4()),
        event_type=EventType.ERROR,
        source="api-gateway",
        payload={"code": 500, "message": "Internal Server Error", "service": "auth"},
        timestamp=sample_timestamp + timedelta(seconds=45),
        user_id="user-1",
        session_id="session-abc",
        status=EventStatus.RECEIVED,
    )


@pytest.fixture
def sample_events(
    page_view_event: AnalyticsEvent,
    click_event: AnalyticsEvent,
    purchase_event: AnalyticsEvent,
    signup_event: AnalyticsEvent,
    error_event: AnalyticsEvent,
) -> list[AnalyticsEvent]:
    return [page_view_event, click_event, purchase_event, signup_event, error_event]


@pytest.fixture
def sample_aggregated_metric(sample_timestamp: datetime) -> AggregatedMetric:
    ws = sample_timestamp.replace(second=0, microsecond=0)
    return AggregatedMetric(
        metric_id=str(uuid.uuid4()),
        metric_name="event_count.page_view",
        window=AggregationWindow.MINUTE,
        window_start=ws,
        window_end=ws + timedelta(minutes=1),
        value=5.0,
        count=5,
        dimensions={"event_type": "page_view", "source": "web-app"},
    )


@pytest.fixture
def sample_dashboard() -> Dashboard:
    widget = DashboardWidget(
        title="Page Views",
        widget_type=WidgetType.TIMESERIES,
        metric_name="event_count.page_view",
        config={"time_range": "24h", "aggregation": "hourly"},
        position=0,
        width=6,
        height=4,
    )
    return Dashboard(
        name="Main Dashboard",
        description="Main analytics dashboard",
        widgets=[widget],
        owner_id="user-1",
        is_public=False,
    )


@pytest.fixture
def sample_user() -> User:
    return User(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$abcdefghijklmnopqrstuv",
        role=UserRole.ANALYST,
        is_active=True,
    )


@pytest.fixture
def sample_filter_criteria() -> FilterCriteria:
    return FilterCriteria(
        event_types=["page_view", "click"],
        sources=["web-app"],
        user_ids=["user-1"],
    )


@pytest.fixture
def sample_event_payload() -> EventPayload:
    return EventPayload.create({"key": "value", "nested": {"a": 1}})


# ---- Mock repositories ----

@pytest.fixture
def mock_event_repo() -> AsyncMock:
    repo = AsyncMock(spec=EventRepositoryInterface)
    repo.save.return_value = str(uuid.uuid4())
    repo.save_batch.return_value = [str(uuid.uuid4()) for _ in range(3)]
    repo.get_by_id.return_value = None
    repo.query.return_value = PaginatedResult(items=[], total=0, page=1, page_size=20)
    repo.count_by_type.return_value = {"page_view": 10, "click": 5}
    repo.count_by_source.return_value = {"web-app": 12, "mobile-app": 3}
    repo.delete_older_than.return_value = 100
    return repo


@pytest.fixture
def mock_analytics_repo() -> AsyncMock:
    repo = AsyncMock(spec=AnalyticsRepositoryInterface)
    repo.save_aggregation.return_value = str(uuid.uuid4())
    repo.get_aggregation.return_value = None
    repo.query_aggregations.return_value = PaginatedResult(items=[], total=0, page=1, page_size=20)
    repo.get_latest_aggregation.return_value = None
    repo.delete_aggregations_older_than.return_value = 50
    return repo


@pytest.fixture
def mock_dashboard_repo() -> AsyncMock:
    repo = AsyncMock(spec=DashboardRepositoryInterface)
    repo.save.return_value = str(uuid.uuid4())
    repo.get_by_id.return_value = None
    repo.list_dashboards.return_value = PaginatedResult(items=[], total=0, page=1, page_size=20)
    return repo


@pytest.fixture
def mock_cache() -> AsyncMock:
    cache = AsyncMock(spec=CacheInterface)
    cache.get.return_value = None
    cache.set.return_value = None
    cache.delete.return_value = None
    cache.exists.return_value = False
    cache.incr.return_value = 1
    return cache


@pytest.fixture
def mock_consumer() -> AsyncMock:
    consumer = AsyncMock(spec=QueueConsumerInterface)
    consumer.consume.return_value = []
    return consumer


@pytest.fixture
def mock_producer() -> AsyncMock:
    producer = AsyncMock(spec=QueueProducerInterface)
    producer.publish.return_value = str(uuid.uuid4())
    producer.publish_batch.return_value = [str(uuid.uuid4())]
    return producer


# ---- Core service fixtures ----

@pytest.fixture
def sampler() -> Sampler:
    return Sampler()


@pytest.fixture
def aggregation_engine(mock_analytics_repo: AsyncMock) -> AggregationEngine:
    return AggregationEngine(mock_analytics_repo)


@pytest.fixture
def analytics_service(
    mock_event_repo: AsyncMock,
    mock_analytics_repo: AsyncMock,
    mock_dashboard_repo: AsyncMock,
    mock_cache: AsyncMock,
) -> AnalyticsService:
    return AnalyticsService(mock_event_repo, mock_analytics_repo, mock_dashboard_repo, mock_cache)


@pytest.fixture
def event_processor(
    mock_event_repo: AsyncMock,
    mock_analytics_repo: AsyncMock,
    mock_consumer: AsyncMock,
    mock_cache: AsyncMock,
    aggregation_engine: AggregationEngine,
    sampler: Sampler,
) -> EventProcessor:
    return EventProcessor(
        mock_event_repo, mock_analytics_repo, mock_consumer, mock_cache,
        aggregation_engine, sampler,
    )


@pytest.fixture
def retention_manager(
    mock_event_repo: AsyncMock,
    mock_analytics_repo: AsyncMock,
) -> RetentionManager:
    return RetentionManager(mock_event_repo, mock_analytics_repo)


@pytest.fixture
def mock_paginated_events(sample_events: list[AnalyticsEvent]) -> PaginatedResult[AnalyticsEvent]:
    return PaginatedResult(items=sample_events, total=len(sample_events), page=1, page_size=20)


@pytest.fixture
def mock_paginated_aggregations(
    sample_aggregated_metric: AggregatedMetric,
) -> PaginatedResult[AggregatedMetric]:
    return PaginatedResult(items=[sample_aggregated_metric], total=1, page=1, page_size=20)
