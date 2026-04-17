#!/usr/bin/env python3
"""
ML API - FastAPI 集成接口
竹林司马 ML预测模块 → FastAPI 端点

路由：
    POST /api/v1/ml/predict          单股预测
    POST /api/v1/ml/predict/batch    批量预测
    GET  /api/v1/ml/health            健康检查

竹林司马 AI驱动A股技术分析引擎 · ML预测模块
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

# 添加项目根目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 延迟导入，避免启动时不必要的依赖加载
# from .predictor import MLPredictor, MLPredictionResult

router = APIRouter(prefix="/api/v1/ml", tags=["ML预测"])


# ──────────────────────────────────────────
# 请求 / 响应模型
# ──────────────────────────────────────────

class PredictRequest(BaseModel):
    """单股预测请求"""
    stock_code: str = Field(..., description="股票代码，如 600000")
    rule_score: Optional[float] = Field(None, ge=0, le=100,
                                          description="规则评分（来自AIScoreEngine），0-100")


class BatchPredictRequest(BaseModel):
    """批量预测请求"""
    stock_codes: List[str] = Field(..., min_items=1, max_items=50,
                                     description="股票代码列表，最多50只")
    rule_scores: Optional[dict] = Field(None,
                                           description="股票→规则评分字典")


class TopFeature(BaseModel):
    name: str
    importance: float


class PredictResponse(BaseModel):
    """单股预测响应"""
    stock_code: str
    date: str
    next_1d_prob_up: float = Field(..., description="次日上涨概率 [0,1]")
    next_5d_prob_up: float = Field(..., description="5日上涨概率 [0,1]")
    next_20d_prob_up: float = Field(..., description="20日上涨概率 [0,1]")
    signal: str             = Field(..., description="BUY / SELL / HOLD")
    confidence: float        = Field(..., description="置信度 [0,1]")
    risk_level: str          = Field(..., description="低 / 中 / 高 / 极高")
    risk_score: float        = Field(..., ge=0, le=1)
    predicted_max_drawdown: float = Field(..., description="预测最大回撤 %（负数）")
    predicted_var_95: float  = Field(..., description="预测 VaR 95% %（负数）")
    ml_enhanced_score: float = Field(..., description="融合评分 [0,100]")
    top_features: List[TopFeature]
    interpretation: str


class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    model_dir: str


# ──────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────

_predictor = None


def _get_predictor():
    global _predictor
    if _predictor is None:
        from .predictor import MLPredictor
        _predictor = MLPredictor()
        _predictor.load_models()
    return _predictor


@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    单股ML预测

    自动从AkShare获取最新日K数据，结合ML模型输出：
    - 多周期涨跌概率
    - 风险量化指标
    - ML增强综合评分
    """
    try:
        from .predictor import MLPredictor

        predictor = MLPredictor()
        predictor.load_models()

        # 获取日K数据
        from ..stock.data.fetcher import StockFetcher
        fetcher = StockFetcher()
        df_daily = fetcher.get_daily(request.stock_code, start_date="20230101")

        # 规则评分
        rule_score = request.rule_score

        # 预测
        result = predictor.predict(
            stock_code=request.stock_code,
            df_daily=df_daily,
            rule_score=rule_score,
        )

        return PredictResponse(
            stock_code=result.stock_code,
            date=result.date,
            next_1d_prob_up=result.next_1d_prob_up,
            next_5d_prob_up=result.next_5d_prob_up,
            next_20d_prob_up=result.next_20d_prob_up,
            signal=result.signal,
            confidence=result.confidence,
            risk_level=result.risk_level,
            risk_score=result.risk_score,
            predicted_max_drawdown=result.predicted_max_drawdown,
            predicted_var_95=result.predicted_var_95,
            ml_enhanced_score=result.ml_enhanced_score,
            top_features=[TopFeature(**f) for f in result.top_features],
            interpretation=result.interpretation,
        )

    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"依赖未安装: {e}，请运行: pip install xgboost lightgbm"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="ML模型未训练，请先运行: python -m src.core.ai.ml.trainer"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch", response_model=List[PredictResponse])
async def predict_batch(request: BatchPredictRequest):
    """
    批量ML预测

    一次最多预测50只股票，返回各股预测结果列表
    """
    from .predictor import MLPredictor
    from ..stock.data.fetcher import StockFetcher

    predictor = MLPredictor()
    predictor.load_models()
    fetcher = StockFetcher()

    results = []
    rule_scores = request.rule_scores or {}

    for code in request.stock_codes:
        try:
            df_daily = fetcher.get_daily(code, start_date="20230101")
            result = predictor.predict(
                stock_code=code,
                df_daily=df_daily,
                rule_score=rule_scores.get(code),
            )
            results.append(PredictResponse(
                stock_code=result.stock_code,
                date=result.date,
                next_1d_prob_up=result.next_1d_prob_up,
                next_5d_prob_up=result.next_5d_prob_up,
                next_20d_prob_up=result.next_20d_prob_up,
                signal=result.signal,
                confidence=result.confidence,
                risk_level=result.risk_level,
                risk_score=result.risk_score,
                predicted_max_drawdown=result.predicted_max_drawdown,
                predicted_var_95=result.predicted_var_95,
                ml_enhanced_score=result.ml_enhanced_score,
                top_features=[TopFeature(**f) for f in result.top_features],
                interpretation=result.interpretation,
            ))
        except Exception as e:
            results.append(PredictResponse(
                stock_code=code, date="N/A",
                next_1d_prob_up=0.5, next_5d_prob_up=0.5, next_20d_prob_up=0.5,
                signal="HOLD", confidence=0.0, risk_level="未知",
                risk_score=0.5, predicted_max_drawdown=0.0, predicted_var_95=0.0,
                ml_enhanced_score=0.0, top_features=[],
                interpretation=f"预测失败: {e}",
            ))

    return results


@router.get("/health", response_model=HealthResponse)
async def health():
    """ML服务健康检查"""
    model_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "models", "ml"
    )
    models_loaded = os.path.exists(model_dir) and len(os.listdir(model_dir)) > 0
    return HealthResponse(
        status="healthy" if models_loaded else "model_not_trained",
        models_loaded=models_loaded,
        model_dir=model_dir,
    )
