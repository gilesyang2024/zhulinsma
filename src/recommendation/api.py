"""
推荐系统 API 路由

提供完整的推荐RESTful接口，包括：
- 个性化推荐 (首页/发现/详情相关)
- 热门榜单 (多时间窗口/分类)
- 标签推荐
- 反馈上报
- 引擎状态监控
- 冷启动管理
"""

import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

# 导入模型和引擎
try:
    from .engine import RecommendationEngine, EngineMode
    from .models import (
        InteractionType, RecommendationReason, ItemContentType,
        RecommendationScene,
    )
    from .cache import COLD_START_RECOMMENDATIONS
    ENGINE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"[RecAPI] 模块导入失败: {e}，使用降级模式")
    ENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# 全局引擎实例（懒加载单例）
# ============================================================

_engine_instance: Optional[RecommendationEngine] = None


def get_engine() -> RecommendationEngine:
    """获取全局推荐引擎实例"""
    global _engine_instance
    
    if _engine_instance is None:
        if not ENGINE_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="推荐引擎模块未正确初始化",
            )
        _engine_instance = RecommendationEngine(mode=EngineMode.FULL)
        
        # 用模拟数据预填充引擎（生产环境从数据库加载）
        _initialize_with_mock_data(_engine_instance)
    
    return _engine_instance


def _initialize_with_mock_data(engine: RecommendationEngine):
    """用模拟数据初始化引擎（开发环境用）"""
    # 生成模拟用户交互数据
    mock_interactions = []
    mock_items = []
    
    categories = ["technology", "entertainment", "education", "business", "lifestyle"]
    content_types = ["video", "article", "audio", "course"]
    interaction_types = ["view", "like", "favorite", "share", "comment", "complete"]
    tags_pool = [
        "AI", "Python", "前端", "数据分析", "产品经理", 
        "短视频", "音乐", "电影", "美食", "旅行",
        "健身", "理财", "职场", "编程入门", "深度学习",
        "机器学习", "云计算", "区块链", "设计思维", "效率工具",
    ]
    
    # 100个物品
    for i in range(1, 101):
        item_id = f"item_{i:04d}"
        cat = categories[i % len(categories)]
        ct = content_types[i % len(content_types)]
        item_tags = [tags_pool[(i + j) % len(tags_pool)] for j in range(3)]
        
        mock_items.append({
            "item_id": item_id,
            "title": f"示例内容 #{i} - {cat}/{ct}",
            "category": cat,
            "sub_category": f"{cat}_sub_{i % 5}",
            "tags": item_tags,
            "author_id": f"author_{i % 10}",
            "content_type": ct,
            "quality_score": round(0.4 + (i % 7) * 0.1, 2),
            "popularity_score": round((100 - i) / 100, 3),
            "published_at": datetime.now().isoformat(),
        })
    
    # 500个用户的交互记录
    for user_idx in range(1, 501):
        user_id = f"user_{user_idx:04d}"
        # 每个用户交互 5-30 个物品
        num_interactions = 5 + (user_idx * 17 % 25)
        preferred_cat = categories[user_idx % len(categories)]
        
        for inter_idx in range(num_interactions):
            item_idx_base = (user_idx * 3 + inter_idx * 7) % 100 + 1
            item_id = f"item_{item_idx_base:04d}"
            
            # 偏好同类别的物品
            if inter_idx < num_interactions // 2:
                cat_item_offset = categories.index(preferred_cat) * 20
                item_id = f"item_{((cat_item_offset + inter_idx) % 100) + 1:04d}"
            
            inter_type = interaction_types[
                (user_idx + inter_idx * 3) % len(interaction_types)
            ]
            
            days_ago = (inter_idx * 2 + user_idx % 7) % 30
            
            mock_interactions.append({
                "user_id": user_id,
                "item_id": item_id,
                "interaction_type": inter_type,
                "weight": None,
                "timestamp": datetime.now() - __import__('datetime').timedelta(days=days_ago),
                "metadata": {
                    "category": preferred_cat,
                    "content_type": content_types[item_idx_base % len(content_types)],
                },
            })
    
    engine.load_from_interactions(mock_interactions)
    engine.build_all_models()
    
    logger.info(f"[RecAPI] 引擎已初始化: {len(mock_items)} 物品, "
                 f"{len(mock_interactions)} 交互")


# ============================================================
# Pydantic 请求/响应模型
# ============================================================

class RecommendRequest(BaseModel):
    """推荐请求"""
    scene: str = Field("home_feed", description="推荐场景")
    limit: int = Field(20, ge=1, le=100, description="返回数量")
    context: Optional[dict] = Field(None, description="上下文信息")
    filters: Optional[dict] = Field(None, description="过滤条件")


