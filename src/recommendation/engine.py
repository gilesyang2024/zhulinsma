"""
推荐引擎总编排器 - RecommendationEngine

统一调度所有推荐子模块：
- 协同过滤 (ItemCF / UserCF)
- Content-Based 推荐
- 热度排行 (Trending)
- 多策略融合排序 (Ranking)
- 多级缓存 (Cache)
- 冷启动兜底

是推荐系统的唯一对外入口。
"""

import time
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum

from .collaborative import ItemCollaborativeFilter, UserCollaborativeFilter
from .content_based import ContentBasedRecommender
from .ranking import RankingService
from .trending import TrendingService, TrendingWindow
from .cache import RecommendationCache, COLD_START_RECOMMENDATIONS
from .models import RecommendationScene

logger = logging.getLogger(__name__)


class EngineMode(str, Enum):
    """引擎运行模式"""
    FULL = "full"              # 全量模式：所有通道都参与
    FAST = "fast"              # 快速模式：仅热度 + 缓存
    OFFLINE = "offline"        # 离线模式：仅预计算结果


class RecommendationEngine:
    """
    推荐系统总引擎
    
    架构设计：
    
    ┌──────────────┐     ┌─────────────┐     ┌────────────┐
    │   ItemCF     │     │   UserCF    │     │ Content   │
    │ (协同过滤)   │     │ (协同过滤)  │     │ (内容推荐) │
    └──────┬───────┘     └──────┬──────┘     └─────┬─────┘
           │                    │                   │
           └────────────────────┼───────────────────┘
                                ▼
                      ┌──────────────────┐
                      │  Ranking Service  │
                      │ (融合排序+多样性)  │
                      └────────┬─────────┘
                               ▼
                      ┌──────────────────┐
                      │ Trending Service │
                      │ (热度加权)       │
                      └────────┬─────────┘
                               ▼
                      ┌──────────────────┐
                      │ Cache Layer      │
                      │ (L1内存 + L2Redis)│
                      └────────┬─────────┘
                               ▼
                       用户获得最终推荐列表
    
    使用方式:
        engine = RecommendationEngine()
        engine.load_from_interactions(interactions_data)  # 加载交互数据
        engine.build_all_models()                          # 构建模型
        results = engine.recommend(user_id="xxx")          # 生成推荐
    """
    
    def __init__(
        self,
        mode: EngineMode = EngineMode.FULL,
        cache_ttl_seconds: int = 300,
        default_limit: int = 20,
    ):
        self.mode = mode
        self.default_limit = default_limit
        
        # 初始化子模块
        self.item_cf = ItemCollaborativeFilter(
            top_k=50,
            similarity_method="iuf_cosine",
            time_decay=True,
            decay_half_life=7.0,
        )
        self.user_cf = UserCollaborativeFilter(
            top_k_neighbors=50,
            min_overlap=3,
        )
        self.content_based = ContentBasedRecommender()
        self.ranking = RankingService(
            item_cf_weight=0.35,
            content_weight=0.25,
            trending_weight=0.20,
            diversity_lambda=0.7,
        )
        self.trending = TrendingService(
            default_window=TrendingWindow.DAILY,
        )
        self.cache = RecommendationCache()
        
        # 状态标志
        self._is_built = False
        self._built_at: Optional[datetime] = None
        self._total_items = 0
        self._total_users = 0
        self._total_interactions = 0

    # ================================================================
    # 数据加载与模型构建
    # ================================================================

    def load_from_interactions(self, interactions: List[dict]):
        """加载用户交互数据到各算法模块
        
        Args:
            interactions: [{"user_id", "item_id", "interaction_type", 
                           "weight", "timestamp"}, ...]
        """
        logger.info(f"[Engine] 开始加载 {len(interactions)} 条交互记录...")
        
        user_item_map: Dict[str, Dict[str, float]] = defaultdict(dict)
        item_feature_map: Dict[str, dict] = {}
        
        for inter in interactions:
            uid = inter["user_id"]
            iid = inter["item_id"]
            inter_type = inter.get("interaction_type", "view")
            weight = inter.get("weight")
            timestamp = inter.get("timestamp")
            
            # ItemCF / UserCF 数据
            self.item_cf.add_interaction(uid, iid, inter_type, weight, timestamp)
            
            w = weight or 1.0
            user_item_map[uid][iid] = max(user_item_map[uid].get(iid, 0), w)
            
            # Trending 数据
            meta = inter.get("metadata", {})
            category = meta.get("category")
            self.trending.register_item(iid, meta)
            self.trending.record_event(iid, inter_type, weight, timestamp, category)
            
            # 记录物品元信息
            if iid not in item_feature_map:
                item_feature_map[iid] = {
                    "item_id": iid,
                    "tags": meta.get("tags", []),
                    "category": meta.get("category"),
                    "sub_category": meta.get("sub_category"),
                    "author_id": meta.get("author_id"),
                    "content_type": meta.get("content_type", "video"),
                    "quality_score": meta.get("quality_score", 0.8),
                    "popularity_score": meta.get("popularity_score", 0),
                    "embedding": meta.get("embedding"),
                    "published_at": meta.get("published_at"),
                }
        
        # UserCF 需要完整的用户向量
        for uid, items in user_item_map.items():
            self.user_cf.add_user_vector(uid, items)
        
        # ContentBased 注册物品特征
        for iid, features in item_feature_map.items():
            self.content_based.add_item(iid, features)
            self.ranking.register_item_features({iid: features})
        
        self._total_interactions += len(interactions)
        self._total_items = len(item_feature_map)
        self._total_users = len(user_item_map)
        
        logger.info(f"[Engine] 数据加载完成: "
                     f"{self._total_users} 用户, "
                     f"{self._total_items} 物品, "
                     f"{len(interactions)} 交互")

    def load_items_batch(self, items: List[dict]):
        """单独加载物品特征数据"""
        for item in items:
            iid = item.get("item_id")
            if not iid:
                continue
            
            self.content_based.add_item(iid, item)
            self.ranking.register_item_features({iid: item})
            self.trending.register_item(iid, item)
        
        self._total_items = max(self._total_items, len(items))

    def build_all_models(self, rebuild: bool = True):
        """构建所有推荐模型"""
        start_time = time.time()
        logger.info("[Engine] 开始构建全部模型...")
        
        if self.mode == EngineMode.FULL:
            logger.info("[Engine] 构建ItemCF相似度矩阵...")
            self.item_cf.build(rebuild=rebuild)
            
            logger.info("[Engine] 构建UserCF相似度矩阵...")
            self.user_cf.build(rebuild=rebuild)
        
        # Trending 快照（用于趋势计算）
        self.trending.snapshot_current_state()
        
        self._is_built = True
        self._built_at = datetime.now()
        
        elapsed = time.time() - start_time
        logger.info(f"[Engine] 所有模型构建完成! 耗时{elapsed:.2f}s")

    # ================================================================
    # 核心推荐接口
    # ================================================================

    async def recommend(
        self,
        user_id: Optional[str] = None,
        scene: str = "home_feed",
        limit: int = 20,
        context: Optional[dict] = None,
        filters: Optional[dict] = None,
        use_cache: bool = True,
    ) -> dict:
        """
        生成个性化推荐列表（主入口）
        
        Args:
            user_id: 目标用户ID（None表示非个性化/全局推荐）
            scene: 推荐场景 (home_feed/detail_related/discovery/hot_list等)
            limit: 返回数量上限
            context: 上下文信息（时间、设备、位置等）
            filters: 过滤条件
            use_cache: 是否使用缓存
            
        Returns:
            {
                "recommendations": [...],
                "scene", "user_id",
                "meta": {strategies_used, generation_time_ms, cache_hit, ...},
            }
        """
        start_time = time.time()
        effective_limit = limit or self.default_limit
        
        # ---- 尝试从缓存获取 ----
        if use_cache and user_id:
            cached = await self.cache.get(user_id, scene, filters)
            if cached is not None:
                return {
                    "recommendations": cached[:effective_limit],
                    "scene": scene,
                    "user_id": user_id,
                    "meta": {
                        "cache_hit": True,
                        "strategies_used": ["cached"],
                        "generation_time_ms": int((time.time()-start_time)*1000),
                        "generated_at": datetime.now().isoformat(),
                    },
                }
        
        # ---- 冷启动判断 ----
        if user_id and not self._has_enough_history(user_id):
            logger.info(f"[Engine] 用户 {user_id} 触发冷启动逻辑")
            cold_results = self._get_cold_start_recommendations(
                scene, effective_limit, context
            )
            
            if use_cache:
                await self.cache.set(user_id, scene, cold_results, filters)
            
            return {
                "recommendations": cold_results[:effective_limit],
                "scene": scene,
                "user_id": user_id,
                "meta": {
                    "cache_hit": False,
                    "is_cold_start": True,
                    "strategies_used": ["cold_start"],
                    "generation_time_ms": int((time.time()-start_time)*1000),
                    "generated_at": datetime.now().isoformat(),
                },
            }
        
        # ---- 多路召回 ----
        candidates: Dict[str, List[tuple]] = {}
        
        if self.mode != EngineMode.OFFLINE:
            # Channel 1: ItemCF
            if user_id and self.mode == EngineMode.FULL:
                try:
                    item_cf_results = self.item_cf.recommend(
                        user_id, n=effective_limit*3, filter_seen=True
                    )
                    if item_cf_results:
                        candidates["collaborative_item"] = item_cf_results
                except Exception as e:
                    logger.warning(f"[Engine] ItemCF召回失败: {e}")
            
            # Channel 2: UserCF
            if user_id and self.mode == EngineMode.FULL:
                try:
                    user_cf_results = self.user_cf.recommend(
                        user_id, n=effective_limit*2, filter_seen=True
                    )
                    if user_cf_results:
                        candidates["collaborative_user"] = user_cf_results
                except Exception as e:
                    logger.warning(f"[Engine] UserCF召回失败: {e}")
            
            # Channel 3: Content-Based
            try:
                content_results = self.content_based.recommend(
                    user_id=user_id,
                    n=effective_limit*3,
                )
                if content_results:
                    candidates["content_based"] = content_results
            except Exception as e:
                logger.warning(f"[Engine] Content召回失败: {e}")
        
        # Channel 4: Trending (始终参与)
        try:
            trending_list = self.trending.get_hot_list(scene, limit=effective_limit*2)
            if trending_list:
                trending_tuples = [
                    (t["item_id"], t.get("normalized_score", t["score"]), "trending")
                    for t in trending_list
                ]
                candidates["trending"] = trending_tuples
        except Exception as e:
            logger.warning(f"[Engine] Trending召回失败: {e}")
        
        # ---- 融合排序 ----
        ranked = self.ranking.rank(
            candidates=candidates,
            user_id=user_id,
            n=effective_limit,
            context=context,
            filters=filters,
        )
        
        # 如果排序后结果不足，补充热门
        if len(ranked) < effective_limit:
            supplement = self._supplement_from_trending(
                ranked, effective_limit, user_id
            )
            ranked.extend(supplement)
        
        generation_time = int((time.time() - start_time) * 1000)
        
        result = {
            "recommendations": ranked[:effective_limit],
            "scene": scene,
            "user_id": user_id,
            "meta": {
                "cache_hit": False,
                "strategies_used": list(candidates.keys()),
                "total_candidates": sum(len(v) for v in candidates.values()),
                "final_count": min(len(ranked), effective_limit),
                "generation_time_ms": generation_time,
                "engine_mode": self.mode.value,
                "generated_at": datetime.now().isoformat(),
            },
        }
        
        # 写入缓存
        if use_cache and user_id:
            await self.cache.set(user_id, scene, result["recommendations"], filters)
        
        return result

    async def recommend_related(
        self,
        item_id: str,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> dict:
        """相关内容推荐（详情页场景）"""
        start_time = time.time()
        
        candidates: Dict[str, List[tuple]] = {}
        
        # 基于物品的内容相似推荐
        similar = self.content_based.find_similar_items(
            item_id, n=limit*3, exclude_ids={item_id}
        )
        if similar:
            candidates["content_similarity"] = similar
        
        # ItemCF 相似物品
        item_cf_similar = self.item_cf.recommend_for_item(item_id, n=limit*3)
        if item_cf_similar:
            candidates["collaborative_item"] = item_cf_similar
        
        # 同分类热门
        item_meta = self.content_based.get_item_features(item_id)
        if item_meta and item_meta.get("category"):
            cat_trend = self.trending.get_category_trending(
                item_meta["category"], limit=limit*2
            )
            if cat_trend:
                candidates["trending"] = [
                    (t["item_id"], t.get("normalized_score", t["score"]) * 0.5, "trending")
                    for t in cat_trend
                ]
        
        ranked = self.ranking.rank(candidates, user_id=user_id, n=limit)
        
        return {
            "reference_item_id": item_id,
            "recommendations": ranked[:limit],
            "meta": {
                "generation_time_ms": int((time.time()-start_time)*1000),
                "generated_at": datetime.now().isoformat(),
            },
        }

    async def recommend_by_tags(
        self,
        tags: List[str],
        limit: int = 20,
        category_filter: Optional[str] = None,
    ) -> dict:
        """基于标签的推荐"""
        results = self.content_based.recommend(
            reference_tags=tags,
            reference_category=category_filter,
            n=limit,
        )
        
        formatted = []
        for item_id, score, reason in results:
            feat = self.content_based.get_item_features(item_id) or {}
            formatted.append({
                "item_id": item_id,
                "score": score,
                "reason": reason,
                "metadata": feat,
            })
        
        return {
            "query_tags": tags,
            "recommendations": formatted[:limit],
            "total_found": len(results),
        }

    async def get_trending(self, window: str = "daily",
                           category: Optional[str] = None,
                           limit: int = 20) -> dict:
        """获取热门榜单"""
        trend_window = getattr(TrendingWindow, window.upper(), TrendingWindow.DAILY)
        
        results = self.trending.get_trending(
            window=trend_window,
            category=category,
            limit=limit,
        )
        
        return {
            "window": window,
            "category": category or "__all__",
            "items": results,
            "stats": self.trending.stats,
        }

    # ================================================================
    # 内部方法
    # ================================================================

    def _has_enough_history(self, user_id: str, threshold: int = 5) -> bool:
        """检查用户是否有足够的交互历史用于协同过滤"""
        history = self.item_cf._user_items.get(user_id, {})
        return len(history) >= threshold

    def _get_cold_start_recommendations(
        self, scene: str, limit: int, context: Optional[dict]
    ) -> List[dict]:
        """冷启动推荐策略"""
        results = []
        
        # 优先返回全局热门
        hot_items = COLD_START_RECOMMENDATIONS.get("global_hot", [])
        
        # 尝试按分类筛选
        preferred_cat = None
        if context:
            preferred_cat = context.get("preferred_category")
        
        if preferred_cat:
            cat_cold = COLD_START_RECOMMENDATIONS.get("category_defaults", {}).get(preferred_cat)
            if cat_cold:
                results.extend(cat_cold)
        
        # 补充全局热门
        for item in hot_items:
            if len(results) >= limit:
                break
            if not any(r["item_id"] == item["item_id"] for r in results):
                results.append({
                    "item_id": item["item_id"],
                    "score": item.get("score", 0.8),
                    "final_score": item.get("score", 0.8),
                    "reasons": [item.get("reason", "cold_start")],
                    "rank": len(results) + 1,
                    "metadata": {
                        "content_type": item.get("content_type"),
                        "category": item.get("category"),
                    },
                })
        
        return results[:limit]

    def _supplement_from_trending(
        self, existing: List[dict], target_n: int, user_id: Optional[str]
    ) -> List[dict]:
        """从热门中补充不足的结果"""
        existing_ids = {r["item_id"] for r in existing}
        
        need = target_n - len(existing)
        if need <= 0:
            return []
        
        trending = self.trending.get_hot_list(limit=need*3)
        supplement = []
        
        for t in trending:
            if t["item_id"] not in existing_ids:
                supplement.append({
                    "item_id": t["item_id"],
                    "score": t.get("normalized_score", t["score"]),
                    "final_score": t.get("normalized_score", t["score"]),
                    "reasons": ["trending", "popular"],
                    "rank": len(existing) + len(supplement) + 1,
                    "metadata": t.get("metadata", {}),
                })
                
                if len(supplement) >= need:
                    break
        
        return supplement

    # ================================================================
    # 反馈与实时更新
    # ================================================================

    async def record_feedback(self, user_id: str, item_id: str,
                              action: str, value: float = 1.0):
        """记录用户对推荐的反馈（在线学习）"""
        self.item_cf.add_interaction(user_id, item_id, action, value)
        self.trending.record_event(item_id, action, value)
        
        # 使该用户的缓存失效
        await self.cache.invalidate(user_id=user_id)
        
        logger.debug(f"[Engine] 反馈已记录: user={user_id}, item={item_id}, action={action}")

    # ================================================================
    # 状态与统计
    # ================================================================

    @property
    def status(self) -> dict:
        """引擎完整状态报告"""
        return {
            "engine": {
                "mode": self.mode.value,
                "is_built": self._is_built,
                "built_at": self._built_at.isoformat() if self._built_at else None,
                "total_users": self._total_users,
                "total_items": self._total_items,
                "total_interactions": self._total_interactions,
            },
            "item_cf": self.item_cf.stats,
            "user_cf": self.user_cf.stats,
            "content_based": self.content_based.stats,
            "ranking": {
                "weights": {
                    "item_cf": self.ranking.item_cf_weight,
                    "user_cf": self.ranking.user_cf_weight,
                    "content": self.ranking.content_weight,
                    "trending": self.ranking.trending_weight,
                },
            },
            "trending": self.trending.stats,
            "cache": self.cache.stats,
        }


# Monkey-patch: 为 ItemCF 增加 recommend_for_item 方法
def _recommend_for_item(self, item_id: str, n: int = 20,
                        exclude_ids=None) -> list:
    """根据物品找相似的物品（用于相关推荐）"""
    from typing import Set, Tuple
    similar_items = self._item_similarity.get(item_id, [])
    if exclude_ids:
        similar_items = [(iid, s, "collaborative_item") 
                        for iid, s in similar_items if iid not in exclude_ids]
    else:
        similar_items = [(iid, s, "collaborative_item") for iid, s in similar_items]
    return similar_items[:n]

ItemCollaborativeFilter.recommend_for_item = _recommend_for_item
