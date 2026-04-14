"""
缓存管理模块

提供Redis缓存连接、缓存操作和多级缓存策略。
"""

import asyncio
import json
import logging
import pickle
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List
from uuid import UUID

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool
from cachetools import TTLCache

from .config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""
    
    def __init__(self) -> None:
        """初始化缓存管理器"""
        self._redis_client: Optional[Redis] = None
        self._connection_pool: Optional[ConnectionPool] = None
        self._local_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)  # 5分钟本地缓存
        
    async def connect(self) -> None:
        """连接到Redis"""
        if self._redis_client is not None:
            logger.warning("Redis连接已存在")
            return
        
        try:
            # 创建连接池
            self._connection_pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                max_connections=settings.REDIS_POOL_SIZE,
                decode_responses=False,  # 不自动解码，支持二进制数据
            )
            
            # 创建Redis客户端
            self._redis_client = Redis(
                connection_pool=self._connection_pool,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            
            # 测试连接
            await self._redis_client.ping()
            
            logger.info("Redis连接已建立")
            
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开Redis连接"""
        if self._redis_client is None:
            logger.warning("Redis连接不存在")
            return
        
        await self._redis_client.close()
        await self._connection_pool.disconnect()
        
        self._redis_client = None
        self._connection_pool = None
        
        logger.info("Redis连接已断开")
    
    async def ping(self) -> bool:
        """检查Redis连接状态
        
        Returns:
            bool: 连接是否正常
        """
        try:
            if self._redis_client is None:
                await self.connect()
            
            return await self._redis_client.ping()
        except Exception as e:
            logger.error(f"Redis ping失败: {e}")
            return False
    
    # ==================== 基础缓存操作 ====================
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值（多级缓存）
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在返回None
        """
        # 1. 检查本地缓存
        if key in self._local_cache:
            logger.debug(f"从本地缓存获取: {key}")
            return self._local_cache[key]
        
        # 2. 检查Redis缓存
        try:
            if self._redis_client is None:
                await self.connect()
            
            value = await self._redis_client.get(key)
            
            if value is not None:
                # 反序列化
                try:
                    result = pickle.loads(value)
                    # 缓存到本地
                    self._local_cache[key] = result
                    logger.debug(f"从Redis缓存获取: {key}")
                    return result
                except (pickle.PickleError, TypeError) as e:
                    logger.warning(f"缓存反序列化失败: {key}, {e}")
                    await self._redis_client.delete(key)
            
        except Exception as e:
            logger.error(f"Redis获取失败: {key}, {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None,
    ) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒或timedelta）
            
        Returns:
            bool: 是否设置成功
        """
        try:
            if self._redis_client is None:
                await self.connect()
            
            # 序列化值
            serialized_value = pickle.dumps(value)
            
            # 设置过期时间
            if isinstance(expire, timedelta):
                expire_seconds = int(expire.total_seconds())
            elif isinstance(expire, int):
                expire_seconds = expire
            else:
                expire_seconds = None
            
            # 设置到Redis
            if expire_seconds:
                await self._redis_client.setex(key, expire_seconds, serialized_value)
            else:
                await self._redis_client.set(key, serialized_value)
            
            # 更新本地缓存
            self._local_cache[key] = value
            
            logger.debug(f"设置缓存: {key}, 过期: {expire_seconds}秒")
            return True
            
        except Exception as e:
            logger.error(f"Redis设置失败: {key}, {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 从本地缓存删除
            self._local_cache.pop(key, None)
            
            # 从Redis删除
            if self._redis_client is None:
                await self.connect()
            
            result = await self._redis_client.delete(key)
            
            logger.debug(f"删除缓存: {key}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis删除失败: {key}, {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否存在
        """
        try:
            # 检查本地缓存
            if key in self._local_cache:
                return True
            
            # 检查Redis
            if self._redis_client is None:
                await self.connect()
            
            return await self._redis_client.exists(key) > 0
            
        except Exception as e:
            logger.error(f"Redis检查存在失败: {key}, {e}")
            return False
    
    # ==================== 高级缓存操作 ====================
    
    async def get_or_set(
        self,
        key: str,
        func,
        expire: Optional[Union[int, timedelta]] = None,
        *args,
        **kwargs,
    ) -> Any:
        """获取或设置缓存（缓存穿透保护）
        
        Args:
            key: 缓存键
            func: 获取数据的函数
            expire: 过期时间
            *args, **kwargs: 函数参数
            
        Returns:
            缓存值或函数结果
        """
        # 尝试获取缓存
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # 获取数据并设置缓存
        try:
            value = await func(*args, **kwargs) if callable(func) else func
            await self.set(key, value, expire)
            return value
        except Exception as e:
            logger.error(f"获取或设置缓存失败: {key}, {e}")
            raise
    
    async def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的所有缓存
        
        Args:
            pattern: 键模式（支持*通配符）
            
        Returns:
            int: 删除的数量
        """
        try:
            if self._redis_client is None:
                await self.connect()
            
            # 查找匹配的键
            keys = []
            async for key in self._redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if not keys:
                return 0
            
            # 批量删除
            count = await self._redis_client.delete(*keys)
            
            # 清理本地缓存
            for key in keys:
                self._local_cache.pop(key.decode() if isinstance(key, bytes) else key, None)
            
            logger.info(f"清除缓存模式: {pattern}, 删除数量: {count}")
            return count
            
        except Exception as e:
            logger.error(f"清除缓存模式失败: {pattern}, {e}")
            return 0
    
    # ==================== 特定业务缓存 ====================
    
    async def cache_user(self, user_id: UUID, user_data: Dict) -> bool:
        """缓存用户信息
        
        Args:
            user_id: 用户ID
            user_data: 用户数据
            
        Returns:
            bool: 是否缓存成功
        """
        key = f"user:{user_id}"
        return await self.set(key, user_data, expire=timedelta(hours=1))
    
    async def get_user(self, user_id: UUID) -> Optional[Dict]:
        """获取缓存的用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户数据或None
        """
        key = f"user:{user_id}"
        return await self.get(key)
    
    async def cache_content(self, content_id: UUID, content_data: Dict) -> bool:
        """缓存内容信息
        
        Args:
            content_id: 内容ID
            content_data: 内容数据
            
        Returns:
            bool: 是否缓存成功
        """
        key = f"content:{content_id}"
        return await self.set(key, content_data, expire=timedelta(minutes=30))
    
    async def get_content(self, content_id: UUID) -> Optional[Dict]:
        """获取缓存的内容信息
        
        Args:
            content_id: 内容ID
            
        Returns:
            内容数据或None
        """
        key = f"content:{content_id}"
        return await self.get(key)
    
    async def invalidate_user_cache(self, user_id: UUID) -> bool:
        """使用户缓存失效
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否成功
        """
        key = f"user:{user_id}"
        return await self.delete(key)
    
    async def invalidate_content_cache(self, content_id: UUID) -> bool:
        """使内容缓存失效
        
        Args:
            content_id: 内容ID
            
        Returns:
            bool: 是否成功
        """
        key = f"content:{content_id}"
        return await self.delete(key)
    
    # ==================== 分布式锁 ====================
    
    @asynccontextmanager
    async def lock(
        self,
        lock_key: str,
        timeout: int = 10,
        blocking_timeout: int = 5,
    ):
        """获取分布式锁
        
        Args:
            lock_key: 锁键
            timeout: 锁超时时间（秒）
            blocking_timeout: 阻塞等待时间（秒）
            
        Yields:
            bool: 是否获取到锁
        """
        acquired = False
        
        try:
            if self._redis_client is None:
                await self.connect()
            
            # 尝试获取锁
            acquired = await self._redis_client.set(
                lock_key,
                "locked",
                nx=True,
                ex=timeout,
            )
            
            if not acquired and blocking_timeout > 0:
                # 阻塞等待
                start_time = datetime.now()
                while (datetime.now() - start_time).total_seconds() < blocking_timeout:
                    await asyncio.sleep(0.1)
                    acquired = await self._redis_client.set(
                        lock_key,
                        "locked",
                        nx=True,
                        ex=timeout,
                    )
                    if acquired:
                        break
            
            yield acquired
            
        finally:
            if acquired:
                await self._redis_client.delete(lock_key)
    
    # ==================== 统计信息 ====================
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        try:
            if self._redis_client is None:
                await self.connect()
            
            info = await self._redis_client.info()
            
            return {
                "local_cache_size": len(self._local_cache),
                "redis_connected": True,
                "redis_used_memory": info.get("used_memory_human", "未知"),
                "redis_connections": info.get("connected_clients", 0),
                "redis_keys": info.get("db0", {}).get("keys", 0),
                "redis_hit_rate": info.get("keyspace_hits", 0) / max(
                    info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1
                ),
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                "local_cache_size": len(self._local_cache),
                "redis_connected": False,
                "error": str(e),
            }
    
    async def clear_local_cache(self) -> None:
        """清空本地缓存"""
        self._local_cache.clear()
        logger.info("本地缓存已清空")


# 全局缓存实例
cache = CacheManager()


# 健康检查函数
async def check_cache_health() -> Dict[str, Any]:
    """检查缓存健康状态
    
    Returns:
        缓存健康状态信息
    """
    try:
        if await cache.ping():
            return {
                "status": "healthy",
                "message": "缓存连接正常",
                "local_cache_size": len(cache._local_cache),
            }
        else:
            return {
                "status": "unhealthy",
                "message": "缓存连接失败",
            }
    except Exception as e:
        logger.error(f"缓存健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"缓存连接异常: {str(e)}",
        }