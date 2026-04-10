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

# 创建主路由
api_router = APIRouter()

# 注册子路由
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(users_router, prefix="/users", tags=["用户"])
api_router.include_router(content_router, prefix="/content", tags=["内容"])
api_router.include_router(media_router, prefix="/media", tags=["媒体"])
api_router.include_router(admin_router, prefix="/admin", tags=["管理后台"])

__all__ = ["api_router"]