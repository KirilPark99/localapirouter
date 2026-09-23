import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from sqlalchemy import DateTime, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.core.config import settings

from sqlalchemy.pool import NullPool

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool if "sqlite" in settings.DATABASE_URL else None,
    # SQLite requires check_same_thread=False for async connection sharing
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

async def _safe_close_session(session: AsyncSession) -> None:
    """
    Safely close an AsyncSession, protecting connection termination from
    asyncio.CancelledError when a client disconnects mid-request.
    """
    try:
        close_task = asyncio.create_task(session.close())
        try:
            await asyncio.shield(close_task)
        except asyncio.CancelledError:
            try:
                await close_task
            except Exception:
                pass
            raise
    except asyncio.CancelledError:
        raise
    except Exception:
        pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        try:
            rb_task = asyncio.create_task(session.rollback())
            try:
                await asyncio.shield(rb_task)
            except asyncio.CancelledError:
                try:
                    await rb_task
                except Exception:
                    pass
                raise
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        raise
    finally:
        await _safe_close_session(session)
