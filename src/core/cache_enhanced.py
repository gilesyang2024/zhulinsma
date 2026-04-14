"""
缓存增强模块

提供Redis集群支持、缓存预热、热点数据保护、缓存击穿保护等高级功能。
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union, Callable
from functools import wraps

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool, RedisCluster
from cachetools import TTLCache, LFUCache

from .config import settings

logger = logging.getLogger(__name__)


class CacheEnhancer:
    """缓存增强器"""
    
    def __init__(self):
        self.redis_client = None
        self.cluster_client = None
        self.local_cache = TTLCache(maxsize=5000, ttl=300)  # 5分钟本地缓存
        self.lfu_cache = LFUCache(maxsize=1000)  # LFU缓存用于热点数据
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "local_hits": 0,
            "redis_hits": 0,
            "errors": 0
        }
        self.hot_keys: Set[str] = set()  # 热点键集合
        self.bloom_filter = set()  # 简化版布隆过滤器（实际应用应使用RedisBloom）
        
    async def init(self):
        """初始化缓存客户端"""
        try:
            if settings.REDIS_CLUSTER_ENABLED:
                # Redis集群模式
                startup_nodes = [
                    {"host": node.split(":")[0], "port": int(node.split(":")[1])}
                    for node in settings.REDIS_CLUSTER_NODES
                ]
                self.cluster_client = RedisCluster(
                    startup_nodes=startup_nodes,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=False,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                )
                logger.info("Redis集群客户端已初始化")
            else:
                # 单节点Redis
                connection_pool = ConnectionPool.from_url(
                    settings.REDIS_URL,
                    password=settings.REDIS_PASSWORD,
                    max_connections=settings.REDIS_POOL_SIZE,
                    decode_responses=False,
                )
                self.redis_client = Redis(
                    connection_pool=connection_pool,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                logger.info("Redis客户端已初始化")
                
            await self.ping()
            return True
            
        except Exception as e:
            logger.error(f"缓存客户端初始化失败: {e}")
            return False
    
    def get_client(self):
        """获取Redis客户端"""
        if settings.REDIS_CLUSTER_ENABLED and self.cluster_client:
            return self.cluster_client
        return self.redis_client
    
    async def ping(self) -> bool:
        """检查Redis连接"""
        try:
            client = self.get_client()
            if client:
                return await client.ping()
            return False
        except Exception as e:
            logger.error(f"Redis ping失败: {e}")
            return False
    
    async def smart_get(
        self,
        key: str,
        fallback_func: Optional[Callable] = None,
        fallback_args: tuple = (),
        fallback_kwargs: Dict = None,
        expire: Optional[Union[int, timedelta]] = None,
        enable_bloom: bool = True,
        hot_key_protection: bool = True,
    ) -> Any:
        """
        智能获取缓存（支持多级缓存、缓存击穿保护、热点数据保护）
        
        Args:
            key: 缓存键
            fallback_func: 回退函数（当缓存不存在时调用）
            fallback_args: 回退函数参数
            fallback_kwargs: 回退函数关键字参数
            expire: 过期时间
            enable_bloom: 是否启用布隆过滤器
            hot_key_protection: 是否启用热点键保护
        """
        start_time = time.time()
        
        # 0. 布隆过滤器检查（防止缓存穿透）
        if enable_bloom and key not in self.bloom_filter:
            self.cache_stats["misses"] += 1
            logger.debug(f"布隆过滤器阻止缓存穿透: {key}")
            return None
        
        # 1. 检查LFU缓存（热点数据）
        if hot_key_protection and key in self.lfu_cache:
            self.cache_stats["hits"] += 1
            self.cache_stats["local_hits"] += 1
            logger.debug(f"从LFU缓存获取热点数据: {key}")
            return self.lfu_cache[key]
        
        # 2. 检查本地TTL缓存
        if key in self.local_cache:
            self.cache_stats["hits"] += 1
            self.cache_stats["local_hits"] += 1
            logger.debug(f"从本地缓存获取: {key}")
            return self.local_cache[key]
        
        # 3. 检查Redis缓存
        try:
            client = self.get_client()
            if not client:
                raise Exception("Redis客户端未初始化")
            
            value = await client.get(key)
            
            if value is not None:
                # 反序列化
                import pickle
                result = pickle.loads(value)
                
                # 更新本地缓存
                self.local_cache[key] = result
                
                # 如果是热点键，加入LFU缓存
                if hot_key_protection and key in self.hot_keys:
                    self.lfu_cache[key] = result
                
                self.cache_stats["hits"] += 1
                self.cache_stats["redis_hits"] += 1
                
                elapsed = time.time() - start_time
                logger.debug(f"从Redis缓存获取: {key}, 耗时: {elapsed:.3f}s")
                return result
            else:
                self.cache_stats["misses"] += 1
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Redis获取失败: {key}, {e}")
        
        # 4. 缓存未命中，尝试回退函数
        if fallback_func:
            try:
                result = await fallback_func(*fallback_args, **(fallback_kwargs or {}))
                
                # 异步设置缓存（不阻塞当前请求）
                asyncio.create_task(self._async_set(key, result, expire))
                
                # 更新布隆过滤器
                if enable_bloom:
                    self.bloom_filter.add(key)
                
                elapsed = time.time() - start_time
                logger.debug(f"回退函数获取: {key}, 耗时: {elapsed:.3f}s")
                return result
                
            except Exception as e:
                logger.error(f"回退函数执行失败: {key}, {e}")
                raise
        
        elapsed = time.time() - start_time
        logger.debug(f"缓存未命中: {key}, 耗时: {elapsed:.3f}s")
        return None
    
    async def _async_set(self, key: str, value: Any, expire: Optional[Union[int, timedelta]] = None):
        """异步设置缓存"""
        try:
            await self.smart_set(key, value, expire)
        except Exception as e:
            logger.error(f"异步设置缓存失败: {key}, {e}")
    
    async def smart_set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None,
        update_local: bool = True,
        update_lfu: bool = False,
    ) -> bool:
        """
        智能设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间
            update_local: 是否更新本地缓存
            update_lfu: 是否更新LFU缓存
        """
        try:
            client = self.get_client()
            if not client:
                raise Exception("Redis客户端未初始化")
            
            # 序列化值
            import pickle
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
                await client.setex(key, expire_seconds, serialized_value)
            else:
                await client.set(key, serialized_value)
            
            # 更新本地缓存
            if update_local:
                self.local_cache[key] = value
            
            # 更新LFU缓存
            if update_lfu:
                self.lfu_cache[key] = value
            
            logger.debug(f"设置缓存: {key}, 过期: {expire_seconds}秒")
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败: {key}, {e}")
            return False
    
    async def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        results = {}
        
        for key in keys:
            try:
                value = await self.smart_get(key)
                if value is not None:
                    results[key] = value
            except Exception as e:
                logger.error(f"批量获取缓存失败: {key}, {e}")
        
        return results
    
    async def batch_set(self, items: Dict[str, Any], expire: Optional[int] = None) -> int:
        """批量设置缓存"""
        success_count = 0
        
        for key, value in items.items():
            try:
                if await self.smart_set(key, value, expire):
                    success_count += 1
            except Exception as e:
                logger.error(f"批量设置缓存失败: {key}, {e}")
        
        return success_count
    
    async def mark_hot_key(self, key: str):
        """标记为热点键"""
        self.hot_keys.add(key)
        logger.debug(f"标记热点键: {key}")
    
    async def unmark_hot_key(self, key: str):
        """取消热点键标记"""
        if key in self.hot_keys:
            self.hot_keys.remove(key)
            logger.debug(f"取消热点键标记: {key}")
    
    async def get_hot_keys(self) -> List[str]:
        """获取热点键列表"""
        return list(self.hot_keys)
    
    async def cache_preheat(self, preheat_funcs: List[Callable]):
        """缓存预热"""
        logger.info("开始缓存预热...")
        
        tasks = []
        for func in preheat_funcs:
            task = asyncio.create_task(func())
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
            logger.info("缓存预热完成")
        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
    
    async def clear_cache_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存（支持集群）"""
        try:
            client = self.get_client()
            if not client:
                return 0
            
            if isinstance(client, RedisCluster):
                # Redis集群模式
                deleted_count = 0
                for node in client.get_primaries():
                    keys = []
                    async for key in client.scan_iter(match=pattern, target_nodes=[node]):
                        keys.append(key)
                    
                    if keys:
                        deleted = await client.delete(*keys)
                        deleted_count += deleted
                
                return deleted_count
            else:
                # 单节点模式
                keys = []
                async for key in client.scan_iter(match=pattern):
                    keys.append(key)
                
                if not keys:
                    return 0
                
                deleted = await client.delete(*keys)
                return deleted
                
        except Exception as e:
            logger.error(f"清除缓存模式失败: {pattern}, {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            client = self.get_client()
            info = await client.info() if client else {}
            
            total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
            hit_rate = self.cache_stats["hits"] / max(total_requests, 1)
            
            return {
                "local_cache_size": len(self.local_cache),
                "lfu_cache_size": len(self.lfu_cache),
                "hot_keys_count": len(self.hot_keys),
                "bloom_filter_size": len(self.bloom_filter),
                "hits": self.cache_stats["hits"],
                "misses": self.cache_stats["misses"],
                "local_hits": self.cache_stats["local_hits"],
                "redis_hits": self.cache_stats["redis_hits"],
                "errors": self.cache_stats["errors"],
                "hit_rate": hit_rate,
                "local_hit_rate": self.cache_stats["local_hits"] / max(self.cache_stats["hits"], 1),
                "redis_connected": client is not None and await self.ping(),
                "redis_used_memory": info.get("used_memory_human", "未知"),
                "redis_keys": info.get("db0", {}).get("keys", 0),
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                "local_cache_size": len(self.local_cache),
                "lfu_cache_size": len(self.lfu_cache),
                "hot_keys_count": len(self.hot_keys),
                "redis_connected": False,
                "error": str(e),
            }
    
    def cache_decorator(
        self,
        key_prefix: str = "",
        expire: Optional[Union[int, timedelta]] = None,
        enable_bloom: bool = True,
        hot_key_protection: bool = True,
    ):
        """
        缓存装饰器
        
        Args:
            key_prefix: 键前缀
            expire: 过期时间
            enable_bloom: 是否启用布隆过滤器
            hot_key_protection: 是否启用热点键保护
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{key_prefix}:{func.__name__}"
                if args:
                    cache_key += f":{hash(str(args))}"
                if kwargs:
                    cache_key += f":{hash(str(sorted(kwargs.items())))}"
                
                # 尝试从缓存获取
                result = await self.smart_get(
                    cache_key,
                    fallback_func=func,
                    fallback_args=args,
                    fallback_kwargs=kwargs,
                    expire=expire,
                    enable_bloom=enable_bloom,
                    hot_key_protection=hot_key_protection,
                )
                
                return result
            
            return wrapper
        return decorator


# 全局缓存增强实例
cache_enhancer = CacheEnhancer()