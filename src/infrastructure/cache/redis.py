from __future__ import annotations

from typing import Optional

import redis.asyncio as aioredis

from src.config import config
from src.domain.interfaces import CacheInterface
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class RedisCache(CacheInterface):
    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        if self._client:
            return
        self._client = await aioredis.from_url(
            config.redis.dsn,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("Connected to Redis cache")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis cache")

    async def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        value = await self._client.get(key)
        return value

    async def set(
        self, key: str, value: str, ttl_seconds: int = 300
    ) -> None:
        if not self._client:
            return
        await self._client.setex(key, ttl_seconds, value)

    async def delete(self, key: str) -> None:
        if not self._client:
            return
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        if not self._client:
            return False
        result = await self._client.exists(key)
        return bool(result)

    async def incr(self, key: str) -> int:
        if not self._client:
            return 0
        return await self._client.incr(key)

    async def expire(self, key: str, ttl_seconds: int) -> None:
        if not self._client:
            return
        await self._client.expire(key, ttl_seconds)

    async def get_json(self, key: str) -> Optional[dict]:
        import json
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(
        self, key: str, value: dict, ttl_seconds: int = 300
    ) -> None:
        import json
        await self.set(key, json.dumps(value, default=str), ttl_seconds)

    async def add_to_stream(
        self, stream_name: str, data: dict, maxlen: int = 100000
    ) -> str:
        if not self._client:
            return ""
        return await self._client.xadd(
            stream_name, data, maxlen=maxlen
        )

    async def read_from_stream(
        self,
        stream_name: str,
        count: int = 100,
        block_ms: int = 1000,
        last_id: str = "$",
    ) -> list[dict]:
        if not self._client:
            return []
        results = await self._client.xread(
            {stream_name: last_id}, count=count, block=block_ms
        )
        messages = []
        for stream in results:
            for msg_id, msg_data in stream[1]:
                messages.append({"id": msg_id, "data": msg_data})
        return messages

    async def create_consumer_group(
        self, stream_name: str, group_name: str
    ) -> None:
        if not self._client:
            return
        try:
            await self._client.xgroup_create(
                stream_name, group_name, id="0", mkstream=True
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read_from_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        count: int = 100,
        timeout_ms: int = 1000,
    ) -> list[dict]:
        if not self._client:
            return []
        results = await self._client.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: ">"},
            count=count,
            block=timeout_ms,
        )
        messages = []
        for stream in results:
            for msg_id, msg_data in stream[1]:
                messages.append({"id": msg_id, "data": msg_data})
        return messages

    async def acknowledge_message(
        self, stream_name: str, group_name: str, msg_id: str
    ) -> None:
        if not self._client:
            return
        await self._client.xack(stream_name, group_name, msg_id)

    async def get_pending_count(
        self, stream_name: str, group_name: str
    ) -> int:
        if not self._client:
            return 0
        info = await self._client.xpending(stream_name, group_name)
        return info.get("pending", 0)
