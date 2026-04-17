"""
A/B测试框架

支持：实验配置 / 用户分流 / 指标收集 / 效果分析
"""

import logging
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Experiment:
    """A/B实验配置"""
    name: str
    traffic_percent: float = 0.10          # 流量占比（0-1）
    variants: List[str] = field(default_factory=lambda: ["control", "treatment"])
    default_variant: str = "control"
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricRecord:
    """指标记录"""
    experiment: str
    variant: str
    user_id: str
    metric_name: str
    value: float
    timestamp: str = ""


class ABSplitter:
    """
    用户分流器

    特性：
    - 确定性分流（同一用户始终分到同一组）
    - 可配置流量比例
    - 支持多实验正交分层
    - 多实验重叠兼容
    """

    def __init__(
        self,
        hash_salt: str = "zhulinsma_rec_v1",
    ):
        self.hash_salt = hash_salt
        self._experiments: Dict[str, Experiment] = {}
        self._user_assignments: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._layer_version: int = 1

    def register_experiment(self, exp: Experiment):
        """注册实验"""
        self._experiments[exp.name] = exp
        logger.info(f"[ABSplitter] 注册实验: {exp.name} ({exp.traffic_percent*100:.0f}%流量)")

    def get_variant(
        self,
        experiment_name: str,
        user_id: str,
    ) -> Optional[str]:
        """
        获取用户在指定实验中的分组

        确定性分流：hash(user_id + salt + experiment) % 100 < traffic_percent → treatment
        """
        exp = self._experiments.get(experiment_name)
        if not exp or not exp.enabled:
            return None

        if user_id in self._user_assignments and experiment_name in self._user_assignments[user_id]:
            return self._user_assignments[user_id][experiment_name]

        hash_str = f"{user_id}:{self.hash_salt}:{experiment_name}"
        hash_val = int(hashlib.md5(hash_str.encode()).hexdigest(), 16)
        bucket = (hash_val % 10000) / 10000.0

        variant = exp.variants[1] if bucket < exp.traffic_percent else exp.default_variant
        self._user_assignments[user_id][experiment_name] = variant

        return variant

    def get_all_variants(
        self,
        user_id: str,
    ) -> Dict[str, str]:
        """获取用户所有实验的分组"""
        return {
            name: self.get_variant(name, user_id) or exp.default_variant
            for name, exp in self._experiments.items()
            if exp.enabled
        }

    def is_in_experiment(
        self,
        experiment_name: str,
        user_id: str,
    ) -> bool:
        """判断用户是否参与实验"""
        variant = self.get_variant(experiment_name, user_id)
        return variant is not None

    def set_variant_override(
        self,
        experiment_name: str,
        user_id: str,
        variant: str,
    ):
        """手动覆盖用户分组（用于测试）"""
        self._user_assignments[user_id][experiment_name] = variant

    def list_experiments(self) -> List[Experiment]:
        return list(self._experiments.values())

    def get_experiment(self, name: str) -> Optional[Experiment]:
        return self._experiments.get(name)


