"""Shared database connection — SQLAlchemy async with PostgreSQL"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from urllib.parse import quote_plus

_DEFAULT_DB_URL = "postgresql+asyncpg://openhands:" + quote_plus("OpenHands@ERP2026") + "@127.0.0.1:5432/erp_stack"
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5, max_overflow=10)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
