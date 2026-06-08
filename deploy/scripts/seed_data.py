#!/usr/bin/env python3
"""Seed test data into the Real-Time Analytics Pipeline via the API."""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
EVENT_TYPES = [
    "page_view", "click", "signup", "purchase", "login", "logout", "error", "custom"
]
SOURCES = [
    "web-app", "mobile-app", "api-gateway", "admin-panel", "landing-page",
    "email-service", "notification-service", "payment-service",
]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "PostmanRuntime/7.36.0",
    "axios/1.6.0",
]


class SeedClient:
    def __init__(self, base_url: str, username: str = "admin", password: str = "admin123!"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        self.access_token: str | None = None
        self.username = username
        self.password = password

    async def __aenter__(self):
        await self._register()
        await self._login()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.client.aclose()

    async def _register(self) -> None:
        try:
            resp = await self.client.post(
                "/api/v1/auth/register",
                json={
                    "username": self.username,
                    "email": f"{self.username}@example.com",
                    "password": self.password,
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                self.access_token = data["access_token"]
                print(f"[+] Registered user: {self.username}")
        except Exception as e:
            print(f"[~] Registration skipped (user may exist): {e}")

    async def _login(self) -> None:
        resp = await self.client.post(
            "/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if resp.status_code == 200:
            data = resp.json()
            self.access_token = data["access_token"]
            self.client.headers["Authorization"] = f"Bearer {self.access_token}"
            print(f"[+] Logged in as: {self.username}")
        else:
            print(f"[!] Login failed: {resp.text}")
            sys.exit(1)

    async def ingest_event(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "event_type": event_type,
            "source": source,
            "payload": payload or {},
        }
        if user_id:
            body["user_id"] = user_id
        if session_id:
            body["session_id"] = session_id
        if timestamp:
            body["timestamp"] = timestamp

        resp = await self.client.post("/api/v1/events/ingest", json=body)
        resp.raise_for_status()
        return resp.json()

    async def ingest_batch(
        self, events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        resp = await self.client.post("/api/v1/events/ingest/batch", json=events)
        resp.raise_for_status()
        return resp.json()

    async def create_dashboard(self, name: str, description: str = "") -> dict[str, Any]:
        widgets = [
            {
                "title": "Page Views Over Time",
                "widget_type": "timeseries",
                "metric_name": "page_view.count",
                "config": {"aggregation": "hourly", "color": "#1f77b4"},
                "position": 0,
                "width": 6,
                "height": 4,
            },
            {
                "title": "Event Distribution",
                "widget_type": "pie_chart",
                "metric_name": "events.by_type",
                "config": {"color_scheme": "category10"},
                "position": 1,
                "width": 6,
                "height": 4,
            },
            {
                "title": "Total Events Counter",
                "widget_type": "counter",
                "metric_name": "events.total",
                "config": {"prefix": "", "suffix": " events"},
                "position": 2,
                "width": 3,
                "height": 2,
            },
            {
                "title": "Errors Over Time",
                "widget_type": "timeseries",
                "metric_name": "error.count",
                "config": {"aggregation": "minute", "color": "#d62728"},
                "position": 3,
                "width": 6,
                "height": 4,
            },
            {
                "title": "Top Sources",
                "widget_type": "table",
                "metric_name": "events.by_source",
                "config": {"limit": 10, "sort_column": "count"},
                "position": 4,
                "width": 6,
                "height": 4,
            },
        ]
        resp = await self.client.post(
            "/api/v1/dashboards",
            json={"name": name, "description": description, "widgets": widgets},
        )
        resp.raise_for_status()
        return resp.json()


def generate_payload(event_type: str) -> dict[str, Any]:
    payloads = {
        "page_view": {
            "url": random.choice([
                "/home", "/products", "/pricing", "/docs", "/blog",
                "/about", "/contact", "/dashboard", "/settings",
            ]),
            "referrer": random.choice([
                "https://google.com", "https://github.com", "",
                "https://twitter.com", "https://linkedin.com",
            ]),
            "title": random.choice([
                "Home", "Products", "Pricing", "Documentation", "Blog",
            ]),
            "duration_ms": random.randint(1000, 120000),
            "viewport_width": random.choice([1920, 1440, 1366, 768, 375]),
            "viewport_height": random.choice([1080, 900, 768, 812, 667]),
        },
        "click": {
            "element": random.choice([
                "button-submit", "nav-link", "cta-button", "menu-item",
                "card-click", "accordion-header", "tab-item",
            ]),
            "x_position": random.randint(0, 1920),
            "y_position": random.randint(0, 1080),
            "target_url": random.choice([
                "/signup", "/pricing", "/docs/getting-started", "/contact",
            ]),
        },
        "signup": {
            "method": random.choice(["email", "google", "github", "microsoft"]),
            "referral_source": random.choice([
                "direct", "organic", "paid-ad", "referral", "social",
            ]),
            "plan": random.choice(["free", "starter", "pro", "enterprise"]),
        },
        "purchase": {
            "amount": round(random.uniform(9.99, 999.99), 2),
            "currency": random.choice(["USD", "EUR", "GBP"]),
            "payment_method": random.choice([
                "credit_card", "paypal", "stripe", "crypto",
            ]),
            "items_count": random.randint(1, 10),
            "coupon_applied": random.choice([True, False]),
        },
        "login": {
            "method": random.choice(["password", "oauth", "saml", "magic_link"]),
            "mfa_used": random.choice([True, False]),
            "device_type": random.choice(["desktop", "mobile", "tablet"]),
        },
        "logout": {
            "session_duration_minutes": random.randint(1, 480),
            "reason": random.choice(["user_action", "timeout", "tab_close"]),
        },
        "error": {
            "error_code": random.choice([
                "ERR_404", "ERR_500", "ERR_503", "ERR_TIMEOUT",
                "ERR_VALIDATION", "ERR_AUTH",
            ]),
            "error_message": random.choice([
                "Resource not found", "Internal server error",
                "Service unavailable", "Request timed out",
                "Validation failed", "Authentication failed",
            ]),
            "stack_trace": "Error: mock stack trace for testing",
        },
        "custom": {
            "custom_key": str(uuid.uuid4())[:8],
            "custom_value": random.random() * 1000,
            "tags": random.sample(
                ["test", "seed", "demo", "monitoring", "experiment"],
                k=random.randint(1, 3),
            ),
        },
    }
    return payloads.get(event_type, {})


async def seed_events(
    client: SeedClient,
    count: int = 1000,
    start_date: datetime | None = None,
) -> int:
    end_date = datetime.utcnow()
    start_date = start_date or (end_date - timedelta(days=7))
    total_seconds = (end_date - start_date).total_seconds()

    event_ids = []
    batch_size = 50

    for i in range(0, count, batch_size):
        batch_events = []
        batch_count = min(batch_size, count - i)

        for _ in range(batch_count):
            event_type = random.choice(EVENT_TYPES)
            offset_seconds = random.uniform(0, total_seconds)
            ts = start_date + timedelta(seconds=offset_seconds)

            batch_events.append({
                "event_type": event_type,
                "source": random.choice(SOURCES),
                "payload": generate_payload(event_type),
                "user_id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "timestamp": ts.isoformat(),
                "user_agent": random.choice(USER_AGENTS),
            })

        result = await client.ingest_batch(batch_events)
        event_ids.extend(result.get("event_ids", []))
        print(
            f"  Ingested {i + batch_count}/{count} events...",
            end="\r",
            flush=True,
        )

    print()
    return len(event_ids)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed test data into the analytics pipeline")
    parser.add_argument(
        "--url", default=BASE_URL,
        help=f"Base URL of the API (default: {BASE_URL})",
    )
    parser.add_argument(
        "--events", type=int, default=1000,
        help="Number of events to seed (default: 1000)",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to spread events over (default: 7)",
    )
    parser.add_argument(
        "--username", default="admin",
        help="Admin username (default: admin)",
    )
    parser.add_argument(
        "--password", default="admin123!",
        help="Admin password (default: admin123!)",
    )
    parser.add_argument(
        "--dashboard", action="store_true", default=True,
        help="Create a sample dashboard (default: True)",
    )
    args = parser.parse_args()

    start_time = time.time()
    start_date = datetime.utcnow() - timedelta(days=args.days)

    print(f"[*] Seeding data to {args.url}")
    print(f"[*] Events: {args.events} | Span: {args.days} days")

    async with SeedClient(args.url, args.username, args.password) as client:
        total = await seed_events(client, args.events, start_date)
        elapsed = time.time() - start_time
        rate = total / elapsed if elapsed > 0 else 0
        print(f"[+] Seeded {total} events in {elapsed:.2f}s ({rate:.0f} events/s)")

        if args.dashboard:
            dash = await client.create_dashboard(
                name="Main Dashboard",
                description=f"Auto-generated dashboard with {total} test events",
            )
            print(f"[+] Created dashboard: {dash['dashboard_id']} - {dash['name']}")

        print("[+] Health check:")
        resp = await client.client.get("/health")
        print(f"    {resp.json()}")


if __name__ == "__main__":
    asyncio.run(main())
