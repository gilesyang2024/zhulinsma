"""
社交功能数据模型

定义关注、点赞、收藏、评论等社交功能的数据模型。
"""

from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from src.core.database import Base


# 内容类型枚举
class ContentType(str, Enum):
    ARTICLE = "article"
    VIDEO = "video"
    AUDIO = "audio"
    COURSE = "course"
    USER = "user"
    COMMENT = "comment"
    REPLY = "reply"


# 互动类型枚举
class InteractionType(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    BOOKMARK = "bookmark"
    SHARE = "share"
    REPORT = "report"


class FollowRelationship(Base):
    """关注关系模型"""
    __tablename__ = "follow_relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(String(36), nullable=False, index=True)  # 关注者ID
    following_id = Column(String(36), nullable=False, index=True)  # 被关注者ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 状态字段
    is_mutual = Column(Boolean, default=False)  # 是否互相关注
    notifications_enabled = Column(Boolean, default=True)  # 是否开启通知
    notes = Column(Text, nullable=True)  # 备注
    
    # 约束：同一个关注者不能重复关注同一个被关注者
    __table_args__ = ({"sqlite_autoincrement": True},)
    
    def __repr__(self):
        return f"<FollowRelationship {self.follower_id} -> {self.following_id}>"


class LikeRecord(Base):
    """点赞记录模型"""
    __tablename__ = "like_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # 点赞用户ID
    content_id = Column(String(36), nullable=False, index=True)  # 内容ID
    content_type = Column(String(20), nullable=False)  # 内容类型
    like_type = Column(String(10), default="like")  # like/dislike
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 元数据
    extra_data = Column(JSON, nullable=True)  # 额外信息
    
    # 约束：同一个用户对同一个内容只能点赞一次
    __table_args__ = ({"sqlite_autoincrement": True},)
    
    def __repr__(self):
        return f"<LikeRecord user:{self.user_id} content:{self.content_id} type:{self.like_type}>"


class BookmarkRecord(Base):
    """收藏记录模型"""
    __tablename__ = "bookmark_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # 收藏用户ID
    content_id = Column(String(36), nullable=False, index=True)  # 内容ID
    content_type = Column(String(20), nullable=False)  # 内容类型
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 收藏夹信息
    folder = Column(String(50), nullable=True)  # 收藏夹名称
    tags = Column(JSON, nullable=True)  # 标签
    notes = Column(Text, nullable=True)  # 备注
    
    # 约束：同一个用户不能重复收藏同一个内容
    __table_args__ = ({"sqlite_autoincrement": True},)
    
    def __repr__(self):
        return f"<BookmarkRecord user:{self.user_id} content:{self.content_id}>"


class ShareRecord(Base):
    """分享记录模型"""
    __tablename__ = "share_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # 分享用户ID
    content_id = Column(String(36), nullable=False, index=True)  # 内容ID
    content_type = Column(String(20), nullable=False)  # 内容类型
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 分享信息
    platform = Column(String(50), nullable=True)  # 分享平台
    share_url = Column(String(500), nullable=True)  # 分享链接
    message = Column(Text, nullable=True)  # 分享消息
    
    # 统计信息
    click_count = Column(Integer, default=0)  # 点击次数
    view_count = Column(Integer, default=0)  # 浏览次数
    
    def __repr__(self):
        return f"<ShareRecord user:{self.user_id} content:{self.content_id} platform:{self.platform}>"


class SocialComment(Base):
    """评论模型"""
    __tablename__ = "social_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # 评论用户ID
    content_id = Column(String(36), nullable=False, index=True)  # 内容ID
    content_type = Column(String(20), nullable=False)  # 内容类型
    
    # 评论内容
    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)  # 父评论ID
    reply_to_id = Column(String(36), nullable=True)  # 回复给的用户ID
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 状态字段
    is_deleted = Column(Boolean, default=False)
    is_edited = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)  # 是否置顶
    
    # 统计字段
    like_count = Column(Integer, default=0)
    dislike_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    
    # 元数据
    extra_data = Column(JSON, nullable=True)
    
    # 关系
    replies = relationship("SocialComment", back_populates="parent", remote_side=[id])
    parent = relationship("SocialComment", back_populates="replies", remote_side=[id])
    
    def __repr__(self):
        return f"<Comment id:{self.id} user:{self.user_id} content:{self.content_id[:10]}...>"


class Notification(Base):
    """通知模型"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # 接收用户ID
    sender_id = Column(String(36), nullable=True)  # 发送者ID
    
    # 通知内容
    type = Column(String(50), nullable=False)  # 通知类型
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    
    # 关联资源
    resource_type = Column(String(20), nullable=True)  # 资源类型
    resource_id = Column(String(36), nullable=True)  # 资源ID
    
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)  # 阅读时间
    
    # 状态字段
    is_read = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    
    # 元数据
    extra_data = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Notification user:{self.user_id} type:{self.type} read:{self.is_read}>"