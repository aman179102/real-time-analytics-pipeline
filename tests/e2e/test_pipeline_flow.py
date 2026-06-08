from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_analytics_service,
    get_queue_producer,
    verify_token,
)
from src.api.routes.health import router as health_router
from src.api.routes.auth import router as auth_router
from src.api.routes.events import router as events_router
from src.api.routes.analytics import router as analytics_router
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

E2E_USER_ID = str(uuid.uuid4())
E2E_USERNAME = "e2euser"
E2E_EMAIL = "e2e@test.com"


def create_e2e_token(user_id: str = E2E_USER_ID, role: str = "analyst") -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "username": E2E_USERNAME,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "type": "access",
    }
    return pyjwt.encode(payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm)


@pytest.fixture
def e2e_mock_event_repo() -> AsyncMock:
    repo = AsyncMock(spec=EventRepositoryInterface)

    stored_events: dict[str, AnalyticsEvent] = {}

    async def save(event: AnalyticsEvent) -> str:
        stored_events[event.event_id] = event
        return event.event_id

    async def save_batch(events: list[AnalyticsEvent]) -> list[str]:
        ids = []
        for e in events:
            stored_events[e.event_id] = e
            ids.append(e.event_id)
        return ids

    async def get_by_id(eid: str):
        return stored_events.get(eid)

    now = datetime.utcnow()
    ingested_events = [
        AnalyticsEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PAGE_VIEW,
            source="web-app",
            payload={"url": f"/page/{i}"},
            timestamp=now - timedelta(minutes=i),
            user_id=E2E_USER_ID,
            session_id="e2e-session",
            status=EventStatus.AGGREGATED,
        )
        for i in range(3)
    ]
    for e in ingested_events:
        stored_events[e.event_id] = e

    repo.query.return_value = PaginatedResult(
        items=ingested_events, total=len(ingested_events), page=1, page_size=20,
    )
    repo.save.side_effect = save
    repo.save_batch.side_effect = save_batch
    repo.get_by_id.side_effect = get_by_id
    repo.count_by_type.return_value = {"page_view": 3, "click": 1}
    repo.count_by_source.return_value = {"web-app": 4}
    return repo


@pytest.fixture
def e2e_mock_analytics_repo() -> AsyncMock:
    repo = AsyncMock(spec=AnalyticsRepositoryInterface)
    now = datetime.utcnow()
    ws = now.replace(second=0, microsecond=0)
    metrics = [
        AggregatedMetric(
            metric_id=str(uuid.uuid4()),
            metric_name="event_count.page_view",
            window=AggregationWindow.MINUTE,
            window_start=ws - timedelta(minutes=i + 1),
            window_end=ws - timedelta(minutes=i),
            value=float(3 - i),
            count=3 - i,
            dimensions={"event_type": "page_view", "source": "web-app"},
        )
        for i in range(3)
    ]
    repo.query_aggregations.return_value = PaginatedResult(
        items=metrics, total=len(metrics), page=1, page_size=20,
    )
    repo.get_latest_aggregation.return_value = metrics[0] if metrics else None
    repo.save_aggregation.return_value = str(uuid.uuid4())
    return repo


@pytest.fixture
def e2e_mock_dashboard_repo() -> AsyncMock:
    repo = AsyncMock(spec=DashboardRepositoryInterface)
    dashboard = Dashboard(
        name="E2E Dashboard",
        description="Created during e2e test",
        widgets=[
            DashboardWidget(
                title="Page Views",
                widget_type=WidgetType.TIMESERIES,
                metric_name="event_count.page_view",
                config={"period": "24h"},
                position=0,
            ),
        ],
        owner_id=E2E_USER_ID,
    )
    repo.save.return_value = dashboard.dashboard_id
    repo.get_by_id.return_value = dashboard
    repo.list_dashboards.return_value = PaginatedResult(
        items=[dashboard], total=1, page=1, page_size=20,
    )
    return repo


@pytest.fixture
def e2e_mock_cache() -> AsyncMock:
    cache = AsyncMock(spec=CacheInterface)
    cache.get.return_value = None
    return cache


@pytest.fixture
def e2e_mock_producer() -> AsyncMock:
    producer = AsyncMock(spec=QueueProducerInterface)
    producer.publish.return_value = str(uuid.uuid4())
    producer.publish_batch.return_value = [str(uuid.uuid4())]
    return producer


@pytest.fixture
def e2e_mock_analytics_service(
    e2e_mock_event_repo: AsyncMock,
    e2e_mock_analytics_repo: AsyncMock,
    e2e_mock_dashboard_repo: AsyncMock,
    e2e_mock_cache: AsyncMock,
):
    from src.core.analytics_service import AnalyticsService
    return AnalyticsService(
        e2e_mock_event_repo, e2e_mock_analytics_repo,
        e2e_mock_dashboard_repo, e2e_mock_cache,
    )


@pytest.fixture
def e2e_test_app(
    e2e_mock_analytics_service,
    e2e_mock_producer: AsyncMock,
    e2e_mock_event_repo: AsyncMock,
) -> FastAPI:
    app = FastAPI()

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(analytics_router)

    async def override_verify_token():
        now = datetime.utcnow()
        return {
            "sub": E2E_USER_ID,
            "username": E2E_USERNAME,
            "role": "analyst",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "type": "access",
        }

    async def override_get_queue_producer():
        yield e2e_mock_producer

    async def override_get_analytics_service():
        return e2e_mock_analytics_service

    app.dependency_overrides[verify_token] = override_verify_token
    app.dependency_overrides[get_queue_producer] = override_get_queue_producer
    app.dependency_overrides[get_analytics_service] = override_get_analytics_service

    return app


