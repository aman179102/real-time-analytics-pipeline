from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from src.domain.models import (
    AggregatedMetric,
    AggregationWindow,
    AnalyticsEvent,
    Dashboard,
    DashboardWidget,
    EventStatus,
    EventType,
    RetainedDataRecord,
    User,
    UserRole,
    WidgetType,
)


class TestAnalyticsEvent:
    def test_create_defaults(self):
        event = AnalyticsEvent(
            event_type=EventType.PAGE_VIEW,
            source="web",
            payload={"url": "/"},
        )
        assert event.event_id is not None
        assert uuid.UUID(event.event_id)
        assert event.event_type == EventType.PAGE_VIEW
        assert event.source == "web"
        assert event.payload == {"url": "/"}
        assert event.status == EventStatus.RECEIVED
        assert isinstance(event.timestamp, datetime)
        assert event.user_id is None
        assert event.session_id is None

    def test_create_with_all_fields(self, sample_timestamp: datetime):
        eid = str(uuid.uuid4())
        event = AnalyticsEvent(
            event_id=eid,
            event_type=EventType.PURCHASE,
            source="mobile",
            payload={"amount": 99.99},
            timestamp=sample_timestamp,
            user_id="u1",
            session_id="s1",
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
            status=EventStatus.PROCESSING,
        )
        assert event.event_id == eid
        assert event.event_type == EventType.PURCHASE
        assert event.source == "mobile"
        assert event.payload == {"amount": 99.99}
        assert event.timestamp == sample_timestamp
        assert event.user_id == "u1"
        assert event.session_id == "s1"
        assert event.ip_address == "10.0.0.1"
        assert event.user_agent == "TestAgent/1.0"
        assert event.status == EventStatus.PROCESSING

    def test_to_dict(self, page_view_event: AnalyticsEvent):
        d = page_view_event.to_dict()
        assert d["event_id"] == page_view_event.event_id
        assert d["event_type"] == "page_view"
        assert d["source"] == "web-app"
        assert d["payload"] == {"url": "/home", "referrer": "/login", "duration_ms": 1500}
        assert "timestamp" in d
        assert d["user_id"] == "user-1"
        assert d["session_id"] == "session-abc"
        assert d["status"] == "received"

    def test_from_dict_roundtrip(self, page_view_event: AnalyticsEvent):
        d = page_view_event.to_dict()
        restored = AnalyticsEvent.from_dict(d)
        assert restored.event_id == page_view_event.event_id
        assert restored.event_type == page_view_event.event_type
        assert restored.source == page_view_event.source
        assert restored.payload == page_view_event.payload
        assert restored.user_id == page_view_event.user_id
        assert restored.session_id == page_view_event.session_id
        assert restored.ip_address == page_view_event.ip_address
        assert restored.user_agent == page_view_event.user_agent
        assert restored.status == page_view_event.status

    def test_from_dict_with_string_timestamp(self):
        now = datetime.utcnow()
        data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "login",
            "source": "web",
            "payload": {},
            "timestamp": now.isoformat(),
            "status": "processing",
        }
        event = AnalyticsEvent.from_dict(data)
        assert event.event_type == EventType.LOGIN
        assert event.status == EventStatus.PROCESSING
        assert event.timestamp == now

    def test_event_type_values(self):
        assert EventType.PAGE_VIEW.value == "page_view"
        assert EventType.CLICK.value == "click"
        assert EventType.SIGNUP.value == "signup"
        assert EventType.PURCHASE.value == "purchase"
        assert EventType.LOGIN.value == "login"
        assert EventType.LOGOUT.value == "logout"
        assert EventType.ERROR.value == "error"
        assert EventType.CUSTOM.value == "custom"

    def test_event_status_values(self):
        assert EventStatus.RECEIVED.value == "received"
        assert EventStatus.PROCESSING.value == "processing"
        assert EventStatus.AGGREGATED.value == "aggregated"
        assert EventStatus.SAMPLED.value == "sampled"
        assert EventStatus.RETENTION_EXPIRED.value == "retention_expired"
        assert EventStatus.ERROR.value == "error"


class TestAggregatedMetric:
    def test_create(self, sample_timestamp: datetime):
        ws = sample_timestamp.replace(second=0, microsecond=0)
        we = ws + timedelta(minutes=1)
        metric = AggregatedMetric(
            metric_name="event_count.purchase",
            window=AggregationWindow.MINUTE,
            window_start=ws,
            window_end=we,
            value=10.0,
            count=10,
            dimensions={"event_type": "purchase", "source": "web"},
        )
        assert metric.metric_id is not None
        assert uuid.UUID(metric.metric_id)
        assert metric.metric_name == "event_count.purchase"
        assert metric.window == AggregationWindow.MINUTE
        assert metric.window_start == ws
        assert metric.window_end == we
        assert metric.value == 10.0
        assert metric.count == 10
        assert metric.dimensions == {"event_type": "purchase", "source": "web"}

    def test_to_dict_roundtrip(self, sample_aggregated_metric: AggregatedMetric):
        d = sample_aggregated_metric.to_dict()
        restored = AggregatedMetric.from_dict(d)
        assert restored.metric_id == sample_aggregated_metric.metric_id
        assert restored.metric_name == sample_aggregated_metric.metric_name
        assert restored.window == sample_aggregated_metric.window
        assert restored.window_start == sample_aggregated_metric.window_start
        assert restored.window_end == sample_aggregated_metric.window_end
        assert restored.value == sample_aggregated_metric.value
        assert restored.count == sample_aggregated_metric.count
        assert restored.dimensions == sample_aggregated_metric.dimensions

    def test_window_types(self):
        assert AggregationWindow.MINUTE.value == "minute"
        assert AggregationWindow.HOURLY.value == "hourly"
        assert AggregationWindow.DAILY.value == "daily"

    def test_empty_dimensions_defaults(self, sample_timestamp: datetime):
        ws = sample_timestamp.replace(second=0, microsecond=0)
        metric = AggregatedMetric(
            metric_name="test",
            window=AggregationWindow.HOURLY,
            window_start=ws,
            window_end=ws + timedelta(hours=1),
            value=1.0,
            count=1,
        )
        assert metric.dimensions == {}


