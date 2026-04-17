"""
用户画像特征提取器

从用户历史行为数据中提取结构化特征向量，用于ML排序模型输入。
包括：偏好特征、活跃度特征、价值特征、行为模式特征。
"""

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserProfileFeatures:
    """用户画像特征向量"""
    # 偏好特征
    preference_diversity: float = 0.0
    top_category_ratio: float = 0.0
    preference_entropy: float = 0.0

    # 活跃度特征
    total_interactions: int = 0
    active_days: int = 0
    interaction_velocity_7d: float = 0.0
    interaction_velocity_30d: float = 0.0
    session_count: int = 0
    avg_session_length: float = 0.0

    # 价值特征
    avg_interaction_weight: float = 0.0
    high_weight_ratio: float = 0.0
    completion_rate: float = 0.0
    share_ratio: float = 0.0

    # 行为模式特征
    avg_session_interval_hours: float = 0.0
    preferred_time_slot: int = 0
    preferred_day_of_week: int = 0
    recency_days: int = 9999
    first_interaction_days: int = 9999
    user_lifespan_days: int = 0

    # 分类偏好（动态维度，输出时展平）
    category_scores: Dict[str, float] = field(default_factory=dict)
    content_type_scores: Dict[str, float] = field(default_factory=dict)
    tag_scores: Dict[str, float] = field(default_factory=dict)

    def to_vector(self) -> List[float]:
        """转换为固定维度向量（39维）"""
        top5_cats = sorted(self.category_scores.values(), reverse=True)[:5]
        while len(top5_cats) < 5:
            top5_cats.append(0.0)

        ct_types = ["video", "article", "audio", "course", "series"]
        ct_vals = [self.content_type_scores.get(t, 0.0) for t in ct_types]

        return [
            self.preference_diversity,
            self.top_category_ratio,
            self.preference_entropy,
            float(self.total_interactions),
            float(self.active_days),
            self.interaction_velocity_7d,
            self.interaction_velocity_30d,
            float(self.session_count),
            self.avg_session_length,
            self.avg_interaction_weight,
            self.high_weight_ratio,
            self.completion_rate,
            self.share_ratio,
            self.avg_session_interval_hours,
            float(self.preferred_time_slot) / 24.0,
            float(self.preferred_day_of_week) / 7.0,
            min(float(self.recency_days) / 30.0, 3.0),
            min(float(self.first_interaction_days) / 365.0, 5.0),
            min(float(self.user_lifespan_days) / 30.0, 5.0),
        ] + top5_cats + ct_vals

    @property
    def dimension(self) -> int:
        return 39


