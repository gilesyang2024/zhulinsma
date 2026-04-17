"""
ML在线推理服务

将ML模型集成到推荐引擎，提供实时排序推理能力。
"""

import logging
from typing import Dict, List, Optional, Any, Tuple

from ..models.ctr_model import CTRRankingModel
from ..models.embedding_model import EmbeddingCollaborativeFilter
from ..features.feature_pipeline import RecommendationFeaturePipeline
from ..features.context_features import ContextFeatureExtractor
from ..ab_test.splitter import ABSplitter, MetricsCollector

logger = logging.getLogger(__name__)


class MLRecommenderService:
    """
    ML推荐服务

    将CTR模型和Embedding模型集成到推荐管道中。
    支持：
    1. ML排序（替代或增强规则排序）
    2. Embedding协同过滤召回
    3. A/B测试分流
    4. 在线指标收集
    """

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = model_dir
        self.ctr_model: Optional[CTRRankingModel] = None
        self.embedding_model: Optional[EmbeddingCollaborativeFilter] = None
        self.feature_pipeline = RecommendationFeaturePipeline()
        self.ab_splitter = ABSplitter()
        self.metrics_collector = MetricsCollector()
        self._is_initialized = False

    def initialize(self, load_ctr: bool = True, load_embedding: bool = True):
        """从磁盘加载已训练模型"""
        logger.info("[MLService] 初始化ML服务...")

        if load_ctr:
            try:
                self.ctr_model = CTRRankingModel(model_dir=f"{self.model_dir}/ctr")
                self.ctr_model.load()
                logger.info("[MLService] CTR模型加载成功")
            except Exception as e:
                logger.warning(f"[MLService] CTR模型加载失败: {e}，使用降级模式")

        if load_embedding:
            try:
                self.embedding_model = EmbeddingCollaborativeFilter(
                    model_dir=f"{self.model_dir}/embedding",
                )
                self.embedding_model.load()
                logger.info("[MLService] Embedding模型加载成功")
            except Exception as e:
                logger.warning(f"[MLService] Embedding加载失败: {e}")

        self._is_initialized = True
        logger.info("[MLService] ML服务初始化完成")

    def rank_candidates(
        self,
        user_id: str,
        candidate_items: List[str],
        user_features: Optional[List[float]] = None,
        item_features_map: Optional[Dict[str, List[float]]] = None,
        context: Optional[dict] = None,
    ) -> List[dict]:
        """
        对候选物品进行ML排序

        Returns: [{"item_id", "ml_score", "rank"}, ...]
        """
        if not self._is_initialized or self.ctr_model is None:
            return [{"item_id": iid, "ml_score": 0.5, "rank": r + 1}
                    for r, iid in enumerate(candidate_items)]

        if user_features is None:
            user_features = self.feature_pipeline.get_user_features(user_id) or [0.0] * 39

        item_feats = []
        valid_items = []
        for iid in candidate_items:
            if item_features_map:
                vec = item_features_map.get(iid)
            else:
                feat_obj = self.feature_pipeline._item_features_cache.get(iid)
                vec = feat_obj.to_vector() if feat_obj else None
            item_feats.append(vec if vec else [0.0] * 16)
            valid_items.append(iid)

        ctx_vec = [0.0] * 12
        if context:
            ctx_feat = ContextFeatureExtractor.extract(
                timestamp=context.get("timestamp"),
                device_type=context.get("device_type", "mobile"),
            )
            ctx_vec = ctx_feat.to_vector()

        user_batch = [user_features] * len(valid_items)
        ctx_batch = [ctx_vec] * len(valid_items)

        ctr_scores = self.ctr_model.predict(user_batch, item_feats, ctx_batch)

        results = [
            {"item_id": iid, "ml_score": float(score), "ctr_score": float(score)}
            for iid, score in zip(valid_items, ctr_scores)
        ]
        results.sort(key=lambda x: x["ml_score"], reverse=True)

        for rank, item in enumerate(results):
            item["rank"] = rank + 1

        return results

    def get_embedding_recs(
        self,
        user_id: str,
        exclude_items: Optional[set] = None,
        top_k: int = 20,
    ) -> List[dict]:
        """Embedding协同过滤推荐"""
        if not self.embedding_model or not self.embedding_model.is_trained:
            return []
        recs = self.embedding_model.recommend_for_user(
            user_id, exclude_items=exclude_items, top_k=top_k
        )
        return [{"item_id": r.item_id, "score": r.score, "reason": r.reason} for r in recs]

    def record_impression(
        self,
        experiment: str,
        variant: str,
        user_id: str,
        item_id: str,
    ):
        self.metrics_collector.record(experiment, variant, user_id, "impression", 1.0)

    def record_click(
        self,
        experiment: str,
        variant: str,
        user_id: str,
        item_id: str,
    ):
        self.metrics_collector.record(experiment, variant, user_id, "click", 1.0)

    def record_watch_duration(
        self,
        experiment: str,
        variant: str,
        user_id: str,
        item_id: str,
        duration_seconds: float,
    ):
        self.metrics_collector.record(experiment, variant, user_id, "watch_duration", duration_seconds)

    def get_experiment_lift(
        self,
        experiment: str,
        metric_name: str = "click",
    ) -> Optional[dict]:
        return self.metrics_collector.compute_lift(experiment, metric_name)

    @property
    def is_ready(self) -> bool:
        return self._is_initialized
