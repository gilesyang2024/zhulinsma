"""
上下文特征提取器 + 序列特征

上下文特征：时间、设备、场景等请求级特征。
序列特征：用户最近N个行为序列的模式特征（基于已看物品推断下一行为偏好）。
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================
# 上下文特征
# ============================================================

@dataclass
class ContextFeatures:
    """上下文特征向量（12维）"""
    hour_bucket: int = 0       # 时间段(0=凌晨,1=上午,2=下午,3=晚上)
    is_weekend: bool = False
    is_holiday: bool = False
    session_position: float = 0.0  # 会话内位置(0-1)
    exposure_rank: float = 0.0    # 候选在候选集中的相对排名(0-1)
    device_type_score: float = 0.0  # 0=PC, 0.5=平板, 1=移动
    content_type_preference: float = 0.0  # 用户近期偏好内容类型编码

    def to_vector(self) -> List[float]:
        return [
            float(self.hour_bucket) / 4.0,
            1.0 if self.is_weekend else 0.0,
            1.0 if self.is_holiday else 0.0,
            self.session_position,
            self.exposure_rank,
            self.device_type_score,
            self.content_type_preference,
        ] + [0.0] * 5  # padding to fixed

    @property
    def dimension(self) -> int:
        return 12


class ContextFeatureExtractor:
    """上下文特征提取"""

    HOLIDAYS = {
        "01-01", "05-01", "10-01",  # 元旦/劳动节/国庆
    }

    @staticmethod
    def extract(
        timestamp: Optional[datetime] = None,
        device_type: str = "mobile",
        session_position: float = 0.0,
        exposure_rank: int = 0,
        total_candidates: int = 100,
        content_type_preference: float = 0.5,
    ) -> ContextFeatures:
        """从请求上下文提取特征"""
        ts = timestamp or datetime.now()

        hour = ts.hour
        if 0 <= hour < 6:
            bucket = 0  # 凌晨
        elif 6 <= hour < 12:
            bucket = 1  # 上午
        elif 12 <= hour < 18:
            bucket = 2  # 下午
        else:
            bucket = 3  # 晚上

        month_day = f"{ts.month:02d}-{ts.day:02d}"
        is_holiday = month_day in ContextFeatureExtractor.HOLIDAYS

        device_score = {"pc": 0.0, "tablet": 0.5, "mobile": 1.0}.get(
            device_type.lower(), 1.0
        )

        return ContextFeatures(
            hour_bucket=bucket,
            is_weekend=ts.weekday() >= 5,
            is_holiday=is_holiday,
            session_position=session_position,
            exposure_rank=exposure_rank / max(total_candidates, 1),
            device_type_score=device_score,
            content_type_preference=content_type_preference,
        )


# ============================================================
# 序列特征（用户行为序列模式）
# ============================================================

@dataclass
class SequenceFeatures:
    """用户行为序列特征（20维）"""
    seq_length: int = 0
    seq_entropy: float = 0.0          # 序列熵（行为多样性）
    seq_avg_recency: float = 0.0      # 平均最近度
    last_item_quality: float = 0.0    # 最后一个物品质量
    last_item_popularity: float = 0.0 # 最后一个物品热度
    seq_trend: float = 0.0            # 序列趋势（从热到冷还是从冷到热）
    category_switch_count: float = 0.0  # 分类切换频率
    avg_item_quality: float = 0.0      # 平均物品质量
    seq_diversity: float = 0.0         # 序列多样性

    def to_vector(self) -> List[float]:
        return [
            min(float(self.seq_length) / 50.0, 1.0),
            self.seq_entropy,
            self.seq_avg_recency,
            self.last_item_quality,
            self.last_item_popularity,
            self.seq_trend,
            self.category_switch_count,
            self.avg_item_quality,
            self.seq_diversity,
        ] + [0.0] * 11  # padding

    @property
    def dimension(self) -> int:
        return 20


class SequenceFeatureExtractor:
    """用户行为序列特征提取

    从用户最近N个交互行为中提取模式特征。
    核心思想：用户近期行为模式预测下一行为的偏好。
    """

    DEFAULT_SEQUENCE_LENGTH = 20

    def __init__(self, max_sequence_length: int = 20):
        self.max_sequence_length = max_sequence_length

    def extract(
        self,
        user_history: List[dict],
        item_features: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> SequenceFeatures:
        """从用户历史交互中提取序列特征

        Args:
            user_history: 用户历史交互列表（按时间排序，早→晚）
            item_features: 物品特征字典（用于查询物品质量/热度）
            now: 参考时间
        """
        now = now or datetime.now()
        features = SequenceFeatures()

        if not user_history:
            return features

        # 取最近N条
        seq = user_history[-self.max_sequence_length:]
        features.seq_length = len(seq)

        # 质量序列
        qualities = []
        popularities = []
        categories = []
        now_ts = now.timestamp()

        for inter in seq:
            iid = inter.get("item_id")
            feat = (item_features or {}).get(iid, {})
            q = feat.get("quality_score", inter.get("quality_score", 0.5))
            qualities.append(q)
            popularities.append(feat.get("popularity_score", inter.get("popularity_score", 0.5)))

            meta = inter.get("metadata", {})
            cat = meta.get("category") or inter.get("category")
            if cat:
                categories.append(cat)

            # 时间权重
            ts = inter.get("timestamp")
            if isinstance(ts, datetime):
                ts = ts.timestamp()
            if ts:
                recency = 1.0 - min((now_ts - ts) / (7 * 86400), 1.0)
                features.seq_avg_recency += recency

        features.seq_avg_recency /= len(seq) if seq else 1

        # 序列熵
        if qualities:
            avg_q = sum(qualities) / len(qualities)
            variance = sum((q - avg_q) ** 2 for q in qualities) / len(qualities)
            features.seq_entropy = min(variance * 10, 1.0)

        # 最后物品特征
        if seq:
            last_feat = (item_features or {}).get(seq[-1].get("item_id"), {})
            features.last_item_quality = seq[-1].get("quality_score", last_feat.get("quality_score", 0.5))
            features.last_item_popularity = seq[-1].get("popularity_score", last_feat.get("popularity_score", 0.5))

        # 序列趋势（前1/3 vs 后1/3质量均值）
        if len(seq) >= 6:
            mid = len(seq) // 3
            first_third_avg = sum(q for q in qualities[:mid]) / mid
            last_third_avg = sum(q for q in qualities[-mid:]) / mid
            features.seq_trend = last_third_avg - first_third_avg

        # 分类切换
        if len(categories) >= 2:
            switches = sum(
                1 for i in range(1, len(categories))
                if categories[i] != categories[i - 1]
            )
            features.category_switch_count = switches / (len(categories) - 1)

        # 平均质量
        if qualities:
            features.avg_item_quality = sum(qualities) / len(qualities)

        # 序列多样性
        if categories:
            features.seq_diversity = len(set(categories)) / len(categories)

        return features

    def extract_interaction_feature(
        self,
        user_interaction: dict,
        item_id: str,
        position: int,
        item_features: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> List[float]:
        """为单个(user, item, position)组合生成交互特征

        这是ML模型的直接输入特征之一。
        """
        now = now or datetime.now()
        feat = (item_features or {}).get(item_id, {})

        ts = user_interaction.get("timestamp")
        if isinstance(ts, datetime):
            ts = ts.timestamp()
        recency = 0.0
        if ts:
            recency = 1.0 - min((now.timestamp() - ts) / (30 * 86400), 1.0)

        interaction_type_weight = {
            "view": 1.0, "click": 2.0, "like": 4.0,
            "favorite": 5.0, "share": 6.0, "complete": 8.0,
        }.get(user_interaction.get("type", "view"), 1.0)

        return [
            float(position) / 50.0,  # 位置衰减
            recency,
            interaction_type_weight / 8.0,
            feat.get("quality_score", 0.5),
            feat.get("popularity_score", 0.5),
            feat.get("freshness_score", 0.5),
            0.0,  # padding
        ]
