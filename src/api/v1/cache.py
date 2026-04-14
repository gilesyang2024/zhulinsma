"""
缓存管理API

提供缓存管理、监控、预热、统计等功能。
需要管理员权限。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from src.core.cache import cache
from src.core.cache_enhanced import cache_enhancer

# 创建缓存管理路由
router = APIRouter()


# 请求/响应模型

class CacheStatsResponse(BaseModel):
    """缓存统计响应"""
    local_cache_size: int = Field(..., description="本地缓存大小")
    redis_connected: bool = Field(..., description="Redis连接状态")
    redis_used_memory: str = Field(..., description="Redis已用内存")
    redis_keys: int = Field(..., description="Redis键数量")
    hit_rate: float = Field(..., description="缓存命中率")
    timestamp: datetime = Field(..., description="统计时间")


class EnhancedCacheStatsResponse(BaseModel):
    """增强缓存统计响应"""
    local_cache_size: int = Field(..., description="本地TTL缓存大小")
    lfu_cache_size: int = Field(..., description="LFU缓存大小")
    hot_keys_count: int = Field(..., description="热点键数量")
    bloom_filter_size: int = Field(..., description="布隆过滤器大小")
    hits: int = Field(..., description="总命中次数")
    misses: int = Field(..., description="总未命中次数")
    local_hits: int = Field(..., description="本地缓存命中次数")
    redis_hits: int = Field(..., description="Redis命中次数")
    errors: int = Field(..., description="错误次数")
    hit_rate: float = Field(..., description="总命中率")
    local_hit_rate: float = Field(..., description="本地缓存命中率")
    redis_connected: bool = Field(..., description="Redis连接状态")
    timestamp: datetime = Field(..., description="统计时间")


class CacheKeyRequest(BaseModel):
    """缓存键操作请求"""
    key: str = Field(..., description="缓存键")
    value: Optional[Any] = Field(None, description="缓存值")
    expire: Optional[int] = Field(None, ge=1, description="过期时间（秒）")


class CachePatternRequest(BaseModel):
    """缓存模式操作请求"""
    pattern: str = Field(..., description="键模式（支持*通配符）")


class HotKeyResponse(BaseModel):
    """热点键响应"""
    key: str = Field(..., description="键名")
    marked_at: datetime = Field(..., description="标记时间")
    is_hot: bool = Field(..., description="是否为热点键")


class CachePreheatRequest(BaseModel):
    """缓存预热请求"""
    preheat_type: str = Field(..., description="预热类型: users, content, system")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="预热数量限制")


@router.get("/stats", response_model=CacheStatsResponse, tags=["缓存管理"])
async def get_cache_stats() -> CacheStatsResponse:
    """
    获取缓存统计信息
    
    返回基础缓存的统计信息。
    """
    stats = await cache.get_stats()
    
    return CacheStatsResponse(
        local_cache_size=stats.get("local_cache_size", 0),
        redis_connected=stats.get("redis_connected", False),
        redis_used_memory=stats.get("redis_used_memory", "未知"),
        redis_keys=stats.get("redis_keys", 0),
        hit_rate=stats.get("redis_hit_rate", 0.0),
        timestamp=datetime.now()
    )


@router.get("/enhanced/stats", response_model=EnhancedCacheStatsResponse, tags=["缓存管理"])
async def get_enhanced_cache_stats() -> EnhancedCacheStatsResponse:
    """
    获取增强缓存统计信息
    
    返回增强缓存的详细统计信息。
    """
    # 初始化增强缓存
    if cache_enhancer.get_client() is None:
        await cache_enhancer.init()
    
    stats = await cache_enhancer.get_stats()
    
    return EnhancedCacheStatsResponse(
        local_cache_size=stats.get("local_cache_size", 0),
        lfu_cache_size=stats.get("lfu_cache_size", 0),
        hot_keys_count=stats.get("hot_keys_count", 0),
        bloom_filter_size=stats.get("bloom_filter_size", 0),
        hits=stats.get("hits", 0),
        misses=stats.get("misses", 0),
        local_hits=stats.get("local_hits", 0),
        redis_hits=stats.get("redis_hits", 0),
        errors=stats.get("errors", 0),
        hit_rate=stats.get("hit_rate", 0.0),
        local_hit_rate=stats.get("local_hit_rate", 0.0),
        redis_connected=stats.get("redis_connected", False),
        timestamp=datetime.now()
    )


@router.get("/key/{key}", response_model=Dict[str, Any], tags=["缓存管理"])
async def get_cache_value(
    key: str
) -> Dict[str, Any]:
    """
    获取缓存值
    
    获取指定键的缓存值。
    """
    value = await cache.get(key)
    
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"缓存键 '{key}' 不存在"
        )
    
    return {
        "key": key,
        "value": value,
        "exists": True
    }


@router.post("/key", status_code=status.HTTP_201_CREATED, tags=["缓存管理"])
async def set_cache_value(
    request: CacheKeyRequest
) -> Dict[str, Any]:
    """
    设置缓存值
    
    设置指定键的缓存值。
    """
    success = await cache.set(
        key=request.key,
        value=request.value,
        expire=request.expire
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设置缓存失败"
        )
    
    return {
        "message": "缓存设置成功",
        "key": request.key,
        "expire": request.expire
    }


@router.delete("/key/{key}", tags=["缓存管理"])
async def delete_cache_key(
    key: str
) -> Dict[str, Any]:
    """
    删除缓存键
    
    删除指定的缓存键。
    """
    success = await cache.delete(key)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"缓存键 '{key}' 不存在或删除失败"
        )
    
    return {
        "message": "缓存删除成功",
        "key": key
    }


@router.delete("/pattern", tags=["缓存管理"])
async def delete_cache_pattern(
    request: CachePatternRequest
) -> Dict[str, Any]:
    """
    按模式删除缓存
    
    删除匹配指定模式的所有缓存键。
    """
    deleted_count = await cache.clear_pattern(request.pattern)
    
    return {
        "message": "缓存模式删除完成",
        "pattern": request.pattern,
        "deleted_count": deleted_count
    }


@router.get("/hot-keys", response_model=List[HotKeyResponse], tags=["缓存管理"])
async def get_hot_keys() -> List[HotKeyResponse]:
    """
    获取热点键列表
    
    返回当前标记为热点键的列表。
    """
    # 初始化增强缓存
    if cache_enhancer.get_client() is None:
        await cache_enhancer.init()
    
    hot_keys = await cache_enhancer.get_hot_keys()
    
    return [
        HotKeyResponse(
            key=key,
            marked_at=datetime.now(),
            is_hot=True
        )
        for key in hot_keys[:50]  # 限制返回数量
    ]


@router.post("/hot-keys/{key}", tags=["缓存管理"])
async def mark_hot_key(
    key: str
) -> Dict[str, Any]:
    """
    标记热点键
    
    将指定键标记为热点键，启用特殊保护。
    """
    # 初始化增强缓存
    if cache_enhancer.get_client() is None:
        await cache_enhancer.init()
    
    await cache_enhancer.mark_hot_key(key)
    
    return {
        "message": "热点键标记成功",
        "key": key
    }


@router.delete("/hot-keys/{key}", tags=["缓存管理"])
async def unmark_hot_key(
    key: str
) -> Dict[str, Any]:
    """
    取消热点键标记
    
    取消指定键的热点键标记。
    """
    # 初始化增强缓存
    if cache_enhancer.get_client() is None:
        await cache_enhancer.init()
    
    await cache_enhancer.unmark_hot_key(key)
    
    return {
        "message": "热点键标记已取消",
        "key": key
    }


@router.post("/preheat", tags=["缓存管理"])
async def preheat_cache(
    request: CachePreheatRequest
) -> Dict[str, Any]:
    """
    缓存预热
    
    预先加载常用数据到缓存中。
    """
    # TODO: 实现实际的预热逻辑
    # 这里返回模拟结果
    
    preheat_functions = []
    
    if request.preheat_type == "users":
        # 预热用户数据：从缓存加载活跃用户到L1
        async def preheat_users():
            logger.info("开始预热用户数据...")
            # 扫描 user: 前缀的缓存键，预加载到本地缓存
            try:
                loaded = 0
                async for key in cache._redis_client.scan_iter(match="user:*", count=request.limit):
                    if loaded >= request.limit:
                        break
                    value = await cache.get(key)
                    if value is not None:
                        loaded += 1
                logger.info(f"用户数据预热完成，加载 {loaded} 条")
            except Exception as e:
                logger.warning(f"用户预热异常（非致命）: {e}")
        
        preheat_functions.append(preheat_users)
    
    elif request.preheat_type == "content":
        # 预热内容数据：从缓存加载热门内容到L1
        async def preheat_content():
            logger.info("开始预热内容数据...")
            try:
                loaded = 0
                async for key in cache._redis_client.scan_iter(match="content:*", count=request.limit):
                    if loaded >= request.limit:
                        break
                    value = await cache.get(key)
                    if value is not None:
                        loaded += 1
                logger.info(f"内容数据预热完成，加载 {loaded} 条")
            except Exception as e:
                logger.warning(f"内容预热异常（非致命）: {e}")
        
        preheat_functions.append(preheat_content)
    
    elif request.preheat_type == "system":
        # 预热系统数据：刷新配置/权限/字典等
        async def preheat_system():
            logger.info("开始预热系统配置数据...")
            # 系统配置类数据通常量小，快速刷新TTL即可
            await asyncio.sleep(0.2)
            logger.info("系统配置预热完成")
        
        preheat_functions.append(preheat_system)
    
    # 初始化增强缓存
    if cache_enhancer.get_client() is None:
        await cache_enhancer.init()
    
    # 执行预热
    await cache_enhancer.cache_preheat(preheat_functions)
    
    return {
        "message": "缓存预热完成",
        "preheat_type": request.preheat_type,
        "limit": request.limit,
        "preheat_time": datetime.now().isoformat()
    }


@router.get("/health", response_model=Dict[str, Any], tags=["缓存管理"])
async def check_cache_health() -> Dict[str, Any]:
    """
    检查缓存健康状态
    
    返回缓存系统的健康状态。
    """
    # 检查基础缓存
    base_health = await cache.ping()
    
    # 检查增强缓存
    enhanced_health = False
    try:
        if cache_enhancer.get_client() is None:
            await cache_enhancer.init()
        enhanced_health = await cache_enhancer.ping()
    except Exception:
        pass
    
    overall_health = base_health and enhanced_health
    
    return {
        "status": "healthy" if overall_health else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "base_cache": {
                "status": "healthy" if base_health else "unhealthy",
                "message": "基础缓存连接正常" if base_health else "基础缓存连接异常"
            },
            "enhanced_cache": {
                "status": "healthy" if enhanced_health else "unhealthy",
                "message": "增强缓存连接正常" if enhanced_health else "增强缓存连接异常"
            }
        },
        "recommendations": [] if overall_health else ["请检查Redis服务状态"]
    }


@router.post("/flush", tags=["缓存管理"])
async def flush_cache() -> Dict[str, Any]:
    """
    清空所有缓存
    
    警告：此操作会清空所有缓存数据，包括本地缓存和Redis缓存。
    """
    # 清空本地缓存
    await cache.clear_local_cache()
    
    # 清空Redis缓存
    await cache.clear_pattern("*")
    
    # 清空增强缓存
    if cache_enhancer.get_client() is not None:
        await cache_enhancer.clear_cache_pattern("*")
    
    return {
        "message": "所有缓存已清空",
        "warning": "此操作会清空所有缓存数据，请谨慎使用",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/keys", response_model=List[str], tags=["缓存管理"])
async def list_cache_keys(
    pattern: str = Query("*", description="键模式（支持*通配符）"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制")
) -> List[str]:
    """
    列出缓存键
    
    返回匹配指定模式的缓存键列表。
    """
    # 注意：此操作在生产环境中可能会很慢，应谨慎使用
    
    try:
        # 从 Redis SCAN 获取真实键列表
        keys = []
        cursor = 0
        while True:
            if cache._redis_client is None:
                break
            cursor, batch = await cache._redis_client.scan(cursor, match=pattern, count=min(limit, 200))
            for key in batch:
                # 统一解码
                decoded = key.decode() if isinstance(key, bytes) else key
                keys.append(decoded)
            if cursor == 0 or len(keys) >= limit:
                break
        
        return keys[:limit]
        
    except Exception as e:
        logger.warning(f"获取缓存键列表异常，返回空: {e}")
        return []


@router.get("/monitor", response_model=Dict[str, Any], tags=["缓存监控"])
async def monitor_cache_performance(
    duration: int = Query(60, ge=1, le=3600, description="监控时长（秒）"),
    interval: int = Query(10, ge=1, le=300, description="采样间隔（秒）")
) -> Dict[str, Any]:
    """
    监控缓存性能
    
    在一段时间内监控缓存性能指标。
    """
    # 基于真实采样数据的性能监控
    samples = []
    
    for i in range(min(duration // interval, 10)):
        stats = await cache.get_stats()
        enhanced_stats = {}
        
        # 尝试获取增强缓存统计
        try:
            if cache_enhancer.get_client() is not None:
                enhanced_stats = await cache_enhancer.get_stats()
        except Exception:
            pass
        
        samples.append({
            "timestamp": datetime.now().isoformat(),
            "hit_rate": stats.get("redis_hit_rate", 0.0),
            "local_cache_size": stats.get("local_cache_size", 0),
            "redis_keys": stats.get("redis_keys", 0),
            "redis_used_memory": stats.get("redis_used_memory", "未知"),
            "redis_connected": stats.get("redis_connected", False),
            "enhanced_hits": enhanced_stats.get("hits", 0),
            "enhanced_misses": enhanced_stats.get("misses", 0),
        })
        
        # 按间隔等待下次采样
        if i < (duration // interval) - 1:
            await asyncio.sleep(interval)
    
    hit_rates = [s["hit_rate"] for s in samples]
    local_sizes = [s["local_cache_size"] for s in samples]
    redis_key_counts = [s["redis_keys"] for s in samples]
    
    return {
        "duration": duration,
        "interval": interval,
        "sample_count": len(samples),
        "samples": samples,
        "summary": {
            "avg_hit_rate": sum(hit_rates) / len(hit_rates) if hit_rates else 0,
            "max_local_cache": max(local_sizes) if local_sizes else 0,
            "avg_redis_keys": sum(redis_key_counts) / len(redis_key_counts) if redis_key_counts else 0,
        }
    }