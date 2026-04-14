"""
Content-Based 推荐算法

基于内容的推荐引擎，利用物品自身的特征进行匹配推荐。
包括：
- 标签/分类匹配（精确匹配 + 层级扩展）
- 向量相似度（TF-IDF / Embedding）
- 多维度特征融合
- 冷启动友好（无需历史行为数据）
"""

import math
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


# 分类层级映射（可配置）
CATEGORY_HIERARCHY = {
    # 一级分类 → 二级分类列表（用于层级扩展匹配）
    "technology": ["ai", "programming", "data_science", "cybersecurity", "cloud"],
    "entertainment": ["movie", "music", "gaming", "variety_show"],
    "education": ["language", "science", "history", "skill_training"],
    "business": ["finance", "management", "marketing", "entrepreneurship"],
    "lifestyle": ["food", "travel", "health", "fashion"],
    "news": ["domestic", "international", "tech_news", "finance_news"],
}

# 内容类型之间的亲和性（跨类型推荐）
CONTENT_TYPE_AFFINITY = {
    ("video", "video"): 1.0,
    ("video", "series"): 0.9,
    ("video", "live"): 0.7,
    ("video", "course"): 0.8,
    ("article", "article"): 1.0,
    ("article", "course"): 0.7,
    ("audio", "audio"): 1.0,
    ("audio", "course"): 0.6,
    ("series", "video"): 0.9,
    ("course", "video"): 0.8,
}