class FeedbackRequest(BaseModel):
    """反馈上报"""
    item_id: str = Field(..., description="内容ID")
    action: str = Field(..., description="行为类型(view/like/favorite/share/comment等)")
    value: float = Field(1.0, ge=0, le=10, description="行为权重分")
    scene: Optional[str] = Field(None, description="发生场景")


class TagRecommendRequest(BaseModel):
    """标签推荐请求"""
    tags: List[str] = Field(..., min_length=1, max_length=20, description="标签列表")
    limit: int = Field(20, ge=1, le=100, description="返回数量")
    category_filter: Optional[str] = Field(None, description="分类筛选")


class BatchFeedbackRequest(BaseModel):
    """批量反馈"""
    feedbacks: List[FeedbackRequest] = Field(..., min_length=1, max_length=50)


class EngineConfigUpdate(BaseModel):
    """引擎配置更新"""
    mode: Optional[str] = Field(None, description="运行模式(full/fast/offline)")
    item_cf_weight: Optional[float] = Field(None, ge=0, le=1)
    content_weight: Optional[float] = Field(None, ge=0, le=1)
    trending_weight: Optional[float] = Field(None, ge=0, le=1)
    diversity_lambda: Optional[float] = Field(None, ge=0, le=1)


# ============================================================
# API 端点定义
# ============================================================

@router.get("/recommendations", tags=["推荐"])
async def get_recommendations(
    user_id: Optional[str] = Query(None, description="用户ID"),
    scene: str = Query("home_feed", description="推荐场景"),
    limit: int = Query(20, ge=1, le=100, description="数量上限"),
):
    """
    🎯 获取个性化推荐列表
    
    **多策略融合推荐**：协同过滤 + 内容匹配 + 热度排序 + 多样性优化
    
    - `scene=home_feed`: 首页信息流推荐（综合）
    - `scene=detail_related`: 详情页相关推荐
    - `scene=discovery`: 发现页探索推荐
    - `scene=hot_list`: 热门榜单
    - `scene=following_feed`: 关注动态流
    
    不传 user_id 时返回全局热门推荐。
    """
    start = time.time()
    engine = get_engine()
    
    result = await engine.recommend(
        user_id=user_id,
        scene=scene,
        limit=limit,
    )
    
    result["meta"]["api_latency_ms"] = int((time.time() - start) * 1000)
    return result


@router.post("/recommendations", tags=["推荐"])
async def post_recommendations(req: RecommendRequest):
    """POST方式获取个性化推荐（支持更复杂的上下文参数）"""
    engine = get_engine()
    
    result = await engine.recommend(
        user_id=req.context.get("user_id") if req.context else None,
        scene=req.scene,
        limit=req.limit,
        context=req.context,
        filters=req.filters,
        use_cache=False,  # POST默认不读缓存
    )
    return result


@router.get("/recommendations/related/{item_id}", tags=["推荐"])
async def get_related_recommendations(
    item_id: str,
    limit: int = Query(10, ge=1, le=50, description="相关推荐数量"),
    user_id: Optional[str] = Query(None, description="用户ID"),
):
    """
    🔗 获取与指定内容相关的推荐
    
    用于详情页"猜你喜欢"/"相关推荐"模块。
    结合内容相似度 + 协同过滤 + 同类热门。
    """
    engine = get_engine()
    result = await engine.recommend_related(item_id, limit, user_id)
    return result


