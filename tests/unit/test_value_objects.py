from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.domain.value_objects import (
    EventPayload,
    FilterCriteria,
    MetricValue,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)


class TestTimeRange:
    def test_create(self, sample_time_range: TimeRange):
        assert sample_time_range.start < sample_time_range.end
        assert sample_time_range.timezone == "UTC"

    def test_invalid_range_raises(self, sample_timestamp: datetime):
        with pytest.raises(ValueError, match="start must be before end"):
            TimeRange(start=sample_timestamp, end=sample_timestamp - timedelta(hours=1))

    def test_equal_times_raises(self, sample_timestamp: datetime):
        with pytest.raises(ValueError, match="start must be before end"):
            TimeRange(start=sample_timestamp, end=sample_timestamp)

    def test_duration_seconds(self, sample_timestamp: datetime):
        tr = TimeRange(
            start=sample_timestamp - timedelta(minutes=5),
            end=sample_timestamp,
        )
        assert tr.duration_seconds() == 300.0

    def test_to_dict(self, sample_time_range: TimeRange):
        d = sample_time_range.to_dict()
        assert "start" in d
        assert "end" in d
        assert d["timezone"] == "UTC"
        assert isinstance(d["start"], str)
        assert isinstance(d["end"], str)


class TestPaginationParams:
    def test_default_values(self):
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20
        assert p.offset == 0
        assert p.limit == 20

    def test_custom_values(self):
        p = PaginationParams(page=3, page_size=10)
        assert p.page == 3
        assert p.page_size == 10
        assert p.offset == 20
        assert p.limit == 10

    def test_page_size_capped(self):
        p = PaginationParams(page=1, page_size=500)
        assert p.page_size == 100

    def test_invalid_page_raises(self):
        with pytest.raises(ValueError, match="page must be >= 1"):
            PaginationParams(page=0)

    def test_invalid_page_size_raises(self):
        with pytest.raises(ValueError, match="page_size must be >= 1"):
            PaginationParams(page_size=0)

    def test_offset_calculation(self):
        assert PaginationParams(page=2, page_size=10).offset == 10
        assert PaginationParams(page=5, page_size=25).offset == 100


class TestPaginatedResult:
    def test_empty_result(self):
        r = PaginatedResult(items=[], total=0, page=1, page_size=20)
        assert r.total_pages == 0
        assert r.has_next is False
        assert r.has_previous is False

    def test_single_page(self):
        r = PaginatedResult(items=[1, 2, 3], total=3, page=1, page_size=20)
        assert r.total_pages == 1
        assert r.has_next is False
        assert r.has_previous is False

    def test_multiple_pages(self):
        r = PaginatedResult(items=list(range(10)), total=25, page=2, page_size=10)
        assert r.total_pages == 3
        assert r.has_next is True
        assert r.has_previous is True

    def test_first_page(self):
        r = PaginatedResult(items=list(range(10)), total=25, page=1, page_size=10)
        assert r.has_next is True
        assert r.has_previous is False

    def test_last_page(self):
        r = PaginatedResult(items=list(range(5)), total=25, page=3, page_size=10)
        assert r.has_next is False
        assert r.has_previous is True

    def test_to_dict(self):
        r = PaginatedResult(items=["a", "b"], total=2, page=1, page_size=10)
        d = r.to_dict()
        assert d["items"] == ["a", "b"]
        assert d["total"] == 2
        assert d["page"] == 1
        assert d["page_size"] == 10
        assert d["total_pages"] == 1
        assert d["has_next"] is False
        assert d["has_previous"] is False

    def test_to_dict_multi_page(self):
        r = PaginatedResult(items=[1], total=100, page=3, page_size=10)
        d = r.to_dict()
        assert d["total_pages"] == 10
        assert d["has_next"] is True
        assert d["has_previous"] is True


class TestEventPayload:
    def test_create(self):
        data = {"event": "click", "value": 42}
        payload = EventPayload.create(data)
        assert payload.data == data
        assert payload.content_type == "application/json"
        assert payload.size_bytes > 0

    def test_size_bytes_accurate(self):
        payload = EventPayload.create({"a": "b"})
        expected = len(b'{"a": "b"}')
        assert payload.size_bytes == expected

    def test_empty_data(self):
        payload = EventPayload.create({})
        assert payload.size_bytes == len(b"{}")
        assert payload.data == {}


class TestFilterCriteria:
    def test_defaults(self):
        f = FilterCriteria()
        assert f.event_types is None
        assert f.sources is None
        assert f.user_ids is None
        assert f.session_ids is None
        assert f.statuses is None
        assert f.search_query is None
        assert f.custom_filters == {}

    def test_with_values(self, sample_filter_criteria: FilterCriteria):
        assert sample_filter_criteria.event_types == ["page_view", "click"]
        assert sample_filter_criteria.sources == ["web-app"]
        assert sample_filter_criteria.user_ids == ["user-1"]

    def test_custom_filters(self):
        f = FilterCriteria(custom_filters={"browser": "chrome"})
        assert f.custom_filters == {"browser": "chrome"}


class TestMetricValue:
    def test_create(self):
        mv = MetricValue(name="cpu_usage", value=85.5, unit="percent", labels={"host": "server1"})
        assert mv.name == "cpu_usage"
        assert mv.value == 85.5
        assert mv.unit == "percent"
        assert mv.labels == {"host": "server1"}

    def test_default_unit(self):
        mv = MetricValue(name="requests", value=100.0)
        assert mv.unit == "count"

    def test_to_dict(self):
        mv = MetricValue(name="latency", value=250.0, unit="ms", labels={"endpoint": "/api"})
        d = mv.to_dict()
        assert d["name"] == "latency"
        assert d["value"] == 250.0
        assert d["unit"] == "ms"
        assert d["labels"] == {"endpoint": "/api"}
