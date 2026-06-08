from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.infrastructure.database.session import BaseModel


def generate_uuid() -> str:
    return str(uuid4())


class EventModel(BaseModel):
    __tablename__ = "analytics_events"

    event_id = Column(
        String(36), primary_key=True, default=generate_uuid
    )
    event_type = Column(String(50), nullable=False, index=True)
    source = Column(String(255), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=datetime.utcnow,
    )
    user_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    status = Column(
        String(20), nullable=False, default="received", index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_events_type_timestamp", "event_type", "timestamp"),
        Index("idx_events_source_timestamp", "source", "timestamp"),
        Index("idx_events_user_timestamp", "user_id", "timestamp"),
    )


class AggregatedMetricModel(BaseModel):
    __tablename__ = "aggregated_metrics"

    metric_id = Column(
        String(36), primary_key=True, default=generate_uuid
    )
    metric_name = Column(String(255), nullable=False, index=True)
    window = Column(String(20), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    value = Column(Float, nullable=False, default=0.0)
    count = Column(BigInteger, nullable=False, default=0)
    dimensions = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "idx_metrics_name_window",
            "metric_name",
            "window",
            "window_start",
        ),
    )


class DashboardModel(BaseModel):
    __tablename__ = "dashboards"

    dashboard_id = Column(
        String(36), primary_key=True, default=generate_uuid
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    widgets = Column(JSONB, nullable=False, default=list)
    owner_id = Column(String(36), nullable=True, index=True)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class UserModel(BaseModel):
    __tablename__ = "users"

    user_id = Column(
        String(36), primary_key=True, default=generate_uuid
    )
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        String(20), nullable=False, default="viewer"
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class RetentionLogModel(BaseModel):
    __tablename__ = "retention_logs"

    record_id = Column(
        String(36), primary_key=True, default=generate_uuid
    )
    table_name = Column(String(100), nullable=False)
    partition_name = Column(String(255), nullable=False)
    retention_date = Column(DateTime(timezone=True), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )
