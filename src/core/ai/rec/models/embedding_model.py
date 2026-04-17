"""
Embedding协同过滤模型

基于矩阵分解（MF）的Neural CF实现，学习用户和物品的向量表示。
支持：训练 / 推理 / 相似度计算 / 推荐生成
"""

import logging
import os
import json
import math
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import numpy as np
    LIB_AVAILABLE = True
except ImportError:
    LIB_AVAILABLE = False


@dataclass
class EmbeddingResult:
    """Embedding推理结果"""
    item_id: str
    score: float
    reason: str


class EmbeddingCollaborativeFilter:
    """
    Embedding协同过滤（Neural Matrix Factorization）

    核心：用BPR损失学习用户向量U和物品向量V，推荐时找 dot(U, V) 最高的物品。
    """

    def __init__(
        self,
        embedding_dim: int = 64,
        learning_rate: float = 0.01,
        regularization: float = 0.01,
        num_epochs: int = 50,
        batch_size: int = 256,
        model_dir: str = "./models/embedding",
    ):
        self.embedding_dim = embedding_dim
        self.lr = learning_rate
        self.reg = regularization
        self.num_epochs = num_epochs
        self.batch_size = batch_size
        self.model_dir = model_dir

        self._user_embeddings: Dict[str, np.ndarray] = {}
        self._item_embeddings: Dict[str, np.ndarray] = {}
        self._user_bias: Dict[str, float] = {}
        self._item_bias: Dict[str, float] = {}
        self._user_ids: List[str] = []
        self._item_ids: List[str] = []
        self._is_trained = False
        os.makedirs(model_dir, exist_ok=True)

    def train(
        self,
        interactions: List[dict],
        item_features: Optional[Dict[str, List[float]]] = None,
    ) -> dict:
        """用BPR损失训练Embedding模型"""
        if not LIB_AVAILABLE:
            logger.warning("[Embedding] NumPy未安装，跳过训练")
            return {"status": "skipped"}

        logger.info(f"[Embedding] 开始训练: {len(interactions)} 交互")

        user_set = {i["user_id"] for i in interactions if i.get("user_id")}
        item_set = {i["item_id"] for i in interactions if i.get("item_id")}
        self._user_ids = list(user_set)
        self._item_ids = list(item_set)

        n_users = len(self._user_ids)
        n_items = len(self._item_ids)
        logger.info(f"[Embedding] 用户={n_users}, 物品={n_items}")

        rng = np.random.default_rng(42)
        self._user_embeddings = {
            u: rng.standard_normal(self.embedding_dim).astype(np.float32)
            for u in self._user_ids
        }
        self._item_embeddings = {
            v: rng.standard_normal(self.embedding_dim).astype(np.float32)
            for v in self._item_ids
        }
        self._user_bias = {u: 0.0 for u in self._user_ids}
        self._item_bias = {v: 0.0 for v in self._item_ids}

        # 用物品特征初始化
        if item_features:
            feat_dim = next(iter(item_features.values()), []).__len__()
            scale = min(self.embedding_dim, feat_dim)
            for iid, feat in item_features.items():
                if iid in self._item_embeddings and feat:
                    arr = np.array(feat[:scale], dtype=np.float32)
                    norm = np.linalg.norm(arr)
                    if norm > 0:
                        self._item_embeddings[iid][:scale] = arr / norm * rng.normal(0.5, 0.1)

        positive_pairs = set()
        for inter in interactions:
            uid, iid = inter.get("user_id"), inter.get("item_id")
            if uid and iid:
                positive_pairs.add((uid, iid))

        pair_list = list(positive_pairs)
        all_items = list(item_set)

        for epoch in range(self.num_epochs):
            total_loss = 0.0
            np.random.shuffle(pair_list)

            for batch_start in range(0, len(pair_list), self.batch_size):
                batch = pair_list[batch_start:batch_start + self.batch_size]
                for uid, pos_iid in batch:
                    neg_iid = all_items[np.random.randint(len(all_items))]
                    while neg_iid in {p[1] for p in positive_pairs if p[0] == uid}:
                        neg_iid = all_items[np.random.randint(len(all_items))]

                    u_vec = self._user_embeddings[uid]
                    pos_vec = self._item_embeddings[pos_iid]
                    neg_vec = self._item_embeddings[neg_iid]

                    pos_score = np.dot(u_vec, pos_vec)
                    neg_score = np.dot(u_vec, neg_vec)
                    diff = pos_score - neg_score
                    loss = -math.log(math.sigmoid(diff) + 1e-10)
                    total_loss += loss

                    grad = math.sigmoid(diff) - 1
                    lr = self.lr
                    self._user_embeddings[uid] = u_vec + lr * (grad * (pos_vec - neg_vec) - self.reg * u_vec)
                    self._item_embeddings[pos_iid] = pos_vec + lr * (grad * u_vec - self.reg * pos_vec)
                    self._item_embeddings[neg_iid] = neg_vec + lr * (-grad * u_vec - self.reg * neg_vec)

            if (epoch + 1) % 10 == 0:
                logger.info(f"[Embedding] Epoch {epoch+1}/{self.num_epochs}: loss={total_loss/max(len(pair_list),1):.4f}")

        self._is_trained = True
        self.save()
        logger.info("[Embedding] 训练完成")
        return {"status": "trained", "n_users": n_users, "n_items": n_items}

    def recommend_for_user(
        self,
        user_id: str,
        exclude_items: Optional[set] = None,
        top_k: int = 20,
    ) -> List[EmbeddingResult]:
        """为用户生成Embedding推荐"""
        if not self._is_trained or user_id not in self._user_embeddings:
            return []
        u_vec = self._user_embeddings[user_id]
        exclude = exclude_items or set()
        scores = []
        for iid in self._item_ids:
            if iid in exclude:
                continue
            i_vec = self._item_embeddings.get(iid, np.zeros(self.embedding_dim))
            score = float(np.dot(u_vec, i_vec))
            scores.append(EmbeddingResult(item_id=iid, score=score, reason="embedding_cf"))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]

    def find_similar_items(
        self,
        item_id: str,
        top_k: int = 20,
    ) -> List[EmbeddingResult]:
        """查找与指定物品最相似的物品"""
        if item_id not in self._item_embeddings:
            return []
        i_vec = self._item_embeddings[item_id]
        norm_i = np.linalg.norm(i_vec) + 1e-10
        scores = []
        for iid, vec in self._item_embeddings.items():
            if iid == item_id:
                continue
            norm_v = np.linalg.norm(vec) + 1e-10
            score = float(np.dot(i_vec, vec) / (norm_i * norm_v))
            scores.append(EmbeddingResult(item_id=iid, score=score, reason="item_similarity"))
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[:top_k]

    def get_user_embedding(self, user_id: str) -> Optional[List[float]]:
        vec = self._user_embeddings.get(user_id)
        return vec.tolist() if vec is not None else None

    def get_item_embedding(self, item_id: str) -> Optional[List[float]]:
        vec = self._item_embeddings.get(item_id)
        return vec.tolist() if vec is not None else None

    def save(self, version: Optional[str] = None):
        version = version or datetime.now().strftime("%Y%m%d")
        path = os.path.join(self.model_dir, f"embeddings_{version}.npz")
        np.savez(
            path,
            user_ids=self._user_ids,
            item_ids=self._item_ids,
            user_embeddings=np.array([self._user_embeddings.get(u, np.zeros(self.embedding_dim)) for u in self._user_ids]),
            item_embeddings=np.array([self._item_embeddings.get(v, np.zeros(self.embedding_dim)) for v in self._item_ids]),
        )
        logger.info(f"[Embedding] 已保存: {path}")

    def load(self, version: Optional[str] = None, path: Optional[str] = None):
        if not LIB_AVAILABLE:
            return
        if path:
            data_path = path
        else:
            files = [f for f in os.listdir(self.model_dir) if f.startswith("embeddings_") and f.endswith(".npz")]
            if not files:
                raise FileNotFoundError("无可用Embedding文件")
            data_path = os.path.join(self.model_dir, sorted(files)[-1])
        data = np.load(data_path, allow_pickle=True)
        self._user_ids = data["user_ids"].tolist()
        self._item_ids = data["item_ids"].tolist()
        for i, uid in enumerate(self._user_ids):
            self._user_embeddings[uid] = data["user_embeddings"][i]
        for i, iid in enumerate(self._item_ids):
            self._item_embeddings[iid] = data["item_embeddings"][i]
        self._is_trained = True
        logger.info(f"[Embedding] 已加载: {data_path}")

    @property
    def is_trained(self) -> bool:
        return self._is_trained
