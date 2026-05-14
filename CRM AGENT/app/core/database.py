"""
Database configuration and connection management with performance optimizations.
"""
import asyncio
from typing import AsyncGenerator

import structlog
from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import get_settings

logger = structlog.get_logger()

# Database metadata and base model
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Database engines and sessions
engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None

# Connection pool monitoring
active_connections = 0


def get_database_url(async_mode: bool = False) -> str:
    """Get database URL with appropriate driver for sync/async mode."""
    settings = get_settings()
    db_url = settings.DATABASE_URL
    
    if async_mode and db_url.startswith("postgresql://"):
        # Convert to async PostgreSQL URL
        return db_url.replace("postgresql://", "postgresql+asyncpg://")
    elif async_mode and db_url.startswith("sqlite:///"):
        # Convert to async SQLite URL
        return db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    
    return db_url


def get_pool_config(db_url: str) -> dict:
    """Get optimized pool configuration based on database type."""
    if "sqlite" in db_url:
        return {
            "poolclass": StaticPool,
            "pool_pre_ping": True,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 20
            }
        }
    else:
        return {
            "poolclass": QueuePool,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "pool_timeout": 30
        }


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance."""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


@event.listens_for(engine, "checkout")
def track_connection_checkout(dbapi_connection, connection_record, connection_proxy):
    """Track database connection checkout."""
    global active_connections
    active_connections += 1


@event.listens_for(engine, "checkin")
def track_connection_checkin(dbapi_connection, connection_record):
    """Track database connection checkin."""
    global active_connections
    active_connections = max(0, active_connections - 1)


async def init_db() -> None:
    """Initialize database connections and create tables with performance optimizations."""
    global engine, async_engine, SessionLocal, AsyncSessionLocal
    
    settings = get_settings()
    
    try:
        sync_db_url = get_database_url(async_mode=False)
        async_db_url = get_database_url(async_mode=True)
        
        # Get pool configuration
        pool_config = get_pool_config(sync_db_url)
        
        # Create sync engine for migrations with connection pooling
        engine = create_engine(
            sync_db_url,
            echo=settings.DEBUG,
            **pool_config
        )
        
        # Create async engine for application use with connection pooling
        async_pool_config = pool_config.copy()
        if "connect_args" in async_pool_config:
            async_pool_config.pop("connect_args")  # Not supported in async
        
        async_engine = create_async_engine(
            async_db_url,
            echo=settings.DEBUG,
            **async_pool_config
        )
        
        # Create session factories
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
        
        AsyncSessionLocal = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully with connection pooling",
                   pool_size=pool_config.get("pool_size", "static"),
                   max_overflow=pool_config.get("max_overflow", "N/A"))
        
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_db() -> None:
    """Close database connections."""
    global engine, async_engine
    
    try:
        if async_engine:
            await async_engine.dispose()
        if engine:
            engine.dispose()
        
        logger.info("Database connections closed")
        
    except Exception as e:
        logger.error("Error closing database connections", error=str(e))


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    """Get sync database session for migrations."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()