from src.infrastructure.database.session import (
    DatabaseSessionManager,
    get_db_session,
    init_db,
    close_db,
)
from src.infrastructure.database.repositories import (
    PostgresEventRepository,
    PostgresAnalyticsRepository,
    PostgresDashboardRepository,
)
from src.infrastructure.cache.redis import RedisCache
from src.infrastructure.queue.redis_streams import RedisStreamQueueProducer, RedisStreamQueueConsumer
from src.infrastructure.queue.kafka import KafkaQueueProducer, KafkaQueueConsumer
from src.infrastructure.logging import StructuredLogger, get_logger
from src.infrastructure.metrics import MetricsCollector
from src.infrastructure.tracing import TracerProvider

__all__ = [
    "DatabaseSessionManager",
    "get_db_session",
    "init_db",
    "close_db",
    "PostgresEventRepository",
    "PostgresAnalyticsRepository",
    "PostgresDashboardRepository",
    "RedisCache",
    "RedisStreamQueueProducer",
    "RedisStreamQueueConsumer",
    "KafkaQueueProducer",
    "KafkaQueueConsumer",
    "StructuredLogger",
    "get_logger",
    "MetricsCollector",
    "TracerProvider",
]

# test: add regression tests for authentication bug fix
