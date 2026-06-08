from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from src.domain.models import (
    AggregatedMetric,
    AggregationWindow,
    AnalyticsEvent,
    Dashboard,
    User,
)
from src.domain.value_objects import (
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)


class EventRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, event: AnalyticsEvent) -> str:
        ...

    @abstractmethod
    async def save_batch(self, events: list[AnalyticsEvent]) -> list[str]:
        ...

    @abstractmethod
    async def get_by_id(self, event_id: str) -> Optional[AnalyticsEvent]:
        ...

    @abstractmethod
    async def query(
        self,
        time_range: TimeRange,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AnalyticsEvent]:
        ...

    @abstractmethod
    async def count_by_type(
        self, time_range: TimeRange
    ) -> dict[str, int]:
        ...

    @abstractmethod
    async def count_by_source(
        self, time_range: TimeRange
    ) -> dict[str, int]:
        ...

    @abstractmethod
    async def delete_older_than(self, cutoff: datetime) -> int:
        ...


class AnalyticsRepositoryInterface(ABC):
    @abstractmethod
    async def save_aggregation(
        self, metric: AggregatedMetric
    ) -> str:
        ...

    @abstractmethod
    async def get_aggregation(
        self,
        metric_name: str,
        window: AggregationWindow,
        window_start: datetime,
        window_end: datetime,
        dimensions: Optional[dict[str, str]] = None,
    ) -> Optional[AggregatedMetric]:
        ...

    @abstractmethod
    async def query_aggregations(
        self,
        metric_name: str,
        window: AggregationWindow,
        time_range: TimeRange,
        dimensions: Optional[dict[str, str]] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AggregatedMetric]:
        ...

    @abstractmethod
    async def get_latest_aggregation(
        self,
        metric_name: str,
        window: AggregationWindow,
    ) -> Optional[AggregatedMetric]:
        ...

    @abstractmethod
    async def delete_aggregations_older_than(
        self, window: AggregationWindow, cutoff: datetime
    ) -> int:
        ...


class DashboardRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, dashboard: Dashboard) -> str:
        ...

    @abstractmethod
    async def get_by_id(self, dashboard_id: str) -> Optional[Dashboard]:
        ...

    @abstractmethod
    async def list_dashboards(
        self,
        owner_id: Optional[str] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Dashboard]:
        ...

    @abstractmethod
    async def update(self, dashboard: Dashboard) -> None:
        ...

    @abstractmethod
    async def delete(self, dashboard_id: str) -> None:
        ...


class QueueProducerInterface(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def publish(
        self, event: AnalyticsEvent
    ) -> str:
        ...

    @abstractmethod
    async def publish_batch(
        self, events: list[AnalyticsEvent]
    ) -> list[str]:
        ...


class QueueConsumerInterface(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def consume(
        self,
        batch_size: int = 100,
        timeout_ms: int = 1000,
    ) -> list[AnalyticsEvent]:
        ...

    @abstractmethod
    async def acknowledge(self, event: AnalyticsEvent) -> None:
        ...

    @abstractmethod
    async def acknowledge_batch(self, events: list[AnalyticsEvent]) -> None:
        ...


class CacheInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    async def set(
        self, key: str, value: str, ttl_seconds: int = 300
    ) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def incr(self, key: str) -> int:
        ...

    @abstractmethod
    async def expire(self, key: str, ttl_seconds: int) -> None:
        ...


class RetentionPolicyInterface(ABC):
    @abstractmethod
    async def apply_retention_policy(self) -> dict[str, int]:
        ...

    @abstractmethod
    async def get_retention_summary(self) -> dict[str, Any]:
        ...


class AggregationEngineInterface(ABC):
    @abstractmethod
    async def aggregate_events(
        self,
        events: list[AnalyticsEvent],
        window: AggregationWindow,
    ) -> list[AggregatedMetric]:
        ...

    @abstractmethod
    async def rollup_aggregations(
        self,
        source_window: AggregationWindow,
        target_window: AggregationWindow,
    ) -> int:
        ...