class UserProfileFeatureExtractor:
    """用户画像特征提取器"""

    INTERACTION_WEIGHTS = {
        "view": 1.0, "click": 2.0, "like": 4.0,
        "favorite": 5.0, "share": 6.0, "comment": 5.0,
        "follow": 3.0, "subscribe": 7.0, "download": 4.0,
        "complete": 8.0, "rating": 6.0,
    }

    def __init__(self, high_weight_threshold: float = 4.0):
        self.high_weight_threshold = high_weight_threshold

    def extract(
        self,
        user_interactions: Dict[str, List[dict]],
        now: Optional[datetime] = None,
    ) -> Dict[str, UserProfileFeatures]:
        """从用户交互数据中提取所有用户画像特征"""
        now = now or datetime.now()
        results: Dict[str, UserProfileFeatures] = {}

        for user_id, interactions in user_interactions.items():
            try:
                results[user_id] = self.extract_single(user_id, interactions, now)
            except Exception as e:
                logger.warning(f"[UserProfile] 提取用户 {user_id} 特征失败: {e}")
                results[user_id] = UserProfileFeatures()

        logger.info(f"[UserProfile] 特征提取完成: {len(results)} 用户")
        return results

    def extract_single(
        self,
        user_id: str,
        interactions: List[dict],
        now: Optional[datetime] = None,
    ) -> UserProfileFeatures:
        """提取单个用户的画像特征"""
        now = now or datetime.now()
        features = UserProfileFeatures()

        if not interactions:
            return features

        sorted_ints = sorted(interactions, key=lambda x: x.get("timestamp", now) or now)
        n = len(sorted_ints)

        total_weight = 0.0
        high_weight_count = 0
        complete_count = 0
        share_count = 0

        category_weights: Dict[str, float] = defaultdict(float)
        content_type_weights: Dict[str, float] = defaultdict(float)
        tag_weights: Dict[str, float] = defaultdict(float)
        timestamps: List[datetime] = []
        time_slots: List[int] = []
        day_of_weeks: List[int] = []

        for inter in sorted_ints:
            w = inter.get("weight") or self.INTERACTION_WEIGHTS.get(
                inter.get("type", "view"), 1.0
            )
            ts = inter.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = now
            if ts is None:
                ts = now
            timestamps.append(ts)

            total_weight += w
            if w >= self.high_weight_threshold:
                high_weight_count += 1
            if inter.get("type") == "complete":
                complete_count += 1
            if inter.get("type") == "share":
                share_count += 1

            meta = inter.get("metadata", {})
            cat = meta.get("category") or inter.get("category")
            if cat:
                category_weights[cat] += w

            ct = meta.get("content_type") or inter.get("content_type")
            if ct:
                content_type_weights[ct] += w

            tags = meta.get("tags") or inter.get("tags", [])
            for tag in (tags if isinstance(tags, list) else []):
                tag_weights[str(tag)] += w

            time_slots.append(ts.hour)
            day_of_weeks.append(ts.weekday())

        # 基础统计
        features.total_interactions = n
        features.avg_interaction_weight = total_weight / n
        features.high_weight_ratio = high_weight_count / n
        features.completion_rate = complete_count / n
        features.share_ratio = share_count / n

        # 偏好特征
        features.category_scores = dict(category_weights)
        features.content_type_scores = dict(content_type_weights)
        features.tag_scores = dict(tag_weights)

        total_cat_w = sum(category_weights.values()) or 1.0
        cat_probs = [w / total_cat_w for w in category_weights.values()]
        features.preference_entropy = -sum(
            p * math.log(max(p, 1e-10)) for p in cat_probs
        )
        features.preference_diversity = len(category_weights) / n
        features.top_category_ratio = max(cat_probs) if cat_probs else 0.0

        # 时间特征
        if timestamps:
            features.recency_days = (now - timestamps[-1]).days
            features.first_interaction_days = (now - timestamps[0]).days
            features.user_lifespan_days = max(1, (timestamps[-1] - timestamps[0]).days)

            slot_counts: Dict[int, int] = defaultdict(int)
            for s in time_slots:
                slot_counts[s] += 1
            features.preferred_time_slot = max(slot_counts, key=slot_counts.get) if slot_counts else 0

            dow_counts: Dict[int, int] = defaultdict(int)
            for d in day_of_weeks:
                dow_counts[d] += 1
            features.preferred_day_of_week = max(dow_counts, key=dow_counts.get) if dow_counts else 0

        # 活跃度
        active_day_set = {ts.date() for ts in timestamps}
        features.active_days = len(active_day_set)
        features.interaction_velocity_7d = sum(
            1 for ts in timestamps if (now - ts).days <= 7
        ) / 7.0
        features.interaction_velocity_30d = sum(
            1 for ts in timestamps if (now - ts).days <= 30
        ) / 30.0

        # 会话检测
        sessions = self._detect_sessions(timestamps)
        features.session_count = len(sessions)
        if sessions:
            lengths = [len(s) for s in sessions]
            features.avg_session_length = sum(lengths) / len(lengths)
            intervals = []
            for i in range(1, len(sessions)):
                gap = (sessions[i][0] - sessions[i - 1][-1]).total_seconds() / 3600
                intervals.append(gap)
            if intervals:
                features.avg_session_interval_hours = sum(intervals) / len(intervals)

        return features

    def _detect_sessions(
        self,
        timestamps: List[datetime],
        gap_hours: float = 2.0,
    ) -> List[List[datetime]]:
        """检测会话边界（间隔超过gap_hours则新会话）"""
        if not timestamps:
            return []
        sessions: List[List[datetime]] = [[]]
        for ts in sorted(timestamps):
            if sessions[-1] and (ts - sessions[-1][-1]).total_seconds() > gap_hours * 3600:
                sessions.append([])
            sessions[-1].append(ts)
        return sessions