@pytest.fixture
async def e2e_client(e2e_test_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=e2e_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestPipelineFlow:
    async def test_full_pipeline_flow(self, e2e_client: AsyncClient):
        now = datetime.utcnow()

        with patch("src.api.routes.auth._get_user_by_username", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None
            with patch("src.api.routes.auth._get_user_by_email", new_callable=AsyncMock) as mock_get_email:
                mock_get_email.return_value = None
                with patch("src.api.routes.auth.db_manager.session") as mock_session_ctx:
                    mock_session = AsyncMock()
                    mock_session_ctx.return_value.__aenter__.return_value = mock_session

                    register_response = await e2e_client.post(
                        "/api/v1/auth/register",
                        json={
                            "username": E2E_USERNAME,
                            "email": E2E_EMAIL,
                            "password": "e2epassword123",
                        },
                    )
                    assert register_response.status_code == 201
                    register_data = register_response.json()
                    assert "access_token" in register_data
                    assert "refresh_token" in register_data
                    access_token = register_data["access_token"]

        auth_headers = {"Authorization": f"Bearer {access_token}"}

        ingest_response = await e2e_client.post(
            "/api/v1/events/ingest",
            json={
                "event_type": "page_view",
                "source": "web-app",
                "payload": {"url": "/dashboard", "referrer": "/login"},
                "user_id": E2E_USER_ID,
                "session_id": "e2e-session",
            },
            headers=auth_headers,
        )
        assert ingest_response.status_code == 201
        ingest_data = ingest_response.json()
        event_id = ingest_data["event_id"]
        assert ingest_data["status"] == "accepted"

        batch_response = await e2e_client.post(
            "/api/v1/events/ingest/batch",
            json=[
                {
                    "event_type": "click",
                    "source": "web-app",
                    "payload": {"element": "nav-button", "page": "/dashboard"},
                },
                {
                    "event_type": "page_view",
                    "source": "mobile-app",
                    "payload": {"url": "/settings"},
                },
            ],
            headers=auth_headers,
        )
        assert batch_response.status_code == 201
        batch_data = batch_response.json()
        assert batch_data["count"] == 2

        query_response = await e2e_client.get(
            "/api/v1/events",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": now.isoformat(),
                "page": 1,
                "page_size": 10,
            },
            headers=auth_headers,
        )
        assert query_response.status_code == 200
        query_data = query_response.json()
        assert query_data["total"] >= 0
        assert "items" in query_data

        event_detail_response = await e2e_client.get(
            f"/api/v1/events/{event_id}",
            headers=auth_headers,
        )
        assert event_detail_response.status_code in (200, 404)

        agg_response = await e2e_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": now.isoformat(),
                "window": "minute",
            },
            headers=auth_headers,
        )
        assert agg_response.status_code == 200
        agg_data = agg_response.json()
        assert "items" in agg_data

        latest_response = await e2e_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view/latest",
            params={"window": "minute"},
            headers=auth_headers,
        )
        assert latest_response.status_code == 200
        latest_data = latest_response.json()
        assert latest_data["metric_name"] == "event_count.page_view"

        type_counts_response = await e2e_client.get(
            "/api/v1/analytics/counts/types",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": now.isoformat(),
            },
            headers=auth_headers,
        )
        assert type_counts_response.status_code == 200
        type_counts = type_counts_response.json()
        assert isinstance(type_counts, dict)

        source_counts_response = await e2e_client.get(
            "/api/v1/analytics/counts/sources",
            params={
                "start": (now - timedelta(hours=1)).isoformat(),
                "end": now.isoformat(),
            },
            headers=auth_headers,
        )
        assert source_counts_response.status_code == 200
        source_counts = source_counts_response.json()
        assert isinstance(source_counts, dict)

        realtime_response = await e2e_client.get(
            "/api/v1/analytics/realtime",
            params={"window_seconds": 60},
            headers=auth_headers,
        )
        assert realtime_response.status_code == 200
        realtime_data = realtime_response.json()
        assert "total_events" in realtime_data
        assert "events_per_second" in realtime_data
        assert "by_type" in realtime_data
        assert "by_source" in realtime_data

    async def test_pipeline_health_check(self, e2e_client: AsyncClient):
        response = await e2e_client.get("/health")
        assert response.status_code == 200

    async def test_pipeline_unauthorized_access(self, e2e_client: AsyncClient):
        response = await e2e_client.get("/api/v1/events")
        assert response.status_code == 401

    async def test_pipeline_invalid_event_rejected(self, e2e_client: AsyncClient):
        token = create_e2e_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = await e2e_client.post(
            "/api/v1/events/ingest",
            json={"event_type": "", "source": "", "payload": {}},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_pipeline_multiple_event_types(self, e2e_client: AsyncClient):
        token = create_e2e_token()
        headers = {"Authorization": f"Bearer {token}"}

        for event_type in ["page_view", "click", "purchase", "signup", "login", "logout", "error"]:
            response = await e2e_client.post(
                "/api/v1/events/ingest",
                json={
                    "event_type": event_type,
                    "source": "e2e-test",
                    "payload": {"type": event_type},
                },
                headers=headers,
            )
            assert response.status_code == 201
