"""
推荐结果缓存服务

多级缓存策略：
- L1: 内存缓存（进程内，毫秒级响应）
- L2: Redis缓存（跨实例共享，支持TTL）
- L3: 数据库持久化（推荐历史可追溯）

同时提供冷启动推荐数据管理。
"""

import json
import hashlib
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# 默认缓存TTL配置（秒）
CACHE_TTL = {
    "home_feed": 300,            # 首页推荐: 5分钟
    "detail_related": 3600,      # 详情相关: 1小时
    "discovery": 600,            # 发现页: 10分钟
    "trending": 120,             # 热榜: 2分钟
    "user_personalized": 180,    # 个人化推荐: 3分钟
    "cold_start": 900,           # 冷启动: 15分钟
    "default": 600,              # 默认: 10分钟
}


class RecommendationCache:
    """推荐结果多级缓存"""
    
    def __init__(self, redis_client=None, enable_l1=True, enable_l2=True):
        self.redis = redis_client
        self.enable_l1 = enable_l1
        self.enable_l2 = enable_l2
        
        # L1内存缓存
        self._l1_cache: Dict[str, dict] = {}
        self._l1_timestamps: Dict[str, float] = {}
        
        # 统计
        self._hits = {"l1": 0, "l2": 0, "miss": 0}
        self._max_l1_size = 10000

    @staticmethod
    def _cache_key(user_id: Optional[str], scene: str,
                   extra: Optional[dict] = None) -> str:
        """生成缓存键"""
        parts = [f"rec:{scene}"]
        if user_id:
            parts.append(f"u:{user_id}")
        if extra:
            extra_str = json.dumps(extra, sort_keys=True)
            hash_hex = hashlib.md5(extra_str.encode()).hexdigest()[:12]
            parts.append(hash_hex)
        return ":".join(parts)

    async def get(self, user_id: Optional[str], scene: str,
                  extra: Optional[dict] = None) -> Optional[List[dict]]:
        """获取缓存的推荐结果"""
        key = self._cache_key(user_id, scene, extra)
        
        # L1: 内存缓存
        if self.enable_l1 and key in self._l1_cache:
            ts = self._l1_timestamps.get(key, 0)
            ttl = CACHE_TTL.get(scene, CACHE_TTL["default"])
            
            if (time.time() - ts) < ttl:
                self._hits["l1"] += 1
                logger.debug(f"[RecCache] L1命中: {key}")
                return self._l1_cache[key]
            else:
                del self._l1_cache[key]
                self._l1_timestamps.pop(key, None)
        
        # L2: Redis缓存
        if self.enable_l2 and self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    data = json.loads(cached)
                    self._hits["l2"] += 1
                    
                    # 回填L1
                    if self.enable_l1:
                        self._set_l1(key, data)
                    
                    logger.debug(f"[RecCache] L2命中: {key}")
                    return data
            except Exception as e:
                logger.warning(f"[RecCache] L2查询失败: {e}")
        
        self._hits["miss"] += 1
        return None

    async def set(self, user_id: Optional[str], scene: str,
                  results: List[dict], extra: Optional[dict] = None,
                  ttl_override: Optional[int] = None):
        """写入缓存"""
        key = self._cache_key(user_id, scene, extra)
        ttl = ttl_override or CACHE_TTL.get(scene, CACHE_TTL["default"])
        
        # L1
        if self.enable_l1:
            self._set_l1(key, results)
        
        # L2
        if self.enable_l2 and self.redis:
            try:
                await self.redis.setex(
                    key, ttl,
                    json.dumps(results, ensure_ascii=False, default=str)
                )
            except Exception as e:
                logger.warning(f"[RecCache] L2写入失败: {e}")

    def _set_l1(self, key: str, data: list):
        """写入L1缓存（LRU简化版）"""
        if len(self._l1_cache) >= self._max_l1_size:
            # 淘汰最旧的条目
            oldest_key = min(self._l1_timestamps, 
                            key=self._l1_timestamps.get)
            self._l1_cache.pop(oldest_key, None)
            self._l1_timestamps.pop(oldest_key, None)
        
        self._l1_cache[key] = data
        self._l1_timestamps[key] = time.time()

    async def invalidate(self, user_id: Optional[str] = None,
                         scene: Optional[str] = None):
        """使缓存失效"""
        patterns = []
        if user_id and scene:
            patterns.append(self._cache_key(user_id, scene))
        elif scene:
            patterns.append(f"rec:{scene}:*")
        elif user_id:
            patterns.append(f"rec:*:u:{user_id}*")
        
        # 清除L1匹配的键
        keys_to_remove = []
        for k in list(self._l1_cache.keys()):
            for p in patterns:
                if k.startswith(p.replace("*", "")):
                    keys_to_remove.append(k)
                    break
        
        for k in keys_to_remove:
            self._l1_cache.pop(k, None)
            self._l1_timestamps.pop(k, None)
        
        # 清除L2
        if self.redis:
            try:
                for pattern in patterns:
                    cursor = 0
                    while True:
                        cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                        if keys:
                            await self.redis.delete(*keys)
                        if cursor == 0:
                            break
            except Exception as e:
                logger.warning(f"[RecCache] 失效操作失败: {e}")
        
        logger.info(f"[RecCache] 已失效 {len(keys_to_remove)} 个L1缓存")

    async def invalidate_item(self, item_id: str):
        """当物品内容变化时，使相关缓存失效（保守策略）"""
        # 物品级别精确失效较复杂，这里使用场景级别的批量失效
        # 实际生产环境可以用事件驱动+发布订阅实现精准失效
        for scene in ["detail_related", "discovery", "home_feed"]:
            await self.invalidate(scene=scene)

    @property
    def stats(self) -> dict:
        total = sum(self._hits.values()) + self._hits["miss"]
        return {
            "service": "RecommendationCache",
            "l1_size": len(self._l1_cache),
            "hits": dict(self._hits),
            "hit_rate": (sum(self._hits.values()) / total * 100) if total > 0 else 0,
            "max_l1_size": self._max_l1_size,
        }


