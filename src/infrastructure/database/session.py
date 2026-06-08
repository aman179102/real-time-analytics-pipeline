from __future__ import annotations

import contextlib
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncSessionTransaction,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config import config


class BaseModel(DeclarativeBase):
    pass


class DatabaseSessionManager:
    def __init__(self) -> None:
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._engine = create_async_engine(
            config.database.dsn,
            pool_size=config.database.pool_size,
            max_overflow=config.database.pool_overflow,
            pool_timeout=config.database.pool_timeout,
            echo=config.database.echo,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._initialized = True

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self._initialized:
            await self.initialize()
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @contextlib.asynccontextmanager
    async def transactional_session(
        self,
    ) -> AsyncGenerator[AsyncSession, None]:
        if not self._initialized:
            await self.initialize()
        async with self._session_factory() as session:
            async with session.begin():
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

    @property
    def is_initialized(self) -> bool:
        return self._initialized


db_manager = DatabaseSessionManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session() as session:
        yield session


async def init_db() -> None:
    await db_manager.initialize()
    async with db_manager.session() as session:
        await session.run_sync(BaseModel.metadata.create_all)


async def close_db() -> None:
    await db_manager.close()
