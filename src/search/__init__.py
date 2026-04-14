"""
搜索功能模块

提供全文搜索、推荐和发现功能。
支持内容、用户、标签等多种资源的搜索。
"""

from .api import router as search_router

__all__ = ["search_router"]