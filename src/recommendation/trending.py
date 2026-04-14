"""
热门趋势与排行榜服务

实时/近实时热门内容排行，支持多维度的榜单管理。
包括：
- 时间窗口热度计算（小时榜/日榜/周榜/月榜）
- 时间衰减热度分数
- 多维度榜单（全局/分类/标签）
- 趋势检测（上升/下降/新上榜）
"""

import math
import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class TrendingWindow(str, Enum):
    """榜单时间窗口"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# 交互行为的热度权重
TRENDING_WEIGHTS = {
    "view": 0.5,           # 浏览 - 权重较低（被动行为）
    "click": 1.0,
    "like": 4.0,           # 点赞 - 强信号
    "favorite": 5.0,
    "share": 8.0,          # 分享 - 非常强的传播信号
    "comment": 5.0,
    "complete": 10.0,      # 完播 - 最强信号之一
}

# 时间衰减半衰期（小时）
DECAY_HALF_LIFE_HOURS = {
    TrendingWindow.HOURLY: 0.5,     # 小时榜: 30分钟半衰
    TrendingWindow.DAILY: 4.0,      # 日榜: 4小时半衰
    TrendingWindow.WEEKLY: 24.0,    # 周榜: 1天半衰
    TrendingWindow.MONTHLY: 72.0,   # 月榜: 3天半衰
}


class TrendingService:
    """热门趋势服务
    
    功能：
    1. 实时接收交互事件并更新热度分
    2. 支持多时间窗口的独立排名
    3. 支持按分类/标签维度的子榜单
    4. 趋势变化追踪（上升↓/上升↑/新入→/持平=）
    """
    
    def __init__(
        self,
        default_window: TrendingWindow = TrendingWindow.DAILY,
        top_n: int = 100,
        min_interactions: int = 3,
        enable_category_ranking: bool = True,
        smoothing_alpha: float = 0.3,     # EMA平滑因子
    ):
        self.default_window = default_window
        self.top_n = top_n
        self.min_interactions = min_interactions
        self.enable_category_ranking = enable_category_ranking
        self.smoothing_alpha = smoothing_alpha
        
        # 核心数据结构: window -> category -> {item_id: trending_data}
        self._scores: Dict[str, Dict[str, Dict[str, dict]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        
        # 上一次的快照（用于计算趋势）
        self._prev_snapshots: Dict[str, Dict[str, List[Tuple[str, float]]]] = {}
        
        # 物品元数据缓存
        self._item_meta: Dict[str, dict] = {}
        
        # 统计计数器
        self._event_count = 0
        self._last_update: Optional[datetime] = None

    # ----------------------------------------------------------
    # 数据录入
    # ----------------------------------------------------------

    def register_item(self, item_id: str, meta: dict = None):
        """注册物品元数据"""
        self._item_meta[item_id] = meta or {}

    def record_event(self, item_id: str, event_type: str = "view",
                     weight: Optional[float] = None,
                     timestamp: Optional[datetime] = None,
                     category: Optional[str] = None):
        """记录一条交互事件（更新所有窗口的热度）"""
        now = datetime.now()
        
        event_weight = weight or TRENDING_WEIGHTS.get(event_type, 1.0)
        meta = self._item_meta.get(item_id, {})
        item_category = category or meta.get("category")
        
        for window_name in TrendingWindow:
            half_life = DECAY_HALF_LIFE_HOURS.get(window_name, 4.0)
            
            # 全局榜
            self._update_score(window_name, "__global__", item_id, 
                               event_weight, half_life, now, timestamp)
            
            # 分类榜
            if item_category and self.enable_category_ranking:
                self._update_score(window_name, item_category.lower(), item_id,
                                   event_weight, half_life, now, timestamp)
        
        self._event_count += 1
        self._last_update = now

    def record_events_batch(self, events: List[dict]):
        """批量录入事件"""
        for ev in events:
            self.record_event(
                item_id=ev["item_id"],
                event_type=ev.get("event_type", "view"),
                weight=ev.get("weight"),
                timestamp=ev.get("timestamp"),
                category=ev.get("category"),
            )

    def _update_score(self, window: str, category: str, item_id: str,
                      weight: float, half_life_hours: float,
                      now: datetime, event_time: Optional[datetime]):
        """使用指数移动平均(EMA)更新热度分"""
        data = self._scores[window][category]
        
        if item_id not in data:
            data[item_id] = {
                "score": 0.0,
                "raw_score": 0.0,
                "event_count": 0,
                "first_seen": now,
                "last_updated": now,
                "events_breakdown": {},
            }
        
        entry = data[item_id]
        entry["raw_score"] += weight
        entry["event_count"] += 1
        entry["last_updated"] = now
        
        # 事件类型统计
        # events breakdown handled by caller conceptually
        entry["events_breakdown"][weight] = entry["events_breakdown"].get(weight, 0) + 1
        
        # EMA平滑
        entry["score"] = (
            self.smoothing_alpha * entry["raw_score"] +
            (1 - self.smoothing_alpha) * entry["score"]
        )

    # ----------------------------------------------------------
    # 榜单查询
    # ----------------------------------------------------------

    def get_trending(
        self,
        window: Optional[TrendingWindow] = None,
        category: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """
        获取热门榜单
        
        Returns:
            [{"item_id", "rank", "score", "trend", "score_delta", "metadata"}, ...]
        """
        w = window or self.default_window
        cat_key = (category or "__global__").lower()
        
        data = self._scores.get(w.value if isinstance(w, TrendingWindow) else w, {}).get(cat_key, {})
        
        if not data:
            return []
        
        # 按得分排序
        sorted_items = sorted(data.items(), key=lambda x: x[1]["score"], reverse=True)
        
        # 与上一次快照比较计算趋势
        prev_key = f"{w.value}_{cat_key}"
        prev_ranks = self._prev_snapshots.get(prev_key, {})
        prev_rank_map = {iid: rank for rank, (iid, _) in enumerate(prev_ranks)}
        
        results = []
        for rank_idx, (item_id, item_data) in enumerate(sorted_items[offset:offset+limit]):
            actual_rank = rank_idx + offset + 1
            prev_rank = prev_rank_map.get(item_id)
            
            trend, delta = self._calc_trend(prev_rank, actual_rank, item_data)
            
            meta = self._item_meta.get(item_id, {})
            
            results.append({
                "item_id": item_id,
                "rank": actual_rank,
                "score": round(item_data["score"], 4),
                "normalized_score": round(item_data["score"] / max(d["score"] 
                                              for _, d in sorted_items[:1]), 4),
                "trend": trend,
                "rank_change": (prev_rank or actual_rank) - actual_rank if prev_rank else None,
                "score_delta": round(delta, 4),
                "event_count": item_data["event_count"],
                "is_new": prev_rank is None,
                "metadata": {
                    "title": meta.get("title"),
                    "content_type": meta.get("content_type"),
                    "category": meta.get("category"),
                    "author_id": meta.get("author_id"),
                    "thumbnail_url": meta.get("thumbnail_url"),
                },
            })
        
        return results

    def get_hot_list(self, scene: str = "home_feed",
                     limit: int = 20) -> List[dict]:
        """获取场景化热榜（根据不同场景定制排序逻辑）"""
        if scene == "home_feed":
            # 首页：综合热度 + 新鲜度
            daily = self.get_trending(TrendingWindow.DAILY, limit=limit*2)
            hourly = self.get_trending(TrendingWindow.HOURLY, limit=limit//2)
            
            # 合并去重
            seen_ids = set()
            combined = []
            for item in hourly + daily:
                if item["item_id"] not in seen_ids:
                    seen_ids.add(item["item_id"])
                    combined.append(item)
                    if len(combined) >= limit:
                        break
            
            return combined
        
        elif scene == "discovery":
            # 发现页：周榜为主，兼顾长尾
            weekly = self.get_trending(TrendingWindow.WEEKLY, limit=limit)
            return weekly
        
        elif scene == "hot_list":
            # 热榜：纯日榜
            return self.get_trending(TrendingWindow.DAILY, limit=limit)
        
        else:
            return self.get_trending(limit=limit)

    def get_category_trending(self, category: str,
                              limit: int = 20) -> List[dict]:
        """获取分类热门榜单"""
        return self.get_trending(category=category, limit=limit)

    def snapshot_current_state(self):
        """保存当前状态快照（用于下次计算趋势变化）"""
        for w in TrendingWindow:
            for cat_key, data in self._scores.get(w.value, {}).items():
                key = f"{w.value}_{cat_key}"
                sorted_items = sorted(data.items(), key=lambda x: x[1]["score"], reverse=True)[:self.top_n]
                self._prev_snapshots[key] = [(iid, d["score"]) for iid, d in sorted_items]

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _calc_trend(self, prev_rank: Optional[int], curr_rank: int,
                   item_data: dict) -> Tuple[str, float]:
        """计算趋势状态"""
        if prev_rank is None:
            # 新上榜
            if item_data["score"] > 50:
                return "hot", item_data["score"]
            return "new", item_data["score"]
        
        rank_diff = prev_rank - curr_rank
        
        if rank_diff > 5:
            return "up", float(rank_diff)
        elif rank_diff < -5:
            return "down", float(abs(rank_diff))
        else:
            return "same", 0.0

    @property
    def stats(self) -> dict:
        """统计信息"""
        total_items = set()
        for win_data in self._scores.values():
            for cat_data in win_data.values():
                total_items.update(cat_data.keys())
        
        return {
            "service": "TrendingService",
            "default_window": self.default_window.value,
            "total_events_recorded": self._event_count,
            "unique_items_tracked": len(total_items),
            "categories_active": sum(len(v) for v in self._scores.values()),
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    def get_item_score(self, item_id: str,
                       window: TrendingWindow = None) -> Optional[float]:
        """查询单个物品的热度分"""
        w = (window or self.default_window).value
        global_data = self._scores.get(w, {}).get("__global__", {})
        item = global_data.get(item_id)
        return item["score"] if item else None

    def reset(self):
        """重置所有数据"""
        self._scores.clear()
        self._prev_snapshots.clear()
        self._event_count = 0
        logger.info("[TrendingService] 数据已重置")
