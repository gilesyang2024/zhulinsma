#!/usr/bin/env python3
"""
MLPredictor - 推理引擎
单股实时预测入口，整合涨跌模型 + 风险模型 + AIScoreEngine

竹林司马 AI驱动A股技术分析引擎 · ML预测模块

使用方式：
    predictor = MLPredictor()
    result = predictor.predict("600000", df_daily)
    print(result)
"""

from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# 添加项目根目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from feature_engineering import MLFeatureEngine
from models.price_direction import PriceDirectionModel
from models.risk_quant import RiskQuantModel


MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "models", "ml"
)

FEATURE_EXCLUDE = [
    "stock_code", "date", "close",
    "label_next_1d", "label_next_5d", "label_next_20d",
    "return_next_1d", "return_next_5d", "return_next_20d",
    "max_drawdown_20d", "var_95_20d",
]


@dataclass
class MLPredictionResult:
    """ML预测完整结果"""
    stock_code: str
    date: str
    # 涨跌概率
    next_1d_prob_up: float
    next_5d_prob_up: float
    next_20d_prob_up: float
    # 信号
    signal: str          # 综合ML信号
    confidence: float
    # 风险
    risk_level: str
    risk_score: float
    predicted_max_drawdown: float
    predicted_var_95: float
    # 融合评分（ML 30% + 规则 70%）
    ml_enhanced_score: float
    # Top特征
    top_features: List[Dict[str, Any]]
    # 解读
    interpretation: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


class MLPredictor:
    """
    ML推理引擎

    端到端单股预测，整合：
    1. 涨跌方向预测（XGBoost）
    2. 风险量化（LightGBM）
    3. 融合评分（ML + 规则）

    支持：
    - 模型加载（从磁盘）
    - 实时推理（需要df_daily）
    - 与现有AIScoreEngine集成
    """

    def __init__(self, model_dir: str = None):
        self.model_dir = model_dir or MODEL_DIR
        self.feature_engine = MLFeatureEngine(lookback=120)

        # 涨跌方向模型
        self.direction_model = PriceDirectionModel(model_dir=self.model_dir)
        # 风险量化模型
        self.risk_model = RiskQuantModel(model_dir=self.model_dir)

        self._loaded = False

    def load_models(self, horizons: List[int] = [1, 5, 20]):
        """从磁盘加载已训练模型"""
        if os.path.exists(self.model_dir):
            self.direction_model.load(horizons=horizons)
            self.risk_model.load()
            self._loaded = True
            print(f"[MLPredictor] 模型加载完成")
        else:
            print(f"[MLPredictor] 模型目录不存在: {self.model_dir}，请先运行训练")

    def predict(
        self,
        stock_code: str,
        df_daily: pd.DataFrame,
        horizons: List[int] = [1, 5, 20],
        rule_score: Optional[float] = None,   # 来自AIScoreEngine的规则评分
    ) -> MLPredictionResult:
        """
        实时预测（单股）

        参数:
            stock_code:  股票代码
            df_daily:    最新日K DataFrame（date/open/high/low/close/volume）
            horizons:    预测周期
            rule_score:  规则评分（0-100），来自AIScoreEngine

        返回:
            MLPredictionResult
        """
        if not self._loaded:
            self.load_models(horizons)

        # ── Step 1: 特征工程 ─────────────────────
        df_feat = self.feature_engine.build_features(
            df_daily,
            stock_code=stock_code,
        )

        # 取最后一行作为当前特征
        latest = df_feat.iloc[-1:]
        date_str = str(latest["date"].values[0])

        # 提取特征向量
        feature_cols = [c for c in df_feat.columns if c not in FEATURE_EXCLUDE]
        X = latest[feature_cols].values

        # ── Step 2: 涨跌方向预测 ─────────────────
        direction_preds = self.direction_model.predict_multi_horizon(X, horizons)
        prob_1d = direction_preds.get(1, None)
        prob_5d = direction_preds.get(5, None)
        prob_20d = direction_preds.get(20, None)

        # ── Step 3: 风险量化 ──────────────────────
        try:
            risk_pred = self.risk_model.predict(X)
            risk_pred.stock_code = stock_code
        except Exception:
            risk_pred = None

        # ── Step 4: 信号融合 ─────────────────────
        probs = {1: prob_1d, 5: prob_5d, 20: prob_20d}
        signals = {h: p.signal for h, p in probs.items() if p}

        # 综合信号：少数服从多数
        if not signals:
            final_signal = "HOLD"
            final_conf   = 0.0
        else:
            buy_count  = sum(1 for s in signals.values() if s == "BUY")
            sell_count = sum(1 for s in signals.values() if s == "SELL")
            if buy_count >= 2:
                final_signal = "BUY"
            elif sell_count >= 2:
                final_signal = "SELL"
            else:
                final_signal = "HOLD"
            final_conf = float(np.mean([p.confidence for p in probs.values() if p]))

        # ── Step 5: 融合评分 ─────────────────────
        valid_probs = [p.prob_up for p in probs.values() if p is not None]
        ml_avg_prob = float(np.mean(valid_probs)) if valid_probs else 0.5
        # ML概率[0,1] → 转换为评分[0,100]
        ml_score = ml_avg_prob * 100
        if rule_score is not None:
            ml_enhanced_score = rule_score * 0.7 + ml_score * 0.3
        else:
            ml_enhanced_score = ml_score

        # ── Step 6: Top特征 ───────────────────────
        top_features = []
        if prob_1d and prob_1d.top_features:
            top_features = prob_1d.top_features[:5]

        # ── Step 7: 解读文本 ───────────────────────
        interp = self._interpret(
            stock_code, final_signal, probs, risk_pred, ml_enhanced_score
        )

        return MLPredictionResult(
            stock_code=stock_code,
            date=date_str,
            next_1d_prob_up=round(prob_1d.prob_up, 4) if prob_1d else 0.5,
            next_5d_prob_up=round(prob_5d.prob_up, 4) if prob_5d else 0.5,
            next_20d_prob_up=round(prob_20d.prob_up, 4) if prob_20d else 0.5,
            signal=final_signal,
            confidence=round(final_conf, 4),
            risk_level=risk_pred.risk_level if risk_pred else "中",
            risk_score=risk_pred.risk_score if risk_pred else 0.5,
            predicted_max_drawdown=risk_pred.predicted_max_drawdown if risk_pred else 0.0,
            predicted_var_95=risk_pred.predicted_var_95 if risk_pred else 0.0,
            ml_enhanced_score=round(ml_enhanced_score, 2),
            top_features=top_features,
            interpretation=interp,
        )

    @staticmethod
    def _interpret(
        stock_code: str,
        signal: str,
        probs: Dict[int, Any],
        risk: Any,
        ml_score: float,
    ) -> str:
        parts = [f"代码：{stock_code}"]
        parts.append(f"ML综合评分：{ml_score:.0f}/100")
        parts.append(f"信号：{signal}")

        prob_parts = []
        for h, p in probs.items():
            if p:
                prob_parts.append(f"{h}日涨={p.prob_up:.0%}")
        if prob_parts:
            parts.append(" | ".join(prob_parts))

        if risk:
            parts.append(f"风险等级：{risk.risk_level}（预测最大回撤{risk.predicted_max_drawdown:.1f}%）")

        parts.append("本预测仅供参考，不构成投资建议。")
        return " ".join(parts)


# ──────────────────────────────────────────
# 便捷入口（用于FastAPI直接调用）
# ──────────────────────────────────────────

_predictor_instance: Optional[MLPredictor] = None


def get_predictor() -> MLPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MLPredictor()
        _predictor_instance.load_models()
    return _predictor_instance
