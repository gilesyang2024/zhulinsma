"""
ML排序模型 - LightGBM点击率预测

用梯度提升树预测候选物品的点击概率，用于推荐排序阶段。
支持：训练 / 评估 / 在线推理 / 模型持久化
"""

import logging
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score, log_loss, ndcg_score
    LIB_AVAILABLE = True
except ImportError:
    LIB_AVAILABLE = False
    logger.warning("[CTRModel] LightGBM未安装，将使用降级逻辑")


@dataclass
class CTRPrediction:
    """CTR模型预测结果"""
    item_id: str
    ctr_score: float = 0.5
    rank_score: float = 0.0
    feature_contributions: Dict[str, float] = field(default_factory=dict)


@dataclass
class ModelPerformance:
    """模型性能报告"""
    version: str
    auc: float = 0.0
    logloss: float = 0.0
    ndcg_at_10: float = 0.0
    ndcg_at_20: float = 0.0
    total_samples: int = 0
    positive_rate: float = 0.0
    trained_at: str = ""
    training_time_seconds: float = 0.0


class CTRRankingModel:
    """
    LightGBM CTR排序模型

    核心：用点击/未点击标签训练模型，预测 p(click | user, item, context)
    排序时按点击概率从高到低排列。

    输入特征维度：
      - 用户特征：39维
      - 物品特征：16维
      - 上下文特征：12维
      - 合计：67维
    """

    FEATURE_NAMES = (
        [f"user_{i}" for i in range(39)] +
        [f"item_{i}" for i in range(16)] +
        [f"context_{i}" for i in range(12)]
    )

    def __init__(
        self,
        model_dir: str = "./models/ctr",
        version: Optional[str] = None,
    ):
        self.model_dir = model_dir
        self.version = version or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._model: Optional[Any] = None
        self._feature_importance: Optional[List[float]] = None
        self._performance: Optional[ModelPerformance] = None
        os.makedirs(model_dir, exist_ok=True)

    def train(
        self,
        train_data: dict,
        val_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> ModelPerformance:
        """训练CTR模型"""
        if not LIB_AVAILABLE:
            raise RuntimeError("LightGBM未安装，请执行: pip install lightgbm")

        logger.info("[CTRModel] 开始训练...")
        start_time = time.time()

        X_train = self._stack_features(train_data)
        y_train = np.array(train_data["y"])
        w_train = np.array(train_data.get("weights", [1.0] * len(y_train)))

        X_val = None
        y_val = None
        if val_data:
            X_val = self._stack_features(val_data)
            y_val = np.array(val_data["y"])

        default_params = {
            "objective": "binary",
            "metric": "auc",
            "boosting_type": "gbdt",
            "num_leaves": 63,
            "max_depth": 8,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 20,
            "verbose": -1,
            "random_state": 42,
        }
        if params:
            default_params.update(params)

        pos_count = int(sum(y_train))
        neg_count = len(y_train) - pos_count
        if neg_count > 0 and pos_count > 0:
            default_params["scale_pos_weight"] = neg_count / pos_count

        train_set = lgb.Dataset(X_train, label=y_train, weight=w_train)
        valid_sets = []
        if X_val is not None:
            valid_sets.append(lgb.Dataset(X_val, label=y_val, reference=train_set))

        self._model = lgb.train(
            default_params,
            train_set,
            num_boost_round=1000,
            valid_sets=valid_sets if valid_sets else [train_set],
            callbacks=[
                lgb.early_stopping(stopping_rounds=30, verbose=False),
                lgb.log_evaluation(period=100),
            ],
        )

        training_time = time.time() - start_time
        self._feature_importance = self._model.feature_importance(importance_type="gain")
        perf = self._evaluate(train_data, val_data)
        perf.version = self.version
        perf.training_time_seconds = training_time
        perf.trained_at = datetime.now().isoformat()
        self._performance = perf

        logger.info(f"[CTRModel] 训练完成: AUC={perf.auc:.4f}, "
                    f"LogLoss={perf.logloss:.4f}, 耗时={training_time:.1f}s")

        self.save()
        return perf

    def _stack_features(self, data: dict) -> np.ndarray:
        """拼接 user + item + context 特征"""
        X_u = np.array(data.get("X_user", []))
        X_i = np.array(data.get("X_item", []))
        X_c = np.array(data.get("X_context", []))

        if X_u.ndim == 1:
            X_u = X_u.reshape(1, -1)
        if X_i.ndim == 1:
            X_i = X_i.reshape(1, -1)
        if X_c.ndim == 1:
            X_c = X_c.reshape(1, -1)

        return np.hstack([X_u, X_i, X_c])

    def _evaluate(self, train_data: dict, val_data: Optional[dict]) -> ModelPerformance:
        perf = ModelPerformance(version=self.version)
        X_train = self._stack_features(train_data)
        y_train = np.array(train_data["y"])
        y_pred = self._model.predict(X_train)

        perf.auc = roc_auc_score(y_train, y_pred)
        perf.logloss = log_loss(y_train, y_pred)
        perf.total_samples = len(y_train)
        perf.positive_rate = sum(y_train) / len(y_train)

        if len(y_train) >= 10:
            try:
                perf.ndcg_at_10 = ndcg_score(
                    y_train.reshape(1, -1), y_pred.reshape(1, -1),
                    k=min(10, len(y_train))
                )
            except Exception:
                pass

        if val_data:
            X_val = self._stack_features(val_data)
            y_val = np.array(val_data["y"])
            val_pred = self._model.predict(X_val)
            val_auc = roc_auc_score(y_val, val_pred)
            logger.info(f"[CTRModel] 验证集 AUC={val_auc:.4f}")

        return perf

    def predict(
        self,
        user_features: List[List[float]],
        item_features: List[List[float]],
        context_features: Optional[List[List[float]]] = None,
    ) -> List[float]:
        """批量预测点击概率"""
        if not LIB_AVAILABLE or self._model is None:
            return [0.5] * len(item_features)

        n = len(user_features)
        if context_features is None:
            context_features = [[0.0] * 12 for _ in range(n)]

        X = self._stack_batch(user_features, item_features, context_features)
        return self._model.predict(X).tolist()

    def predict_scores(
        self,
        user_features: List[float],
        candidate_item_features: List[List[float]],
        context_features: Optional[List[float]] = None,
    ) -> List[CTRPrediction]:
        """为候选物品批量预测，返回排序结果"""
        n = len(candidate_item_features)
        user_batch = [user_features] * n
        ctx_batch = [[context_features or [0.0] * 12]] * n

        scores = self.predict(user_batch, candidate_item_features, ctx_batch)

        results = []
        for i, score in enumerate(scores):
            results.append(CTRPrediction(
                item_id=str(i),
                ctr_score=float(score),
                rank_score=float(score),
            ))

        results.sort(key=lambda x: x.ctr_score, reverse=True)
        return results

    def _stack_batch(
        self,
        user_feats: List[List[float]],
        item_feats: List[List[float]],
        ctx_feats: List[List[float]],
    ) -> np.ndarray:
        return np.hstack([
            np.array(user_feats),
            np.array(item_feats),
            np.array(ctx_feats),
        ])

    def save(self, path: Optional[str] = None) -> str:
        """保存模型"""
        if not LIB_AVAILABLE or self._model is None:
            raise RuntimeError("模型未训练")

        path = path or os.path.join(self.model_dir, f"ctr_model_{self.version}.txt")
        self._model.save_model(path)

        meta = {
            "version": self.version,
            "performance": {
                "auc": self._performance.auc if self._performance else 0,
                "logloss": self._performance.logloss if self._performance else 0,
                "trained_at": self._performance.trained_at if self._performance else "",
                "total_samples": self._performance.total_samples if self._performance else 0,
            },
            "feature_importance": (
                self._feature_importance.tolist()
                if hasattr(self._feature_importance, "tolist")
                else self._feature_importance
            ) if self._feature_importance else [],
        }
        with open(path.replace(".txt", "_meta.json"), "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        logger.info(f"[CTRModel] 模型已保存: {path}")
        return path

    def load(self, version: Optional[str] = None, path: Optional[str] = None):
        """加载模型"""
        if not LIB_AVAILABLE:
            return

        if path:
            model_path = path
        else:
            files = [
                f for f in os.listdir(self.model_dir)
                if f.startswith("ctr_model_") and f.endswith(".txt")
            ]
            if not files:
                raise FileNotFoundError("无可用模型文件")
            model_path = os.path.join(self.model_dir, sorted(files)[-1])

        self._model = lgb.Booster(model_file=model_path)

        meta_path = model_path.replace(".txt", "_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self.version = meta.get("version", "unknown")
            self._feature_importance = meta.get("feature_importance", [])

        logger.info(f"[CTRModel] 模型已加载: {model_path}")

    def get_feature_importance(self, top_k: int = 20) -> List[Tuple[str, float]]:
        """获取特征重要性"""
        if self._feature_importance is None:
            return []
        pairs = list(zip(self.FEATURE_NAMES, self._feature_importance))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:top_k]

    @property
    def is_trained(self) -> bool:
        return self._model is not None