class MetricsCollector:
    """
    A/B实验指标收集器

    收集并汇总各实验分组的指标，用于计算实验效果。
    """

    def __init__(self):
        self._records: List[MetricRecord] = []
        self._aggregates: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        )
        self._counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )

    def record(
        self,
        experiment: str,
        variant: str,
        user_id: str,
        metric_name: str,
        value: float,
        timestamp: Optional[str] = None,
    ):
        """记录一条指标"""
        record = MetricRecord(
            experiment=experiment,
            variant=variant,
            user_id=user_id,
            metric_name=metric_name,
            value=value,
            timestamp=timestamp or datetime.now().isoformat(),
        )
        self._records.append(record)

        self._aggregates[experiment][variant][metric_name]["sum"] += value
        self._aggregates[experiment][variant][metric_name]["sq_sum"] += value * value
        self._counts[experiment][variant][metric_name] += 1

    def get_variant_stats(
        self,
        experiment: str,
        metric_name: str,
    ) -> Dict[str, dict]:
        """获取指定实验指定指标的分组统计"""
        if experiment not in self._aggregates:
            return {}

        results = {}
        for variant, metrics in self._aggregates[experiment].items():
            if metric_name not in metrics:
                continue
            s = metrics[metric_name]
            n = self._counts[experiment][variant].get(metric_name, 0)
            if n == 0:
                continue
            mean = s["sum"] / n
            variance = (s["sq_sum"] / n) - (mean * mean)
            std = max(0.0, variance) ** 0.5

            results[variant] = {
                "count": n,
                "mean": round(mean, 6),
                "std": round(std, 6),
                "sum": round(s["sum"], 4),
            }

        return results

    def compute_lift(
        self,
        experiment: str,
        metric_name: str,
        treatment_variant: str = "treatment",
        control_variant: str = "control",
    ) -> Optional[dict]:
        """计算Treatment相对Control的提升"""
        stats = self.get_variant_stats(experiment, metric_name)

        treatment = stats.get(treatment_variant, {})
        control = stats.get(control_variant, {})

        if not treatment or not control:
            return None

        t_mean = treatment.get("mean", 0)
        c_mean = control.get("mean", 0)

        if c_mean == 0:
            return None

        lift = (t_mean - c_mean) / c_mean
        lift_pct = lift * 100

        # 简单Z检验（不严谨，适合快速迭代）
        se = ((treatment.get("std", 0) ** 2 / max(treatment["count"], 1)) +
              (control.get("std", 0) ** 2 / max(control["count"], 1))) ** 0.5
        z_score = (t_mean - c_mean) / se if se > 0 else 0.0

        return {
            "treatment_mean": round(t_mean, 6),
            "control_mean": round(c_mean, 6),
            "lift": round(lift, 6),
            "lift_pct": f"{lift_pct:+.2f}%",
            "z_score": round(z_score, 3),
            "significant": abs(z_score) >= 1.96,
            "p95_significant": abs(z_score) >= 1.645,
            "treatment_n": treatment["count"],
            "control_n": control["count"],
        }

    def get_all_experiments(self) -> List[str]:
        return list(self._aggregates.keys())

    def get_summary(self) -> dict:
        """获取所有实验汇总"""
        summary = {}
        for exp in self._aggregates.keys():
            exp_obj = getattr(self, "_experiments", {}).get(exp)
            summary[exp] = {
                "variants": list(self._aggregates[exp].keys()),
                "metrics": {
                    m: self.get_variant_stats(exp, m)
                    for m in self._aggregates[exp].get(list(self._aggregates[exp].keys())[0], {}).keys()
                },
            }
        return summary

    def clear(self):
        """清空历史数据（切换实验时用）"""
        self._records.clear()
        self._aggregates.clear()
        self._counts.clear()
        logger.info("[MetricsCollector] 数据已清空")


# ============================================================
# 预设推荐系统常用实验配置
# ============================================================

DEFAULT_EXPERIMENTS = [
    Experiment(
        name="ranking_strategy_v2",
        traffic_percent=0.20,
        variants=["control", "treatment"],
        default_variant="control",
        description="ML排序 vs 规则排序",
        metadata={
            "control": {"description": "规则加权融合排序"},
            "treatment": {"description": "ML(CTR)模型排序"},
        },
    ),
    Experiment(
        name="diversity_balance",
        traffic_percent=0.30,
        variants=["low_diversity", "high_diversity"],
        default_variant="low_diversity",
        description="多样性参数调整",
        metadata={
            "low_diversity": {"lambda": 0.3},
            "high_diversity": {"lambda": 0.8},
        },
    ),
    Experiment(
        name="cold_start_strategy",
        traffic_percent=0.50,
        variants=["rule_based", "embedding_based"],
        default_variant="rule_based",
        description="冷启动策略实验",
    ),
]
