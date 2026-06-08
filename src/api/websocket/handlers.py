from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from src.api.websocket.manager import manager
from src.core.analytics_service import AnalyticsService
from src.domain.value_objects import TimeRange
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/dashboard/{dashboard_id}")
async def dashboard_websocket(
    websocket: WebSocket,
    dashboard_id: str,
    token: Optional[str] = Query(None),
) -> None:
    user_id = None
    if token:
        try:
            import jwt as pyjwt
            from src.config import config
            payload = pyjwt.decode(
                token, config.auth.jwt_secret, algorithms=[config.auth.jwt_algorithm]
            )
            user_id = payload.get("sub")
        except Exception:
            pass

    await manager.connect(websocket, dashboard_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await _handle_message(websocket, dashboard_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
    except WebSocketDisconnect:
        await manager.disconnect(websocket, dashboard_id, user_id)
    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
        await manager.disconnect(websocket, dashboard_id, user_id)


async def _handle_message(
    websocket: WebSocket, dashboard_id: str, message: dict[str, Any]
) -> None:
    msg_type = message.get("type", "")

    if msg_type == "ping":
        await websocket.send_json({"type": "pong"})

    elif msg_type == "subscribe":
        metrics_name = message.get("metric_name")
        window_seconds = message.get("window_seconds", 60)
        await websocket.send_json({
            "type": "subscribed",
            "metric_name": metrics_name,
            "window_seconds": window_seconds,
        })

    elif msg_type == "refresh":
        await websocket.send_json({
            "type": "refresh_ack",
            "dashboard_id": dashboard_id,
        })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })


async def broadcast_realtime_update(
    dashboard_id: str,
    metric_name: str,
    value: float,
    timestamp: Optional[datetime] = None,
    dimensions: Optional[dict[str, str]] = None,
) -> None:
    await manager.broadcast_to_dashboard(
        dashboard_id,
        {
            "type": "metric_update",
            "metric_name": metric_name,
            "value": value,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "dimensions": dimensions or {},
        },
    )
