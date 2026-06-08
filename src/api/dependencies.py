from __future__ import annotations

from typing import AsyncGenerator, Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import AuthenticationError, AuthorizationError
from src.config import config
from src.core.analytics_service import AnalyticsService
from src.core.aggregator import AggregationEngine
from src.core.event_processor import EventProcessor
from src.core.retention import RetentionManager
from src.core.sampling import Sampler
from src.domain.interfaces import (
    AnalyticsRepositoryInterface,
    CacheInterface,
    DashboardRepositoryInterface,
    EventRepositoryInterface,
    QueueProducerInterface,
)
from src.domain.models import UserRole
from src.infrastructure.cache.redis import RedisCache
from src.infrastructure.database.repositories import (
    PostgresAnalyticsRepository,
    PostgresDashboardRepository,
    PostgresEventRepository,
)
from src.infrastructure.database.session import db_manager, get_db_session
from src.infrastructure.logging import get_logger
from src.infrastructure.queue.redis_streams import RedisStreamQueueProducer

logger = get_logger(__name__)


async def get_cache() -> AsyncGenerator[CacheInterface, None]:
    cache = RedisCache()
    try:
        await cache.connect()
        yield cache
    finally:
        await cache.disconnect()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session() as session:
        yield session


async def get_event_repo(
    session: AsyncSession = Depends(get_db),
) -> EventRepositoryInterface:
    return PostgresEventRepository(session)


async def get_analytics_repo(
    session: AsyncSession = Depends(get_db),
) -> AnalyticsRepositoryInterface:
    return PostgresAnalyticsRepository(session)


async def get_dashboard_repo(
    session: AsyncSession = Depends(get_db),
) -> DashboardRepositoryInterface:
    return PostgresDashboardRepository(session)


async def get_queue_producer() -> AsyncGenerator[QueueProducerInterface, None]:
    cache = RedisCache()
    await cache.connect()
    producer = RedisStreamQueueProducer(cache)
    await producer.connect()
    try:
        yield producer
    finally:
        await producer.disconnect()
        await cache.disconnect()


async def get_analytics_service(
    event_repo: EventRepositoryInterface = Depends(get_event_repo),
    analytics_repo: AnalyticsRepositoryInterface = Depends(get_analytics_repo),
    dashboard_repo: DashboardRepositoryInterface = Depends(get_dashboard_repo),
    cache: CacheInterface = Depends(get_cache),
) -> AnalyticsService:
    return AnalyticsService(event_repo, analytics_repo, dashboard_repo, cache)


async def get_sampler() -> Sampler:
    return Sampler()


async def get_aggregation_engine(
    analytics_repo: AnalyticsRepositoryInterface = Depends(get_analytics_repo),
) -> AggregationEngine:
    return AggregationEngine(analytics_repo)


async def get_event_processor(
    event_repo: EventRepositoryInterface = Depends(get_event_repo),
    analytics_repo: AnalyticsRepositoryInterface = Depends(get_analytics_repo),
    cache: CacheInterface = Depends(get_cache),
    aggregation_engine: AggregationEngine = Depends(get_aggregation_engine),
    sampler: Sampler = Depends(get_sampler),
) -> EventProcessor:
    cache_for_producer = RedisCache()
    await cache_for_producer.connect()
    consumer = RedisStreamQueueProducer(cache_for_producer)
    await consumer.connect()
    from src.infrastructure.queue.redis_streams import RedisStreamQueueConsumer
    rcache = RedisCache()
    await rcache.connect()
    redis_consumer = RedisStreamQueueConsumer(rcache)
    return EventProcessor(
        event_repo, analytics_repo, redis_consumer, cache,
        aggregation_engine, sampler,
    )


async def get_retention_manager(
    event_repo: EventRepositoryInterface = Depends(get_event_repo),
    analytics_repo: AnalyticsRepositoryInterface = Depends(get_analytics_repo),
) -> RetentionManager:
    return RetentionManager(event_repo, analytics_repo)


async def verify_token(
    authorization: Optional[str] = Header(None),
) -> dict:
    if not authorization:
        raise AuthenticationError("Missing authorization header")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise AuthenticationError("Invalid authorization scheme")

        import jwt as pyjwt
        payload = pyjwt.decode(
            token,
            config.auth.jwt_secret,
            algorithms=[config.auth.jwt_algorithm],
        )
        return payload
    except ValueError:
        raise AuthenticationError("Invalid authorization header format")
    except pyjwt.ExpiredSignatureError:
        raise AuthenticationError("Token expired")
    except pyjwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")


async def require_role(
    required_role: UserRole,
    token: dict = Depends(verify_token),
) -> dict:
    role = UserRole(token.get("role", "viewer"))
    roles_order = [UserRole.VIEWER, UserRole.ANALYST, UserRole.ADMIN]
    if roles_order.index(role) < roles_order.index(required_role):
        raise AuthorizationError(
            f"Requires {required_role.value} role"
        )
    return token
