"""
ML推荐系统 API 端点

提供ML模型的训练、推理、A/B测试管理接口。
集成到 FastAPI 主应用。
"""

import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ml", tags=["ML推荐"])


# ============================================================
# 全局实例（懒加载）
# ============================================================

_ml_service = None
_trainer = None
_ranker = None


def get_ml_service():
    global _ml_service
    if _ml_service is None:
        try:
            from .serving.ml_serving import MLRecommenderService
            model_dir = os.environ.get("ML_MODEL_DIR", "./models")
            _ml_service = MLRecommenderService(model_dir=model_dir)
            _ml_service.initialize()
        except Exception as e:
            logger.error(f"[MLAPI] ML服务初始化失败: {e}")
            raise HTTPException(status_code=503, detail=f"ML服务不可用: {e}")
    return _ml_service


def get_ranker():
    global _ranker
    if _ranker is None:
        try:
            from .integration import MLEnhancedRanker
            model_dir = os.environ.get("ML_MODEL_DIR", "./models")
            _ranker = MLEnhancedRanker(model_dir=model_dir)
        except Exception as e:
            logger.error(f"[MLAPI] Ranker初始化失败: {e}")
    return _ranker


def get_trainer():
    global _trainer
    if _trainer is None:
        try:
            from .training.trainer import RecommendationTrainer
            model_dir = os.environ.get("ML_MODEL_DIR", "./models")
            _trainer = RecommendationTrainer(model_dir=model_dir)
        except Exception as e:
            logger.error(f"[MLAPI] 训练器初始化失败: {e}")
    return _trainer


# ============================================================
# Pydantic 模型
# ============================================================

class TrainingRequest(BaseModel):
    """训练请求"""
    version: Optional[str] = Field(None, description="模型版本号")
    train_embedding: bool = Field(True, description="是否训练Embedding模型")


class MLRankRequest(BaseModel):
    """ML重排序请求"""
    user_id: str = Field(..., description="用户ID")
    candidate_items: List[str] = Field(..., description="候选物品ID列表")
    user_features: Optional[List[float]] = Field(None, description="用户特征向量（39维）")
    item_features_map: Optional[Dict[str, List[float]]] = Field(None, description="物品特征字典")
    context: Optional[dict] = Field(None, description="上下文信息")


class FeedbackRequest(BaseModel):
    """ML反馈上报"""
    experiment: str = Field(..., description="实验名称")
    variant: str = Field(..., description="实验分组")
    user_id: str = Field(..., description="用户ID")
    item_id: str = Field(..., description="物品ID")
    metric: str = Field(..., description="指标名(impression/click/watch_duration)")
    value: float = Field(1.0, description="指标值")


class ABExperimentCreate(BaseModel):
    """创建A/B实验"""
    name: str = Field(..., description="实验名称")
    traffic_percent: float = Field(0.10, ge=0.0, le=1.0)
    variants: List[str] = Field(default_factory=lambda: ["control", "treatment"])
    default_variant: str = Field("control")
    description: str = Field("")


# ============================================================
# API 端点
# ============================================================

@router.get("/status")
async def get_ml_status():
    """ML服务状态"""
    service = get_ml_service()
    ranker = get_ranker()

    return {
        "ml_ready": service.is_ready if service else False,
        "ctr_loaded": service.ctr_model.is_trained if service and service.ctr_model else False,
        "embedding_loaded": service.embedding_model.is_trained if service and service.embedding_model else False,
        "ranker_ready": ranker is not None,
        "ab_experiments": len(service.ab_splitter.list_experiments()) if service else 0,
    }


@router.post("/train")
async def trigger_training(
    req: TrainingRequest,
    background_tasks: BackgroundTasks,
):
    """
    触发ML模型训练（后台执行）

    训练完成后自动加载最新模型。
    """
    def _do_training():
        try:
            trainer = get_trainer()
            if trainer is None:
                logger.error("[MLAPI] 训练器不可用")
                return

            # 从模拟数据中获取训练数据（生产环境从数据库加载）
            from src.recommendation.api import get_engine
            engine = get_engine()

            # 从引擎中提取交互数据
            interactions = _extract_interactions_from_engine(engine)
            items = _extract_items_from_engine(engine)
            item_interactions = _group_item_interactions(interactions)

            result = trainer.train(
                interactions=interactions,
                items=items,
                item_interactions=item_interactions,
                train_embedding=req.train_embedding,
                version=req.version,
            )

            logger.info(f"[MLAPI] 训练完成: {result}")

            # 重新加载ML服务
            global _ml_service, _ranker
            _ml_service = None
            _ranker = None
            get_ml_service()
            get_ranker()

        except Exception as e:
            logger.error(f"[MLAPI] 训练失败: {e}")

    background_tasks.add_task(_do_training)

    return {
        "message": "训练任务已启动",
        "status": "running",
        "started_at": datetime.now().isoformat(),
    }


@router.post("/rank")
async def ml_rank(req: MLRankRequest):
    """
    ML重排序接口

    对候选物品列表进行ML排序，返回融合分数。
    """
    ranker = get_ranker()
    if ranker is None:
        raise HTTPException(status_code=503, detail="Ranker不可用")

    if not req.candidate_items:
        return {"recommendations": []}

    ranked = ranker.rerank(
        candidates=[{"item_id": iid, "score": 0.5} for iid in req.candidate_items],
        user_id=req.user_id,
        user_features=req.user_features,
        item_features_map=req.item_features_map,
        context=req.context,
    )

    return {
        "user_id": req.user_id,
        "recommendations": ranked,
        "total": len(ranked),
        "ml_enhanced": True,
    }


