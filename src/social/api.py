"""
社交功能API路由

提供关注、点赞、收藏、评论等社交功能接口。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from . import models

# 创建社交路由
router = APIRouter()


# 响应模型

class FollowInfo(BaseModel):
    """关注信息"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    avatar: Optional[str] = Field(None, description="头像")
    bio: Optional[str] = Field(None, description="个人简介")
    is_mutual: bool = Field(False, description="是否互相关注")
    followed_at: datetime = Field(..., description="关注时间")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "username": "张三",
                "avatar": "https://example.com/avatar.jpg",
                "bio": "技术爱好者",
                "is_mutual": True,
                "followed_at": "2026-01-15T10:30:00"
            }
        }
    }


class FollowStats(BaseModel):
    """关注统计"""
    followers_count: int = Field(0, description="粉丝数量")
    following_count: int = Field(0, description="关注数量")
    mutual_count: int = Field(0, description="互相关注数量")


class LikeRequest(BaseModel):
    """点赞请求"""
    content_id: str = Field(..., description="内容ID")
    content_type: models.ContentType = Field(..., description="内容类型")
    like_type: str = Field("like", description="点赞类型: like/dislike")


class BookmarkRequest(BaseModel):
    """收藏请求"""
    content_id: str = Field(..., description="内容ID")
    content_type: models.ContentType = Field(..., description="内容类型")
    folder: Optional[str] = Field(None, description="收藏夹名称")
    notes: Optional[str] = Field(None, description="备注")


class CommentRequest(BaseModel):
    """评论请求"""
    content_id: str = Field(..., description="内容ID")
    content_type: models.ContentType = Field(..., description="内容类型")
    content: str = Field(..., min_length=1, max_length=5000, description="评论内容")
    parent_id: Optional[int] = Field(None, description="父评论ID")
    reply_to_id: Optional[str] = Field(None, description="回复给的用户ID")


class CommentResponse(BaseModel):
    """评论响应"""
    id: int = Field(..., description="评论ID")
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    avatar: Optional[str] = Field(None, description="头像")
    content: str = Field(..., description="评论内容")
    content_id: str = Field(..., description="内容ID")
    content_type: str = Field(..., description="内容类型")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    like_count: int = Field(0, description="点赞数")
    dislike_count: int = Field(0, description="点踩数")
    reply_count: int = Field(0, description="回复数")
    is_edited: bool = Field(False, description="是否编辑过")
    is_pinned: bool = Field(False, description="是否置顶")
    parent_id: Optional[int] = Field(None, description="父评论ID")
    reply_to_id: Optional[str] = Field(None, description="回复给的用户ID")
    replies: List["CommentResponse"] = Field(default_factory=list, description="回复列表")


# 自引用修复
CommentResponse.model_rebuild()


# 关注功能

@router.post("/follow/{user_id}", status_code=status.HTTP_201_CREATED, tags=["关注"])
async def follow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    关注用户
    
    关注指定的用户，需要认证。
    """
    # TODO: 需要用户认证，获取当前用户ID
    current_user_id = "current_user_123"  # 临时模拟
    
    if current_user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能关注自己"
        )
    
    # 检查是否已经关注
    # TODO: 检查数据库是否已存在关注关系
    
    # 创建关注记录
    follow_record = {
        "follower_id": current_user_id,
        "following_id": user_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "is_mutual": False  # TODO: 检查是否互相关注
    }
    
    return {
        "message": "关注成功",
        "data": follow_record
    }


@router.delete("/follow/{user_id}", tags=["关注"])
async def unfollow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    取消关注
    
    取消关注指定的用户，需要认证。
    """
    # TODO: 需要用户认证，获取当前用户ID
    current_user_id = "current_user_123"  # 临时模拟
    
    # TODO: 删除关注记录
    
    return {
        "message": "取消关注成功",
        "user_id": user_id
    }


