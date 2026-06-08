from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from src.domain.value_objects import (
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)
from src.infrastructure.database.models import (
    AggregatedMetricModel,
    DashboardModel,
    EventModel,
    RetentionLogModel,
    UserModel,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


def _row_to_event(row: EventModel) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=row.event_id,
        event_type=EventType(row.event_type),
        source=row.source,
        payload=row.payload or {},
        timestamp=row.timestamp,
        user_id=row.user_id,
        session_id=row.session_id,
        ip_address=row.ip_address,
        user_agent=row.user_agent,
        status=EventStatus(row.status),
    )


def _row_to_metric(row: AggregatedMetricModel) -> AggregatedMetric:
    return AggregatedMetric(
        metric_id=row.metric_id,
        metric_name=row.metric_name,
        window=AggregationWindow(row.window),
        window_start=row.window_start,
        window_end=row.window_end,
        value=row.value,
        count=row.count,
        dimensions=row.dimensions or {},
    )


def _row_to_dashboard(row: DashboardModel) -> Dashboard:
    widgets_data = row.widgets or []
    widgets = [DashboardWidget(**w) if isinstance(w, dict) else w for w in widgets_data]
    return Dashboard(
        dashboard_id=row.dashboard_id,
        name=row.name,
        description=row.description,
        widgets=widgets,
        owner_id=row.owner_id,
        is_public=row.is_public,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, event: AnalyticsEvent) -> str:
        model = EventModel(
            event_id=event.event_id,
            event_type=event.event_type.value,
            source=event.source,
            payload=event.payload,
            timestamp=event.timestamp,
            user_id=event.user_id,
            session_id=event.session_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            status=event.status.value,
        )
        self.session.add(model)
        await self.session.flush()
        return model.event_id

    async def save_batch(self, events: list[AnalyticsEvent]) -> list[str]:
        models = [
            EventModel(
                event_id=event.event_id,
                event_type=event.event_type.value,
                source=event.source,
                payload=event.payload,
                timestamp=event.timestamp,
                user_id=event.user_id,
                session_id=event.session_id,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                status=event.status.value,
            )
            for event in events
        ]
        self.session.add_all(models)
        await self.session.flush()
        return [m.event_id for m in models]

    async def get_by_id(self, event_id: str) -> Optional[AnalyticsEvent]:
        stmt = select(EventModel).where(
            EventModel.event_id == event_id,
            EventModel.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_event(row) if row else None

    async def query(
        self,
        time_range: TimeRange,
        filters: Optional[FilterCriteria] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AnalyticsEvent]:
        pagination = pagination or PaginationParams()
        conditions = [
            EventModel.timestamp >= time_range.start,
            EventModel.timestamp <= time_range.end,
            EventModel.deleted_at.is_(None),
        ]

        if filters:
            if filters.event_types:
                conditions.append(EventModel.event_type.in_(filters.event_types))
            if filters.sources:
                conditions.append(EventModel.source.in_(filters.sources))
            if filters.user_ids:
                conditions.append(EventModel.user_id.in_(filters.user_ids))
            if filters.session_ids:
                conditions.append(EventModel.session_id.in_(filters.session_ids))
            if filters.statuses:
                conditions.append(EventModel.status.in_(filters.statuses))
            if filters.search_query:
                conditions.append(EventModel.payload.cast(String).contains(filters.search_query))

        count_stmt = select(func.count()).select_from(EventModel).where(and_(*conditions))
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(EventModel)
            .where(and_(*conditions))
            .order_by(EventModel.timestamp.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return PaginatedResult(
            items=[_row_to_event(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def count_by_type(self, time_range: TimeRange) -> dict[str, int]:
        stmt = (
            select(EventModel.event_type, func.count().label("cnt"))
            .where(
                EventModel.timestamp >= time_range.start,
                EventModel.timestamp <= time_range.end,
                EventModel.deleted_at.is_(None),
            )
            .group_by(EventModel.event_type)
        )
        result = await self.session.execute(stmt)
        return {row.event_type: row.cnt for row in result}

    async def count_by_source(self, time_range: TimeRange) -> dict[str, int]:
        stmt = (
            select(EventModel.source, func.count().label("cnt"))
            .where(
                EventModel.timestamp >= time_range.start,
                EventModel.timestamp <= time_range.end,
                EventModel.deleted_at.is_(None),
            )
            .group_by(EventModel.source)
        )
        result = await self.session.execute(stmt)
        return {row.source: row.cnt for row in result}

    async def delete_older_than(self, cutoff: datetime) -> int:
        stmt = (
            delete(EventModel)
            .where(EventModel.timestamp < cutoff)
            .returning(EventModel.event_id)
        )
        result = await self.session.execute(stmt)
        deleted = len(result.fetchall())
        return deleted


class PostgresAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_aggregation(self, metric: AggregatedMetric) -> str:
        model = AggregatedMetricModel(
            metric_id=metric.metric_id,
            metric_name=metric.metric_name,
            window=metric.window.value,
            window_start=metric.window_start,
            window_end=metric.window_end,
            value=metric.value,
            count=metric.count,
            dimensions=metric.dimensions,
        )
        self.session.add(model)
        await self.session.flush()
        return model.metric_id

    async def get_aggregation(
        self,
        metric_name: str,
        window: AggregationWindow,
        window_start: datetime,
        window_end: datetime,
        dimensions: Optional[dict[str, str]] = None,
    ) -> Optional[AggregatedMetric]:
        conditions = [
            AggregatedMetricModel.metric_name == metric_name,
            AggregatedMetricModel.window == window.value,
            AggregatedMetricModel.window_start == window_start,
            AggregatedMetricModel.window_end == window_end,
        ]
        if dimensions:
            conditions.append(AggregatedMetricModel.dimensions == dimensions)
        stmt = select(AggregatedMetricModel).where(and_(*conditions))
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_metric(row) if row else None

    async def query_aggregations(
        self,
        metric_name: str,
        window: AggregationWindow,
        time_range: TimeRange,
        dimensions: Optional[dict[str, str]] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[AggregatedMetric]:
        pagination = pagination or PaginationParams()
        conditions = [
            AggregatedMetricModel.metric_name == metric_name,
            AggregatedMetricModel.window == window.value,
            AggregatedMetricModel.window_start >= time_range.start,
            AggregatedMetricModel.window_end <= time_range.end,
        ]
        if dimensions:
            for k, v in dimensions.items():
                conditions.append(
                    AggregatedMetricModel.dimensions[k].as_string() == v
                )

        count_stmt = (
            select(func.count())
            .select_from(AggregatedMetricModel)
            .where(and_(*conditions))
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(AggregatedMetricModel)
            .where(and_(*conditions))
            .order_by(AggregatedMetricModel.window_start.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return PaginatedResult(
            items=[_row_to_metric(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def get_latest_aggregation(
        self,
        metric_name: str,
        window: AggregationWindow,
    ) -> Optional[AggregatedMetric]:
        stmt = (
            select(AggregatedMetricModel)
            .where(
                AggregatedMetricModel.metric_name == metric_name,
                AggregatedMetricModel.window == window.value,
            )
            .order_by(AggregatedMetricModel.window_start.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_metric(row) if row else None

    async def delete_aggregations_older_than(
        self, window: AggregationWindow, cutoff: datetime
    ) -> int:
        stmt = (
            delete(AggregatedMetricModel)
            .where(
                AggregatedMetricModel.window == window.value,
                AggregatedMetricModel.window_end < cutoff,
            )
            .returning(AggregatedMetricModel.metric_id)
        )
        result = await self.session.execute(stmt)
        return len(result.fetchall())


class PostgresDashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, dashboard: Dashboard) -> str:
        model = DashboardModel(
            dashboard_id=dashboard.dashboard_id,
            name=dashboard.name,
            description=dashboard.description,
            widgets=[w.to_dict() for w in dashboard.widgets],
            owner_id=dashboard.owner_id,
            is_public=dashboard.is_public,
        )
        self.session.add(model)
        await self.session.flush()
        return model.dashboard_id

    async def get_by_id(self, dashboard_id: str) -> Optional[Dashboard]:
        stmt = select(DashboardModel).where(
            DashboardModel.dashboard_id == dashboard_id,
            DashboardModel.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_dashboard(row) if row else None

    async def list_dashboards(
        self,
        owner_id: Optional[str] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[Dashboard]:
        pagination = pagination or PaginationParams()
        conditions = [DashboardModel.deleted_at.is_(None)]
        if owner_id:
            conditions.append(
                or_(
                    DashboardModel.owner_id == owner_id,
                    DashboardModel.is_public.is_(True),
                )
            )

        count_stmt = (
            select(func.count())
            .select_from(DashboardModel)
            .where(and_(*conditions))
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(DashboardModel)
            .where(and_(*conditions))
            .order_by(DashboardModel.updated_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return PaginatedResult(
            items=[_row_to_dashboard(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def update(self, dashboard: Dashboard) -> None:
        stmt = (
            select(DashboardModel)
            .where(DashboardModel.dashboard_id == dashboard.dashboard_id)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.name = dashboard.name
            row.description = dashboard.description
            row.widgets = [w.to_dict() for w in dashboard.widgets]
            row.is_public = dashboard.is_public
            row.updated_at = datetime.utcnow()

    async def delete(self, dashboard_id: str) -> None:
        stmt = (
            select(DashboardModel)
            .where(DashboardModel.dashboard_id == dashboard_id)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.deleted_at = datetime.utcnow()
