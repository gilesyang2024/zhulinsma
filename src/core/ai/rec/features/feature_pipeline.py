"""
推荐特征工程管道

将原始交互数据转换为ML训练数据集。
生成 (user_features, item_features, context_features, label) 四元组。
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import random

from .user_profile_features import UserProfileFeatureExtractor, UserProfileFeatures
from .item_features import ItemFeatureExtractor, ItemFeatures
from .context_features import ContextFeatureExtractor, ContextFeatures

logger = logging.getLogger(__name__)


class RecommendationFeaturePipeline:
    """推荐特征工程管道

    端到端地将原始数据转换为ML训练样本。
    支持：特征提取 / 训练集构建 / 在线特征服务
    """

    def __init__(
        self,
        sequence_length: int = 20,
        train_ratio: float = 0.8,
        negative_sampling_ratio: float = 4.0,
        min_interactions: int = 3,
    ):
        """
        Args:
            sequence_length: 行为序列最大长度
            train_ratio: 训练集比例（剩余为验证集）
            negative_sampling_ratio: 负采样比例（每个正样本采样N个负样本）
            min_interactions: 最少交互数（低于此跳过）
        """
        self.sequence_length = sequence_length
        self.train_ratio = train_ratio
        self.negative_ratio = negative_sampling_ratio
        self.min_interactions = min_interactions

        self.user_extractor = UserProfileFeatureExtractor()
        self.item_extractor = ItemFeatureExtractor()
        self.context_extractor = ContextFeatureExtractor()

        # 预计算的全局特征（用于在线推理缓存）
        self._user_features_cache: Dict[str, UserProfileFeatures] = {}
        self._item_features_cache: Dict[str, ItemFeatures] = {}
        self._all_item_ids: List[str] = []

    # ================================================================
    # 离线训练数据构建
    # ================================================================

    def build_training_data(
        self,
        interactions: List[dict],
        items: List[dict],
        item_interactions: Dict[str, List[dict]],
    ) -> Tuple[dict, dict]:
        """
        从交互数据构建训练集和验证集。

        Returns:
            (train_data, val_data)
            each: {
                "X_user": [...],   # 用户特征矩阵
                "X_item": [...],   # 物品特征矩阵
                "X_context": [...],# 上下文特征矩阵
                "y": [...],        # 标签 (1=点击, 0=未点击)
                "weights": [...], # 样本权重
            }
        """
        logger.info(f"[Pipeline] 开始构建训练数据: {len(interactions)} 交互")

        # 1. 提取用户特征
        user_interaction_map = self._group_by_user(interactions)
        user_features_map = self.user_extractor.extract(user_interaction_map)

        # 2. 提取物品特征
        item_features_map = self.item_extractor.extract_all(items, item_interactions)
        self._user_features_cache = user_features_map
        self._item_features_cache = item_features_map
        self._all_item_ids = [i.get("item_id") for i in items if i.get("item_id")]
        self._items_dict = {i.get("item_id"): i for i in items if i.get("item_id")}

        # 3. 构建正负样本
        samples = self._build_samples(
            interactions, user_features_map, item_features_map, is_train=True
        )

        # 4. 按时间划分训练/验证集
        train_data, val_data = self._split_train_val(samples)

        logger.info(f"[Pipeline] 训练数据构建完成: "
                    f"train={len(train_data['y'])}, val={len(val_data['y'])}")

        return train_data, val_data

    def _group_by_user(self, interactions: List[dict]) -> Dict[str, List[dict]]:
        """按用户分组"""
        user_map: Dict[str, List[dict]] = {}
        for inter in interactions:
            uid = inter.get("user_id")
            if uid:
                if uid not in user_map:
                    user_map[uid] = []
                user_map[uid].append(inter)
        return user_map

    def _build_samples(
        self,
        interactions: List[dict],
        user_features: Dict[str, UserProfileFeatures],
        item_features: Dict[str, ItemFeatures],
        is_train: bool = True,
    ) -> List[dict]:
        """构建正样本和负样本"""
        samples = []

        # 按用户分组交互（时序）
        user_inter_map = self._group_by_user(interactions)

        POSITIVE_TYPES = {"click", "like", "favorite", "share", "complete", "subscribe"}

        for uid, user_ints in user_inter_map.items():
            if len(user_ints) < self.min_interactions:
                continue

            # 按时间排序
            sorted_ints = sorted(user_ints, key=lambda x: x.get("timestamp") or datetime.now())

            # 提取用户序列特征（截至当前位置）
            for idx, inter in enumerate(sorted_ints):
                iid = inter.get("item_id")
                if not iid:
                    continue

                inter_type = inter.get("type", "view")
                label = 1.0 if inter_type in POSITIVE_TYPES else 0.0

                # 序列历史（当前位置之前的所有交互）
                history = sorted_ints[:idx]

                # 用户特征（基于历史重建）
                uf = self._rebuild_user_features(uid, history, user_features)

                # 物品特征
                if_item_feat = item_features.get(iid)
                if not if_item_feat:
                    continue

                # 上下文特征
                ts = inter.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        ts = datetime.now()
                cf = self.context_extractor.extract(
                    timestamp=ts,
                    device_type=inter.get("device_type", "mobile"),
                    session_position=idx / max(len(sorted_ints), 1),
                    exposure_rank=idx,
                    total_candidates=len(sorted_ints),
                )

                sample = {
                    "user_id": uid,
                    "item_id": iid,
                    "label": label,
                    "interactions": len(history),
                    "user_features": uf,
                    "item_features": if_item_feat,
                    "context_features": cf,
                    "timestamp": ts,
                }
                samples.append(sample)

                # 负采样（仅训练时）
                if is_train and label == 1.0 and self.negative_ratio > 0:
                    neg_count = int(self.negative_ratio)
                    for _ in range(neg_count):
                        neg_iid = self._sample_negative_item(
                            uid, history, user_features, item_features
                        )
                        if neg_iid:
                            neg_item_feat = item_features.get(neg_iid)
                            if neg_item_feat:
                                samples.append({
                                    "user_id": uid,
                                    "item_id": neg_iid,
                                    "label": 0.0,
                                    "interactions": len(history),
                                    "user_features": uf,
                                    "item_features": neg_item_feat,
                                    "context_features": cf,
                                    "timestamp": ts,
                                })

        return samples

    def _rebuild_user_features(
        self,
        user_id: str,
        history: List[dict],
        base_features: Dict[str, UserProfileFeatures],
    ) -> UserProfileFeatures:
        """基于历史子序列重建用户特征（避免数据泄露）"""
        base = base_features.get(user_id, UserProfileFeatures())
        if not history:
            return base

        # 简单策略：用已有特征，但标记recency_days=0（最新）
        features = UserProfileFeatureExtractor().extract_single(user_id, history)
        return features

    def _sample_negative_item(
        self,
        user_id: str,
        history: List[dict],
        user_features: Dict[str, UserProfileFeatures],
        item_features: Dict[str, ItemFeatures],
    ) -> Optional[str]:
        """从用户未交互过的物品中采样负样本"""
        seen = {i.get("item_id") for i in history if i.get("item_id")}
        candidates = [iid for iid in self._all_item_ids if iid not in seen]
        if not candidates:
            return None
        return random.choice(candidates)

    def _split_train_val(
        self,
        samples: List[dict],
    ) -> Tuple[dict, dict]:
        """按时间排序后，从某时间点切分训练/验证集"""
        if not samples:
            return {}, {}

        # 按时间排序
        sorted_samples = sorted(
            samples,
            key=lambda x: x.get("timestamp") or datetime.now()
        )

        split_idx = int(len(sorted_samples) * self.train_ratio)
        train_samples = sorted_samples[:split_idx]
        val_samples = sorted_samples[split_idx:]

        return self._to_numpy(train_samples), self._to_numpy(val_samples)

    def _to_numpy(self, samples: List[dict]) -> dict:
        """将样本列表转换为NumPy矩阵"""
        X_user = []
        X_item = []
        X_context = []
        y = []
        weights = []

        for s in samples:
            uf = s.get("user_features")
            if_item = s.get("item_features")
            cf = s.get("context_features")
            if not (uf and if_item and cf):
                continue

            X_user.append(uf.to_vector())
            X_item.append(if_item.to_vector())
            X_context.append(cf.to_vector())
            y.append(s.get("label", 0.0))

            # 高权重行为样本加权
            inter_type = s.get("interactions", 0)
            weight = 1.0 + min(inter_type / 50.0, 1.0)
            weights.append(weight)

        return {
            "X_user": X_user,
            "X_item": X_item,
            "X_context": X_context,
            "y": y,
            "weights": weights,
        }

    # ================================================================
    # 在线特征服务
    # ================================================================

    def get_user_features(self, user_id: str) -> Optional[List[float]]:
        """在线获取用户特征向量"""
        uf = self._user_features_cache.get(user_id)
        return uf.to_vector() if uf else None

    def get_item_features(self, item_id: str) -> Optional[List[float]]:
        """在线获取物品特征向量"""
        if_item = self._item_features_cache.get(item_id)
        return if_item.to_vector() if if_item else None

    def build_candidate_features(
        self,
        user_id: str,
        candidate_item_ids: List[str],
        context: Optional[dict] = None,
    ) -> Tuple[List[List[float]], List[List[float]], List[str]]:
        """
        为候选集构建特征矩阵（用于在线推理）

        Returns:
            (user_features_batch, item_features_batch, item_ids)
        """
        user_vec = self.get_user_features(user_id) or [0.0] * 39
        context_vec = (
            self.context_extractor.extract(
                timestamp=context.get("timestamp") if context else None,
                device_type=context.get("device_type", "mobile") if context else "mobile",
            ).to_vector()
        )

        user_batch = []
        item_batch = []
        valid_ids = []

        for rank, iid in enumerate(candidate_item_ids):
            item_vec = self.get_item_features(iid)
            if item_vec is None:
                item_vec = [0.0] * 16

            user_batch.append(user_vec)
            item_batch.append(item_vec)
            valid_ids.append(iid)

        return user_batch, item_batch, valid_ids
