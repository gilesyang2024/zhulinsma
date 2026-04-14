#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 缓存优化器
LRU 内存缓存 + 装饰器，零侵入式加速重复计算
"""

import time
import hashlib
import json
import functools
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple


class CacheOptimizer:
    """
    LRU 内存缓存优化器

    特性：
    - 支持 TTL 过期
    - 线程安全（单线程调用）
    - 命中率统计
    - 提供 @cached 装饰器
    """

    def __init__(self, 最大容量: int = 512, 默认ttl: int = 300):
        self.最大容量 = 最大容量
        self.默认ttl = 默认ttl
        self._缓存: OrderedDict = OrderedDict()
        self._命中次数 = 0
        self._未命中次数 = 0

    def get(self, key: str) -> Tuple[bool, Any]:
        """返回 (命中, 值)"""
        if key in self._缓存:
            entry = self._缓存[key]
            if time.time() < entry["expire_at"]:
                self._缓存.move_to_end(key)
                self._命中次数 += 1
                return True, entry["value"]
            else:
                del self._缓存[key]
        self._未命中次数 += 1
        return False, None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        有效ttl = ttl if ttl is not None else self.默认ttl
        if key in self._缓存:
            self._缓存.move_to_end(key)
        self._缓存[key] = {"value": value, "expire_at": time.time() + 有效ttl}
        if len(self._缓存) > self.最大容量:
            self._缓存.popitem(last=False)

    def 命中率(self) -> float:
        总数 = self._命中次数 + self._未命中次数
        if 总数 == 0:
            return 0.0
        return round(self._命中次数 / 总数, 4)

    def 统计(self) -> Dict:
        return {
            "缓存容量": len(self._缓存),
            "最大容量": self.最大容量,
            "命中次数": self._命中次数,
            "未命中次数": self._未命中次数,
            "命中率": f"{self.命中率() * 100:.1f}%",
        }

    def 清空(self) -> None:
        self._缓存.clear()
        self._命中次数 = 0
        self._未命中次数 = 0

    def cached(self, ttl: Optional[int] = None):
        """函数缓存装饰器"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存 key
                try:
                    key_data = {"fn": func.__qualname__, "args": str(args), "kwargs": str(kwargs)}
                    key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
                except Exception:
                    return func(*args, **kwargs)

                hit, value = self.get(key)
                if hit:
                    return value
                result = func(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


# 全局默认缓存实例
default_cache = CacheOptimizer(最大容量=256, 默认ttl=300)
