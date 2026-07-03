from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.models import (
    AggregatedMetric,
    AggregationWindow,
    AnalyticsEvent,
    Dashboard,
    EventType,
)
from src.domain.value_objects import (
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)


class TestAnalyticsService:
    async def test_get_events_no_cache(
        self, analytics_service, sample_time_range: TimeRange,
        sample_pagination: PaginationParams, sample_events,
    ):
        analytics_service._event_repo.query.return_value = PaginatedResult(
            items=sample_events, total=5, page=1, page_size=20,
        )
        result = await analytics_service.get_events(sample_time_range, None, sample_pagination)
        assert len(result.items) == 5
        assert result.total == 5
        analytics_service._event_repo.query.assert_awaited_once()

    async def test_get_events_from_cache(
        self, analytics_service, sample_time_range: TimeRange,
        sample_pagination: PaginationParams, sample_events,
    ):
        cache_data = {
            "items": [e.to_dict() for e in sample_events],
            "total": 5,
            "page": 1,
            "page_size": 20,
        }
        analytics_service._cache.get.return_value = json.dumps(cache_data, default=str)
        result = await analytics_service.get_events(sample_time_range, None, sample_pagination)
        assert len(result.items) == 5
        analytics_service._event_repo.query.assert_not_awaited()

    async def test_get_events_caches_result(
        self, analytics_service, sample_time_range: TimeRange,
        sample_pagination: PaginationParams, sample_events,
    ):
        analytics_service._event_repo.query.return_value = PaginatedResult(
            items=sample_events, total=5, page=1, page_size=20,
        )
        await analytics_service.get_events(sample_time_range, None, sample_pagination)
        analytics_service._cache.set.assert_awaited_once()

    async def test_get_event_by_id_not_cached(
        self, analytics_service,
    ):
        eid = "test-id"
        event = AnalyticsEvent(event_id=eid, event_type=EventType.CLICK, source="web", payload={})
        analytics_service._event_repo.get_by_id.return_value = event
        result = await analytics_service.get_event_by_id(eid)
        assert result == event
        analytics_service._event_repo.get_by_id.assert_awaited_once_with(eid)

    async def test_get_event_by_id_cached(
        self, analytics_service,
    ):
        eid = "cached-id"
        event = AnalyticsEvent(event_id=eid, event_type=EventType.CLICK, source="web", payload={})
        analytics_service._cache.get.return_value = json.dumps(event.to_dict(), default=str)
        result = await analytics_service.get_event_by_id(eid)
        assert result is not None
        assert result.event_id == eid
        analytics_service._event_repo.get_by_id.assert_not_awaited()

    async def test_get_aggregations(
        self, analytics_service, sample_time_range: TimeRange,
        sample_aggregated_metric: AggregatedMetric,
    ):
        analytics_service._analytics_repo.query_aggregations.return_value = PaginatedResult(
            items=[sample_aggregated_metric], total=1, page=1, page_size=20,
        )
        result = await analytics_service.get_aggregations(
            "event_count.page_view", AggregationWindow.MINUTE, sample_time_range,
        )
        assert len(result.items) == 1
        assert result.items[0].metric_name == "event_count.page_view"

    async def test_get_aggregations_from_cache(
        self, analytics_service, sample_time_range: TimeRange,
        sample_aggregated_metric: AggregatedMetric,
    ):
        cache_data = {
            "items": [sample_aggregated_metric.to_dict()],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
        analytics_service._cache.get.return_value = json.dumps(cache_data, default=str)
        result = await analytics_service.get_aggregations(
            "event_count.page_view", AggregationWindow.MINUTE, sample_time_range,
        )
        assert len(result.items) == 1
        analytics_service._analytics_repo.query_aggregations.assert_not_awaited()

    async def test_get_latest_aggregation(
        self, analytics_service, sample_aggregated_metric: AggregatedMetric,
    ):
        analytics_service._analytics_repo.get_latest_aggregation.return_value = sample_aggregated_metric
        result = await analytics_service.get_latest_aggregation(
            "event_count.page_view", AggregationWindow.MINUTE,
        )
        assert result is not None
        assert result.metric_name == "event_count.page_view"

    async def test_get_event_type_counts(
        self, analytics_service, sample_time_range: TimeRange,
    ):
        counts = await analytics_service.get_event_type_counts(sample_time_range)
        assert counts == {"page_view": 10, "click": 5}

    async def test_get_source_counts(
        self, analytics_service, sample_time_range: TimeRange,
    ):
        counts = await analytics_service.get_source_counts(sample_time_range)
        assert counts == {"web-app": 12, "mobile-app": 3}

    async def test_create_dashboard(
        self, analytics_service, sample_dashboard: Dashboard,
    ):
        did = await analytics_service.create_dashboard(sample_dashboard)
        assert did is not None
        analytics_service._dashboard_repo.save.assert_awaited_once_with(sample_dashboard)

    async def test_get_dashboard_from_repo(
        self, analytics_service, sample_dashboard: Dashboard,
    ):
        analytics_service._dashboard_repo.get_by_id.return_value = sample_dashboard
        result = await analytics_service.get_dashboard(sample_dashboard.dashboard_id)
        assert result is not None
        assert result.name == "Main Dashboard"
        analytics_service._cache.set.assert_awaited_once()

    async def test_get_dashboard_from_cache(
        self, analytics_service, sample_dashboard: Dashboard,
    ):
        analytics_service._cache.get.return_value = json.dumps(sample_dashboard.to_dict(), default=str)
        result = await analytics_service.get_dashboard(sample_dashboard.dashboard_id)
        assert result is not None
        assert result.name == "Main Dashboard"
        analytics_service._dashboard_repo.get_by_id.assert_not_awaited()

    async def test_list_dashboards(
        self, analytics_service, sample_dashboard: Dashboard,
    ):
        analytics_service._dashboard_repo.list_dashboards.return_value = PaginatedResult(
            items=[sample_dashboard], total=1, page=1, page_size=20,
        )
        result = await analytics_service.list_dashboards("user-1")
        assert len(result.items) == 1

    async def test_update_dashboard(
        self, analytics_service, sample_dashboard: Dashboard,
    ):
        await analytics_service.update_dashboard(sample_dashboard)
        analytics_service._dashboard_repo.update.assert_awaited_once_with(sample_dashboard)
        analytics_service._cache.delete.assert_awaited_once()

    async def test_delete_dashboard(
        self, analytics_service,
    ):
        await analytics_service.delete_dashboard("d-1")
        analytics_service._dashboard_repo.delete.assert_awaited_once_with("d-1")
        analytics_service._cache.delete.assert_awaited_once()

    async def test_get_realtime_metrics(
        self, analytics_service, sample_time_range: TimeRange,
    ):
        with patch.object(analytics_service, "get_event_type_counts") as mock_type:
            mock_type.return_value = {"page_view": 60, "click": 30}
            with patch.object(analytics_service, "get_source_counts") as mock_source:
                mock_source.return_value = {"web": 80, "mobile": 10}
                result = await analytics_service.get_realtime_metrics(window_seconds=60)
                assert result["total_events"] == 90
                assert result["events_per_second"] == 1.5
                assert result["time_range_seconds"] == 60

    async def test_build_cache_key_includes_filters(
        self, analytics_service, sample_time_range: TimeRange,
    ):
        filters = FilterCriteria(event_types=["page_view"])
        pagination = PaginationParams(page=2, page_size=10)
        key = analytics_service._build_cache_key("events", sample_time_range, filters, pagination)
        assert key.startswith("events")
        assert "p2s10" in key
