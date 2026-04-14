"""
协同过滤算法实现

包含 ItemCF (基于物品的协同过滤) 和 UserCF (基于用户的协同过滤)
支持隐式反馈数据、时间衰减、多种相似度计算方法。
"""

import math
import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ============================================================
# 交互行为权重配置
# ============================================================

INTERACTION_WEIGHTS = {
    "view": 1.0,
    "click": 2.0,
    "like": 4.0,
    "favorite": 5.0,
    "share": 6.0,
    "comment": 5.0,
    "follow": 3.0,
    "subscribe": 7.0,
    "download": 4.0,
    "complete": 8.0,      # 完播/完成 = 最强信号
    "rating": 6.0,        # 显式评分
}


class ItemCollaborativeFilter:
    """基于物品的协同过滤 (ItemCF)
    
    核心思路：
    - "喜欢过A的用户，还喜欢B" → A和B相似
    - 对用户交互过的物品，找相似的物品推荐
    
    适用场景：
    - 物品数量相对稳定
    - 用户兴趣多样化
    - 可以离线预计算物品相似度矩阵
    """
    
    def __init__(
        self,
        top_k: int = 50,              # 每个物品保留Top-K相似物品
        min_co_occur: int = 2,         # 最小共现阈值（过滤噪声）
        min_support: int = 3,          # 最小支持度
        similarity_method: str = "iuf_cosine",  # cosine / iuf_cosine / jaccard / pearson
        time_decay: bool = True,       # 是否启用时间衰减
        decay_half_life: float = 7.0,  # 衰减半衰期(天)
    ):
        self.top_k = top_k
        self.min_co_occur = min_co_occur
        self.min_support = min_support
        self.similarity_method = similarity_method
        self.time_decay = time_decay
        self.decay_half_life = decay_half_life
        
        # 内部数据结构
        self._item_users: Dict[str, Dict[str, float]] = defaultdict(dict)   # item_id -> {user_id: score}
        self._user_items: Dict[str, Dict[str, float]] = defaultdict(dict)   # user_id -> {item_id: score}
        self._item_similarity: Dict[str, List[Tuple[str, float]]] = {}     # item_id -> [(sim_item, score)]
        self._item_norms: Dict[str, float] = {}
        
        # 统计信息
        self._total_interactions = 0
        self._unique_items = 0
        self._unique_users = 0
        self._last_built_at: Optional[datetime] = None

    def add_interaction(self, user_id: str, item_id: str, 
                        interaction_type: str = "view",
                        weight: Optional[float] = None,
                        timestamp: Optional[datetime] = None):
        """添加单条交互记录"""
        if weight is None:
            weight = INTERACTION_WEIGHTS.get(interaction_type, 1.0)
        
        if self.time_decay and timestamp:
            days_ago = (datetime.now() - timestamp).days
            decay_factor = math.pow(0.5, days_ago / self.decay_half_life)
            weight *= decay_factor
        
        self._item_users[item_id][user_id] = max(
            self._item_users[item_id].get(user_id, 0), weight
        )
        self._user_items[user_id][item_id] = max(
            self._user_items[user_id].get(item_id, 0), weight
        )
        self._total_interactions += 1

    def add_interactions_batch(self, interactions: List[dict]):
        """批量添加交互记录"""
        for inter in interactions:
            self.add_interaction(
                user_id=inter["user_id"],
                item_id=inter["item_id"],
                interaction_type=inter.get("interaction_type", "view"),
                weight=inter.get("weight"),
                timestamp=inter.get("timestamp"),
            )

    @property
    def stats(self) -> dict:
        """返回构建统计"""
        return {
            "algorithm": "ItemCF",
            "method": self.similarity_method,
            "top_k": self.top_k,
            "total_interactions": self._total_interactions,
            "unique_items": len(self._item_users),
            "unique_users": len(self._user_items),
            "similarity_pairs_computed": sum(len(v) for v in self._item_similarity.values()),
            "last_built_at": self._last_built_at.isoformat() if self._last_built_at else None,
        }

    def build(self, rebuild: bool = True):
        """构建物品相似度矩阵（核心计算步骤）
        
        步骤：
        1. 计算IUF (Inverse User Frequency) 权重
        2. 构建物品向量并归一化
        3. 两两计算相似度
        4. 截断为Top-K邻居
        """
        start_time = time.time()
        logger.info(f"[ItemCF] 开始构建相似度矩阵... 方法={self.similarity_method}")
        
        items = list(self._item_users.keys())
        self._unique_items = len(items)
        self._unique_users = len(self._user_items)
        
        if not rebuild and self._item_similarity:
            logger.info("[ItemCF] 已有缓存，跳过重建")
            return
        
        # ---- 步骤1: IUF权重计算 ----
        iuf_weights = self._compute_iuf_weights()
        
        # ---- 步骤2: 归一化物品向量 ----
        normalized_vectors: Dict[str, Dict[str, float]] = {}
        norms: Dict[str, float] = {}
        
        for item_id, user_scores in self._item_users.items():
            vec = {}
            for user_id, raw_score in user_scores.items():
                # 应用IUF权重
                w = iuf_weights.get(user_id, 1.0)
                vec[user_id] = raw_score * w
            
            # L2归一化
            norm = math.sqrt(sum(v * v for v in vec.values()))
            if norm > 0:
                vec = {k: v / norm for k, v in vec.items()}
            
            normalized_vectors[item_id] = vec
            norms[item_id] = norm
        
        self._item_norms = norms
        
        # ---- 步骤3: 相似度计算 ----
        similarity_matrix: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        
        for i, item_a in enumerate(items):
            vec_a = normalized_vectors.get(item_a, {})
            if not vec_a:
                continue
            
            similarities = []
            
            for j, item_b in enumerate(items):
                if i == j:
                    continue
                
                vec_b = normalized_vectors.get(item_b, {})
                if not vec_b:
                    continue
                
                sim = self._compute_similarity(vec_a, vec_b, item_a, item_b)
                
                if sim >= 0.01 and self._check_min_support(item_a, item_b):  # 过滤低分和低支持度
                    similarities.append((item_b, sim))
            
            # Top-K截断
            similarities.sort(key=lambda x: x[1], reverse=True)
            similarity_matrix[item_a] = similarities[:self.top_k]
            
            if (i + 1) % 500 == 0:
                logger.info(f"[ItemCF] 进度: {i+1}/{len(items)} 物品已处理")
        
        self._item_similarity = dict(similarity_matrix)
        self._last_built_at = datetime.now()
        
        elapsed = time.time() - start_time
        total_pairs = sum(len(v) for v in self._item_similarity.values())
        logger.info(f"[ItemCF] 构建完成! {len(items)}个物品, "
                     f"{total_pairs}对相似关系, 耗时{elapsed:.2f}s")

    def _compute_iuf_weights(self) -> Dict[str, float]:
        """计算Inverse User Frequency权重
        
        对过于活跃的用户降权（惩罚那些什么都点/看的人）
        """
        item_count = len(self._item_users)
        if item_count == 0:
            return {}
        
        user_item_counts: Dict[str, int] = defaultdict(int)
        for item_id, users in self._item_users.items():
            for user_id in users:
                user_item_counts[user_id] += 1
        
        iuf = {}
        for user_id, count in user_item_counts.items():
            # log(总物品数 / 用户交互过的物品数)
            iuf[user_id] = math.log(1 + item_count / (count + 1))
        
        return iuf

    def _compute_similarity(self, vec_a: Dict[str, float], vec_b: Dict[str, float],
                           item_a: str, item_b: str) -> float:
        """根据配置的方法计算相似度"""
        method = self.similarity_method
        
        if method in ("cosine", "iuf_cosine"):
            # 余弦相似度 (vec_a, vec_b已经IUF加权+L2归一化)
            common_keys = set(vec_a.keys()) & set(vec_b.keys())
            if not common_keys:
                return 0.0
            dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
            return max(0.0, dot_product)
        
        elif method == "jaccard":
            # Jaccard系数（用于二值化交互）
            set_a = set(vec_a.keys())
            set_b = set(vec_b.keys())
            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            return intersection / union if union > 0 else 0.0
        
        elif method == "pearson":
            # Pearson相关系数（中心化的余弦）
            mean_a = sum(vec_a.values()) / len(vec_a) if vec_a else 0
            mean_b = sum(vec_b.values()) / len(vec_b) if vec_b else 0
            
            common_keys = set(vec_a.keys()) & set(vec_b.keys())
            if len(common_keys) < 2:
                return 0.0
            
            num = sum((vec_a[k] - mean_a) * (vec_b[k] - mean_b) for k in common_keys)
            den_a = math.sqrt(sum((vec_a[k] - mean_a) ** 2 for k in common_keys))
            den_b = math.sqrt(sum((vec_b[k] - mean_b) ** 2 for k in common_keys))
            
            if den_a == 0 or den_b == 0:
                return 0.0
            return num / (den_a * den_b)
        
        return 0.0

    def _check_min_support(self, item_a: str, item_b: str) -> bool:
        """检查两个物品是否有足够的共现支持"""
        users_a = set(self._item_users.get(item_a, {}).keys())
        users_b = set(self._item_users.get(item_b, {}).keys())
        co_occur = len(users_a & users_b)
        return co_occur >= self.min_co_occur

    def recommend(self, user_id: int, n: int = 20,
                  filter_seen: bool = True,
                  candidate_items: Optional[Set[str]] = None) -> List[Tuple[str, float, str]]:
        """为用户生成ItemCF推荐列表
        
        Args:
            user_id: 目标用户ID
            n: 推荐数量上限
            filter_seen: 是否过滤已交互过的物品
            candidate_items: 候选物品集合（None表示全量）
            
        Returns:
            [(item_id, score, reason), ...]
        """
        user_history = self._user_items.get(user_id, {})
        if not user_history:
            return []
        
        seen_items = set(user_history.keys()) if filter_seen else set()
        
        # 收集候选物品及其得分
        candidate_scores: Dict[str, float] = defaultdict(float)
        
        for item_id, interact_score in user_history.items():
            similar_items = self._item_similarity.get(item_id, [])
            
            for sim_item_id, sim_score in similar_items:
                if sim_item_id in seen_items:
                    continue
                if candidate_items and sim_item_id not in candidate_items:
                    continue
                
                # 加权得分: 用户对该物品的兴趣 × 物品间相似度
                candidate_scores[sim_item_id] += interact_score * sim_score
        
        # 排序截断
        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:n]
        
        results = []
        for item_id, score in ranked:
            results.append((item_id, round(score, 6), "collaborative_item"))
        
        return results


