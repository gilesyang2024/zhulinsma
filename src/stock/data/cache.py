#!/usr/bin/env python3
"""
DataCache - 行情数据 Redis 缓存层
为行情数据提供统一的 Redis 缓存，减少 akshare API 调用
"""

import json
import pickle
from typing import Optional, Any
from datetime import datetime, timedelta
import redis

# 尝试导入 Redis（可选依赖）
try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class DataCache:
    """
    行情数据缓存

    支持：
    - L1 内存缓存（TTL 5分钟）
    - L2 Redis 分布式缓存（TTL 15分钟）
    - 自动降级（Redis 不可用时自动回退）
    """

    # 各数据类型 TTL（秒）
    TTL = {
        "daily": 900,       # 日K 15分钟
        "realtime": 60,     # 实时行情 1分钟
        "auction": 300,     # 竞价数据 5分钟
        "limit_up": 300,    # 涨停数据 5分钟
        "intraday": 60,     # 分时数据 1分钟
    }

    def __init__(self, redis_url: Optional[str] = None):
        self.l1_cache: dict[str, tuple[Any, datetime]] = {}
        self.l1_ttl = 300  # 5分钟内存缓存

        if _REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                self.redis_available = True
            except Exception:
                self.redis_client = None
                self.redis_available = False
        else:
            self.redis_client = None
            self.redis_available = False

    # ─────────────────────────────────────────────
    # L1 内存缓存
    # ─────────────────────────────────────────────

    def _l1_get(self, key: str) -> Optional[Any]:
        if key not in self.l1_cache:
            return None
        _, expire_at = self.l1_cache[key]
        if datetime.now() > expire_at:
            del self.l1_cache[key]
            return None
        return self.l1_cache[key][0]

    def _l1_set(self, key: str, value: Any, ttl: int = 300):
        expire_at = datetime.now() + timedelta(seconds=ttl)
        self.l1_cache[key] = (value, expire_at)

    # ─────────────────────────────────────────────
    # L2 Redis 缓存
    # ─────────────────────────────────────────────

    def _l2_get(self, key: str) -> Optional[Any]:
        if not self.redis_available:
            return None
        try:
            raw = self.redis_client.get(f"stock:{key}")
            if raw:
                return pickle.loads(raw)
        except Exception:
            pass
        return None

    def _l2_set(self, key: str, value: Any, ttl: int = 900):
        if not self.redis_available:
            return
        try:
            self.redis_client.setex(f"stock:{key}", ttl, pickle.dumps(value))
        except Exception:
            pass

    # ─────────────────────────────────────────────
    # 统一接口
    # ─────────────────────────────────────────────

    def get(self, key: str, data_type: str = "daily") -> Optional[Any]:
        """读取缓存（先L1再L2）"""
        # L1 查询
        val = self._l1_get(key)
        if val is not None:
            return val
        # L2 查询
        val = self._l2_get(key)
        if val is not None:
            # 回填 L1
            ttl = self.TTL.get(data_type, 300)
            self._l1_set(key, val, min(ttl, self.l1_ttl))
        return val

    def set(self, key: str, value: Any, data_type: str = "daily"):
        """写入缓存（L1 + L2）"""
        ttl = self.TTL.get(data_type, 300)
        self._l1_set(key, value, min(ttl, self.l1_ttl))
        self._l2_set(key, value, ttl)

    def invalidate(self, key: str):
        """删除缓存"""
        if key in self.l1_cache:
            del self.l1_cache[key]
        if self.redis_available:
            try:
                self.redis_client.delete(f"stock:{key}")
            except Exception:
                pass

    def stats(self) -> dict:
        """返回缓存统计"""
        return {
            "l1_size": len(self.l1_cache),
            "l1_ttl": self.l1_ttl,
            "l2_available": self.redis_available,
        }