@router.get("/recommendations/by-tags", tags=["推荐"])
async def get_tag_recommendations(
    tags: str = Query(..., description="标签，逗号分隔"),
    category: Optional[str] = Query(None, description="分类筛选"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    🏷️ 基于标签的内容推荐
    
    输入一个或多个标签，返回匹配度最高的内容。
    支持层级分类扩展和跨类型推荐。
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(status_code=400, detail="至少提供一个标签")
    
    engine = get_engine()
    result = await engine.recommend_by_tags(tag_list, limit, category)
    return result


@router.post("/recommendations/by-tags", tags=["推荐"])
async def post_tag_recommendations(req: TagRecommendRequest):
    """POST方式基于标签推荐"""
    engine = get_engine()
    result = await engine.recommend_by_tags(req.tags, req.limit, req.category_filter)
    return result


# ----------------------------------------------------------
# 热门榜单端点
# ----------------------------------------------------------

@router.get("/trending", tags=["热门榜单"])
async def get_trending(
    window: str = Query("daily", description="时间窗口: hourly/daily/weekly/monthly"),
    category: Optional[str] = Query(None, description="分类筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """
    🔥 获取热门排行榜
    
    支持四个时间维度的热度排名：
    - **hourly**: 小时榜（实时热点）
    - **daily**: 日榜（当日最热）
    - **weekly**: 周榜（周度精选）
    - **monthly**: 月榜（月度经典）
    
    可按分类查看子榜单。
    """
    engine = get_engine()
    result = await engine.get_trending(window, category, limit)
    return result


@router.get("/trending/categories", tags=["热门榜单"])
async def get_trending_categories():
    """获取所有可用的热门分类"""
    categories = [
        {"key": "technology", "name": "科技", "icon": "💻"},
        {"key": "entertainment", "name": "娱乐", "icon": "🎬"},
        {"key": "education", "name": "教育", "icon": "📚"},
        {"key": "business", "name": "商业", "icon": "💼"},
        {"key": "lifestyle", "name": "生活", "icon": "🌟"},
        {"key": "news", "name": "资讯", "icon": "📰"},
    ]
    return {"categories": categories}


@router.get("/trending/hot-searches", tags=["热门榜单"])
async def get_hot_searches(limit: int = Query(20, ge=1, le=50)):
    """获取热搜关键词排行"""
    engine = get_engine()
    hot_keywords = [
        {"keyword": "AI短剧制作", "count": 12580, "trend": "up", "heat": 98.5},
        {"keyword": "短视频变现", "count": 8920, "trend": "up", "heat": 92.1},
        {"keyword": "数字人直播", "count": 7560, "trend": "hot", "heat": 88.3},
        {"keyword": "内容创作工具", "count": 6340, "trend": "stable", "heat": 82.7},
        {"keyword": "AIGC应用", "count": 5890, "trend": "up", "heat": 79.4},
        {"keyword": "自媒体运营", "count": 5120, "trend": "down", "heat": 74.2},
        {"keyword": "视频剪辑技巧", "count": 4860, "trend": "stable", "heat": 71.8},
        {"keyword": "IP孵化", "count": 4230, "trend": "up", "heat": 68.5},
        {"keyword": "跨平台分发", "count": 3980, "trend": "new", "heat": 65.1},
        {"keyword": "粉丝增长策略", "count": 3540, "trend": "stable", "heat": 62.3},
    ]
    return {"hot_searches": hot_keywords[:limit], "updated_at": datetime.now().isoformat()}


# ----------------------------------------------------------
# 用户反馈端点
# ----------------------------------------------------------

@router.post("/feedback", tags=["用户反馈"])
async def submit_feedback(feedback: FeedbackRequest):
    """
    📝 上报用户行为反馈
    
    用于实时更新推荐模型。支持的行为类型：
    view, click, like, favorite, share, comment, follow, complete, rating 等。
    """
    engine = get_engine()
    
    await engine.record_feedback(
        user_id=feedback.__dict__.get("user_id", "anonymous"),
        item_id=feedback.item_id,
        action=feedback.action,
        value=feedback.value,
    )
    
    return {
        "success": True,
        "message": "反馈已记录",
        "item_id": feedback.item_id,
        "action": feedback.action,
    }


@router.post("/feedback/batch", tags=["用户反馈"])
async def submit_batch_feedback(req: BatchFeedbackRequest):
    """批量上报用户反馈"""
    engine = get_engine()
    count = 0
    
    for fb in req.feedbacks:
        await engine.record_feedback(
            user_id="anonymous",
            item_id=fb.item_id,
            action=fb.action,
            value=fb.value,
        )
        count += 1
    
    return {"success": True, "recorded_count": count}


# ----------------------------------------------------------
# 引擎管理与监控端点
# ----------------------------------------------------------

@router.get("/engine/status", tags=["引擎管理"])
async def get_engine_status():
    """
    ⚙️ 推荐引擎状态面板
    
    返回引擎各模块的运行状态、统计数据、健康检查等信息。
    用于运维监控和调试。
    """
    engine = get_engine()
    return engine.status


@router.post("/engine/rebuild", tags=["引擎管理"])
async def rebuild_models(background_tasks: BackgroundTasks):
    """
    🔧 重建推荐模型（后台任务）
    
    触发全量模型重算。适合数据量变化较大时使用。
    返回立即响应，重建在后台执行。
    """
    def _rebuild():
        try:
            engine = get_engine()
            engine.build_all_models(rebuild=True)
            logger.info("[RecAPI] 后台模型重建完成")
        except Exception as e:
            logger.error(f"[RecAPI] 后台模型重建失败: {e}")
    
    background_tasks.add_task(_rebuild)
    
    return {
        "message": "模型重建任务已在后台启动",
        "status": "running",
        "started_at": datetime.now().isoformat(),
    }


@router.post("/engine/config", tags=["引擎管理"])
async def update_engine_config(config: EngineConfigUpdate):
    """动态调整引擎运行参数"""
    engine = get_engine()
    updated_fields = []
    
    if config.mode is not None:
        try:
            engine.mode = EngineMode(config.mode)
            updated_fields.append(f"mode={config.mode}")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的模式: {config.mode}")
    
    if config.item_cf_weight is not None:
        engine.ranking.item_cf_weight = config.item_cf_weight
        updated_fields.append(f"item_cf_weight={config.item_cf_weight}")
    
    if config.content_weight is not None:
        engine.ranking.content_weight = config.content_weight
        updated_fields.append(f"content_weight={config.content_weight}")
    
    if config.trending_weight is not None:
        engine.ranking.trending_weight = config.trending_weight
        updated_fields.append(f"trending_weight={config.trending_weight}")
    
    if config.diversity_lambda is not None:
        engine.ranking.diversity_lambda = config.diversity_lambda
        updated_fields.append(f"diversity_lambda={config.diversity_lambda}")
    
    return {
        "message": "配置已更新",
        "updated_fields": updated_fields,
        "current_config": {
            "mode": engine.mode.value,
            "weights": {
                "item_cf": engine.ranking.item_cf_weight,
                "content": engine.ranking.content_weight,
                "trending": engine.ranking.trending_weight,
            },
            "diversity_lambda": engine.ranking.diversity_lambda,
        },
    }


@router.delete("/engine/cache", tags=["引擎管理"])
async def clear_cache(
    user_id: Optional[str] = Query(None, description="清除指定用户缓存"),
    scene: Optional[str] = Query(None, description="清除指定场景缓存"),
):
    """清除推荐缓存"""
    engine = get_engine()
    await engine.cache.invalidate(user_id=user_id, scene=scene)
    
    target = "全部缓存"
    if user_id and scene:
        target = f"用户{user_id}的{scene}缓存"
    elif user_id:
        target = f"用户{user_id}的缓存"
    elif scene:
        target = f"{scene}场景缓存"
    
    return {"success": True, "message": f"{target}已清除"}


# ----------------------------------------------------------
# 冷启动与兜底端点
# ----------------------------------------------------------

@router.get("/cold-start/default", tags=["冷启动"])
async def get_cold_start_defaults(
    category: Optional[str] = Query(None, description="分类"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    ❄️ 获取冷启动默认推荐
    
    新用户/无历史数据时的兜底推荐。
    返回高质量的全局热门内容或分类精选。
    """
    results = COLD_START_RECOMMENDATIONS.get("global_hot", [])
    
    if category:
        cat_results = COLD_START_RECOMMENDATIONS.get("category_defaults", {}).get(category)
        if cat_results:
            # 分类优先，补充全局
            combined = cat_results + [
                r for r in results 
                if r.get("category") != category and not any(c["item_id"] == r["item_id"] for c in cat_results)
            ]
            results = combined
    
    return {
        "is_cold_start": True,
        "category": category or "__all__",
        "recommendations": results[:limit],
        "total_available": len(results),
    }


@router.get("/scenes", tags=["元数据"])
async def get_available_scenes():
    """获取所有可用的推荐场景及其说明"""
    scenes = [
        {"key": "home_feed", "name": "首页信息流", "description": "综合个性化推荐，适合首页Feed流"},
        {"key": "detail_related", "name": "详情页相关", "description": "基于当前内容的相关推荐"},
        {"key": "discovery", "name": "发现页", "description": "探索性推荐，兼顾多样性和新鲜感"},
        {"key": "search_result", "name": "搜索结果页", "description": "搜索结果的智能排序和补充"},
        {"key": "user_profile", "name": "个人主页", "description": "用户可能喜欢的内容"},
        {"key": "category", "name": "分类频道", "description": "特定分类下的推荐"},
        {"key": "hot_list", "name": "热榜", "description": "纯热度驱动的排行榜"},
        {"key": "following_feed", "name": "关注动态", "description": "基于社交关系的推荐"},
    ]
    return {"scenes": scenes}


# ----------------------------------------------------------
# A/B 测试与实验接口
# ----------------------------------------------------------

@router.get("/ab/config", tags=["A/B测试"])
async def get_ab_config(user_id: Optional[str] = Query(None)):
    """获取当前A/B实验配置（预留接口）"""
    return {
        "experiments": [
            {
                "name": "ranking_strategy_v2",
                "enabled": True,
                "traffic_percent": 30,
                "config": {
                    "use_new_diversity": True,
                    "fresh_content_boost": 1.3,
                },
            },
            {
                "name": "cold_start_improvement",
                "enabled": True,
                "traffic_percent": 50,
                "config": {
                    "use_tag_expansion": True,
                    "quality_threshold": 0.3,
                },
            },
        ],
        "user_group": hash(user_id or "anonymous") % 100 if user_id else None,
    }
