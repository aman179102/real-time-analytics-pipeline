from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class EventPayload:
    data: dict[str, Any]
    content_type: str = "application/json"
    size_bytes: int = 0

    @classmethod
    def create(cls, data: dict[str, Any]) -> EventPayload:
        import json
        raw = json.dumps(data, default=str)
        return cls(
            data=data,
            size_bytes=len(raw.encode("utf-8")),
        )


@dataclass
class MetricValue:
    name: str
    value: float
    unit: str = "count"
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "labels": self.labels,
        }


@dataclass
class TimeRange:
    start: datetime
    end: datetime
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("start must be before end")

    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "timezone": self.timezone,
        }


@dataclass
class PaginationParams:
    page: int = 1
    page_size: int = 20
    max_page_size: int = 100

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.page_size < 1:
            raise ValueError("page_size must be >= 1")
        if self.page_size > self.max_page_size:
            self.page_size = self.max_page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


@dataclass
class PaginatedResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
        }


@dataclass
class FilterCriteria:
    event_types: Optional[list[str]] = None
    sources: Optional[list[str]] = None
    user_ids: Optional[list[str]] = None
    session_ids: Optional[list[str]] = None
    statuses: Optional[list[str]] = None
    search_query: Optional[str] = None
    custom_filters: dict[str, Any] = field(default_factory=dict)

# feat: implement file storage with full test coverage