class TestDashboard:
    def test_create(self, sample_dashboard: Dashboard):
        assert sample_dashboard.dashboard_id is not None
        assert sample_dashboard.name == "Main Dashboard"
        assert sample_dashboard.description == "Main analytics dashboard"
        assert len(sample_dashboard.widgets) == 1
        assert sample_dashboard.owner_id == "user-1"
        assert sample_dashboard.is_public is False

    def test_create_widget(self):
        widget = DashboardWidget(
            title="Revenue",
            widget_type=WidgetType.COUNTER,
            metric_name="revenue.total",
            config={"format": "currency", "prefix": "$"},
            position=0,
            width=3,
            height=2,
        )
        assert widget.widget_id is not None
        assert widget.title == "Revenue"
        assert widget.widget_type == WidgetType.COUNTER
        assert widget.metric_name == "revenue.total"
        assert widget.width == 3
        assert widget.height == 2

    def test_widget_to_dict_roundtrip(self):
        widget = DashboardWidget(
            title="Chart",
            widget_type=WidgetType.PIE_CHART,
            metric_name="events.by_type",
            config={"colors": ["red", "blue"]},
            position=1,
            width=12,
            height=6,
        )
        d = widget.to_dict()
        restored = DashboardWidget.from_dict(d)
        assert restored.title == widget.title
        assert restored.widget_type == widget.widget_type
        assert restored.metric_name == widget.metric_name
        assert restored.config == widget.config
        assert restored.position == widget.position
        assert restored.width == widget.width
        assert restored.height == widget.height

    def test_dashboard_to_dict_roundtrip(self, sample_dashboard: Dashboard):
        d = sample_dashboard.to_dict()
        restored = Dashboard.from_dict(d)
        assert restored.dashboard_id == sample_dashboard.dashboard_id
        assert restored.name == sample_dashboard.name
        assert restored.description == sample_dashboard.description
        assert len(restored.widgets) == len(sample_dashboard.widgets)
        assert restored.widgets[0].title == sample_dashboard.widgets[0].title
        assert restored.owner_id == sample_dashboard.owner_id
        assert restored.is_public == sample_dashboard.is_public

    def test_default_widget_dimensions(self):
        widget = DashboardWidget(
            title="Default",
            widget_type=WidgetType.TABLE,
            metric_name="test",
            config={},
            position=0,
        )
        assert widget.width == 6
        assert widget.height == 4

    def test_widget_types(self):
        assert WidgetType.TIMESERIES.value == "timeseries"
        assert WidgetType.COUNTER.value == "counter"
        assert WidgetType.PIE_CHART.value == "pie_chart"
        assert WidgetType.TABLE.value == "table"
        assert WidgetType.HEATMAP.value == "heatmap"


class TestUser:
    def test_create(self, sample_user: User):
        assert sample_user.user_id is not None
        assert sample_user.username == "testuser"
        assert sample_user.email == "test@example.com"
        assert sample_user.hashed_password == "$2b$12$abcdefghijklmnopqrstuv"
        assert sample_user.role == UserRole.ANALYST
        assert sample_user.is_active is True

    def test_to_dict_excludes_password(self, sample_user: User):
        d = sample_user.to_dict()
        assert "hashed_password" not in d
        assert d["username"] == "testuser"
        assert d["email"] == "test@example.com"
        assert d["role"] == "analyst"
        assert d["is_active"] is True

    def test_from_dict_roundtrip(self):
        now = datetime.utcnow()
        user_id = str(uuid.uuid4())
        original = User(
            user_id=user_id,
            username="alice",
            email="alice@test.com",
            hashed_password="hash123",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        d = original.to_dict()
        d["hashed_password"] = "hash123"
        restored = User.from_dict(d)
        assert restored.user_id == original.user_id
        assert restored.username == original.username
        assert restored.email == original.email
        assert restored.hashed_password == "hash123"
        assert restored.role == UserRole.ADMIN
        assert restored.is_active is True

    def test_default_role_is_viewer(self):
        user = User(
            username="viewer",
            email="viewer@test.com",
            hashed_password="pw",
        )
        assert user.role == UserRole.VIEWER

    def test_user_roles(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.ANALYST.value == "analyst"
        assert UserRole.VIEWER.value == "viewer"


class TestRetainedDataRecord:
    def test_create(self):
        now = datetime.utcnow()
        record = RetainedDataRecord(
            table_name="raw_events",
            partition_name="events_2025_06_01",
            retention_date=now - timedelta(days=30),
            deleted_at=now,
        )
        assert record.record_id is not None
        assert record.table_name == "raw_events"
        assert record.partition_name == "events_2025_06_01"

    def test_to_dict(self):
        now = datetime.utcnow()
        record = RetainedDataRecord(
            table_name="hourly_agg",
            partition_name="agg_2025_06",
            retention_date=now - timedelta(days=90),
            deleted_at=now,
        )
        d = record.to_dict()
        assert d["table_name"] == "hourly_agg"
        assert d["partition_name"] == "agg_2025_06"
