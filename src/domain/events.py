from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class DomainEvent:
    event_id: str
    event_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


@dataclass
class EventIngested(DomainEvent):
    source: str = ""
    payload_size: int = 0
    event_type_name: str = ""


@dataclass
class EventProcessed(DomainEvent):
    source: str = ""
    processing_time_ms: float = 0.0
    success: bool = True


@dataclass
class AggregationCompleted(DomainEvent):
    metric_name: str = ""
    window: str = ""
    record_count: int = 0


@dataclass
class RetentionApplied(DomainEvent):
    table_name: str = ""
    records_deleted: int = 0
    cutoff_date: str = ""
