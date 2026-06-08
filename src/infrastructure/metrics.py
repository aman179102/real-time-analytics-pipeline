from __future__ import annotations

from typing import Optional

from src.config import config
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    def __init__(self) -> None:
        self._enabled = config.metrics.enabled
        self._counters: dict[str, int] = {}
        self._latencies: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}

    async def initialize(self) -> None:
        if not self._enabled:
            logger.info("Metrics collection disabled")
            return
        try:
            from prometheus_client import start_http_server
            start_http_server(config.metrics.port)
            logger.info(
                "Metrics server started on port %d", config.metrics.port
            )
        except ImportError:
            logger.warning(
                "prometheus_client not installed, metrics disabled"
            )

    async def shutdown(self) -> None:
        logger.info("Metrics collector shut down")

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        if not self._enabled:
            return
        key = self._build_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value

    def record_latency(
        self,
        name: str,
        value_seconds: float,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        if not self._enabled:
            return
        key = self._build_key(name, labels)
        if key not in self._latencies:
            self._latencies[key] = []
        self._latencies[key].append(value_seconds)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        if not self._enabled:
            return
        key = self._build_key(name, labels)
        self._gauges[key] = value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_latency_stats(self, name: str) -> dict[str, float]:
        values = self._latencies.get(name, [])
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "max": 0.0, "min": 0.0}
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "max": max(values),
            "min": min(values),
        }

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def _build_key(
        self,
        name: str,
        labels: Optional[dict[str, str]] = None,
    ) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}[{label_str}]"
        return name

    def snapshot(self) -> dict[str, Any]:
        from copy import deepcopy
        return {
            "counters": deepcopy(self._counters),
            "gauges": deepcopy(self._gauges),
            "latency_stats": {
                k: self.get_latency_stats(k) for k in self._latencies
            },
        }


metrics = MetricsCollector()