@router.get("/followers", response_model=List[FollowInfo], tags=["关注"])
async def get_followers(
    user_id: Optional[str] = Query(None, description="用户ID，为空时获取当前用户的粉丝"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> List[FollowInfo]:
    """
    获取粉丝列表
    
    返回指定用户的粉丝列表。
    """
    # TODO: 获取实际数据
    
    # 模拟数据
    mock_followers = [
        FollowInfo(
            user_id=f"follower_{i}",
            username=f"粉丝用户{i}",
            avatar=f"https://example.com/avatar_{i}.jpg",
            bio=f"这是粉丝{i}的个人简介",
            is_mutual=i % 2 == 0,
            followed_at=datetime.now()
        )
        for i in range(min(page_size, 5))
    ]
    
    return mock_followers


@router.get("/following", response_model=List[FollowInfo], tags=["关注"])
async def get_following(
    user_id: Optional[str] = Query(None, description="用户ID，为空时获取当前用户的关注"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> List[FollowInfo]:
    """
    获取关注列表
    
    返回指定用户关注的用户列表。
    """
    # TODO: 获取实际数据
    
    # 模拟数据
    mock_following = [
        FollowInfo(
            user_id=f"following_{i}",
            username=f"关注用户{i}",
            avatar=f"https://example.com/avatar_{i}.jpg",
            bio=f"这是关注用户{i}的个人简介",
            is_mutual=i % 3 == 0,
            followed_at=datetime.now()
        )
        for i in range(min(page_size, 5))
    ]
    
    return mock_following


@router.get("/follow/stats/{user_id}", response_model=FollowStats, tags=["关注"])
async def get_follow_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> FollowStats:
    """
    获取关注统计
    
    返回用户的粉丝数、关注数、互相关注数。
    """
    # TODO: 获取实际统计数据
    
    return FollowStats(
        followers_count=156,
        following_count=89,
        mutual_count=42
    )


# 点赞功能

@router.post("/like", status_code=status.HTTP_201_CREATED, tags=["点赞"])
async def like_content(
    request: LikeRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    点赞内容
    
    给指定的内容点赞或点踩。
    """
    # TODO: 需要用户认证
    current_user_id = "current_user_123"  # 临时模拟
    
    # TODO: 检查是否已经点赞
    
    like_record = {
        "user_id": current_user_id,
        "content_id": request.content_id,
        "content_type": request.content_type.value,
        "like_type": request.like_type,
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "message": f"{request.like_type}成功",
        "data": like_record
    }


@router.delete("/like", tags=["点赞"])
async def unlike_content(
    content_id: str = Query(..., description="内容ID"),
    content_type: models.ContentType = Query(..., description="内容类型"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    取消点赞
    
    取消对指定内容的点赞或点踩。
    """
    # TODO: 需要用户认证
    current_user_id = "current_user_123"  # 临时模拟
    
    # TODO: 删除点赞记录
    
    return {
        "message": "取消点赞成功",
        "content_id": content_id,
        "content_type": content_type.value
    }


@router.get("/likes", response_model=List[Dict[str, Any]], tags=["点赞"])
async def get_user_likes(
    user_id: Optional[str] = Query(None, description="用户ID，为空时获取当前用户的点赞"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    获取用户点赞记录
    
    返回用户的点赞历史。
    """
    # TODO: 获取实际数据
    
    mock_likes = [
        {
            "content_id": f"content_{i}",
            "content_type": "article",
            "title": f"点赞的内容 {i}",
            "like_type": "like",
            "liked_at": datetime.now().isoformat()
        }
        for i in range(min(page_size, 5))
    ]
    
    return mock_likes


@router.get("/content/{content_id}/likes", response_model=Dict[str, Any], tags=["点赞"])
async def get_content_likes(
    content_id: str,
    content_type: models.ContentType = Query(..., description="内容类型"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取内容点赞统计
    
    返回指定内容的点赞统计信息。
    """
    # TODO: 获取实际统计数据
    
    return {
        "content_id": content_id,
        "content_type": content_type.value,
        "like_count": 156,
        "dislike_count": 8,
        "user_liked": True,  # 当前用户是否点赞
        "user_disliked": False,  # 当前用户是否点踩
        "recent_likers": [
            {"user_id": "user_1", "username": "用户1", "avatar": "avatar1.jpg"},
            {"user_id": "user_2", "username": "用户2", "avatar": "avatar2.jpg"},
            {"user_id": "user_3", "username": "用户3", "avatar": "avatar3.jpg"}
        ]
    }


# 收藏功能

@router.post("/bookmark", status_code=status.HTTP_201_CREATED, tags=["收藏"])
async def bookmark_content(
    request: BookmarkRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    收藏内容
    
    将指定内容添加到收藏夹。
    """
    # TODO: 需要用户认证
    current_user_id = "current_user_123"  # 临时模拟
    
    # TODO: 检查是否已经收藏
    
    bookmark_record = {
        "user_id": current_user_id,
        "content_id": request.content_id,
        "content_type": request.content_type.value,
        "folder": request.folder or "默认收藏夹",
        "notes": request.notes,
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "message": "收藏成功",
        "data": bookmark_record
    }


@router.delete("/bookmark", tags=["收藏"])
async def remove_bookmark(
    content_id: str = Query(..., description="内容ID"),
    content_type: models.ContentType = Query(..., description="内容类型"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    取消收藏
    
    从收藏夹中移除指定内容。
    """
    # TODO: 需要用户认证
    current_user_id = "current_user_123"  # 临时模拟
    
    # TODO: 删除收藏记录
    
    return {
        "message": "取消收藏成功",
        "content_id": content_id,
        "content_type": content_type.value
    }


@router.get("/bookmarks", response_model=List[Dict[str, Any]], tags=["收藏"])
async def get_user_bookmarks(
    user_id: Optional[str] = Query(None, description="用户ID，为空时获取当前用户的收藏"),
    folder: Optional[str] = Query(None, description="收藏夹名称"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    获取用户收藏
    
    返回用户的收藏内容。
    """
    # TODO: 获取实际数据
    
    mock_bookmarks = [
        {
            "content_id": f"content_{i}",
            "content_type": "article",
            "title": f"收藏的内容 {i}",
            "folder": folder or "默认收藏夹",
            "notes": f"这是收藏{i}的备注",
            "bookmarked_at": datetime.now().isoformat()
        }
        for i in range(min(page_size, 5))
    ]
    
    return mock_bookmarks


# 评论功能

@router.post("/comment", status_code=status.HTTP_201_CREATED, tags=["评论"])
async def create_comment(
    request: CommentRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    创建评论
    
    对指定内容创建评论。
    """
    # TODO: 需要用户认证
    current_user_id = "current_user_123"  # 临时模拟
    
    comment_data = {
        "id": 1001,  # 模拟ID
        "user_id": current_user_id,
        "username": "当前用户",
        "avatar": "https://example.com/avatar.jpg",
        "content": request.content,
        "content_id": request.content_id,
        "content_type": request.content_type.value,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "parent_id": request.parent_id,
        "reply_to_id": request.reply_to_id
    }
    
    return {
        "message": "评论创建成功",
        "data": comment_data
    }


@router.get("/content/{content_id}/comments", response_model=List[CommentResponse], tags=["评论"])
async def get_content_comments(
    content_id: str,
    content_type: models.ContentType = Query(..., description="内容类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("newest", description="排序方式: newest, oldest, hottest"),
    db: AsyncSession = Depends(get_db)
) -> List[CommentResponse]:
    """
    获取内容评论
    
    返回指定内容的评论列表。
    """
    # TODO: 获取实际数据
    
    mock_comments = [
        CommentResponse(
            id=1000 + i,
            user_id=f"user_{i}",
            username=f"用户{i}",
            avatar=f"https://example.com/avatar_{i}.jpg",
            content=f"这是第{i}条评论内容，用于测试评论功能。",
            content_id=content_id,
            content_type=content_type.value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            like_count=10 + i,
            dislike_count=i,
            reply_count=2 + i,
            is_edited=i % 3 == 0,
            is_pinned=i == 0,
            replies=[]
        )
        for i in range(min(page_size, 5))
    ]
    
    return mock_comments


@router.delete("/comment/{comment_id}", tags=["评论"])
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    删除评论
    
    删除指定的评论（需要是评论所有者或管理员）。
    """
    # TODO: 需要用户认证和权限检查
    
    return {
        "message": "评论删除成功",
        "comment_id": comment_id
    }


@router.put("/comment/{comment_id}", tags=["评论"])
async def update_comment(
    comment_id: int,
    content: str = Query(..., min_length=1, max_length=5000, description="评论内容"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    更新评论
    
    更新指定的评论内容。
    """
    # TODO: 需要用户认证和权限检查
    
    return {
        "message": "评论更新成功",
        "comment_id": comment_id,
        "content": content,
        "updated_at": datetime.now().isoformat(),
        "is_edited": True
    }


# 社交统计

@router.get("/user/{user_id}/social-stats", response_model=Dict[str, Any], tags=["社交统计"])
async def get_user_social_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取用户社交统计
    
    返回用户的关注、点赞、收藏等社交统计信息。
    """
    # TODO: 获取实际统计数据
    
    return {
        "user_id": user_id,
        "follow_stats": {
            "followers_count": 156,
            "following_count": 89,
            "mutual_count": 42
        },
        "like_stats": {
            "likes_given": 1250,
            "likes_received": 980,
            "dislikes_given": 25,
            "dislikes_received": 15
        },
        "bookmark_stats": {
            "bookmarks_count": 156,
            "folders": ["技术", "生活", "学习"],
            "most_bookmarked_category": "technology"
        },
        "comment_stats": {
            "comments_count": 89,
            "replies_received": 156,
            "most_commented_content": "content_123"
        },
        "share_stats": {
            "shares_count": 42,
            "most_shared_content": "content_456",
            "top_platform": "wechat"
        }
    }


# 互动通知

@router.get("/notifications", response_model=List[Dict[str, Any]], tags=["通知"])
async def get_user_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    unread_only: bool = Query(False, description="是否只获取未读通知"),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    获取用户通知
    
    返回用户的通知列表，包括关注、点赞、评论等互动通知。
    """
    # TODO: 需要用户认证
    # TODO: 获取实际通知数据
    
    mock_notifications = [
        {
            "id": 1000 + i,
            "type": ["follow", "like", "comment", "reply"][i % 4],
            "title": f"通知标题{i}",
            "content": f"这是第{i}条通知内容",
            "sender": {
                "user_id": f"sender_{i}",
                "username": f"发送者{i}",
                "avatar": f"https://example.com/avatar_{i}.jpg"
            },
            "resource": {
                "type": ["article", "comment", "user"][i % 3],
                "id": f"resource_{i}",
                "title": f"相关资源{i}"
            },
            "created_at": datetime.now().isoformat(),
            "is_read": i % 3 == 0,
            "read_at": datetime.now().isoformat() if i % 3 == 0 else None
        }
        for i in range(min(page_size, 5))
    ]
    
    if unread_only:
        mock_notifications = [n for n in mock_notifications if not n["is_read"]]
    
    return mock_notifications