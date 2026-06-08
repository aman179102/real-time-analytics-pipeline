from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_analytics_service, require_role, verify_token
from src.api.errors import NotFoundError, ValidationError
from src.core.analytics_service import AnalyticsService
from src.domain.models import Dashboard, DashboardWidget, UserRole, WidgetType
from src.domain.value_objects import PaginationParams

logger = __import__("src.infrastructure.logging", fromlist=["get_logger"]).get_logger(__name__)

router = APIRouter(prefix="/api/v1/dashboards", tags=["Dashboards"])


class WidgetCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    widget_type: str = Field(..., description="timeseries, counter, pie_chart, table, heatmap")
    metric_name: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    position: int = Field(..., ge=0)
    width: int = Field(6, ge=1, le=12)
    height: int = Field(4, ge=1, le=12)


class DashboardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    widgets: list[WidgetCreateRequest] = Field(default_factory=list)
    is_public: bool = False


class DashboardUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    widgets: Optional[list[WidgetCreateRequest]] = None
    is_public: Optional[bool] = None


class WidgetResponse(BaseModel):
    widget_id: str
    title: str
    widget_type: str
    metric_name: str
    config: dict[str, Any]
    position: int
    width: int
    height: int


class DashboardResponse(BaseModel):
    dashboard_id: str
    name: str
    description: str
    widgets: list[WidgetResponse]
    owner_id: Optional[str]
    is_public: bool
    created_at: datetime
    updated_at: datetime


class DashboardListResponse(BaseModel):
    items: list[DashboardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


@router.post("", response_model=DashboardResponse, status_code=201)
async def create_dashboard(
    request: DashboardCreateRequest,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> DashboardResponse:
    widgets = []
    for w in request.widgets:
        try:
            wtype = WidgetType(w.widget_type)
        except ValueError:
            raise ValidationError(f"Invalid widget type: {w.widget_type}")
        widgets.append(
            DashboardWidget(
                title=w.title,
                widget_type=wtype,
                metric_name=w.metric_name,
                config=w.config,
                position=w.position,
                width=w.width,
                height=w.height,
            )
        )

    dashboard = Dashboard(
        name=request.name,
        description=request.description,
        widgets=widgets,
        owner_id=token.get("sub"),
        is_public=request.is_public,
    )

    dashboard_id = await analytics_service.create_dashboard(dashboard)

    created = await analytics_service.get_dashboard(dashboard_id)
    assert created is not None

    return DashboardResponse(
        dashboard_id=created.dashboard_id,
        name=created.name,
        description=created.description,
        widgets=[
            WidgetResponse(
                widget_id=w.widget_id,
                title=w.title,
                widget_type=w.widget_type.value,
                metric_name=w.metric_name,
                config=w.config,
                position=w.position,
                width=w.width,
                height=w.height,
            )
            for w in created.widgets
        ],
        owner_id=created.owner_id,
        is_public=created.is_public,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> DashboardListResponse:
    pagination = PaginationParams(page=page, page_size=page_size)
    result = await analytics_service.list_dashboards(
        owner_id=token.get("sub"), pagination=pagination
    )

    return DashboardListResponse(
        items=[
            DashboardResponse(
                dashboard_id=d.dashboard_id,
                name=d.name,
                description=d.description,
                widgets=[
                    WidgetResponse(
                        widget_id=w.widget_id,
                        title=w.title,
                        widget_type=w.widget_type.value,
                        metric_name=w.metric_name,
                        config=w.config,
                        position=w.position,
                        width=w.width,
                        height=w.height,
                    )
                    for w in d.widgets
                ],
                owner_id=d.owner_id,
                is_public=d.is_public,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: str,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> DashboardResponse:
    dashboard = await analytics_service.get_dashboard(dashboard_id)
    if not dashboard:
        raise NotFoundError(f"Dashboard {dashboard_id} not found")

    return DashboardResponse(
        dashboard_id=dashboard.dashboard_id,
        name=dashboard.name,
        description=dashboard.description,
        widgets=[
            WidgetResponse(
                widget_id=w.widget_id,
                title=w.title,
                widget_type=w.widget_type.value,
                metric_name=w.metric_name,
                config=w.config,
                position=w.position,
                width=w.width,
                height=w.height,
            )
            for w in dashboard.widgets
        ],
        owner_id=dashboard.owner_id,
        is_public=dashboard.is_public,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
    )


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> DashboardResponse:
    dashboard = await analytics_service.get_dashboard(dashboard_id)
    if not dashboard:
        raise NotFoundError(f"Dashboard {dashboard_id} not found")

    if request.name is not None:
        dashboard.name = request.name
    if request.description is not None:
        dashboard.description = request.description
    if request.widgets is not None:
        dashboard.widgets = []
        for w in request.widgets:
            try:
                wtype = WidgetType(w.widget_type)
            except ValueError:
                raise ValidationError(f"Invalid widget type: {w.widget_type}")
            dashboard.widgets.append(
                DashboardWidget(
                    title=w.title,
                    widget_type=wtype,
                    metric_name=w.metric_name,
                    config=w.config,
                    position=w.position,
                    width=w.width,
                    height=w.height,
                )
            )
    if request.is_public is not None:
        dashboard.is_public = request.is_public

    dashboard.updated_at = datetime.utcnow()
    await analytics_service.update_dashboard(dashboard)

    updated = await analytics_service.get_dashboard(dashboard_id)
    assert updated is not None

    return DashboardResponse(
        dashboard_id=updated.dashboard_id,
        name=updated.name,
        description=updated.description,
        widgets=[
            WidgetResponse(
                widget_id=w.widget_id,
                title=w.title,
                widget_type=w.widget_type.value,
                metric_name=w.metric_name,
                config=w.config,
                position=w.position,
                width=w.width,
                height=w.height,
            )
            for w in updated.widgets
        ],
        owner_id=updated.owner_id,
        is_public=updated.is_public,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{dashboard_id}", status_code=204)
async def delete_dashboard(
    dashboard_id: str,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> None:
    dashboard = await analytics_service.get_dashboard(dashboard_id)
    if not dashboard:
        raise NotFoundError(f"Dashboard {dashboard_id} not found")

    await analytics_service.delete_dashboard(dashboard_id)
