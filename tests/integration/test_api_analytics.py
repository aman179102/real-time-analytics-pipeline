from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient


class TestAnalyticsAggregations:
    async def test_get_aggregations(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "window": "minute",
        }
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 0

    async def test_get_aggregations_with_dimensions(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "window": "hourly",
            "dimension_key": "event_type",
            "dimension_value": "page_view",
        }
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200

    async def test_get_aggregations_invalid_window(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "window": "invalid",
        }
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 422

    async def test_get_aggregations_unauthorized(self, async_client: AsyncClient):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params=params,
        )
        assert response.status_code == 401

    async def test_get_aggregations_pagination(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "page": 1,
            "page_size": 5,
        }
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    async def test_get_latest_aggregation(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        response = await async_client.get(
            "/api/v1/analytics/aggregations/event_count.page_view/latest",
            params={"window": "minute"},
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "metric_id" in data
        assert data["metric_name"] == "event_count.page_view"
        assert data["window"] == "minute"

    async def test_get_latest_aggregation_not_found(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        from unittest.mock import patch
        with patch("src.api.routes.analytics.get_analytics_service") as mock_get_svc:
            svc = mock_get_svc.return_value
            svc.get_latest_aggregation.return_value = None
            response = await async_client.get(
                "/api/v1/analytics/aggregations/nonexistent/latest",
                params={"window": "daily"},
                headers=auth_header,
            )
            assert response.status_code == 404


class TestAnalyticsCounts:
    async def test_get_event_type_counts(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }
        response = await async_client.get(
            "/api/v1/analytics/counts/types",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    async def test_get_source_counts(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }
        response = await async_client.get(
            "/api/v1/analytics/counts/sources",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestAnalyticsRealtime:
    async def test_get_realtime_metrics(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        response = await async_client.get(
            "/api/v1/analytics/realtime",
            params={"window_seconds": 60},
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_range_seconds" in data
        assert "total_events" in data
        assert "events_per_second" in data
        assert "by_type" in data
        assert "by_source" in data
        assert data["time_range_seconds"] == 60

    async def test_get_realtime_metrics_default(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        response = await async_client.get(
            "/api/v1/analytics/realtime",
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["time_range_seconds"] == 60

    async def test_get_realtime_metrics_custom_window(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        response = await async_client.get(
            "/api/v1/analytics/realtime",
            params={"window_seconds": 300},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["time_range_seconds"] == 300

    async def test_get_realtime_metrics_invalid_window(
        self, async_client: AsyncClient, auth_header: dict,
    ):
        response = await async_client.get(
            "/api/v1/analytics/realtime",
            params={"window_seconds": 5},
            headers=auth_header,
        )
        assert response.status_code == 422
