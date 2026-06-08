from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    PAGE_VIEW = "page_view"
    CLICK = "click"
    SIGNUP = "signup"
    PURCHASE = "purchase"
    LOGIN = "login"
    LOGOUT = "logout"
    ERROR = "error"
    CUSTOM = "custom"


class EventStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    AGGREGATED = "aggregated"
    SAMPLED = "sampled"
    RETENTION_EXPIRED = "retention_expired"
    ERROR = "error"


class AggregationWindow(str, Enum):
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"


class WidgetType(str, Enum):
    TIMESERIES = "timeseries"
    COUNTER = "counter"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    HEATMAP = "heatmap"


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AnalyticsEvent:
    def __init__(
        self,
        event_type: EventType,
        source: str,
        payload: dict[str, Any],
        timestamp: Optional[datetime] = None,
        event_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: EventStatus = EventStatus.RECEIVED,
    ):
        self.event_id = event_id or str(uuid.uuid4())
        self.event_type = event_type
        self.source = source
        self.payload = payload
        self.timestamp = timestamp or datetime.utcnow()
        self.user_id = user_id
        self.session_id = session_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalyticsEvent:
        return cls(
            event_id=data.get("event_id"),
            event_type=EventType(data["event_type"]),
            source=data["source"],
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            status=EventStatus(data.get("status", "received")),
        )


class AggregatedMetric:
    def __init__(
        self,
        metric_name: str,
        window: AggregationWindow,
        window_start: datetime,
        window_end: datetime,
        value: float,
        count: int,
        dimensions: Optional[dict[str, str]] = None,
        metric_id: Optional[str] = None,
    ):
        self.metric_id = metric_id or str(uuid.uuid4())
        self.metric_name = metric_name
        self.window = window
        self.window_start = window_start
        self.window_end = window_end
        self.value = value
        self.count = count
        self.dimensions = dimensions or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "metric_name": self.metric_name,
            "window": self.window.value,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "value": self.value,
            "count": self.count,
            "dimensions": self.dimensions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AggregatedMetric:
        return cls(
            metric_id=data.get("metric_id"),
            metric_name=data["metric_name"],
            window=AggregationWindow(data["window"]),
            window_start=datetime.fromisoformat(data["window_start"]),
            window_end=datetime.fromisoformat(data["window_end"]),
            value=float(data["value"]),
            count=int(data["count"]),
            dimensions=data.get("dimensions", {}),
        )


class DashboardWidget:
    def __init__(
        self,
        title: str,
        widget_type: WidgetType,
        metric_name: str,
        config: dict[str, Any],
        position: int,
        widget_id: Optional[str] = None,
        width: int = 6,
        height: int = 4,
    ):
        self.widget_id = widget_id or str(uuid.uuid4())
        self.title = title
        self.widget_type = widget_type
        self.metric_name = metric_name
        self.config = config
        self.position = position
        self.width = width
        self.height = height

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "widget_type": self.widget_type.value,
            "metric_name": self.metric_name,
            "config": self.config,
            "position": self.position,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardWidget:
        return cls(
            widget_id=data.get("widget_id"),
            title=data["title"],
            widget_type=WidgetType(data["widget_type"]),
            metric_name=data["metric_name"],
            config=data.get("config", {}),
            position=data["position"],
            width=data.get("width", 6),
            height=data.get("height", 4),
        )


class Dashboard:
    def __init__(
        self,
        name: str,
        description: str,
        widgets: Optional[list[DashboardWidget]] = None,
        dashboard_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_public: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.dashboard_id = dashboard_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.widgets = widgets or []
        self.owner_id = owner_id
        self.is_public = is_public
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "widgets": [w.to_dict() for w in self.widgets],
            "owner_id": self.owner_id,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dashboard:
        return cls(
            dashboard_id=data.get("dashboard_id"),
            name=data["name"],
            description=data["description"],
            widgets=[DashboardWidget.from_dict(w) for w in data.get("widgets", [])],
            owner_id=data.get("owner_id"),
            is_public=data.get("is_public", False),
            created_at=datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str)
            else data.get("created_at"),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if isinstance(data.get("updated_at"), str)
            else data.get("updated_at"),
        )


class User:
    def __init__(
        self,
        username: str,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.VIEWER,
        user_id: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.user_id = user_id or str(uuid.uuid4())
        self.username = username
        self.email = email
        self.hashed_password = hashed_password
        self.role = role
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> User:
        return cls(
            user_id=data.get("user_id"),
            username=data["username"],
            email=data["email"],
            hashed_password=data["hashed_password"],
            role=UserRole(data.get("role", "viewer")),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str)
            else data.get("created_at"),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if isinstance(data.get("updated_at"), str)
            else data.get("updated_at"),
        )


class RetainedDataRecord:
    def __init__(
        self,
        table_name: str,
        partition_name: str,
        retention_date: datetime,
        deleted_at: datetime,
        record_id: Optional[str] = None,
    ):
        self.record_id = record_id or str(uuid.uuid4())
        self.table_name = table_name
        self.partition_name = partition_name
        self.retention_date = retention_date
        self.deleted_at = deleted_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "table_name": self.table_name,
            "partition_name": self.partition_name,
            "retention_date": self.retention_date.isoformat(),
            "deleted_at": self.deleted_at.isoformat(),
        }