# ============================================================
# 冷启动推荐数据
# ============================================================

COLD_START_RECOMMENDATIONS = {
    "global_hot": [
        {
            "item_id": f"cold_global_{i}",
            "title": f"热门推荐内容 #{i+1}",
            "category": ["technology", "entertainment", "education", "business", 
                        "lifestyle", "news"][i % 6],
            "content_type": ["video", "article", "audio", "course"][i % 4],
            "tags": ["热门", "精选", "推荐"],
            "reason": "popular",
            "score": 0.95 - (i * 0.05),
        }
        for i in range(20)
    ],
    "new_user_welcome": [
        {
            "item_id": f"cold_new_{i}",
            "title": f"新人必看 #{i+1}",
            "category": "technology",
            "content_type": "video",
            "tags": ["新人", "入门", "教程"],
            "reason": "cold_start",
            "score": 0.9 - (i * 0.04),
        }
        for i in range(15)
    ],
    "category_defaults": {
        "technology": [
            {"item_id": "cold_tech_1", "title": "AI技术趋势2026", "category": "technology"},
            {"item_id": "cold_tech_2", "title": "Python高级编程技巧", "category": "technology"},
            {"item_id": "cold_tech_3", "title": "云原生架构实践", "category": "technology"},
            {"item_id": "cold_tech_4", "title": "大模型应用开发指南", "category": "technology"},
            {"item_id": "cold_tech_5", "title": "数据工程最佳实践", "category": "technology"},
        ],
        "entertainment": [
            {"item_id": "cold_ent_1", "title": "本周热映电影推荐", "category": "entertainment"},
            {"item_id": "cold_ent_2", "title": "音乐新歌速递", "category": "entertainment"},
            {"item_id": "cold_ent_3", "title": "游戏攻略合集", "category": "entertainment"},
            {"item_id": "cold_ent_4", "title": "综艺精彩片段", "category": "entertainment"},
            {"item_id": "cold_ent_5", "title": "热门短剧推荐", "category": "entertainment"},
        ],
        "education": [
            {"item_id": "cold_edu_1", "title": "高效学习方法论", "category": "education"},
            {"item_id": "cold_edu_2", "title": "英语口语突破训练", "category": "education"},
            {"item_id": "cold_edu_3", "title": "数学思维培养", "category": "education"},
            {"item_id": "cold_edu_4", "title": "编程启蒙课", "category": "education"},
            {"item_id": "cold_edu_5", "title": "职场技能提升", "category": "education"},
        ],
    },
}
