#!/usr/bin/env python3
"""
RiskQuantModel - 风险量化模型
基于 LightGBM 回归器，预测未来N日最大回撤和VaR

竹林司马 AI驱动A股技术分析引擎 · ML预测模块
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


HGB_PARAMS = {
    "loss":              "absolute_error",
    "learning_rate":     0.05,
    "max_iter":         200,
    "max_leaf_nodes":   31,       # 等效 num_leaves
    "max_depth":        5,
    "min_samples_leaf": 10,
    "l2_regularization": 1.0,
    "random_state":      42,
    "early_stopping":   True,
    "validation_fraction": 0.1,
    "n_iter_no_change":  30,
    "verbose":          0,
}

FEATURE_EXCLUDE = [
    "stock_code", "date", "close",
    "label_next_1d", "label_next_5d", "label_next_20d",
    "return_next_1d", "return_next_5d", "return_next_20d",
    "max_drawdown_20d", "var_95_20d",
]


@dataclass
class RiskPrediction:
    """风险预测结果"""
    stock_code: str
    predicted_max_drawdown: float   # 预测最大回撤（%，负数）
    predicted_var_95: float         # 预测VaR 95%（%，负数）
    risk_level: str                  # 低 / 中 / 高 / 极高
    risk_score: float                # 量化风险评分 [0, 1]


class RiskQuantModel:
    """
    风险量化模型（sklearn HistGradientBoostingRegressor）

    预测目标：
    - max_drawdown_20d：未来20日最大回撤
    - var_95_20d：未来20日 95% VaR

    使用方式：
        model = RiskQuantModel()
        model.fit(df_features)
        risk = model.predict(X_latest)
    """

    def __init__(self, model_dir: str = "models/ml"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        self._model_dd: Optional[Any] = None
        self._model_var: Optional[Any] = None
        self._feature_names: list = []

    def fit(
        self,
        df_features: pd.DataFrame,
        val_size: float = 0.2,
    ) -> Dict[str, float]:
        """
        训练风险量化模型

        参数:
            df_features: 完整特征+标签DataFrame
            val_size:    验证集比例

        返回:
            Dict 验证集 MAE 指标
        """
        if not HAS_SKLEARN:
            raise ImportError("scikit-learn 未安装，请运行: pip install scikit-learn")

        feature_cols = [c for c in df_features.columns if c not in FEATURE_EXCLUDE]
        self._feature_names = feature_cols

        X = df_features[feature_cols].values
        n = len(X)
        split_idx = int(n * (1 - val_size))

        X_tr = np.nan_to_num(X[:split_idx], nan=0.0)
        X_val = np.nan_to_num(X[split_idx:], nan=0.0)

        results = {}

        for target_col in ["max_drawdown_20d", "var_95_20d"]:
            if target_col not in df_features.columns:
                continue
            y_tr  = df_features[target_col].values[:split_idx]
            y_val = df_features[target_col].values[split_idx:]

            # 过滤NaN
            valid_tr  = ~np.isnan(y_tr)
            valid_val = ~np.isnan(y_val)
            if valid_tr.sum() < 30:
                continue

            params = HGB_PARAMS.copy()
            n_iter = params.pop("max_iter")
            val_frac = params.pop("validation_fraction")
            n_no_chg = params.pop("n_iter_no_change")
            verbose  = params.pop("verbose")

            model = HistGradientBoostingRegressor(
                **params,
                max_iter=n_iter,
                validation_fraction=val_frac,
                n_iter_no_change=n_no_chg,
                verbose=verbose,
            )
            model.fit(X_tr[valid_tr], y_tr[valid_tr])

            y_pred = model.predict(X_val[valid_val])
            mae    = float(np.mean(np.abs(y_pred - y_val[valid_val])))

            results[target_col] = round(mae, 4)
            print(f"  {target_col}: MAE={mae:.4f}")

            if "max_drawdown" in target_col:
                self._model_dd = model
            else:
                self._model_var = model

            save_path = os.path.join(self.model_dir, f"risk_{target_col}.pkl")
            joblib.dump(model, save_path)
            print(f"  ✓ 已保存: {save_path}")

        return results

    def predict(self, X: np.ndarray) -> RiskPrediction:
        """
        推理：预测风险指标

        参数:
            X: 特征数组（1行或N行）

        返回:
            RiskPrediction
        """
        X = np.atleast_2d(X)
        X = np.nan_to_num(X, nan=0.0)

        pred_dd  = float(self._model_dd.predict(X)[0])  if self._model_dd  else 0.0
        pred_var = float(self._model_var.predict(X)[0]) if self._model_var else 0.0

        # 风险评分（综合）
        risk_score = 0.0
        if pred_dd < -10:
            risk_score += 0.4
        elif pred_dd < -5:
            risk_score += 0.2
        if pred_var < -5:
            risk_score += 0.4
        elif pred_var < -2:
            risk_score += 0.2
        risk_score = min(1.0, max(0.0, risk_score))

        # 风险等级
        if risk_score >= 0.7:
            risk_level = "极高"
        elif risk_score >= 0.5:
            risk_level = "高"
        elif risk_score >= 0.3:
            risk_level = "中"
        else:
            risk_level = "低"

        return RiskPrediction(
            stock_code="UNKNOWN",
            predicted_max_drawdown=round(pred_dd, 2),
            predicted_var_95=round(pred_var, 2),
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
        )

    def load(self):
        """从磁盘加载已训练模型"""
        for target in ["max_drawdown_20d", "var_95_20d"]:
            path = os.path.join(self.model_dir, f"risk_{target}.pkl")
            if os.path.exists(path):
                model = joblib.load(path)
                if "max_drawdown" in target:
                    self._model_dd = model
                else:
                    self._model_var = model
                print(f"[RiskQuantModel] 已加载: {target}")
