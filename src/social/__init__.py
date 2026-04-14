"""
社交功能模块

提供用户关注、点赞、收藏、分享等社交互动功能。
"""

from .api import router as social_router
from .models import (
    FollowRelationship,
    LikeRecord,
    BookmarkRecord,
    ShareRecord,
    SocialComment,
    Notification
)

__all__ = [
    "social_router",
    "FollowRelationship",
    "LikeRecord",
    "BookmarkRecord",
    "ShareRecord",
    "SocialComment",
    "Notification"
]