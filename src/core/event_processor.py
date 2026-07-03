from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Optional

from src.config import config
from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    CacheInterface,
    EventRepositoryInterface,
    QueueConsumerInterface,
)
from src.domain.models import AnalyticsEvent, EventStatus
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics
from src.infrastructure.tracing import tracer
from src.core.aggregator import AggregationEngine
from src.core.sampling import Sampler

logger = get_logger(__name__)


class EventProcessor:
    def __init__(
        self,
        event_repo: EventRepositoryInterface,
        analytics_repo: AnalyticsRepositoryInterface,
        consumer: QueueConsumerInterface,
        cache: CacheInterface,
        aggregation_engine: AggregationEngine,
        sampler: Sampler,
    ) -> None:
        self._event_repo = event_repo
        self._analytics_repo = analytics_repo
        self._consumer = consumer
        self._cache = cache
        self._aggregation_engine = aggregation_engine
        self._sampler = sampler
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._batch_size = config.batch_size
        self._flush_interval = config.flush_interval_seconds

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._consumer.connect()
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Event processor started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._consumer.disconnect()
        logger.info("Event processor stopped")

    async def _process_loop(self) -> None:
        while self._running:
            try:
                events = await self._consumer.consume(
                    batch_size=self._batch_size,
                    timeout_ms=int(self._flush_interval * 1000),
                )
                if not events:
                    await asyncio.sleep(0.1)
                    continue
                await self._process_batch(events)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in process loop: %s", str(e))
                await asyncio.sleep(1.0)

    async def _process_batch(
        self, events: list[AnalyticsEvent]
    ) -> None:
        if not events:
            return

        sampled_events = [
            e for e in events
            if self._sampler.should_sample(e)
        ]
        if not sampled_events:
            return

        start_time = time.monotonic()
        span = tracer.start_span("process_events_batch")

        try:
            for event in sampled_events:
                event.status = EventStatus.PROCESSING

            event_ids = await self._event_repo.save_batch(sampled_events)

            for event in sampled_events:
                event.status = EventStatus.AGGREGATED

            aggregated = await self._aggregation_engine.aggregate_events(
                sampled_events
            )

            for metric in aggregated:
                await self._analytics_repo.save_aggregation(metric)

            await self._consumer.acknowledge_batch(sampled_events)

            cache_keys = [f"event:{e.event_id}" for e in sampled_events]
            for ck, eid in zip(cache_keys, event_ids):
                await self._cache.set(ck, eid, ttl_seconds=3600)

            latency = time.monotonic() - start_time
            metrics.increment_counter("events_processed", len(sampled_events))
            metrics.record_latency("process_batch_latency", latency)

            logger.info(
                "Processed batch: %d events in %.3fs",
                len(sampled_events),
                latency,
            )

        except Exception as e:
            logger.error("Batch processing failed: %s", str(e))
            metrics.increment_counter("process_batch_errors")
        finally:
            if span:
                span.end()

    async def process_single_event(
        self, event: AnalyticsEvent
    ) -> str:
        span = tracer.start_span("process_single_event", {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
        })
        try:
            if not self._sampler.should_sample(event):
                event.status = EventStatus.SAMPLED
                return event.event_id

            event.status = EventStatus.PROCESSING
            event_id = await self._event_repo.save(event)

            event.status = EventStatus.AGGREGATED
            aggregated = await self._aggregation_engine.aggregate_events([event])
            for metric in aggregated:
                await self._analytics_repo.save_aggregation(metric)

            await self._cache.set(
                f"event:{event_id}",
                event_id,
                ttl_seconds=3600,
            )

            metrics.increment_counter("events_processed_direct")
            logger.info("Processed direct event %s", event_id)
            return event_id

        except Exception as e:
            event.status = EventStatus.ERROR
            logger.error("Failed to process event %s: %s", event.event_id, str(e))
            metrics.increment_counter("process_single_errors")
            raise
        finally:
            if span:
                span.end()
