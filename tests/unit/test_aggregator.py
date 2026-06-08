from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.models import AggregatedMetric, AggregationWindow, AnalyticsEvent, EventType


class TestAggregationEngine:
    async def test_aggregate_empty_events(self, aggregation_engine):
        result = await aggregation_engine.aggregate_events([])
        assert result == []

    async def test_aggregate_single_event(self, aggregation_engine, page_view_event: AnalyticsEvent):
        result = await aggregation_engine.aggregate_events([page_view_event])
        assert len(result) == 1
        metric = result[0]
        assert metric.metric_name == "event_count.page_view"
        assert metric.window == AggregationWindow.MINUTE
        assert metric.value == 1.0
        assert metric.count == 1
        assert metric.dimensions["event_type"] == "page_view"
        assert metric.dimensions["source"] == "web-app"

    async def test_aggregate_same_type_source(self, aggregation_engine, page_view_event: AnalyticsEvent):
        e1 = page_view_event
        from copy import deepcopy
        e2 = deepcopy(e1)
        e2.event_id = "second-id"
        result = await aggregation_engine.aggregate_events([e1, e2])
        assert len(result) == 1
        metric = result[0]
        assert metric.value == 2.0
        assert metric.count == 2

    async def test_aggregate_different_types(self, aggregation_engine, sample_events):
        result = await aggregation_engine.aggregate_events(sample_events)
        event_types_seen = {m.dimensions["event_type"] for m in result}
        sources_seen = {m.dimensions["source"] for m in result}
        assert "page_view" in event_types_seen
        assert "click" in event_types_seen
        assert "purchase" in event_types_seen
        assert "signup" in event_types_seen
        assert "error" in event_types_seen
        assert "web-app" in sources_seen
        assert "mobile-app" in sources_seen
        assert "api-gateway" in sources_seen
        assert len(result) == 5

    async def test_aggregate_two_same_one_different(
        self, aggregation_engine, page_view_event: AnalyticsEvent, click_event: AnalyticsEvent,
    ):
        from copy import deepcopy
        pv2 = deepcopy(page_view_event)
        pv2.event_id = "pv-2"
        result = await aggregation_engine.aggregate_events([page_view_event, pv2, click_event])
        assert len(result) == 2
        metric_map = {m.dimensions["event_type"]: m for m in result}
        assert metric_map["page_view"].value == 2.0
        assert metric_map["page_view"].count == 2
        assert metric_map["click"].value == 1.0
        assert metric_map["click"].count == 1

    async def test_get_window_start_minute(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.MINUTE)
        assert ws.second == 0
        assert ws.microsecond == 0
        assert ws.minute == 30

    async def test_get_window_start_hourly(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.HOURLY)
        assert ws.minute == 0
        assert ws.second == 0
        assert ws.microsecond == 0

    async def test_get_window_start_daily(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.DAILY)
        assert ws.hour == 0
        assert ws.minute == 0
        assert ws.second == 0

    async def test_get_window_end_minute(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.MINUTE)
        we = aggregation_engine._get_window_end(ws, AggregationWindow.MINUTE)
        assert (we - ws).total_seconds() == 60

    async def test_get_window_end_hourly(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.HOURLY)
        we = aggregation_engine._get_window_end(ws, AggregationWindow.HOURLY)
        assert (we - ws).total_seconds() == 3600

    async def test_get_window_end_daily(self, aggregation_engine, sample_timestamp: datetime):
        ws = aggregation_engine._get_window_start(sample_timestamp, AggregationWindow.DAILY)
        we = aggregation_engine._get_window_end(ws, AggregationWindow.DAILY)
        assert (we - ws).total_seconds() == 86400

    async def test_aggregate_hourly_window(
        self, aggregation_engine, page_view_event: AnalyticsEvent,
    ):
        result = await aggregation_engine.aggregate_events(
            [page_view_event], window=AggregationWindow.HOURLY,
        )
        metric = result[0]
        assert metric.window == AggregationWindow.HOURLY
        assert metric.window_start.minute == 0
        assert metric.window_start.second == 0

    async def test_aggregate_daily_window(
        self, aggregation_engine, page_view_event: AnalyticsEvent,
    ):
        result = await aggregation_engine.aggregate_events(
            [page_view_event], window=AggregationWindow.DAILY,
        )
        metric = result[0]
        assert metric.window == AggregationWindow.DAILY
        assert metric.window_start.hour == 0
        assert metric.window_start.minute == 0

    async def test_aggregate_multiple_sources(self, aggregation_engine):
        events = [
            AnalyticsEvent(
                event_type=EventType.CLICK,
                source="web",
                payload={"x": 1},
                timestamp=datetime.utcnow(),
            ),
            AnalyticsEvent(
                event_type=EventType.CLICK,
                source="mobile",
                payload={"x": 1},
                timestamp=datetime.utcnow(),
            ),
        ]
        result = await aggregation_engine.aggregate_events(events)
        assert len(result) == 2
        sources = {m.dimensions["source"] for m in result}
        assert sources == {"web", "mobile"}
