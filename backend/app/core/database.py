# ============================================================================
# AsyncPG Database Configuration
# ============================================================================
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
import asyncpg
from .config import get_settings, get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages async database connections and sessions"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
    
    async def initialize(self):
        """Create async engine and session factory"""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Test connections before using
            connect_args={
                "timeout": 10,
                "command_timeout": 60,
            }
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        logger.info(f"Database initialized: {self.database_url}")
    
    async def close(self):
        """Close engine and all connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Dependency for FastAPI to inject async session"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()


# Global instance
_db_manager: DatabaseManager = None


def get_db_manager() -> DatabaseManager:
    """Get or create database manager instance"""
    global _db_manager
    if _db_manager is None:
        settings = get_settings()
        _db_manager = DatabaseManager(settings.DATABASE_URL)
    return _db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for AsyncSession in route handlers"""
    db_manager = get_db_manager()
    async for session in db_manager.get_session():
        yield session
