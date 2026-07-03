from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.models import AggregationWindow
from src.core.retention import RetentionManager


class TestRetentionManager:
    async def test_apply_retention_policy_all_success(self, retention_manager: RetentionManager):
        result = await retention_manager.apply_retention_policy()
        assert "raw_events_deleted" in result
        assert "hourly_aggregations_deleted" in result
        assert "daily_aggregations_deleted" in result
        assert result["raw_events_deleted"] == 100
        assert result["hourly_aggregations_deleted"] == 50
        assert result["daily_aggregations_deleted"] == 50
        retention_manager._event_repo.delete_older_than.assert_awaited_once()
        assert retention_manager._analytics_repo.delete_aggregations_older_than.await_count == 2

    async def test_apply_retention_policy_raw_event_error(self, retention_manager: RetentionManager):
        retention_manager._event_repo.delete_older_than.side_effect = Exception("DB error")
        result = await retention_manager.apply_retention_policy()
        assert "raw_events_error" in result
        assert "hourly_aggregations_deleted" in result
        assert "daily_aggregations_deleted" in result

    async def test_apply_retention_policy_hourly_error(self, retention_manager: RetentionManager):
        retention_manager._analytics_repo.delete_aggregations_older_than.side_effect = [
            Exception("Hourly error"),
            50,
        ]
        result = await retention_manager.apply_retention_policy()
        assert "raw_events_deleted" in result
        assert "hourly_error" in result
        assert "daily_aggregations_deleted" in result

    async def test_apply_retention_policy_all_errors(self, retention_manager: RetentionManager):
        retention_manager._event_repo.delete_older_than.side_effect = Exception("Raw error")
        retention_manager._analytics_repo.delete_aggregations_older_than.side_effect = Exception("Agg error")
        result = await retention_manager.apply_retention_policy()
        assert "raw_events_error" in result
        assert "hourly_error" in result
        assert "daily_error" in result

    async def test_apply_retention_policy_calls_correct_cutoffs(self, retention_manager: RetentionManager):
        import src.config as config_mod
        from unittest.mock import patch

        with patch.object(config_mod.config.retention, "raw_events_days", 10):
            with patch.object(config_mod.config.retention, "aggregated_hourly_days", 30):
                with patch.object(config_mod.config.retention, "aggregated_daily_days", 60):
                    await retention_manager.apply_retention_policy()

        raw_call = retention_manager._event_repo.delete_older_than.call_args[0][0]
        assert isinstance(raw_call, datetime)

    async def test_get_retention_summary(self, retention_manager: RetentionManager):
        summary = await retention_manager.get_retention_summary()
        assert "raw_events_retention_days" in summary
        assert "hourly_aggregations_retention_days" in summary
        assert "daily_aggregations_retention_days" in summary
        assert "raw_events_cutoff" in summary
        assert "hourly_cutoff" in summary
        assert "daily_cutoff" in summary
        assert "checkpoint_interval_seconds" in summary

    async def test_get_retention_summary_values(self, retention_manager: RetentionManager):
        import src.config as config_mod
        with patch.object(config_mod.config.retention, "raw_events_days", 7):
            with patch.object(config_mod.config.retention, "aggregated_hourly_days", 14):
                with patch.object(config_mod.config.retention, "aggregated_daily_days", 30):
                    summary = await retention_manager.get_retention_summary()
                    assert summary["raw_events_retention_days"] == 7
                    assert summary["hourly_aggregations_retention_days"] == 14
                    assert summary["daily_aggregations_retention_days"] == 30

    async def test_delete_older_than_called_with_correct_window(
        self, retention_manager: RetentionManager,
    ):
        await retention_manager.apply_retention_policy()
        calls = retention_manager._analytics_repo.delete_aggregations_older_than.call_args_list
        assert len(calls) == 2
        window_args = [call[0][0] for call in calls]
        assert AggregationWindow.HOURLY in window_args
        assert AggregationWindow.DAILY in window_args
