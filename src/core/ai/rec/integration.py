"""
ML增强推荐引擎集成层

将ML模型（CTR排序 + Embedding协同）无缝集成到现有RecommendationEngine。
提供：
1. ML + 规则双轨排序
2. 融合权重可配置
3. A/B测试通道
4. FastAPI端点
"""

import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# 延迟导入，避免循环依赖
ML_SERVICE = None
TRAINER = None


def get_ml_service(model_dir: str = "./models") -> Any:
    """懒加载ML服务单例"""
    global ML_SERVICE
    if ML_SERVICE is None:
        try:
            from .serving.ml_serving import MLRecommenderService
            ML_SERVICE = MLRecommenderService(model_dir=model_dir)
            ML_SERVICE.initialize()
        except Exception as e:
            logger.warning(f"[MLIntegration] ML服务初始化失败: {e}")
            ML_SERVICE = None
    return ML_SERVICE


def get_trainer(model_dir: str = "./models") -> Any:
    """懒加载训练器单例"""
    global TRAINER
    if TRAINER is None:
        try:
            from .training.trainer import RecommendationTrainer
            TRAINER = RecommendationTrainer(model_dir=model_dir)
        except Exception as e:
            logger.warning(f"[MLIntegration] 训练器初始化失败: {e}")
            TRAINER = None
    return TRAINER


# ============================================================
# 融合策略：ML + 规则双轨
# ============================================================

class MLFusionStrategy:
    """
    ML + 规则融合策略

    公式：final_score = w_ml * ml_score + w_rule * rule_score

    支持的融合模式：
    - ml_only: 纯ML排序
    - rule_only: 纯规则排序
    - hybrid: 混合（推荐）
    - ml_boost: ML分数作为加成（ML分数高则加分）
    """

    MODE_ML_ONLY = "ml_only"
    MODE_RULE_ONLY = "rule_only"
    MODE_HYBRID = "hybrid"
    MODE_ML_BOOST = "ml_boost"

    DEFAULT_WEIGHTS = {
        MODE_ML_ONLY:      {"ml": 1.0, "rule": 0.0},
        MODE_RULE_ONLY:    {"ml": 0.0, "rule": 1.0},
        MODE_HYBRID:       {"ml": 0.6, "rule": 0.4},   # ML占60%，规则40%
        MODE_ML_BOOST:     {"ml": 0.0, "rule": 1.0},  # 先规则，再用ML加成
    }

    def __init__(
        self,
        mode: str = MODE_HYBRID,
        ml_weight: float = 0.6,
        rule_weight: float = 0.4,
    ):
        self.mode = mode
        self.ml_weight = ml_weight
        self.rule_weight = rule_weight

    def fuse(
        self,
        ml_score: float,
        rule_score: float,
    ) -> float:
        """融合ML分数和规则分数"""
        if self.mode == self.MODE_ML_ONLY:
            return ml_score
        elif self.mode == self.MODE_RULE_ONLY:
            return rule_score
        elif self.mode == self.MODE_ML_BOOST:
            # ML分数作为加成因子（范围0.8-1.2）
            boost = 0.8 + ml_score * 0.4
            return rule_score * boost
        else:  # hybrid
            return self.ml_weight * ml_score + self.rule_weight * rule_score


# ============================================================
# ML增强推荐管道
# ==========================================================

