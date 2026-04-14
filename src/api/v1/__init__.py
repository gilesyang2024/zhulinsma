"""
API v1 路由模块

组织和管理所有v1版本的API路由。
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .content import router as content_router
from .media import router as media_router
from .admin import router as admin_router
from src.search.api import router as search_router
from src.social.api import router as social_router
from .cache import router as cache_router
from src.tasks.api import router as tasks_router
from src.websocket.api import router as websocket_router
from src.monitoring.health import health_router
from src.monitoring.api import router as monitoring_router
from src.storage.api import router as storage_router
from src.analytics.api import router as analytics_router
from src.recommendation.api import router as recommendation_router
from src.api.v1.stock import router as stock_router

# 创建主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(users_router, prefix="/users", tags=["用户"])
api_router.include_router(content_router, prefix="/content", tags=["内容"])
api_router.include_router(media_router, prefix="/media", tags=["媒体"])
api_router.include_router(admin_router, prefix="/admin", tags=["管理后台"])
api_router.include_router(search_router, prefix="/search", tags=["搜索与推荐"])
api_router.include_router(social_router, prefix="/social", tags=["社交互动"])
api_router.include_router(cache_router, prefix="/cache", tags=["缓存管理"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["异步任务"])
api_router.include_router(websocket_router, prefix="/ws", tags=["实时通信"])
api_router.include_router(health_router, prefix="/health", tags=["健康检查"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["监控系统"])
api_router.include_router(storage_router, prefix="/storage", tags=["文件存储"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["数据分析"])
api_router.include_router(recommendation_router, prefix="/recommendation", tags=["智能推荐"])
api_router.include_router(stock_router, prefix="/stock", tags=["选股战法"])

__all__ = ["api_router"]