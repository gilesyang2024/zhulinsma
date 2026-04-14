"""
推荐排序与重排服务

负责多策略结果的融合排序、多样性调整、业务规则过滤等。
是推荐系统的最后一道工序，直接决定用户体验。
"""

import math
import random
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


# 业务规则配置
BUSINESS_RULES = {
    # 去重：同一作者在推荐列表中的最大占比
    "max_author_ratio": 0.3,
    # 同一分类的最大占比
    "max_category_ratio": 0.5,
    # 最小推荐间隔（同一物品再次出现的最小天数）
    "min_re_recommend_days": 1,
    # 低质量内容阈值
    "min_quality_threshold": 0.1,
    # 新内容加成天数
    "fresh_content_days": 3,
    # 新内容加成系数
    "fresh_boost_factor": 1.5,
}


class RankingService:
    """多策略融合排序引擎
    
    职责：
    1. 接收多个召回通道的候选结果
    2. 按权重融合各通道得分
    3. 应用业务规则过滤/重排
    4. 多样性优化（MMR、类别打散）
    5. 最终截断输出
    """
    
    def __init__(
        self,
        item_cf_weight: float = 0.35,
        user_cf_weight: float = 0.15,
        content_weight: float = 0.25,
        trending_weight: float = 0.15,
        random_weight: float = 0.10,      # 探索性流量（EE）
        diversity_lambda: float = 0.7,     # MMR多样性参数(0=纯相关, 1=纯多样)
        enable_exploration: bool = True,   # 是否开启探索-利用平衡
        temperature: float = 0.3,          # Softmax温度（越高越随机）
    ):
        self.item_cf_weight = item_cf_weight
        self.user_cf_weight = user_cf_weight
        self.content_weight = content_weight
        self.trending_weight = trending_weight
        self.random_weight = random_weight
        self.diversity_lambda = diversity_lambda
        self.enable_exploration = enable_exploration
        self.temperature = temperature
        
        # 用户最近看到的物品（用于去重）
        self._user_recent_seen: Dict[str, Set[str]] = {}
        
        # 物品特征缓存（用于打散计算）
        self._item_features_cache: Dict[str, dict] = {}

    def register_item_features(self, items: Dict[str, dict]):
        """注册物品特征用于排序"""
        self._item_features_cache.update(items)

    def record_impression(self, user_id: str, item_ids: List[str]):
        """记录用户曝光（用于去重）"""
        if user_id not in self._user_recent_seen:
            self._user_recent_seen[user_id] = set()
        self._user_recent_seen[user_id].update(item_ids)

    def rank(
        self,
        candidates: Dict[str, List[Tuple[str, float, str]]],
        user_id: Optional[str] = None,
        n: int = 20,
        context: Optional[dict] = None,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        """
        多策略融合排序
        
        Args:
            candidates: 各召回通道结果 {"item_cf": [(id, score, reason), ...], ...}
            user_id: 目标用户
            n: 最终返回数量
            context: 上下文信息（时间、设备、场景等）
            filters: 过滤条件
            
        Returns:
            [{"item_id", "score", "reasons", "rank", "metadata"}, ...]
        """
        if not candidates:
            return []
        
        # Step 1: 合并 + 加权融合
        fused = self._fuse_scores(candidates)
        
        # Step 2: 业务规则过滤
        filtered = self._apply_business_rules(fused, user_id, filters)
        
        # Step 3: 探索-利用 (Epsilon-Greedy / Thompson Sampling 简化版)
        if self.enable_exploration and filtered:
            filtered = self._apply_exploration(filtered, user_id)
        
        # Step 4: MMR多样性重排
        reranked = self._mmr_rerank(filtered, n)
        
        # Step 5: 构建最终结果
        results = []
        for rank, (item_id, score, reasons) in enumerate(reranked):
            features = self._item_features_cache.get(item_id, {})
            results.append({
                "item_id": item_id,
                "score": round(score, 6),
                "final_score": round(score * (1 - rank * 0.01), 6),  # 位置衰减
                "reasons": reasons,
                "rank": rank + 1,
                "metadata": {
                    "content_type": features.get("content_type"),
                    "category": features.get("category"),
                    "author_id": features.get("author_id"),
                    "quality_score": features.get("quality_score"),
                    "published_at": features.get("published_at"),
                },
            })
            
            # 记录曝光
            if user_id:
                self.record_impression(user_id, [item_id])
        
        return results

    def _fuse_scores(
        self, candidates: Dict[str, List[Tuple[str, float, str]]]
    ) -> List[Tuple[str, float, List[str]]]:
        """加权融合多通道得分
        
        策略：
        - 各通道得分归一化到 [0, 1]
        - 按权重线性加权
        - 记录来源原因
        """
        channel_weights = {
            "item_cf": self.item_cf_weight,
            "collaborative_item": self.item_cf_weight,
            "user_cf": self.user_cf_weight,
            "collaborative_user": self.user_cf_weight,
            "content_based": self.content_weight,
            "tag_match": self.content_weight,
            "content_similarity": self.content_weight,
            "user_preference": self.content_weight,
            "trending": self.trending_weight,
            "popular": self.trending_weight,
            "new_release": self.trending_weight * 0.5,
            "cold_start": self.content_weight * 0.8,
            "random": self.random_weight,
        }
        
        # 归一化各通道得分
        normalized: Dict[str, Dict[str, Tuple[float, str]]] = {}
        for channel, items in candidates.items():
            if not items:
                continue
            
            scores = [s for _, s, _ in items]
            max_s = max(scores) if scores else 1
            min_s = min(scores) if scores else 0
            range_s = max_s - min_s or 1
            
            normed = {}
            for item_id, score, reason in items:
                ns = (score - min_s) / range_s
                normed[item_id] = (ns, reason)
            
            normalized[channel] = normed
        
        # 加权融合
        fused_scores: Dict[str, Tuple[float, List[str]]] = defaultdict(lambda: (0.0, []))
        
        for channel, normed_items in normalized.items():
            weight = channel_weights.get(channel, 0.1)
            
            for item_id, (norm_score, reason) in normed_items.items():
                current_total, current_reasons = fused_scores[item_id]
                fused_scores[item_id] = (
                    current_total + norm_score * weight,
                    current_reasons + [reason] if reason not in current_reasons else current_reasons,
                )
        
        result = [
            (item_id, total, reasons) 
            for item_id, (total, reasons) in fused_scores.items()
        ]
        
        # 按总分降序
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def _apply_business_rules(
        self,
        fused: List[Tuple[str, float, List[str]]],
        user_id: Optional[str],
        filters: Optional[dict],
    ) -> List[Tuple[str, float, List[str]]]:
        """应用业务规则过滤"""
        result = []
        
        for item_id, score, reasons in fused:
            features = self._item_features_cache.get(item_id, {})
            
            # 规则1: 最低质量门槛
            quality = features.get("quality_score", 0)
            if quality < BUSINESS_RULES["min_quality_threshold"]:
                continue
            
            # 规则2: 用户已看过去重
            seen = self._user_recent_seen.get(user_id, set())
            if item_id in seen:
                continue
            
            # 自定义过滤器
            skip = False
            if filters:
                # 内容类型过滤
                if filters.get("content_type") and features.get("content_type") != filters["content_type"]:
                    skip = True
                # 分类过滤
                if filters.get("category") and features.get("category") not in [filters["category"], None]:
                    # 允许子分类通过
                    sub_ok = False
                    for sub in CATEGORY_HIERARCHY.get(filters["category"], []):
                        if features.get("sub_category") == sub:
                            sub_ok = True
                            break
                    if features.get("category") != filters["category"] and not sub_ok:
                        skip = True
                # 作者过滤
                if filters.get("exclude_authors") and features.get("author_id") in filters["exclude_authors"]:
                    skip = True
            
            if skip:
                continue
            
            # 新内容加成
            published_at = features.get("published_at")
            if published_at and isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    published_at = None
            
            if published_at and isinstance(published_at, datetime):
                
                days_since_publish = (datetime.now() - published_at).days
                if days_since_publish <= BUSINESS_RULES["fresh_content_days"]:
                    boost = BUSINESS_RULES["fresh_boost_factor"] * (
                        1 - days_since_publish / BUSINESS_RULES["fresh_content_days"]
                    )
                    score *= (1 + boost * 0.3)
                    reasons.append("new_release")
            
            result.append((item_id, score, list(set(reasons))))
        
        return result

    def _apply_exploration(
        self,
        items: List[Tuple[str, float, List[str]]],
        user_id: Optional[str],
    ) -> List[Tuple[str, float, List[str]]]:
        """探索-利用平衡 (Boltzmann分布 / Softmax)
        
        给低排名候选一定概率被选中，避免信息茧房。
        """
        if len(items) <= n if 'n' in dir() else True:
            return items
        
        scores = np.array([s for _, s, _ in items]) if 'np' in dir() else [s for _, s, _ in items]
        # 手动Softmax
        exp_scores = []
        for s in scores:
            try:
                exp_scores.append(math.exp(s / self.temperature))
            except OverflowError:
                exp_scores.append(float('inf'))
        
        total_exp = sum(exp_scores)
        if total_exp == 0:
            return items
        
        probs = [e / total_exp for e in exp_scores]
        
        # 以概率重新排列（不完全打乱，保持大致顺序但加入扰动）
        result = list(items)
        for i in range(len(result)):
            if random.random() < 0.2:  # 20%概率交换
                j = self._weighted_random_sample(probs)
                if i != j:
                    result[i], result[j] = result[j], result[i]
        
        return result

    def _weighted_random_sample(self, probs: List[float]) -> int:
        """加权随机采样"""
        r = random.random()
        cumulative = 0.0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                return i
        return len(probs) - 1

    def _mmr_rerank(
        self,
        items: List[Tuple[str, float, List[str]]],
        n: int,
    ) -> List[Tuple[str, float, List[str]]]:
        """Maximal Marginal Relevance 多样性重排
        
        公式: MMR = λ * Rel(i) - (1-λ) * max(Sim(i, j)), j∈Selected
        
        在相关性和多样性之间取得平衡。
        """
        if len(items) <= n:
            return items
        
        selected = []
        remaining = list(items)
        
        while len(selected) < n and remaining:
            best_score = -float('inf')
            best_idx = 0
            best_item = None
            
            for idx, (item_id, relevance, reasons) in enumerate(remaining):
                # 相关性部分
                rel_part = relevance
                
                # 最大相似度惩罚（与已选物品最相似的）
                if selected:
                    max_sim = self._max_similarity_to_selected(item_id, selected)
                else:
                    max_sim = 0.0
                
                # MMR公式
                mmr_score = self.diversity_lambda * rel_part - (1 - self.diversity_lambda) * max_sim
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
                    best_item = (item_id, relevance, reasons)
            
            if best_item:
                selected.append(best_item)
                remaining.pop(best_idx)
            else:
                break
        
        return selected

    def _max_similarity_to_selected(self, item_id: str, selected: List) -> float:
        """计算物品与已选集合中最大相似度（基于分类和标签）"""
        feat_a = self._item_features_cache.get(item_id, {})
        cat_a = feat_a.get("category", "")
        tags_a = set(feat_a.get("tags") or [])
        
        max_sim = 0.0
        for sel_item in selected:
            sel_id = sel_item[0]
            feat_b = self._item_features_cache.get(sel_id, {})
            cat_b = feat_b.get("category", "")
            tags_b = set(feat_b.get("tags") or [])
            
            # 分类相同 → 高相似度
            if cat_a and cat_b and cat_a == cat_b:
                sim = 0.8
            elif tags_a & tags_b:
                overlap = len(tags_a & tags_b) / max(len(tags_a | tags_b), 1)
                sim = overlap * 0.6
            else:
                sim = 0.0
            
            max_sim = max(max_sim, sim)
        
        return max_sim


# 全局分类层级（RankingService引用用）
CATEGORY_HIERARCHY = {
    "technology": ["ai", "programming", "data_science", "cybersecurity", "cloud"],
    "entertainment": ["movie", "music", "gaming", "variety_show"],
    "education": ["language", "science", "history", "skill_training"],
    "business": ["finance", "management", "marketing", "entrepreneurship"],
    "lifestyle": ["food", "travel", "health", "fashion"],
    "news": ["domestic", "international", "tech_news", "finance_news"],
}
