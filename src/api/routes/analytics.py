from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import get_analytics_service, verify_token
from src.api.errors import NotFoundError
from src.core.analytics_service import AnalyticsService
from src.domain.models import AggregationWindow
from src.domain.value_objects import (
    PaginatedResult,
    PaginationParams,
    TimeRange,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


class AggregatedMetricResponse(BaseModel):
    metric_id: str
    metric_name: str
    window: str
    window_start: datetime
    window_end: datetime
    value: float
    count: int
    dimensions: dict


class AggregationListResponse(BaseModel):
    items: list[AggregatedMetricResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class RealtimeMetricsResponse(BaseModel):
    time_range_seconds: int
    total_events: int
    events_per_second: float
    by_type: dict[str, int]
    by_source: dict[str, int]


@router.get("/aggregations/{metric_name}", response_model=AggregationListResponse)
async def get_aggregations(
    metric_name: str,
    window: str = Query("minute", regex="^(minute|hourly|daily)$"),
    start: datetime = Query(..., description="Start of time range"),
    end: datetime = Query(..., description="End of time range"),
    dimension_key: Optional[str] = Query(None),
    dimension_value: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> AggregationListResponse:
    time_range = TimeRange(start=start, end=end)
    pagination = PaginationParams(page=page, page_size=page_size)

    agg_window = AggregationWindow(window)
    dimensions = None
    if dimension_key and dimension_value:
        dimensions = {dimension_key: dimension_value}

    result = await analytics_service.get_aggregations(
        metric_name, agg_window, time_range, dimensions, pagination
    )

    return AggregationListResponse(
        items=[
            AggregatedMetricResponse(
                metric_id=m.metric_id,
                metric_name=m.metric_name,
                window=m.window.value,
                window_start=m.window_start,
                window_end=m.window_end,
                value=m.value,
                count=m.count,
                dimensions=m.dimensions,
            )
            for m in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )


@router.get("/aggregations/{metric_name}/latest", response_model=AggregatedMetricResponse)
async def get_latest_aggregation(
    metric_name: str,
    window: str = Query("minute", regex="^(minute|hourly|daily)$"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> AggregatedMetricResponse:
    agg_window = AggregationWindow(window)
    metric = await analytics_service.get_latest_aggregation(
        metric_name, agg_window
    )
    if not metric:
        raise NotFoundError(
            f"No aggregation found for {metric_name}/{window}"
        )

    return AggregatedMetricResponse(
        metric_id=metric.metric_id,
        metric_name=metric.metric_name,
        window=metric.window.value,
        window_start=metric.window_start,
        window_end=metric.window_end,
        value=metric.value,
        count=metric.count,
        dimensions=metric.dimensions,
    )


@router.get("/counts/types", response_model=dict[str, int])
async def get_event_type_counts(
    start: datetime = Query(..., description="Start of time range"),
    end: datetime = Query(..., description="End of time range"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> dict[str, int]:
    time_range = TimeRange(start=start, end=end)
    return await analytics_service.get_event_type_counts(time_range)


@router.get("/counts/sources", response_model=dict[str, int])
async def get_source_counts(
    start: datetime = Query(..., description="Start of time range"),
    end: datetime = Query(..., description="End of time range"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> dict[str, int]:
    time_range = TimeRange(start=start, end=end)
    return await analytics_service.get_source_counts(time_range)


@router.get("/realtime", response_model=RealtimeMetricsResponse)
async def get_realtime_metrics(
    window_seconds: int = Query(60, ge=10, le=3600),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> RealtimeMetricsResponse:
    result = await analytics_service.get_realtime_metrics(window_seconds)
    return RealtimeMetricsResponse(**result)
