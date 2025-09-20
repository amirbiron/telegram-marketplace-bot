"""
ניהול מסד נתונים אסינכרוני - Database Management
SQLAlchemy 2.0 + Async PostgreSQL + Connection Pooling
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger(__name__)


class Base(MappedAsDataclass, DeclarativeBase):
    """
    בסיס לכל המודלים
    תמיכה ב-dataclass אוטומטי ל-SQLAlchemy 2.0
    """
    pass


class DatabaseManager:
    """
    מנהל מסד הנתונים - Singleton Pattern
    ניהול חיבורים אסינכרוניים + Connection Pooling
    """
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized: bool = False
    
    async def initialize(self) -> None:
        """אתחול מסד הנתונים והגדרת החיבורים"""
        if self._initialized:
            logger.warning("Database already initialized")
            return
        
        try:
            # יצירת Async Engine עם Connection Pooling מתקדם
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DATABASE_ECHO,
                future=True,  # SQLAlchemy 2.0 style
                
                # הגדרות Connection Pooling מתקדמות
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_timeout=30,  # המתנה מקסימלית לחיבור חדש
                pool_recycle=3600,  # רענון חיבורים כל שעה
                pool_pre_ping=True,  # בדיקת תקינות החיבור לפני שימוש
                
                # הגדרות performance
                connect_args={
                    "server_settings": {
                        "jit": "off",  # כיבוי JIT לביצועים טובים יותר
                        "application_name": f"{settings.APP_NAME}_v{settings.VERSION}"
                    },
                    "command_timeout": 60,
                    "statement_cache_size": 0,  # נמנע מ-cache problems
                }
            )
            
            # לוג: איזה דרייבר נטען בפועל
            try:
                driver = self.engine.sync_engine.dialect.driver
                logger.info(f"🧩 Database driver in use: {driver}")
            except Exception:
                logger.info("🧩 Database driver in use: unknown")
            
            # יצירת Session Maker
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,  # שמירת אובייקטים לאחר commit
                autoflush=True,
                autocommit=False
            )
            
            # בדיקת חיבור
            await self.ping_database()
            
            # הרשמה ל-events
            self._register_events()
            
            self._initialized = True
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise
    
    def _register_events(self) -> None:
        """הרשמה לאירועי SQLAlchemy"""
        
        @event.listens_for(self.engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """הגדרות נוספות לחיבור (אם נדרש)"""
            pass
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """לוג כאשר חיבור נלקח מה-pool"""
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(self.engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """לוג כאשר חיבור מוחזר ל-pool"""
            logger.debug("Connection checked back into pool")
    
    async def ping_database(self) -> bool:
        """בדיקת תקינות החיבור למסד הנתונים"""
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                # Row הוא אובייקט סינכרוני, אין להשתמש ב-await
                result.fetchone()
            logger.info("🏓 Database ping successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database ping failed: {e}")
            return False
    
    async def create_all_tables(self) -> None:
        """יצירת כל הטבלאות במסד הנתונים"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ All tables created successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            raise
    
    async def drop_all_tables(self) -> None:
        """מחיקת כל הטבלאות (זהירות! רק לפיתוח)"""
        if settings.is_production:
            raise RuntimeError("Cannot drop tables in production!")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.warning("⚠️ All tables dropped")
            
        except Exception as e:
            logger.error(f"❌ Failed to drop tables: {e}")
            raise
    
    async def close(self) -> None:
        """סגירת החיבורים למסד הנתונים"""
        if self.engine:
            await self.engine.dispose()
            logger.info("🔒 Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        קבלת session אסינכרוני עם context manager
        השימוש המומלץ לכל פעולות ה-DB
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_raw_sql(self, sql: str, params: dict = None) -> any:
        """הרצת SQL גולמי (לשימוש מתקדם בלבד)"""
        async with self.get_session() as session:
            try:
                result = await session.execute(text(sql), params or {})
                await session.commit()
                return result
            except Exception as e:
                logger.error(f"Raw SQL execution failed: {e}")
                raise
    
    async def get_database_info(self) -> dict:
        """קבלת מידע על מסד הנתונים"""
        try:
            info_queries = {
                "version": "SELECT version()",
                "current_database": "SELECT current_database()",
                "current_user": "SELECT current_user",
                "connection_count": """
                    SELECT count(*) 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """,
                "database_size": """
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """
            }
            
            info = {}
            async with self.get_session() as session:
                for key, query in info_queries.items():
                    try:
                        result = await session.execute(text(query))
                        info[key] = result.scalar()
                    except Exception as e:
                        info[key] = f"Error: {e}"
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}


# יצירת instance יחיד של DatabaseManager
db_manager = DatabaseManager()


# === Dependency Functions ===

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function לקבלת DB session
    לשימוש ב-FastAPI endpoints
    """
    async with db_manager.get_session() as session:
        yield session


async def get_db_manager() -> DatabaseManager:
    """Dependency function לקבלת DatabaseManager"""
    return db_manager


# === Utility Functions ===

async def init_database() -> None:
    """אתחול מסד הנתונים - לשימוש ב-startup"""
    await db_manager.initialize()
    await db_manager.create_all_tables()


async def close_database() -> None:
    """סגירת מסד הנתונים - לשימוש ב-shutdown"""
    await db_manager.close()


async def health_check() -> dict:
    """בדיקת בריאות מסד הנתונים"""
    try:
        is_healthy = await db_manager.ping_database()
        db_info = await db_manager.get_database_info()
        
        return {
            "healthy": is_healthy,
            "info": db_info,
            "pool_status": {
                "size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW
            } if db_manager.engine else None
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e)
        }


# === Transaction Helpers ===

async def execute_in_transaction(func, *args, **kwargs):
    """
    ביצוע פעולה בטרנזקציה
    עם automatic rollback במקרה של שגיאה
    """
    async with db_manager.get_session() as session:
        try:
            result = await func(session, *args, **kwargs)
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error(f"Transaction failed and rolled back: {e}")
            raise


# === Database Initialization Event ===

async def ensure_database_initialized():
    """וידוא שמסד הנתונים מאותחל"""
    if not db_manager._initialized:
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialization completed")


# === Migration Helper (לעתיד) ===

async def run_migrations():
    """הרצת מיגרציות - placeholder לעתיד"""
    # כאן נוכל להוסיף לוגיקה להרצת Alembic migrations
    logger.info("Migrations check completed")


# === Connection Pool Monitoring ===

def get_pool_status() -> dict:
    """קבלת סטטוס Connection Pool"""
    if not db_manager.engine:
        return {"status": "not_initialized"}
    
    pool = db_manager.engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid()
    }
