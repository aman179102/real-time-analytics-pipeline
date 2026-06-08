from __future__ import annotations

import json
from typing import Optional

from src.config import config
from src.domain.interfaces import QueueConsumerInterface, QueueProducerInterface
from src.domain.models import AnalyticsEvent, EventStatus
from src.infrastructure.cache.redis import RedisCache
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class RedisStreamQueueProducer(QueueProducerInterface):
    def __init__(self, redis_cache: RedisCache) -> None:
        self._redis = redis_cache
        self._stream = "analytics:events"
        self._group = config.redis.consumer_group

    async def connect(self) -> None:
        await self._redis.connect()
        await self._redis.create_consumer_group(self._stream, self._group)
        logger.info("Connected to Redis Stream producer")

    async def disconnect(self) -> None:
        await self._redis.disconnect()
        logger.info("Disconnected from Redis Stream producer")

    async def publish(self, event: AnalyticsEvent) -> str:
        data = {k: str(v) if not isinstance(v, (str, bytes)) else v
                for k, v in event.to_dict().items()}
        msg_id = await self._redis.add_to_stream(
            self._stream, data, maxlen=config.redis.stream_maxlen
        )
        logger.debug("Published event %s to stream", event.event_id)
        return msg_id

    async def publish_batch(self, events: list[AnalyticsEvent]) -> list[str]:
        ids = []
        for event in events:
            mid = await self.publish(event)
            ids.append(mid)
        return ids


class RedisStreamQueueConsumer(QueueConsumerInterface):
    def __init__(self, redis_cache: RedisCache) -> None:
        self._redis = redis_cache
        self._stream = "analytics:events"
        self._group = config.redis.consumer_group
        self._consumer = "analytics-consumer-1"

    async def connect(self) -> None:
        await self._redis.connect()
        logger.info("Connected to Redis Stream consumer")

    async def disconnect(self) -> None:
        await self._redis.disconnect()
        logger.info("Disconnected from Redis Stream consumer")

    async def consume(
        self, batch_size: int = 100, timeout_ms: int = 1000
    ) -> list[AnalyticsEvent]:
        messages = await self._redis.read_from_consumer_group(
            self._stream,
            self._group,
            self._consumer,
            count=batch_size,
            timeout_ms=timeout_ms,
        )
        events = []
        for msg in messages:
            try:
                data = msg["data"]
                parsed = {}
                for k, v in data.items():
                    parsed[k] = v
                event = AnalyticsEvent.from_dict(parsed)
                event._msg_id = msg["id"]
                events.append(event)
            except Exception as e:
                logger.error("Failed to parse message %s: %s", msg.get("id"), str(e))
        return events

    async def acknowledge(self, event: AnalyticsEvent) -> None:
        msg_id = getattr(event, "_msg_id", None)
        if msg_id:
            await self._redis.acknowledge_message(
                self._stream, self._group, msg_id
            )

    async def acknowledge_batch(self, events: list[AnalyticsEvent]) -> None:
        for event in events:
            await self.acknowledge(event)
