# MLConfig - ML模块超参数配置
# 竹林司马 AI驱动A股技术分析引擎 · ML预测模块

from dataclasses import dataclass
from typing import List


@dataclass
class MLConfig:
    """ML模块全局配置"""

    # 特征工程
    lookback: int = 120          # 特征计算回看天数
    warmup_days: int = 60       # warmup丢弃天数

    # 涨跌预测
    horizons: List[int] = None   # 预测周期（天），默认 [1, 5, 20]

    def __post_init__(self):
        if self.horizons is None:
            self.horizons = [1, 5, 20]

    # XGBoost 超参数
    xgb_max_depth: int = 6
    xgb_lr: float = 0.05
    xgb_n_estimators: int = 300
    xgb_subsample: float = 0.8
    xgb_colsample: float = 0.8
    xgb_scale_pos_weight: float = 1.2   # A股加权上涨

    # LightGBM 超参数
    lgb_max_depth: int = 5
    lgb_lr: float = 0.05
    lgb_n_estimators: int = 200
    lgb_num_leaves: int = 31
    lgb_subsample: float = 0.8
    lgb_colsample: float = 0.8

    # 融合权重
    rule_weight: float = 0.7      # 规则评分权重
    ml_weight: float = 0.3        # ML预测权重

    # 模型目录
    model_dir: str = "models/ml"

    # 信号阈值
    signal_buy_threshold: float = 0.58   # prob_up > 0.58 → BUY
    signal_sell_threshold: float = 0.42   # prob_up < 0.42 → SELL
