from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.config import config
from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    EventRepositoryInterface,
    RetentionPolicyInterface,
)
from src.domain.models import AggregationWindow
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)


class RetentionManager(RetentionPolicyInterface):
    def __init__(
        self,
        event_repo: EventRepositoryInterface,
        analytics_repo: AnalyticsRepositoryInterface,
    ) -> None:
        self._event_repo = event_repo
        self._analytics_repo = analytics_repo

    async def apply_retention_policy(self) -> dict[str, int]:
        results: dict[str, int] = {}

        try:
            raw_cutoff = datetime.utcnow() - timedelta(
                days=config.retention.raw_events_days
            )
            raw_deleted = await self._event_repo.delete_older_than(raw_cutoff)
            results["raw_events_deleted"] = raw_deleted
            logger.info(
                "Retention: deleted %d raw events older than %s",
                raw_deleted,
                raw_cutoff.isoformat(),
            )
        except Exception as e:
            logger.error("Raw event retention failed: %s", str(e))
            results["raw_events_error"] = 1

        try:
            hourly_cutoff = datetime.utcnow() - timedelta(
                days=config.retention.aggregated_hourly_days
            )
            hourly_deleted = (
                await self._analytics_repo.delete_aggregations_older_than(
                    AggregationWindow.HOURLY, hourly_cutoff
                )
            )
            results["hourly_aggregations_deleted"] = hourly_deleted
            logger.info(
                "Retention: deleted %d hourly aggregations older than %s",
                hourly_deleted,
                hourly_cutoff.isoformat(),
            )
        except Exception as e:
            logger.error("Hourly retention failed: %s", str(e))
            results["hourly_error"] = 1

        try:
            daily_cutoff = datetime.utcnow() - timedelta(
                days=config.retention.aggregated_daily_days
            )
            daily_deleted = (
                await self._analytics_repo.delete_aggregations_older_than(
                    AggregationWindow.DAILY, daily_cutoff
                )
            )
            results["daily_aggregations_deleted"] = daily_deleted
            logger.info(
                "Retention: deleted %d daily aggregations older than %s",
                daily_deleted,
                daily_cutoff.isoformat(),
            )
        except Exception as e:
            logger.error("Daily retention failed: %s", str(e))
            results["daily_error"] = 1

        total_deleted = sum(v for v in results.values() if isinstance(v, int) and v > 0)
        metrics.set_gauge("retention_records_deleted", float(total_deleted))
        metrics.increment_counter("retention_cycles_completed")

        return results

    async def get_retention_summary(self) -> dict:
        now = datetime.utcnow()
        return {
            "raw_events_retention_days": config.retention.raw_events_days,
            "raw_events_cutoff": (
                now - timedelta(days=config.retention.raw_events_days)
            ).isoformat(),
            "hourly_aggregations_retention_days": config.retention.aggregated_hourly_days,
            "hourly_cutoff": (
                now - timedelta(days=config.retention.aggregated_hourly_days)
            ).isoformat(),
            "daily_aggregations_retention_days": config.retention.aggregated_daily_days,
            "daily_cutoff": (
                now - timedelta(days=config.retention.aggregated_daily_days)
            ).isoformat(),
            "checkpoint_interval_seconds": config.retention.checkpoint_interval,
        }
