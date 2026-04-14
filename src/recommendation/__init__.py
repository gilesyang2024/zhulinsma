"""
推荐算法引擎模块

竹林司马智能推荐系统 - 多策略融合推荐引擎
- 协同过滤 (ItemCF / UserCF)
- 内容-based推荐 (标签匹配 + 向量相似度)
- 热度排序 + 时间衰减
- 多策略加权融合
- 实时反馈 + 离线召回
"""

from .models import *
from .engine import RecommendationEngine
from .collaborative import ItemCollaborativeFilter, UserCollaborativeFilter
from .content_based import ContentBasedRecommender
from .ranking import RankingService
from .trending import TrendingService
from .cache import RecommendationCache
from .api import router as recommendation_router

__all__ = [
    "RecommendationEngine",
    "ItemCollaborativeFilter",
    "UserCollaborativeFilter",
    "ContentBasedRecommender",
    "RankingService",
    "TrendingService",
    "RecommendationCache",
    "recommendation_router",
]
