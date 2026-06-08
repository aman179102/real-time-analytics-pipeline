from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    CacheInterface,
    DashboardRepositoryInterface,
    EventRepositoryInterface,
)
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
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(
        self,
        event_repo: EventRepositoryInterface,
        analytics_repo: AnalyticsRepositoryInterface,
        dashboard_repo: DashboardRepositoryInterface,
        cache: CacheInterface,
    ) -> None:
        self._event_repo = event_repo
        self._analytics_repo = analytics_repo
        self._dashboard_repo = dashboard_repo
        self._cache = cache

    async def get_events(
        self,
        time_range: TimeRange,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AnalyticsEvent]:
        cache_key = self._build_cache_key("events", time_range, filters, pagination)
        cached = await self._cache.get(cache_key)
        if cached:
            import json
            try:
                data = json.loads(cached)
                items = [AnalyticsEvent.from_dict(e) for e in data.get("items", [])]
                return PaginatedResult(
                    items=items,
                    total=data["total"],
                    page=data["page"],
                    page_size=data["page_size"],
                )
            except Exception:
                pass

        result = await self._event_repo.query(time_range, filters, pagination)

        try:
            import json
            cache_data = {
                "items": [e.to_dict() for e in result.items],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
            }
            await self._cache.set(cache_key, json.dumps(cache_data, default=str), 60)
        except Exception:
            pass

        metrics.increment_counter("analytics_queries")
        return result

    async def get_event_by_id(
        self, event_id: str
    ) -> Optional[AnalyticsEvent]:
        cached = await self._cache.get(f"event:{event_id}")
        if cached:
            return AnalyticsEvent(event_id=event_id, event_type=EventType.CUSTOM, source="cache", payload={})

        event = await self._event_repo.get_by_id(event_id)
        return event

    async def get_aggregations(
        self,
        metric_name: str,
        window: AggregationWindow,
        time_range: TimeRange,
        dimensions: Optional[dict[str, str]] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AggregatedMetric]:
        cache_key = self._build_cache_key(
            f"agg:{metric_name}:{window.value}", time_range, None, pagination
        )
        cached = await self._cache.get(cache_key)
        if cached:
            import json
            try:
                data = json.loads(cached)
                items = [AggregatedMetric.from_dict(m) for m in data.get("items", [])]
                return PaginatedResult(
                    items=items,
                    total=data["total"],
                    page=data["page"],
                    page_size=data["page_size"],
                )
            except Exception:
                pass

        result = await self._analytics_repo.query_aggregations(
            metric_name, window, time_range, dimensions, pagination
        )

        try:
            import json
            cache_data = {
                "items": [m.to_dict() for m in result.items],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
            }
            await self._cache.set(cache_key, json.dumps(cache_data, default=str), 120)
        except Exception:
            pass

        return result

    async def get_latest_aggregation(
        self,
        metric_name: str,
        window: AggregationWindow,
    ) -> Optional[AggregatedMetric]:
        return await self._analytics_repo.get_latest_aggregation(
            metric_name, window
        )

    async def get_event_type_counts(
        self, time_range: TimeRange
    ) -> dict[str, int]:
        cache_key = f"counts:types:{time_range.start.isoformat()}:{time_range.end.isoformat()}"
        cached = await self._cache.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        counts = await self._event_repo.count_by_type(time_range)
        await self._cache.set(cache_key, str(counts).replace("'", '"'), 60)
        return counts

    async def get_source_counts(
        self, time_range: TimeRange
    ) -> dict[str, int]:
        cache_key = f"counts:sources:{time_range.start.isoformat()}:{time_range.end.isoformat()}"
        cached = await self._cache.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        counts = await self._event_repo.count_by_source(time_range)
        await self._cache.set(cache_key, str(counts).replace("'", '"'), 60)
        return counts

    async def create_dashboard(self, dashboard: Dashboard) -> str:
        dashboard_id = await self._dashboard_repo.save(dashboard)
        metrics.increment_counter("dashboards_created")
        return dashboard_id

    async def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        cached = await self._cache.get(f"dashboard:{dashboard_id}")
        if cached:
            import json
            try:
                return Dashboard.from_dict(json.loads(cached))
            except Exception:
                pass

        dashboard = await self._dashboard_repo.get_by_id(dashboard_id)
        if dashboard:
            import json
            await self._cache.set(
                f"dashboard:{dashboard_id}",
                json.dumps(dashboard.to_dict(), default=str),
                300,
            )
        return dashboard

    async def list_dashboards(
        self,
        owner_id: Optional[str] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Dashboard]:
        return await self._dashboard_repo.list_dashboards(owner_id, pagination)

    async def update_dashboard(self, dashboard: Dashboard) -> None:
        await self._dashboard_repo.update(dashboard)
        await self._cache.delete(f"dashboard:{dashboard.dashboard_id}")

    async def delete_dashboard(self, dashboard_id: str) -> None:
        await self._dashboard_repo.delete(dashboard_id)
        await self._cache.delete(f"dashboard:{dashboard_id}")

    async def get_realtime_metrics(
        self, window_seconds: int = 60
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        time_range = TimeRange(
            start=now - timedelta(seconds=window_seconds),
            end=now,
        )
        type_counts = await self.get_event_type_counts(time_range)
        source_counts = await self.get_source_counts(time_range)
        total = sum(type_counts.values())

        return {
            "time_range_seconds": window_seconds,
            "total_events": total,
            "events_per_second": round(total / max(window_seconds, 1), 2),
            "by_type": type_counts,
            "by_source": source_counts,
        }

    def _build_cache_key(
        self,
        prefix: str,
        time_range: TimeRange,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> str:
        parts = [
            prefix,
            time_range.start.isoformat(),
            time_range.end.isoformat(),
        ]
        if filters:
            parts.append(str(hash(str(filters))))
        if pagination:
            parts.append(f"p{pagination.page}s{pagination.page_size}")
        return ":".join(parts)
