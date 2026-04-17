"""
模型训练引擎

端到端管理推荐ML模型的训练、评估、版本控制流程。
支持：CTR模型 + Embedding模型 + 联合训练
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

from ..models.ctr_model import CTRRankingModel, ModelPerformance
from ..models.embedding_model import EmbeddingCollaborativeFilter
from ..features.feature_pipeline import RecommendationFeaturePipeline

logger = logging.getLogger(__name__)


class RecommendationTrainer:
    """
    推荐ML模型训练引擎

    功能：
    1. 特征工程管道
    2. CTR模型训练（LightGBM）
    3. Embedding模型训练（Neural CF / BPR）
    4. 评估报告
    5. 版本管理
    """

    def __init__(
        self,
        model_dir: str = "./models",
    ):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)

        self.pipeline = RecommendationFeaturePipeline()
        self.ctr_model = CTRRankingModel(
            model_dir=os.path.join(model_dir, "ctr"),
        )
        self.embedding_model = EmbeddingCollaborativeFilter(
            model_dir=os.path.join(model_dir, "embedding"),
            embedding_dim=64,
            num_epochs=50,
        )

        self._current_version: Optional[str] = None
        self._versions: Dict[str, dict] = {}

    def train(
        self,
        interactions: List[dict],
        items: List[dict],
        item_interactions: Dict[str, List[dict]],
        train_embedding: bool = True,
        version: Optional[str] = None,
    ) -> dict:
        """
        端到端训练

        Returns:
            {"version", "ctr": {...}, "embedding": {...}, "total_training_time_seconds"}
        """
        start_time = datetime.now()
        version = version or start_time.strftime("%Y%m%d_%H%M")

        logger.info(f"[Trainer] === 开始训练 v{version} ===")

        # Step 1: 特征工程
        logger.info("[Trainer] Step 1: 特征工程...")
        train_data, val_data = self.pipeline.build_training_data(
            interactions=interactions,
            items=items,
            item_interactions=item_interactions,
        )

        if not train_data.get("y"):
            logger.error("[Trainer] 训练样本为空，请检查数据")
            return {"error": "no training samples"}

        # Step 2: CTR模型
        logger.info("[Trainer] Step 2: 训练CTR模型...")
        ctr_perf = self.ctr_model.train(
            train_data=train_data,
            val_data=val_data if val_data.get("y") else None,
        )

        # Step 3: Embedding模型
        if train_embedding:
            logger.info("[Trainer] Step 3: 训练Embedding模型...")
            item_feat_map = {
                iid: feat.to_vector()
                for iid, feat in self.pipeline._item_features_cache.items()
            }
            emb_result = self.embedding_model.train(
                interactions=interactions,
                item_features=item_feat_map,
            )
        else:
            emb_result = {}

        elapsed = (datetime.now() - start_time).total_seconds()

        result = {
            "version": version,
            "ctr": {
                "auc": round(ctr_perf.auc, 4),
                "logloss": round(ctr_perf.logloss, 4),
                "ndcg_at_10": round(ctr_perf.ndcg_at_10, 4),
                "total_samples": ctr_perf.total_samples,
                "positive_rate": round(ctr_perf.positive_rate, 4),
                "training_time": round(ctr_perf.training_time_seconds, 1),
            },
            "embedding": emb_result,
            "total_training_time_seconds": round(elapsed, 1),
            "trained_at": datetime.now().isoformat(),
        }

        self._current_version = version
        self._versions[version] = result
        self._save_version_registry()

        logger.info(f"[Trainer] === 训练完成 v{version}: AUC={ctr_perf.auc:.4f}, 耗时={elapsed:.1f}s ===")
        return result

    def evaluate(
        self,
        interactions: List[dict],
        items: List[dict],
        item_interactions: Dict[str, List[dict]],
    ) -> dict:
        """评估当前模型"""
        _, val_data = self.pipeline.build_training_data(interactions, items, item_interactions)
        if not val_data.get("y"):
            return {"error": "no validation data"}
        perf = self.ctr_model._evaluate({}, val_data)
        return {"auc": round(perf.auc, 4), "logloss": round(perf.logloss, 4),
                "ndcg_at_10": round(perf.ndcg_at_10, 4), "total_samples": perf.total_samples}

    def get_feature_importance(self, top_k: int = 20) -> List[tuple]:
        return self.ctr_model.get_feature_importance(top_k=top_k)

    def list_versions(self) -> List[dict]:
        return list(self._versions.values())

    def load_version(self, version: str):
        """加载指定版本模型"""
        self.ctr_model.load(version=version)
        try:
            self.embedding_model.load(version=version)
        except FileNotFoundError:
            logger.warning(f"[Trainer] Embedding v{version} 不存在")
        self._current_version = version
        logger.info(f"[Trainer] 已加载版本: {version}")

    def _save_version_registry(self):
        path = os.path.join(self.model_dir, "version_registry.json")
        with open(path, "w") as f:
            json.dump({"versions": self._versions, "current": self._current_version},
                      f, indent=2, ensure_ascii=False, default=str)