class UserCollaborativeFilter:
    """基于用户的协同过滤 (UserCF)
    
    核心思路：
    - 找到与目标用户兴趣相似的用户群
    - 推荐这些相似用户喜欢但目标用户还没看过的内容
    
    适用场景：
    - 用户群体有明显聚类特征
    - 社交属性强的平台
    - 新内容较少时效果更好
    """
    
    def __init__(
        self,
        top_k_neighbors: int = 50,       # 每个用户保留Top-K近邻
        min_overlap: int = 3,             # 最小共同交互数
        similarity_threshold: float = 0.1,# 相似度阈值
        similarity_method: str = "cosine",
        time_decay_days: int = 30,        # 时间衰减窗口
    ):
        self.top_k_neighbors = top_k_neighbors
        self.min_overlap = min_overlap
        self.similarity_threshold = similarity_threshold
        self.similarity_method = similarity_method
        self.time_decay_days = time_decay_days
        
        # 数据结构
        self._user_vectors: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._user_similarity: Dict[str, List[Tuple[str, float]]] = {}
        self._item_popularity: Dict[str, float] = {}
        
        self._last_built_at: Optional[datetime] = None

    def add_user_vector(self, user_id: str, item_scores: Dict[str, float]):
        """添加用户的物品偏好向量"""
        self._user_vectors[user_id].update(item_scores)

    def build(self, rebuild: bool = True):
        """构建用户相似度矩阵"""
        start_time = time.time()
        logger.info(f"[UserCF] 开始构建用户相似度矩阵...")
        
        users = list(self._user_vectors.keys())
        
        if not rebuild and self._user_similarity:
            logger.info("[UserCF] 已有缓存，跳过重建")
            return
        
        # 计算物品流行度（用于后续去偏）
        item_counts: Dict[str, int] = defaultdict(int)
        for user_vec in self._user_vectors.values():
            for item_id in user_vec:
                item_counts[item_id] += 1
        
        total = sum(item_counts.values()) or 1
        self._item_popularity = {k: v / total for k, v in item_counts.items()}
        
        # 用户相似度计算
        similarity_matrix: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        
        for i, user_a in enumerate(users):
            vec_a = self._user_vectors[user_a]
            if not vec_a:
                continue
            
            neighbors = []
            
            for j, user_b in enumerate(users):
                if i == j:
                    continue
                
                vec_b = self._user_vectors[user_b]
                overlap = set(vec_a.keys()) & set(vec_b.keys())
                
                if len(overlap) < self.min_overlap:
                    continue
                
                sim = self._cosine_similar(vec_a, vec_b)
                
                if sim >= self.similarity_threshold:
                    neighbors.append((user_b, sim))
            
            neighbors.sort(key=lambda x: x[1], reverse=True)
            similarity_matrix[user_a] = neighbors[:self.top_k_neighbors]
            
            if (i + 1) % 500 == 0:
                logger.info(f"[UserCF] 进度: {i+1}/{len(users)} 用户")
        
        self._user_similarity = dict(similarity_matrix)
        self._last_built_at = datetime.now()
        
        elapsed = time.time() - start_time
        total_pairs = sum(len(v) for v in self._user_similarity.values())
        logger.info(f"[UserCF] 构建完成! {len(users)}个用户, "
                     f"{total_pairs}对邻居关系, 耗时{elapsed:.2f}s")

    def _cosine_similar(self, vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """余弦相似度"""
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0
        
        dot = sum(vec_a[k] * vec_b[k] for k in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)

    def recommend(self, user_id: str, n: int = 20,
                  filter_seen: bool = True) -> List[Tuple[str, float, str]]:
        """为用户生成UserCF推荐"""
        user_vec = self._user_vectors.get(user_id, {})
        if not user_vec:
            return []
        
        seen = set(user_vec.keys()) if filter_seen else set()
        neighbors = self._user_similarity.get(user_id, [])
        
        if not neighbors:
            return []
        
        candidate_scores: Dict[str, float] = defaultdict(float)
        
        for neighbor_id, sim_score in neighbors:
            neighbor_vec = self._user_vectors.get(neighbor_id, {})
            
            for item_id, score in neighbor_vec.items():
                if item_id in seen:
                    continue
                
                # 去偏：减去物品全局流行度影响
                popularity_penalty = self._item_popularity.get(item_id, 0) * 0.1
                adjusted_score = (score * sim_score) - popularity_penalty
                
                candidate_scores[item_id] += max(0, adjusted_score)
        
        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:n]
        
        return [(iid, round(s, 6), "collaborative_user") for iid, s in ranked]

    @property
    def stats(self) -> dict:
        return {
            "algorithm": "UserCF",
            "method": self.similarity_method,
            "top_k_neighbors": self.top_k_neighbors,
            "total_users": len(self._user_vectors),
            "similarity_pairs_computed": sum(len(v) for v in self._user_similarity.values()),
            "last_built_at": self._last_built_at.isoformat() if self._last_built_at else None,
        }
