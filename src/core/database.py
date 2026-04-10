"""
数据库连接和管理模块

提供异步数据库连接、会话管理和连接池配置。
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy基类"""
    pass


class Database:
    """数据库连接管理器"""
    
    def __init__(self) -> None:
        """初始化数据库连接"""
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        
    async def connect(self) -> None:
        """连接到数据库"""
        if self._engine is not None:
            logger.warning("数据库连接已存在")
            return
        
        # 创建异步引擎
        engine_config = {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            "pool_pre_ping": True,
            "echo": settings.DATABASE_ECHO,
        }
        
        # 测试环境使用NullPool
        if settings.APP_ENV == "test":
            engine_config["poolclass"] = NullPool
        
        try:
            self._engine = create_async_engine(
                str(settings.DATABASE_URL),
                **engine_config,
            )
            
            # 创建会话工厂
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            
            logger.info("数据库连接已建立")
            
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开数据库连接"""
        if self._engine is None:
            logger.warning("数据库连接不存在")
            return
        
        await self._engine.dispose()
        self._engine = None
        self._session_factory = None
        
        logger.info("数据库连接已断开")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话上下文管理器
        
        Yields:
            AsyncSession: 异步数据库会话
            
        Raises:
            RuntimeError: 数据库未连接
        """
        if self._session_factory is None:
            await self.connect()
        
        if self._session_factory is None:
            raise RuntimeError("数据库会话工厂未初始化")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话异常: {e}")
            raise
        finally:
            await session.close()
    
    async def create_all(self) -> None:
        """创建所有表"""
        if self._engine is None:
            await self.connect()
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("数据库表已创建")
    
    async def drop_all(self) -> None:
        """删除所有表（仅用于测试）"""
        if self._engine is None:
            await self.connect()
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("数据库表已删除")
    
    @property
    def engine(self) -> AsyncEngine:
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化")
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("数据库会话工厂未初始化")
        return self._session_factory


# 全局数据库实例
db = Database()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """依赖注入使用的数据库会话获取器
    
    Yields:
        AsyncSession: 异步数据库会话
    """
    async with db.session() as session:
        yield session


async def get_db_session() -> AsyncSession:
    """获取数据库会话（非上下文管理器）"""
    if db.session_factory is None:
        await db.connect()
    
    return db.session_factory()


# 健康检查函数
async def check_database_health() -> dict:
    """检查数据库健康状态
    
    Returns:
        dict: 包含数据库健康状态的信息
    """
    try:
        async with db.session() as session:
            # 执行简单查询检查连接
            result = await session.execute("SELECT 1")
            row = result.fetchone()
            
            if row and row[0] == 1:
                return {
                    "status": "healthy",
                    "message": "数据库连接正常",
                    "connection_pool": {
                        "checked_out": db.engine.pool.checkedout() if db.engine else 0,
                        "checked_in": db.engine.pool.checkedin() if db.engine else 0,
                    }
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": "数据库查询异常",
                }
    
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"数据库连接失败: {str(e)}",
        }


# 连接池监控函数
async def get_database_metrics() -> dict:
    """获取数据库连接池指标
    
    Returns:
        dict: 数据库连接池指标
    """
    if db.engine is None:
        return {
            "status": "disconnected",
            "pool_size": 0,
            "checked_out": 0,
            "checked_in": 0,
            "overflow": 0,
        }
    
    pool = db.engine.pool
    return {
        "status": "connected",
        "pool_size": pool.size() if hasattr(pool, 'size') else 0,
        "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
        "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
        "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
        "timeouts": pool.timeouts() if hasattr(pool, 'timeouts') else 0,
    }