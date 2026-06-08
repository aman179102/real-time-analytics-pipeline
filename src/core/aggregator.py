from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from src.domain.interfaces import AggregationEngineInterface, AnalyticsRepositoryInterface
from src.domain.models import AggregatedMetric, AggregationWindow, AnalyticsEvent
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)


class AggregationEngine(AggregationEngineInterface):
    def __init__(
        self, analytics_repo: AnalyticsRepositoryInterface
    ) -> None:
        self._analytics_repo = analytics_repo

    def _get_window_start(
        self, timestamp: datetime, window: AggregationWindow
    ) -> datetime:
        if window == AggregationWindow.MINUTE:
            return timestamp.replace(second=0, microsecond=0)
        elif window == AggregationWindow.HOURLY:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif window == AggregationWindow.DAILY:
            return timestamp.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        return timestamp

    def _get_window_end(
        self, window_start: datetime, window: AggregationWindow
    ) -> datetime:
        if window == AggregationWindow.MINUTE:
            return window_start + timedelta(minutes=1)
        elif window == AggregationWindow.HOURLY:
            return window_start + timedelta(hours=1)
        elif window == AggregationWindow.DAILY:
            return window_start + timedelta(days=1)
        return window_start

    async def aggregate_events(
        self,
        events: list[AnalyticsEvent],
        window: AggregationWindow = AggregationWindow.MINUTE,
    ) -> list[AggregatedMetric]:
        if not events:
            return []

        counters: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "value": 0.0,
                "count": 0,
                "dimensions": {},
            }
        )

        for event in events:
            ws = self._get_window_start(event.timestamp, window)
            we = self._get_window_end(ws, window)

            key = f"{event.event_type.value}:{event.source}:{ws.isoformat()}"

            counters[key]["value"] += 1.0
            counters[key]["count"] += 1
            counters[key]["dimensions"] = {
                "event_type": event.event_type.value,
                "source": event.source,
            }
            counters[key]["window_start"] = ws
            counters[key]["window_end"] = we

        metrics_list = []
        for key, data in counters.items():
            metric = AggregatedMetric(
                metric_name=f"event_count.{data['dimensions']['event_type']}",
                window=window,
                window_start=data["window_start"],
                window_end=data["window_end"],
                value=data["value"],
                count=data["count"],
                dimensions=data["dimensions"],
            )
            metrics_list.append(metric)

        metrics.increment_counter("aggregations_created", len(metrics_list))
        logger.debug(
            "Created %d aggregations for %d events",
            len(metrics_list),
            len(events),
        )

        return metrics_list

    async def rollup_aggregations(
        self,
        source_window: AggregationWindow,
        target_window: AggregationWindow,
    ) -> int:
        if source_window == target_window:
            return 0

        try:
            from src.infrastructure.database.repositories import (
                PostgresAnalyticsRepository,
            )
            from src.infrastructure.database.session import db_manager

            if not isinstance(self._analytics_repo, PostgresAnalyticsRepository):
                logger.warning("Rollup only supported with Postgres repository")
                return 0

            now = datetime.utcnow()
            if target_window == AggregationWindow.HOURLY:
                cutoff = now - timedelta(hours=2)
            elif target_window == AggregationWindow.DAILY:
                cutoff = now - timedelta(days=2)
            else:
                return 0

            async with db_manager.session() as session:
                repo = PostgresAnalyticsRepository(session)
                source_metrics = await repo.query_aggregations(
                    metric_name="",
                    window=source_window,
                    time_range=type(
                        "TimeRange", (), {"start": cutoff - timedelta(days=30), "end": now}
                    )(),
                    pagination=type(
                        "PaginationParams", (), {"page": 1, "page_size": 10000}
                    )(),
                )

                grouped: dict[str, list[AggregatedMetric]] = defaultdict(list)
                for m in source_metrics.items:
                    ws = self._get_window_start(m.window_start, target_window)
                    we = self._get_window_end(ws, target_window)
                    key = f"{m.metric_name}:{ws.isoformat()}"
                    grouped[key].append(m)

                rollup_count = 0
                for key, metrics_list in grouped.items():
                    total_value = sum(m.value for m in metrics_list)
                    total_count = sum(m.count for m in metrics_list)
                    dims = metrics_list[0].dimensions if metrics_list else {}
                    ws = self._get_window_start(
                        metrics_list[0].window_start, target_window
                    )
                    we = self._get_window_end(ws, target_window)

                    rollup = AggregatedMetric(
                        metric_name=metrics_list[0].metric_name,
                        window=target_window,
                        window_start=ws,
                        window_end=we,
                        value=total_value,
                        count=total_count,
                        dimensions=dims,
                    )
                    await repo.save_aggregation(rollup)
                    rollup_count += 1

                logger.info(
                    "Rolled up %d %s metrics to %s",
                    rollup_count,
                    source_window.value,
                    target_window.value,
                )
                return rollup_count

        except Exception as e:
            logger.error("Rollup failed: %s", str(e))
            return 0