@router.get("/embedding-recs/{user_id}")
async def get_embedding_recommendations(
    user_id: str,
    exclude_items: str = Query(None, description="逗号分隔的排除物品ID"),
    top_k: int = Query(20, ge=1, le=100),
):
    """获取Embedding协同过滤推荐"""
    service = get_ml_service()
    ranker = get_ranker()

    if ranker is None:
        raise HTTPException(status_code=503, detail="Ranker不可用")

    exclude_set = set(exclude_items.split(",")) if exclude_items else None
    recs = ranker.get_embedding_recs(user_id, exclude_items=exclude_set, top_k=top_k)

    return {
        "user_id": user_id,
        "recommendations": recs,
        "total": len(recs),
    }


@router.get("/ctr-model/importance")
async def get_feature_importance(top_k: int = Query(20, ge=1, le=50)):
    """获取CTR模型特征重要性"""
    trainer = get_trainer()
    if trainer is None:
        raise HTTPException(status_code=503, detail="训练器不可用")

    importance = trainer.get_feature_importance(top_k=top_k)
    return {
        "feature_importance": [
            {"feature": name, "importance": round(score, 4)}
            for name, score in importance
        ],
    }


@router.get("/ctr-model/versions")
async def list_model_versions():
    """列出所有模型版本"""
    trainer = get_trainer()
    if trainer is None:
        return {"versions": []}
    return {"versions": trainer.list_versions()}


# ----------------------------------------------------------
# A/B测试端点
# ----------------------------------------------------------

@router.get("/ab/experiments")
async def list_ab_experiments():
    """列出所有A/B实验"""
    service = get_ml_service()
    if service is None:
        return {"experiments": []}
    return {
        "experiments": [
            {
                "name": e.name,
                "traffic_percent": e.traffic_percent,
                "variants": e.variants,
                "enabled": e.enabled,
                "description": e.description,
            }
            for e in service.ab_splitter.list_experiments()
        ]
    }


@router.post("/ab/experiments")
async def create_ab_experiment(req: ABExperimentCreate):
    """创建A/B实验"""
    service = get_ml_service()
    if service is None:
        raise HTTPException(status_code=503, detail="ML服务不可用")

    from ..ab_test.splitter import Experiment
    exp = Experiment(
        name=req.name,
        traffic_percent=req.traffic_percent,
        variants=req.variants,
        default_variant=req.default_variant,
        description=req.description,
    )
    service.ab_splitter.register_experiment(exp)

    return {"message": "实验已创建", "experiment": req.name}


@router.get("/ab/assign/{experiment_name}/{user_id}")
async def get_user_variant(experiment_name: str, user_id: str):
    """获取用户在指定实验中的分组"""
    service = get_ml_service()
    if service is None:
        raise HTTPException(status_code=503, detail="ML服务不可用")

    variant = service.ab_splitter.get_variant(experiment_name, user_id)
    return {
        "experiment": experiment_name,
        "user_id": user_id,
        "variant": variant or "unknown",
    }


@router.post("/ab/feedback")
async def submit_ml_feedback(req: FeedbackRequest):
    """上报ML指标（曝光/点击/观看时长）"""
    service = get_ml_service()
    if service is None:
        raise HTTPException(status_code=503, detail="ML服务不可用")

    if req.metric == "click":
        service.record_click(req.experiment, req.variant, req.user_id, req.item_id)
    elif req.metric == "impression":
        service.record_impression(req.experiment, req.variant, req.user_id, req.item_id)
    elif req.metric == "watch_duration":
        service.record_click(req.experiment, req.variant, req.user_id, req.item_id)

    return {"success": True, "metric": req.metric}


@router.get("/ab/lift/{experiment}")
async def get_experiment_lift(
    experiment: str,
    metric: str = Query("click", description="指标名(click/impression/watch_duration)"),
):
    """获取实验提升报告"""
    service = get_ml_service()
    if service is None:
        raise HTTPException(status_code=503, detail="ML服务不可用")

    lift = service.get_experiment_lift(experiment, metric)
    if lift is None:
        return {"experiment": experiment, "metric": metric, "message": "数据不足"}

    return {
        "experiment": experiment,
        "metric": metric,
        "lift": lift,
    }


# ============================================================
# 辅助函数
# ============================================================

def _extract_interactions_from_engine(engine) -> List[dict]:
    """从推荐引擎提取交互数据"""
    interactions = []
    item_cf = getattr(engine, "item_cf", None)
    if item_cf is None:
        return []

    user_items = getattr(item_cf, "_user_items", {})
    for uid, items in user_items.items():
        for iid, score in items.items():
            interactions.append({
                "user_id": uid,
                "item_id": iid,
                "weight": score,
                "type": "view",
                "timestamp": datetime.now(),
            })
    return interactions


def _extract_items_from_engine(engine) -> List[dict]:
    """从推荐引擎提取物品数据"""
    content_based = getattr(engine, "content_based", None)
    if content_based is None:
        return []

    items = []
    items_dict = getattr(content_based, "_items", {})
    for iid, feat in items_dict.items():
        items.append({"item_id": iid, **feat})
    return items


def _group_item_interactions(interactions: List[dict]) -> Dict[str, List[dict]]:
    """按物品分组交互"""
    grouped: Dict[str, List[dict]] = {}
    for inter in interactions:
        iid = inter.get("item_id")
        if iid:
            if iid not in grouped:
                grouped[iid] = []
            grouped[iid].append(inter)
    return grouped