class MLEnhancedRanker:
    """
    ML增强排序器

    集成到现有 RecommendationEngine 的排序阶段，
    用ML模型重排序候选集。
    """

    def __init__(
        self,
        model_dir: str = "./models",
        fusion_mode: str = MLFusionStrategy.MODE_HYBRID,
    ):
        self.ml_service = get_ml_service(model_dir)
        self.fusion = MLFusionStrategy(mode=fusion_mode)

    def rerank(
        self,
        candidates: List[dict],
        user_id: str,
        user_features: Optional[List[float]] = None,
        item_features_map: Optional[Dict[str, List[float]]] = None,
        context: Optional[dict] = None,
    ) -> List[dict]:
        """
        对候选集进行ML重排序

        Args:
            candidates: 来自规则引擎的候选集 [{"item_id", "score", ...}]
            user_id: 目标用户
            user_features: 用户特征向量
            item_features_map: 物品特征字典

        Returns:
            重排序后的候选集
        """
        if not self.ml_service or not self.ml_service.is_ready:
            logger.debug("[MLRanker] ML服务未就绪，返回原始顺序")
            return candidates

        item_ids = [c.get("item_id") for c in candidates if c.get("item_id")]

        if not item_ids:
            return candidates

        # ML排序
        ranked = self.ml_service.rank_candidates(
            user_id=user_id,
            candidate_items=item_ids,
            user_features=user_features,
            item_features_map=item_features_map,
            context=context,
        )

        # 构建 item_id → ml_rank 的映射
        ml_rank_map = {r["item_id"]: r for r in ranked}

        # 融合
        fused_results = []
        for cand in candidates:
            iid = cand.get("item_id")
            ml_info = ml_rank_map.get(iid, {})
            ml_score = ml_info.get("ml_score", 0.5)
            rule_score = cand.get("score", 0.5)

            fused_score = self.fusion.fuse(ml_score, rule_score)

            result = dict(cand)
            result["ml_score"] = ml_score
            result["fused_score"] = fused_score
            result["ml_rank"] = ml_info.get("rank", 0)
            result["ctr_score"] = ml_info.get("ctr_score", 0.5)
            fused_results.append(result)

        # 按融合分数重排
        fused_results.sort(key=lambda x: x["fused_score"], reverse=True)

        for rank, item in enumerate(fused_results):
            item["final_rank"] = rank + 1

        return fused_results

    def get_embedding_recs(
        self,
        user_id: str,
        exclude_items: Optional[set] = None,
        top_k: int = 20,
    ) -> List[dict]:
        """获取Embedding推荐"""
        if not self.ml_service or not self.ml_service.is_ready:
            return []
        return self.ml_service.get_embedding_recs(
            user_id=user_id,
            exclude_items=exclude_items,
            top_k=top_k,
        )


# ============================================================
# ML训练命令接口（FastAPI / CLI）
# ==========================================================

def run_training(
    interactions: List[dict],
    items: List[dict],
    item_interactions: Dict[str, List[dict]],
    model_dir: str = "./models",
    train_embedding: bool = True,
    version: Optional[str] = None,
) -> dict:
    """执行模型训练"""
    trainer = get_trainer(model_dir)
    if trainer is None:
        return {"error": "训练器不可用"}

    # 全局刷新ML_SERVICE
    global ML_SERVICE
    ML_SERVICE = None

    return trainer.train(
        interactions=interactions,
        items=items,
        item_interactions=item_interactions,
        train_embedding=train_embedding,
        version=version,
    )


# ============================================================
# 依赖注入：将ML增强集成到现有API
# ============================================================

def patch_recommendation_engine():
    """
    Monkey-patch推荐引擎，注入ML能力

    在 RecommendationEngine.recommend() 后调用，
    对候选集进行ML重排序。
    """
    try:
        from src.recommendation.engine import RecommendationEngine

        _original_recommend = RecommendationEngine.recommend

        async def _ml_enhanced_recommend(self, user_id, scene, limit, context, filters, use_cache):
            result = await _original_recommend(self, user_id, scene, limit, context, filters, use_cache)

            # 获取ML增强排序器
            model_dir = os.environ.get("ML_MODEL_DIR", "./models")
            ranker = MLEnhancedRanker(model_dir=model_dir)

            candidates = result.get("recommendations", [])
            if candidates and user_id:
                user_feat = ranker.ml_service.feature_pipeline.get_user_features(user_id) if ranker.ml_service else None
                reranked = ranker.rerank(
                    candidates=candidates,
                    user_id=user_id,
                    user_features=user_feat,
                    context=context,
                )
                result["recommendations"] = reranked
                result["meta"]["ml_enhanced"] = True
            else:
                result["meta"]["ml_enhanced"] = False

            return result

        RecommendationEngine.recommend = _ml_enhanced_recommend
        logger.info("[MLIntegration] 推荐引擎已注入ML能力")

    except ImportError as e:
        logger.warning(f"[MLIntegration] 无法导入推荐引擎: {e}")
