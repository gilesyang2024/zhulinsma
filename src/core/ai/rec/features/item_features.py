"""
物品统计特征提取器

从物品元数据和交互数据中提取统计特征，用于ML排序模型。
包括：热度特征、质量特征、新鲜度特征、分类特征。
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ItemFeatures:
    """物品特征向量（16维）"""
    view_count_norm: float = 0.0
    like_count_norm: float = 0.0
    share_count_norm: float = 0.0
    interaction_count_norm: float = 0.0
    click_through_rate: float = 0.0
    quality_score: float = 0.0
    completion_rate: float = 0.0
    engagement_rate: float = 0.0
    like_ratio: float = 0.0
    share_ratio: float = 0.0
    published_hours_ago: float = 0.0
    freshness_score: float = 1.0
    trending_score: float = 0.0
    category_id: int = 0
    sub_category_id: int = 0
    author_popularity: float = 0.0

    def to_vector(self) -> List[float]:
        return [
            self.view_count_norm,
            self.like_count_norm,
            self.share_count_norm,
            self.interaction_count_norm,
            self.click_through_rate,
            self.quality_score,
            self.completion_rate,
            self.engagement_rate,
            self.like_ratio,
            self.share_ratio,
            min(self.published_hours_ago / 8760.0, 1.0),  # 年小时归一化
            self.freshness_score,
            self.trending_score,
            min(float(self.category_id) / 20.0, 1.0),
            min(float(self.sub_category_id) / 100.0, 1.0),
            self.author_popularity,
        ]

    @property
    def dimension(self) -> int:
        return 16


class ItemFeatureExtractor:
    """物品统计特征提取器"""

    CATEGORY_MAP = {
        "technology": 1, "ai": 2, "programming": 3, "data_science": 4,
        "entertainment": 5, "movie": 6, "music": 7, "gaming": 8,
        "education": 9, "language": 10, "science": 11, "business": 12,
        "finance": 13, "marketing": 14, "lifestyle": 15, "food": 16,
        "travel": 17, "health": 18, "news": 19, "other": 20,
    }

    CONTENT_TYPE_MAP = {
        "video": 1, "article": 2, "audio": 3, "course": 4,
        "series": 5, "live": 6, "image": 7,
    }

    def __init__(self, freshness_half_life_hours: float = 168.0):
        self.freshness_half_life = freshness_half_life_hours

    def extract_all(
        self,
        items: List[dict],
        item_interactions: Dict[str, List[dict]],
        now: Optional[datetime] = None,
    ) -> Dict[str, ItemFeatures]:
        """从物品列表和交互数据中提取所有物品特征"""
        now = now or datetime.now()
        global_stats = self._compute_global_stats(item_interactions)
        results: Dict[str, ItemFeatures] = {}

        for item in items:
            iid = item.get("item_id")
            if not iid:
                continue
            interactions = item_interactions.get(iid, [])
            results[iid] = self.extract_single(item, interactions, global_stats, now)

        logger.info(f"[ItemFeatures] 特征提取完成: {len(results)} 物品")
        return results

    def extract_single(
        self,
        item: dict,
        interactions: List[dict],
        global_stats: Optional[dict] = None,
        now: Optional[datetime] = None,
    ) -> ItemFeatures:
        now = now or datetime.now()
        features = ItemFeatures()

        meta = item.get("metadata", {})
        features.quality_score = item.get("quality_score") or meta.get("quality_score", 0.5)
        cat = item.get("category") or meta.get("category", "other")
        features.category_id = self.CATEGORY_MAP.get(cat.lower(), 20)
        sub_cat = item.get("sub_category") or meta.get("sub_category", "")
        features.sub_category_id = hash(sub_cat) % 100
        ct = item.get("content_type") or meta.get("content_type", "video")
        features.author_popularity = min(
            item.get("author_popularity") or meta.get("author_popularity", 0.0), 1.0
        )

        view_count = 0
        like_count = 0
        share_count = 0
        complete_count = 0
        total_interactions = len(interactions)

        for inter in interactions:
            t = inter.get("type", "view")
            if t in ("view", "click"):
                view_count += 1
            if t == "like":
                like_count += 1
            if t == "share":
                share_count += 1
            if t == "complete":
                complete_count += 1

        gs = global_stats or {}
        max_views = gs.get("max_views", 1)
        max_likes = gs.get("max_likes", 1)
        max_shares = gs.get("max_shares", 1)
        max_interactions = gs.get("max_interactions", 1)

        features.view_count_norm = min(view_count / max_views, 1.0)
        features.like_count_norm = min(like_count / max_likes, 1.0)
        features.share_count_norm = min(share_count / max_shares, 1.0)
        features.interaction_count_norm = min(total_interactions / max_interactions, 1.0)
        features.click_through_rate = like_count / view_count if view_count > 0 else 0.0
        features.like_ratio = like_count / view_count if view_count > 0 else 0.0
        features.share_ratio = share_count / view_count if view_count > 0 else 0.0
        features.completion_rate = complete_count / total_interactions if total_interactions > 0 else 0.0
        features.engagement_rate = (like_count + share_count) / total_interactions if total_interactions > 0 else 0.0

        # 新鲜度
        published_at = item.get("published_at") or meta.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                published_at = now
        if published_at is None:
            published_at = now

        hours_ago = (now - published_at).total_seconds() / 3600
        features.published_hours_ago = hours_ago
        features.freshness_score = math.pow(0.5, hours_ago / self.freshness_half_life)

        # 趋势分
        recent_count = 0
        prev_count = 0
        cutoff_24h = now.timestamp() - 86400
        cutoff_48h = now.timestamp() - 172800
        for inter in interactions:
            ts = inter.get("timestamp")
            if isinstance(ts, datetime):
                ts = ts.timestamp()
            if ts and ts >= cutoff_24h:
                recent_count += 1
            elif ts and cutoff_48h <= ts < cutoff_24h:
                prev_count += 1

        features.trending_score = recent_count / max(prev_count, 1) if prev_count > 0 else 0.0

        return features

    def _compute_global_stats(self, item_interactions: Dict[str, List[dict]]) -> dict:
        def percentile(data: List[float], p: float) -> float:
            if not data:
                return 1.0
            s = sorted(data)
            idx = int(len(s) * p)
            return s[min(idx, len(s) - 1)]

        view_counts = [sum(1 for i in v if i.get("type") in ("view", "click")) for v in item_interactions.values()]
        like_counts = [sum(1 for i in v if i.get("type") == "like") for v in item_interactions.values()]
        share_counts = [sum(1 for i in v if i.get("type") == "share") for v in item_interactions.values()]
        int_counts = [len(v) for v in item_interactions.values()]

        return {
            "max_views": percentile(view_counts, 0.95) or 1,
            "max_likes": percentile(like_counts, 0.95) or 1,
            "max_shares": percentile(share_counts, 0.95) or 1,
            "max_interactions": percentile(int_counts, 0.95) or 1,
        }