class ContentBasedRecommender:
    """基于内容的推荐器
    
    特征体系：
    1. 结构化特征：分类、标签、作者、内容类型
    2. 文本特征：标题/正文 TF-IDF向量
    3. 语义特征：预训练Embedding向量（BERT等）
    4. 统计特征：质量分、完播率等
    """
    
    def __init__(
        self,
        tag_match_weight: float = 0.35,
        category_weight: float = 0.20,
        vector_sim_weight: float = 0.25,
        author_affinity_weight: float = 0.10,
        quality_boost_weight: float = 0.10,
        tag_expansion_depth: int = 1,       # 标签扩展深度（同义词/上下位词）
        min_vector_dim: int = 10,           # 最小向量维度要求
    ):
        self.tag_match_weight = tag_match_weight
        self.category_weight = category_weight
        self.vector_sim_weight = vector_sim_weight
        self.author_affinity_weight = author_affinity_weight
        self.quality_boost_weight = quality_boost_weight
        self.tag_expansion_depth = tag_expansion_depth
        self.min_vector_dim = min_vector_dim
        
        # 物品特征库
        self._items: Dict[str, dict] = {}          # item_id → 完整特征字典
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)   # tag → item_ids
        self._category_index: Dict[str, Set[str]] = defaultdict(set)  # category → item_ids
        self._author_index: Dict[str, Set[str]] = defaultdict(set)   # author_id → item_ids
        self._type_index: Dict[str, Set[str]] = defaultdict(set)     # content_type → item_ids
        
        # 用户画像缓存
        self._user_profiles: Dict[str, dict] = {}

    # ----------------------------------------------------------
    # 数据管理
    # ----------------------------------------------------------

    def add_item(self, item_id: str, features: dict):
        """注册一个物品的特征"""
        self._items[item_id] = features
        
        tags = features.get("tags") or []
        if isinstance(tags, list):
            for tag in tags:
                self._tag_index[tag.lower()].add(item_id)
        
        category = features.get("category")
        if category:
            self._category_index[category.lower()].add(item_id)
        
        sub_category = features.get("sub_category")
        if sub_category:
            self._category_index[sub_category.lower()].add(item_id)
        
        author_id = features.get("author_id")
        if author_id:
            self._author_index[author_id].add(item_id)
        
        content_type = features.get("content_type")
        if content_type:
            self._type_index[content_type].add(item_id)

    def add_items_batch(self, items_list: List[dict]):
        """批量注册物品"""
        for item in items_list:
            self.add_item(item["item_id"], item)

    def update_user_profile(self, user_id: str, profile: dict):
        """更新用户画像"""
        self._user_profiles[user_id] = profile

    @property
    def stats(self) -> dict:
        return {
            "algorithm": "ContentBased",
            "total_items": len(self._items),
            "total_tags": len(self._tag_index),
            "total_categories": len(self._category_index),
            "total_authors": len(self._author_index),
            "user_profiles_cached": len(self._user_profiles),
        }

    # ----------------------------------------------------------
    # 核心推荐逻辑
    # ----------------------------------------------------------

    def recommend(
        self,
        user_id: Optional[str] = None,
        reference_item_id: Optional[str] = None,
        reference_tags: Optional[List[str]] = None,
        reference_category: Optional[str] = None,
        n: int = 20,
        exclude_ids: Optional[Set[str]] = None,
        content_type_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Tuple[str, float, str]]:
        """生成内容推荐列表
        
        三种模式：
        1. 基于用户画像推荐 (user_id)
        2. 基于参考物品推荐 (reference_item_id)
        3. 基于标签/分类推荐 (reference_tags / reference_category)
        """
        if exclude_ids is None:
            exclude_ids = set()
        
        # 确定查询条件
        query_profile = self._build_query_profile(
            user_id=user_id,
            reference_item_id=reference_item_id,
            reference_tags=reference_tags,
            reference_category=reference_category,
        )
        
        if not query_profile:
            # 无条件时返回高质量热门内容
            return self._recommend_by_quality(n, exclude_ids, content_type_filter, category_filter)
        
        # 候选集筛选
        candidates = self._get_candidates(
            query_profile, exclude_ids, content_type_filter, category_filter
        )
        
        if not candidates:
            return []
        
        # 对每个候选打分
        scored_candidates = []
        for cand_id in candidates:
            cand_features = self._items.get(cand_id)
            if not cand_features:
                continue
            
            score, reason = self._score_candidate(query_profile, cand_features)
            scored_candidates.append((cand_id, score, reason))
        
        # 排序截断
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:n]

    def find_similar_items(
        self,
        item_id: str,
        n: int = 20,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[str, float, str]]:
        """查找与指定物品最相似的内容"""
        if exclude_ids is None:
            exclude_ids = set()
        exclude_ids.add(item_id)
        
        ref_item = self._items.get(item_id)
        if not ref_item:
            return []
        
        return self.recommend(
            reference_item_id=item_id,
            n=n,
            exclude_ids=exclude_ids,
            content_type_filter=ref_item.get("content_type"),
        )

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _build_query_profile(
        self,
        user_id: Optional[str],
        reference_item_id: Optional[str],
        reference_tags: Optional[List[str]],
        reference_category: Optional[str],
    ) -> Optional[dict]:
        """构建查询画像（统一三种输入模式）"""
        profile = {"tags": {}, "categories": [], "authors": [],
                    "embedding": None, "tfidf_vector": None, 
                    "preferred_types": []}
        
        # 模式1: 基于用户画像
        if user_id and user_id in self._user_profiles:
            up = self._user_profiles[user_id]
            profile["tags"] = up.get("preference_tags", {})
            profile["categories"] = up.get("preferred_categories", [])
            profile["embedding"] = up.get("interest_vector")
            profile["preferred_types"] = up.get("preferred_content_types", [])
            return profile
        
        # 模式2: 基于参考物品
        if reference_item_id and reference_item_id in self._items:
            ref = self._items[reference_item_id]
            tags = ref.get("tags") or []
            for t in tags:
                profile["tags"][t.lower()] = 1.0
            
            if ref.get("category"):
                profile["categories"].append(ref["category"].lower())
            if ref.get("sub_category"):
                profile["categories"].append(ref["sub_category"].lower())
            
            if ref.get("author_id"):
                profile["authors"].append(ref["author_id"])
            
            profile["embedding"] = ref.get("embedding")
            profile["tfidf_vector"] = ref.get("content_vector") or ref.get("title_vector")
            if ref.get("content_type"):
                profile["preferred_types"].append(ref["content_type"])
            
            return profile
        
        # 模式3: 基于标签/分类直接查询
        has_query = False
        if reference_tags:
            for t in reference_tags:
                profile["tags"][t.lower()] = 1.0
            has_query = True
        
        if reference_category:
            profile["categories"].append(reference_category.lower())
            has_query = True
        
        return profile if has_query else None

    def _get_candidates(
        self,
        query_profile: dict,
        exclude_ids: Set[str],
        type_filter: Optional[str],
        category_filter: Optional[str],
    ) -> Set[str]:
        """获取候选物品集合（多路召回）"""
        candidates: Set[str] = set()
        
        # 路径1: 标签召回
        query_tags = set(profile["tags"].keys() for profile in [query_profile])
        # flatten
        all_query_tags = set()
        for t_set in query_tags:
            all_query_tags.update(t_set)
        
        expanded_tags = self._expand_tags(all_query_tags)
        for tag in expanded_tags:
            candidates.update(self._tag_index.get(tag, set()))
        
        # 路径2: 分类召回
        for cat in query_profile.get("categories", []):
            candidates.update(self._category_index.get(cat, set()))
            # 扩展到子分类
            for sub_cat in CATEGORY_HIERARCHY.get(cat, []):
                candidates.update(self._category_index.get(sub_cat, set()))
        
        # 路径3: 作者召回
        for author_id in query_profile.get("authors", []):
            candidates.update(self._author_index.get(author_id, set()))
        
        # 过滤
        candidates -= exclude_ids
        
        if type_filter:
            candidates &= self._type_index.get(type_filter, set())
        
        if category_filter:
            cat_matches = self._category_index.get(category_filter, set())
            sub_cats = CATEGORY_HIERARCHY.get(category_filter, [])
            for sc in sub_cats:
                cat_matches |= self._category_index.get(sc, set())
            candidates &= cat_matches
        
        return candidates

    def _expand_tags(self, tags: Set[str]) -> Set[str]:
        """标签扩展（同义词、大小写变体）"""
        expanded = set(tags)
        for tag in tags:
            expanded.add(tag.lower())
            # 可扩展：同义词词典、wordnet等
        return expanded

    def _score_candidate(
        self,
        query_profile: dict,
        candidate: dict,
    ) -> Tuple[float, str]:
        """对候选物品打分（多维度加权融合）"""
        scores = []
        reasons = []
        
        # 1. 标签匹配得分 (0~1)
        tag_score = self._calc_tag_score(query_profile["tags"], candidate.get("tags") or [])
        scores.append(tag_score * self.tag_match_weight)
        if tag_score > 0.3:
            reasons.append("tag_match")
        
        # 2. 分类匹配得分
        cat_score = self._calc_category_score(
            query_profile["categories"], 
            candidate.get("category"),
            candidate.get("sub_category"),
        )
        scores.append(cat_score * self.category_weight)
        if cat_score > 0.5:
            reasons.append("category_match")
        
        # 3. 向量相似度 (0~1)
        vec_score = self._calc_vector_similarity(
            query_profile.get("embedding") or query_profile.get("tfidf_vector"),
            candidate.get("embedding") or candidate.get("content_vector"),
        )
        scores.append(vec_score * self.vector_sim_weight)
        if vec_score > 0.5:
            reasons.append("content_similarity")
        
        # 4. 作者亲和性 (0~1)
        author_score = self._calc_author_affinity(
            query_profile.get("authors", []),
            candidate.get("author_id"),
        )
        scores.append(author_score * self.author_affinity_weight)
        
        # 5. 质量加成 (0~1)
        quality = candidate.get("quality_score", 0)
        quality_norm = min(1.0, quality) if quality else 0
        scores.append(quality_norm * self.quality_boost_weight)
        
        total_score = sum(scores)
        primary_reason = reasons[0] if reasons else "content_similarity"
        
        return round(total_score, 6), primary_reason

    def _calc_tag_score(self, query_tags: Dict[str, float], item_tags: List[str]) -> float:
        """标签Jaccard + 加权匹配"""
        if not query_tags or not item_tags:
            return 0.0
        
        item_tags_lower = [t.lower() for t in item_tags]
        
        weighted_sum = 0.0
        match_count = 0
        
        for tag, weight in query_tags.items():
            if tag in item_tags_lower:
                weighted_sum += weight
                match_count += 1
        
        if not match_count:
            return 0.0
        
        # 加权Jaccard
        precision = match_count / len(item_tags_lower) if item_tags_lower else 0
        recall = match_count / len(query_tags) if query_tags else 0
        
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # 结合加权分数
        avg_weight = weighted_sum / match_count if match_count else 0
        
        return 0.6 * f1 + 0.4 * min(1.0, avg_weight)

    def _calc_category_score(self, query_categories: List[str],
                             item_category: Optional[str],
                             item_sub_category: Optional[str]) -> float:
        """分类层级匹配得分"""
        if not query_categories or not item_category:
            return 0.0
        
        item_cat = (item_category or "").lower()
        item_sub = (item_sub_category or "").lower()
        query_cats = {c.lower() for c in query_categories}
        
        if item_cat in query_cats:
            return 1.0  # 一级分类完全匹配
        
        if item_sub and item_sub in query_cats:
            return 0.85  # 二级分类匹配
        
        # 检查是否子分类属于查询的一级分类
        for qc in query_cats:
            if item_sub in CATEGORY_HIERARCHY.get(qc, []):
                return 0.7
            if item_cat in CATEGORY_HIERARCHY.get(qc, []):
                return 0.6
        
        return 0.0

    def _calc_vector_similarity(self, vec_a: Optional[list], vec_b: Optional[list]) -> float:
        """余弦向量相似度"""
        if not vec_a or not vec_b:
            return 0.0
        if len(vec_a) != len(vec_b) or len(vec_a) < self.min_vector_dim:
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        cos_sim = dot / (norm_a * norm_b)
        return max(0.0, cos_sim)

    def _calc_author_affinity(self, query_authors: List[str], item_author: Optional[str]) -> float:
        """作者亲和性（同一作者加分）"""
        if not query_authors or not item_author:
            return 0.0
        
        return 1.0 if item_author in query_authors else 0.0

    def _recommend_by_quality(
        self, n: int, exclude_ids: Set[str],
        type_filter: Optional[str], category_filter: Optional[str]
    ) -> List[Tuple[str, float, str]]:
        """无特定条件时的质量/热度兜底推荐"""
        scored = []
        
        for item_id, features in self._items.items():
            if item_id in exclude_ids:
                continue
            if type_filter and features.get("content_type") != type_filter:
                continue
            if category_filter:
                fc = (features.get("category") or "").lower()
                fsc = (features.get("sub_category") or "").lower()
                cf = category_filter.lower()
                if fc != cf and fsc != cf and cf not in CATEGORY_HIERARCHY.get(fc, []):
                    continue
            
            quality = features.get("quality_score", 0)
            popularity = features.get("popularity_score", 0)
            combined = quality * 0.6 + popularity * 0.4
            
            scored.append((item_id, round(combined, 6), "user_preference"))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def get_item_features(self, item_id: str) -> Optional[dict]:
        """获取物品完整特征"""
        return self._items.get(item_id)

    def get_items_by_tags(self, tags: List[str], limit: int = 50) -> List[str]:
        """按标签检索物品"""
        result_sets = []
        for tag in tags:
            result_sets.append(self._tag_index.get(tag.lower(), set()))
        
        if not result_sets:
            return []
        
        # 交集召回（所有标签都匹配）
        intersection = result_sets[0]
        for s in result_sets[1:]:
            intersection &= s
        
        # 不够则用并集补充
        if len(intersection) < limit:
            union = set()
            for s in result_sets:
                union |= s
            candidates = sorted(
                union, 
                key=lambda iid: self._items.get(iid, {}).get("quality_score", 0),
                reverse=True,
            )
            return candidates[:limit]
        
        return list(intersection)[:limit]
