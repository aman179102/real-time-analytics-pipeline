from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.models import AnalyticsEvent, EventStatus, EventType
from src.domain.value_objects import PaginatedResult


class TestEventProcessor:
    async def test_start_stop(self, event_processor):
        assert event_processor._running is False
        await event_processor.start()
        assert event_processor._running is True
        await event_processor.stop()
        assert event_processor._running is False

    async def test_start_when_already_running(self, event_processor):
        await event_processor.start()
        await event_processor.start()
        assert event_processor._running is True
        await event_processor.stop()

    async def test_process_single_event_success(
        self, event_processor, page_view_event: AnalyticsEvent,
    ):
        event_processor._sampler.should_sample = lambda e: True
        event_id = await event_processor.process_single_event(page_view_event)
        assert event_id == page_view_event.event_id
        assert page_view_event.status == EventStatus.AGGREGATED
        event_processor._event_repo.save.assert_awaited_once_with(page_view_event)
        event_processor._analytics_repo.save_aggregation.assert_awaited()
        event_processor._cache.set.assert_awaited()

    async def test_process_single_event_sampled_out(
        self, event_processor, page_view_event: AnalyticsEvent,
    ):
        event_processor._sampler.should_sample = lambda e: False
        event_id = await event_processor.process_single_event(page_view_event)
        assert event_id == page_view_event.event_id
        assert page_view_event.status == EventStatus.SAMPLED
        event_processor._event_repo.save.assert_not_awaited()

    async def test_process_single_event_error(
        self, event_processor, page_view_event: AnalyticsEvent,
    ):
        event_processor._sampler.should_sample = lambda e: True
        event_processor._event_repo.save.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await event_processor.process_single_event(page_view_event)
        assert page_view_event.status == EventStatus.ERROR

    async def test_process_batch_all_sampled_in(
        self, event_processor, sample_events,
    ):
        event_processor._sampler.should_sample = lambda e: True
        event_processor._consumer.consume.return_value = sample_events
        event_processor._event_repo.save_batch.return_value = [e.event_id for e in sample_events]

        await event_processor._process_batch(sample_events)

        event_processor._event_repo.save_batch.assert_awaited_once()
        event_processor._analytics_repo.save_aggregation.assert_awaited()
        event_processor._consumer.acknowledge_batch.assert_awaited_once()
        for event in sample_events:
            assert event.status == EventStatus.AGGREGATED

    async def test_process_batch_some_sampled_out(
        self, event_processor, sample_events,
    ):
        call_count = 0
        def conditional_sample(e):
            nonlocal call_count
            call_count += 1
            return call_count % 2 == 0
        event_processor._sampler.should_sample = conditional_sample
        event_processor._consumer.consume.return_value = sample_events

        await event_processor._process_batch(sample_events)

        saved_events = event_processor._event_repo.save_batch.call_args[0][0]
        assert len(saved_events) == 2
        event_processor._consumer.acknowledge_batch.assert_awaited_once()

    async def test_process_batch_empty(self, event_processor):
        await event_processor._process_batch([])
        event_processor._event_repo.save_batch.assert_not_awaited()

    async def test_process_loop_consumes_events(self, event_processor, sample_events):
        event_processor._sampler.should_sample = lambda e: True
        event_processor._consumer.consume.return_value = sample_events
        event_processor._event_repo.save_batch.return_value = [e.event_id for e in sample_events]

        event_processor._running = True
        import asyncio

        async def stop_after():
            await asyncio.sleep(0.05)
            event_processor._running = False

        await asyncio.gather(
            event_processor._process_loop(),
            stop_after(),
        )

        event_processor._consumer.consume.assert_awaited()
        event_processor._event_repo.save_batch.assert_awaited()

    async def test_process_loop_no_events_sleeps(self, event_processor):
        event_processor._consumer.consume.return_value = []
        event_processor._running = True
        import asyncio

        async def stop_after():
            await asyncio.sleep(0.15)
            event_processor._running = False

        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            event_processor._process_loop(),
            stop_after(),
        )
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.1

    async def test_process_batch_error_handling(self, event_processor, sample_events):
        event_processor._sampler.should_sample = lambda e: True
        event_processor._event_repo.save_batch.side_effect = Exception("Batch save failed")
        await event_processor._process_batch(sample_events)
        event_processor._consumer.acknowledge_batch.assert_not_awaited()
