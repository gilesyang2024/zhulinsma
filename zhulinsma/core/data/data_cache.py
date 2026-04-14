#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 数据缓存模块
基于内存 LRU 缓存 + 磁盘持久化的两级缓存系统
"""

import os
import json
import time
import hashlib
import pickle
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional


class DataCache:
    """
    两级数据缓存系统

    L1: 内存 LRU 缓存（毫秒级访问，容量可配置）
    L2: 磁盘持久化缓存（秒级访问，跨进程共享）
    """

    def __init__(
        self,
        最大内存条目: int = 256,
        磁盘缓存目录: str = "/tmp/zhulinsma_cache",
        默认过期秒数: int = 3600,
    ):
        self.最大内存条目 = 最大内存条目
        self.磁盘缓存目录 = 磁盘缓存目录
        self.默认过期秒数 = 默认过期秒数
        self._内存缓存: OrderedDict = OrderedDict()
        self._锁 = threading.Lock()
        os.makedirs(磁盘缓存目录, exist_ok=True)

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """读取缓存（L1→L2 顺序）"""
        # L1
        with self._锁:
            if key in self._内存缓存:
                entry = self._内存缓存[key]
                if not self._已过期(entry):
                    self._内存缓存.move_to_end(key)
                    return entry["value"]
                else:
                    del self._内存缓存[key]

        # L2
        磁盘值 = self._磁盘读取(key)
        if 磁盘值 is not None:
            self._内存写入(key, 磁盘值["value"], 磁盘值["ttl"])
            return 磁盘值["value"]

        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        持久化: bool = False,
    ) -> None:
        """写入缓存"""
        有效ttl = ttl if ttl is not None else self.默认过期秒数
        self._内存写入(key, value, 有效ttl)
        if 持久化:
            self._磁盘写入(key, value, 有效ttl)

    def delete(self, key: str) -> None:
        """删除缓存"""
        with self._锁:
            self._内存缓存.pop(key, None)
        磁盘路径 = self._磁盘路径(key)
        if os.path.exists(磁盘路径):
            os.remove(磁盘路径)

    def clear(self) -> None:
        """清空所有缓存"""
        with self._锁:
            self._内存缓存.clear()
        for f in os.listdir(self.磁盘缓存目录):
            try:
                os.remove(os.path.join(self.磁盘缓存目录, f))
            except Exception:
                pass

    def 统计信息(self) -> Dict:
        with self._锁:
            有效条目 = sum(
                1 for e in self._内存缓存.values() if not self._已过期(e)
            )
        磁盘条目 = len(os.listdir(self.磁盘缓存目录))
        return {
            "内存条目总数": len(self._内存缓存),
            "内存有效条目": 有效条目,
            "磁盘条目": 磁盘条目,
            "最大容量": self.最大内存条目,
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _内存写入(self, key: str, value: Any, ttl: int) -> None:
        with self._锁:
            if key in self._内存缓存:
                self._内存缓存.move_to_end(key)
            self._内存缓存[key] = {
                "value": value,
                "expire_at": time.time() + ttl,
                "ttl": ttl,
            }
            if len(self._内存缓存) > self.最大内存条目:
                self._内存缓存.popitem(last=False)

    def _已过期(self, entry: Dict) -> bool:
        return time.time() > entry.get("expire_at", 0)

    def _磁盘路径(self, key: str) -> str:
        哈希 = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.磁盘缓存目录, f"{哈希}.pkl")

    def _磁盘写入(self, key: str, value: Any, ttl: int) -> None:
        try:
            entry = {"value": value, "expire_at": time.time() + ttl, "ttl": ttl}
            with open(self._磁盘路径(key), "wb") as f:
                pickle.dump(entry, f)
        except Exception:
            pass

    def _磁盘读取(self, key: str) -> Optional[Dict]:
        路径 = self._磁盘路径(key)
        if not os.path.exists(路径):
            return None
        try:
            with open(路径, "rb") as f:
                entry = pickle.load(f)
            if time.time() > entry.get("expire_at", 0):
                os.remove(路径)
                return None
            return entry
        except Exception:
            return None
