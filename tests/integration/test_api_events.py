from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient


class TestEventIngestion:
    async def test_ingest_event_success(self, async_client: AsyncClient, auth_header: dict):
        payload = {
            "event_type": "page_view",
            "source": "web-app",
            "payload": {"url": "/home", "referrer": "/login"},
            "user_id": "user-1",
            "session_id": "session-abc",
        }
        response = await async_client.post(
            "/api/v1/events/ingest",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert "event_id" in data
        assert "message_id" in data
        assert data["status"] == "accepted"

    async def test_ingest_event_invalid_type(self, async_client: AsyncClient, auth_header: dict):
        payload = {
            "event_type": "nonexistent_type",
            "source": "web",
            "payload": {},
        }
        response = await async_client.post(
            "/api/v1/events/ingest",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data

    async def test_ingest_event_missing_source(self, async_client: AsyncClient, auth_header: dict):
        payload = {
            "event_type": "click",
            "payload": {},
        }
        response = await async_client.post(
            "/api/v1/events/ingest",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code == 422

    async def test_ingest_event_unauthorized(self, async_client: AsyncClient):
        payload = {
            "event_type": "page_view",
            "source": "web",
            "payload": {},
        }
        response = await async_client.post(
            "/api/v1/events/ingest",
            json=payload,
        )
        assert response.status_code == 401

    async def test_ingest_events_batch(self, async_client: AsyncClient, auth_header: dict):
        events = [
            {
                "event_type": "page_view",
                "source": "web",
                "payload": {"url": "/page1"},
            },
            {
                "event_type": "click",
                "source": "web",
                "payload": {"element": "button"},
            },
        ]
        response = await async_client.post(
            "/api/v1/events/ingest/batch",
            json=events,
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 2
        assert len(data["event_ids"]) == 2
        assert data["status"] == "accepted"

    async def test_ingest_batch_empty(self, async_client: AsyncClient, auth_header: dict):
        response = await async_client.post(
            "/api/v1/events/ingest/batch",
            json=[],
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 0

    async def test_ingest_batch_invalid_events_skipped(self, async_client: AsyncClient, auth_header: dict):
        events = [
            {"event_type": "page_view", "source": "web", "payload": {}},
            {"event_type": "invalid_type", "source": "web", "payload": {}},
        ]
        response = await async_client.post(
            "/api/v1/events/ingest/batch",
            json=events,
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 1

    async def test_ingest_event_with_timestamp(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        payload = {
            "event_type": "purchase",
            "source": "mobile",
            "payload": {"amount": 19.99},
            "timestamp": now.isoformat(),
        }
        response = await async_client.post(
            "/api/v1/events/ingest",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code == 201


class TestEventQuery:
    async def test_list_events(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        }
        response = await async_client.get(
            "/api/v1/events",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 0

    async def test_list_events_with_filters(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "event_type": "page_view",
            "source": "web",
            "page": 1,
            "page_size": 10,
        }
        response = await async_client.get(
            "/api/v1/events",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200

    async def test_list_events_missing_params(self, async_client: AsyncClient, auth_header: dict):
        response = await async_client.get(
            "/api/v1/events",
            headers=auth_header,
        )
        assert response.status_code == 422

    async def test_get_event_by_id_found(self, async_client: AsyncClient, auth_header: dict):
        response = await async_client.get(
            f"/api/v1/events/known-event-id",
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == "known-event-id"
        assert data["event_type"] == "page_view"

    async def test_get_event_by_id_not_found(self, async_client: AsyncClient, auth_header: dict):
        response = await async_client.get(
            "/api/v1/events/nonexistent-id",
            headers=auth_header,
        )
        assert response.status_code == 404

    async def test_get_event_unauthorized(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/events/known-event-id")
        assert response.status_code == 401

    async def test_list_events_pagination(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "page": 1,
            "page_size": 5,
        }
        response = await async_client.get(
            "/api/v1/events",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    async def test_list_events_pagination_out_of_range(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "page": 999,
            "page_size": 100,
        }
        response = await async_client.get(
            "/api/v1/events",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200

    async def test_list_events_with_search(self, async_client: AsyncClient, auth_header: dict):
        now = datetime.utcnow()
        params = {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "search": "home",
        }
        response = await async_client.get(
            "/api/v1/events",
            params=params,
            headers=auth_header,
        )
        assert response.status_code == 200
