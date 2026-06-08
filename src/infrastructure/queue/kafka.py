from __future__ import annotations

import json
from typing import Optional

from src.config import config
from src.domain.interfaces import QueueConsumerInterface, QueueProducerInterface
from src.domain.models import AnalyticsEvent
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KafkaQueueProducer(QueueProducerInterface):
    def __init__(self) -> None:
        self._producer: Optional[object] = None
        self._topic = config.kafka.topic

    async def connect(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=config.kafka.bootstrap_servers,
                max_request_size=config.max_event_size_bytes,
            )
            await self._producer.start()
            logger.info("Connected to Kafka producer")
        except ImportError:
            logger.warning("aiokafka not installed, using mock producer")
            self._producer = None

    async def disconnect(self) -> None:
        if self._producer and hasattr(self._producer, "stop"):
            await self._producer.stop()
            logger.info("Disconnected from Kafka producer")

    async def publish(self, event: AnalyticsEvent) -> str:
        if not self._producer:
            logger.warning("Kafka producer not connected")
            return event.event_id
        payload = json.dumps(event.to_dict(), default=str).encode("utf-8")
        await self._producer.send_and_wait(self._topic, payload)
        logger.debug("Published event %s to Kafka", event.event_id)
        return event.event_id

    async def publish_batch(self, events: list[AnalyticsEvent]) -> list[str]:
        ids = []
        for event in events:
            mid = await self.publish(event)
            ids.append(mid)
        return ids


class KafkaQueueConsumer(QueueConsumerInterface):
    def __init__(self) -> None:
        self._consumer: Optional[object] = None
        self._topic = config.kafka.topic
        self._group = config.kafka.consumer_group

    async def connect(self) -> None:
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=config.kafka.bootstrap_servers,
                group_id=self._group,
                max_poll_records=config.kafka.max_poll_records,
                session_timeout_ms=config.kafka.session_timeout_ms,
            )
            await self._consumer.start()
            logger.info("Connected to Kafka consumer")
        except ImportError:
            logger.warning("aiokafka not installed, using mock consumer")
            self._consumer = None

    async def disconnect(self) -> None:
        if self._consumer and hasattr(self._consumer, "stop"):
            await self._consumer.stop()
            logger.info("Disconnected from Kafka consumer")

    async def consume(
        self, batch_size: int = 100, timeout_ms: int = 1000
    ) -> list[AnalyticsEvent]:
        if not self._consumer:
            return []
        try:
            msg_set = await self._consumer.getmany(
                max_records=batch_size, timeout_ms=timeout_ms
            )
            events = []
            for _tp, msgs in msg_set.items():
                for msg in msgs:
                    try:
                        data = json.loads(msg.value.decode("utf-8"))
                        event = AnalyticsEvent.from_dict(data)
                        event._kafka_msg = msg
                        events.append(event)
                    except Exception as e:
                        logger.error(
                            "Failed to parse Kafka message: %s", str(e)
                        )
            return events
        except Exception as e:
            logger.error("Kafka consume error: %s", str(e))
            return []

    async def acknowledge(self, event: AnalyticsEvent) -> None:
        msg = getattr(event, "_kafka_msg", None)
        if msg and self._consumer:
            await self._consumer.commit()

    async def acknowledge_batch(self, events: list[AnalyticsEvent]) -> None:
        if events and self._consumer:
            await self._consumer.commit()
