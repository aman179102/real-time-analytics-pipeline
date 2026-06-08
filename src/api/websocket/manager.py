from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import WebSocket
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._user_connections: dict[str, list[WebSocket]] = {}

    async def connect(
        self, websocket: WebSocket, dashboard_id: str, user_id: Optional[str] = None
    ) -> None:
        await websocket.accept()

        if dashboard_id not in self._connections:
            self._connections[dashboard_id] = []
        self._connections[dashboard_id].append(websocket)

        if user_id:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = []
            self._user_connections[user_id].append(websocket)

        logger.info(
            "WebSocket connected: dashboard=%s user=%s",
            dashboard_id,
            user_id or "anonymous",
        )

    async def disconnect(
        self, websocket: WebSocket, dashboard_id: str, user_id: Optional[str] = None
    ) -> None:
        if dashboard_id in self._connections:
            self._connections[dashboard_id] = [
                w for w in self._connections[dashboard_id] if w != websocket
            ]
            if not self._connections[dashboard_id]:
                del self._connections[dashboard_id]

        if user_id and user_id in self._user_connections:
            self._user_connections[user_id] = [
                w for w in self._user_connections[user_id] if w != websocket
            ]
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        logger.info(
            "WebSocket disconnected: dashboard=%s", dashboard_id
        )

    async def broadcast_to_dashboard(
        self, dashboard_id: str, data: dict[str, Any]
    ) -> None:
        if dashboard_id not in self._connections:
            return

        message = json.dumps(data, default=str)
        disconnected = []

        for websocket in self._connections[dashboard_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            await self.disconnect(ws, dashboard_id)

    async def broadcast_to_user(
        self, user_id: str, data: dict[str, Any]
    ) -> None:
        if user_id not in self._user_connections:
            return

        message = json.dumps(data, default=str)
        disconnected = []

        for websocket in self._user_connections[user_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)

        for ws in disconnected:
            for dash_id in list(self._connections.keys()):
                if ws in self._connections[dash_id]:
                    await self.disconnect(ws, dash_id, user_id)

    async def broadcast_all(self, data: dict[str, Any]) -> None:
        message = json.dumps(data, default=str)
        for dashboard_id in list(self._connections.keys()):
            await self.broadcast_to_dashboard(dashboard_id, data)

    @property
    def active_connections(self) -> int:
        count = 0
        for conns in self._connections.values():
            count += len(conns)
        return count

    @property
    def active_dashboards(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
