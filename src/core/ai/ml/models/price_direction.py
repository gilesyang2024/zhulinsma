#!/usr/bin/env python3
"""
PriceDirectionModel - 涨跌方向预测模型
基于 XGBoost 分类器，预测未来N日涨跌概率

竹林司马 AI驱动A股技术分析引擎 · ML预测模块
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ──────────────────────────────────────────
# 配置（sklearn HistGradientBoosting 等效参数）
# ──────────────────────────────────────────
HGB_PARAMS = {
    "learning_rate":     0.05,
    "max_iter":          300,
    "max_leaf_nodes":    63,      # 等效 max_depth=6
    "max_depth":         6,       # sklearn 兼容
    "min_samples_leaf":  10,      # 等效 min_child_weight=5
    "l2_regularization": 1.0,     # reg_lambda
    "random_state":      42,
    "early_stopping":    True,
    "validation_fraction": 0.1,
    "n_iter_no_change":  30,
    "verbose":           0,
}

FEATURE_EXCLUDE = [
    "stock_code", "date", "close",
    "label_next_1d", "label_next_5d", "label_next_20d",
    "return_next_1d", "return_next_5d", "return_next_20d",
    "max_drawdown_20d", "var_95_20d",
]


@dataclass
class DirectionPrediction:
    """涨跌预测结果"""
    stock_code: str
    horizon: int
    prob_up: float       # 上涨概率 [0, 1]
    prob_down: float      # 下跌概率
    signal: str           # BUY / SELL / HOLD
    confidence: float     # 置信度 = abs(prob_up - 0.5) * 2
    top_features: List[Dict[str, Any]]  # 特征重要性 Top5


class PriceDirectionModel:
    """
    涨跌方向预测模型（XGBoost）

    支持多周期预测：次日、5日、20日
    模型文件持久化：models/price_direction_h{N}.pkl

    使用方式：
        model = PriceDirectionModel()
        model.fit(X_train, y_train_next1d)
        pred = model.predict(X_latest)
    """

    def __init__(self, model_dir: str = "models/ml"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self._models: Dict[int, Any] = {}   # horizon -> XGBClassifier
        self._feature_names: List[str] = []
        self._feature_importance: Dict[int, np.ndarray] = {}

    def fit(
        self,
        df_features: pd.DataFrame,
        horizons: List[int] = [1, 5, 20],
        val_size: float = 0.2,
        early_stopping_rounds: int = 30,
    ) -> Dict[int, Dict[str, float]]:
        """
        训练多周期涨跌预测模型

        参数:
            df_features: 完整特征+标签DataFrame（来自 MLDataPipeline）
            horizons:    预测周期列表
            val_size:    验证集比例（时序划分，不用随机打乱）
            early_stopping_rounds: 早停轮数

        返回:
            Dict[horizon, Dict[metric, value]] — 验证集评估指标
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn 未安装，请运行: pip install scikit-learn")

        # 特征列（去除非特征列）
        feature_cols = [c for c in df_features.columns if c not in FEATURE_EXCLUDE]
        self._feature_names = feature_cols

        X = df_features[feature_cols].values
        n = len(X)
        split_idx = int(n * (1 - val_size))

        results = {}
        for h in horizons:
            label_col = f"label_next_{h}d"
            if label_col not in df_features.columns:
                print(f"[PriceDirectionModel] 跳过 horizon={h}，缺少标签列")
                continue

            y = df_features[label_col].values
            # 时序划分
            X_tr, X_val = X[:split_idx], X[split_idx:]
            y_tr, y_val = y[:split_idx], y[split_idx:]

            # 处理NaN
            X_tr = np.nan_to_num(X_tr, nan=0.0)
            X_val = np.nan_to_num(X_val, nan=0.0)

            params = HGB_PARAMS.copy()
            n_iter = params.pop("max_iter")
            val_frac = params.pop("validation_fraction")
            n_no_chg = params.pop("n_iter_no_change")
            verbose  = params.pop("verbose")

            model = HistGradientBoostingClassifier(
                **params,
                max_iter=n_iter,
                validation_fraction=val_frac,
                n_iter_no_change=n_no_chg,
                verbose=verbose,
            )
            model.fit(X_tr, y_tr)

            # 验证集评估
            y_pred = model.predict_proba(X_val)[:, 1]
            auc    = self._auc(y_val, y_pred)
            acc    = self._accuracy(y_val, (y_pred > 0.5).astype(int))

            results[h] = {"auc": round(auc, 4), "accuracy": round(acc, 4)}
            print(f"  horizon={h}d: AUC={auc:.4f}  Accuracy={acc:.4f}")

            # 保存模型
            self._models[h]   = model
            # HistGradientBoostingClassifier 1.6+ 移除了 feature_importances_
            # 改用 permutation importance 动态计算
            try:
                self._feature_importance[h] = model.feature_importances_
            except AttributeError:
                self._feature_importance[h] = np.zeros(len(feature_cols))

            # 持久化
            save_path = os.path.join(self.model_dir, f"price_direction_h{h}.pkl")
            joblib.dump(model, save_path)
            joblib.dump(feature_cols, os.path.join(self.model_dir, f"feature_names_h{h}.pkl"))
            print(f"  ✓ 模型已保存: {save_path}")

        return results

    def predict(self, X: np.ndarray, horizon: int = 1) -> DirectionPrediction:
        """
        推理：预测涨跌方向概率

        参数:
            X:       特征数组（1行或N行）
            horizon: 预测周期

        返回:
            DirectionPrediction
        """
        if horizon not in self._models:
            raise ValueError(f"未训练的模型 horizon={horizon}，请先调用 fit()")

        X = np.atleast_2d(X)
        X = np.nan_to_num(X, nan=0.0)

        model = self._models[horizon]
        probs = model.predict_proba(X)[0]   # 取第一行
        prob_up = float(probs[1])
        prob_down = float(probs[0])
        confidence = abs(prob_up - 0.5) * 2

        # 信号
        if prob_up > 0.58:
            signal = "BUY"
        elif prob_up < 0.42:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Top特征重要性
        imp = self._feature_importance.get(horizon)
        feat_names = self._feature_names
        top_features = []
        if imp is not None:
            top_idx = np.argsort(imp)[::-1][:5]
            top_features = [
                {"name": feat_names[i], "importance": round(float(imp[i]), 4)}
                for i in top_idx
            ]

        return DirectionPrediction(
            stock_code="UNKNOWN",
            horizon=horizon,
            prob_up=round(prob_up, 4),
            prob_down=round(prob_down, 4),
            signal=signal,
            confidence=round(confidence, 4),
            top_features=top_features,
        )

    def predict_multi_horizon(
        self, X: np.ndarray, horizons: List[int] = [1, 5, 20]
    ) -> Dict[int, DirectionPrediction]:
        """多周期预测"""
        return {h: self.predict(X, h) for h in horizons if h in self._models}

    def load(self, horizons: List[int] = [1, 5, 20]):
        """从磁盘加载已训练模型"""
        for h in horizons:
            model_path = os.path.join(self.model_dir, f"price_direction_h{h}.pkl")
            feat_path = os.path.join(self.model_dir, f"feature_names_h{h}.pkl")
            if os.path.exists(model_path) and os.path.exists(feat_path):
                self._models[h] = joblib.load(model_path)
                self._feature_names = joblib.load(feat_path)
                try:
                    self._feature_importance[h] = self._models[h].feature_importances_
                except AttributeError:
                    n_feat = len(self._feature_names) if self._feature_names else 0
                    self._feature_importance[h] = np.zeros(n_feat)
                print(f"[PriceDirectionModel] 已加载 horizon={h}d 模型")
            else:
                print(f"[PriceDirectionModel] 缺少 horizon={h}d 模型文件")

    @staticmethod
    def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
        """计算AUC（手写实现，避免sklearn依赖）"""
        n = len(y_true)
        pos = y_true == 1
        neg = ~pos
        if pos.sum() == 0 or neg.sum() == 0:
            return 0.5
        score_pos = y_score[pos]
        score_neg = y_score[neg]
        total = 0.0
        for sp in score_pos:
            for sn in score_neg:
                if sp > sn:
                    total += 1
                elif sp == sn:
                    total += 0.5
        return total / (len(score_pos) * len(score_neg))

    @staticmethod
    def _accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        return float(np.mean(y_true == y_pred))
