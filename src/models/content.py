"""
内容管理系统模型
包含 Content, Comment, Tag, Category 等模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, DateTime, Date, Integer, ForeignKey, JSON, CheckConstraint, UniqueConstraint, Text, ARRAY, BigInteger
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from src.core.database import Base


class Tag(Base):
    """
    标签模型
    用于内容分类和检索
    """
    __tablename__ = "tags"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    color = Column(String(7))  # HEX颜色代码，如 #FF5733
    icon_url = Column(String(500))
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    content_tags = relationship("ContentTag", back_populates="tag", cascade="all, delete-orphan")
    contents = relationship("Content", secondary="content_tags", back_populates="tags", viewonly=True)
    
    @validates('slug')
    def validate_slug(self, key, slug):
        """验证slug格式"""
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug):
            raise ValueError("Slug只能包含小写字母、数字和连字符")
        return slug
    
    def increment_usage_count(self):
        """增加使用计数"""
        self.usage_count += 1
    
    def decrement_usage_count(self):
        """减少使用计数"""
        if self.usage_count > 0:
            self.usage_count -= 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "color": self.color,
            "icon_url": self.icon_url,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    def __repr__(self):
        return f"<Tag(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class ContentTag(Base):
    """
    内容-标签关联表
    多对多关系
    """
    __tablename__ = "content_tags"
    
    content_id = Column(PG_UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(PG_UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    content = relationship("Content", back_populates="content_tags")
    tag = relationship("Tag", back_populates="content_tags")
    
    def __repr__(self):
        return f"<ContentTag(content_id={self.content_id}, tag_id={self.tag_id})>"


class Category(Base):
    """
    分类模型
    用于内容组织
    """
    __tablename__ = "categories"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    parent_id = Column(PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    icon_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent", cascade="all, delete-orphan")
    content_categories = relationship("ContentCategory", back_populates="category", cascade="all, delete-orphan")
    contents = relationship("Content", secondary="content_categories", back_populates="categories", viewonly=True)
    
    @validates('slug')
    def validate_slug(self, key, slug):
        """验证slug格式"""
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug):
            raise ValueError("Slug只能包含小写字母、数字和连字符")
        return slug
    
    def to_dict(self, include_children: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "icon_url": self.icon_url,
            "sort_order": self.sort_order,
            "is_featured": self.is_featured,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_children and self.children:
            data["children"] = [child.to_dict(include_children=False) for child in self.children]
        
        return data
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class ContentCategory(Base):
    """
    内容-分类关联表
    多对多关系
    """
    __tablename__ = "content_categories"
    
    content_id = Column(PG_UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
    is_primary = Column(Boolean, default=False)  # 是否为主要分类
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    content = relationship("Content", back_populates="content_categories")
    category = relationship("Category", back_populates="content_categories")
    
    __table_args__ = (
        UniqueConstraint("content_id", "category_id", name="content_category_unique"),
    )
    
    def __repr__(self):
        return f"<ContentCategory(content_id={self.content_id}, category_id={self.category_id})>"


class Content(Base):
    """
    内容核心模型
    支持多种类型的内容（文章、视频、音频等）
    """
    __tablename__ = "content"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    excerpt = Column(Text)
    content = Column(Text, nullable=False)
    content_type = Column(String(50), nullable=False, default="article")
    format = Column(String(20), default="markdown")
    
    # 作者和所有权
    author_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(PG_UUID(as_uuid=True), nullable=True)
    
    # 状态管理
    status = Column(String(20), nullable=False, default="draft")
    visibility = Column(String(20), default="public")
    is_featured = Column(Boolean, default=False)
    is_sticky = Column(Boolean, default=False)
    is_commentable = Column(Boolean, default=True)
    
    # 元数据
    metadata = Column(JSONB, default=dict)
    tags = Column(ARRAY(String))  # 标签数组
    cover_image_url = Column(String(500))
    seo_title = Column(String(255))
    seo_description = Column(Text)
    seo_keywords = Column(ARRAY(String))
    
    # 统计
    view_count = Column(Integer, default=0)
    unique_view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    bookmark_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    
    # 时间管理
    published_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    reading_time_minutes = Column(Integer, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    author = relationship("User", foreign_keys=[author_id], back_populates="created_content")
    owner = relationship("User", foreign_keys=[owner_id])
    comments = relationship("Comment", back_populates="content", cascade="all, delete-orphan")
    content_tags = relationship("ContentTag", back_populates="content", cascade="all, delete-orphan")
    content_categories = relationship("ContentCategory", back_populates="content", cascade="all, delete-orphan")
    tags_obj = relationship("Tag", secondary="content_tags", back_populates="contents", viewonly=True)
    categories = relationship("Category", secondary="content_categories", back_populates="contents", viewonly=True)
    versions = relationship("ContentVersion", back_populates="content", cascade="all, delete-orphan")
    media_items = relationship("Media", back_populates="content", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("content_type IN ('article', 'video', 'audio', 'image', 'document', 'link')", 
                       name="content_type_enum"),
        CheckConstraint("format IN ('markdown', 'html', 'plaintext')", name="format_enum"),
        CheckConstraint("status IN ('draft', 'review', 'published', 'archived', 'deleted')", name="status_enum"),
        CheckConstraint("visibility IN ('public', 'private', 'unlisted', 'members_only')", name="visibility_enum"),
        CheckConstraint("length(title) >= 1 AND length(title) <= 255", name="chk_title_length"),
        CheckConstraint("slug ~* '^[a-z0-9]+(?:-[a-z0-9]+)*$'", name="chk_slug_format"),
    )
    
    @validates('slug')
    def validate_slug(self, key, slug):
        """验证slug格式"""
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug):
            raise ValueError("Slug只能包含小写字母、数字和连字符")
        return slug
    
    @hybrid_property
    def is_published(self) -> bool:
        """检查是否已发布"""
        return self.status == "published" and self.published_at is not None
    
    @hybrid_property
    def is_visible(self) -> bool:
        """检查内容是否可见"""
        if self.visibility == "public":
            return True
        elif self.visibility == "private":
            return False
        elif self.visibility == "unlisted":
            return True  # 需要特殊处理
        elif self.visibility == "members_only":
            return False  # 需要会员检查
        return False
    
    def increment_view_count(self, is_unique: bool = False):
        """增加查看计数"""
        self.view_count += 1
        if is_unique:
            self.unique_view_count += 1
    
    def increment_like_count(self, amount: int = 1):
        """增加点赞计数"""
        self.like_count += amount
    
    def increment_share_count(self, amount: int = 1):
        """增加分享计数"""
        self.share_count += amount
    
    def increment_bookmark_count(self, amount: int = 1):
        """增加收藏计数"""
        self.bookmark_count += amount
    
    def update_comment_count(self):
        """更新评论计数"""
        from sqlalchemy import func
        from src.core.database import SessionLocal
        
        with SessionLocal() as session:
            count = session.query(func.count(Comment.id)).filter(
                Comment.content_id == self.id,
                Comment.status == 'published',
                Comment.deleted_at.is_(None)
            ).scalar()
            self.comment_count = count or 0
    
    def publish(self):
        """发布内容"""
        if self.status != "published":
            self.status = "published"
            self.published_at = datetime.now()
    
    def unpublish(self):
        """取消发布"""
        self.status = "draft"
        self.published_at = None
    
    def to_dict(self, include_content: bool = True, include_author: bool = True) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "title": self.title,
            "slug": self.slug,
            "excerpt": self.excerpt,
            "content_type": self.content_type,
            "format": self.format,
            "status": self.status,
            "visibility": self.visibility,
            "is_featured": self.is_featured,
            "is_sticky": self.is_sticky,
            "is_commentable": self.is_commentable,
            "view_count": self.view_count,
            "unique_view_count": self.unique_view_count,
            "like_count": self.like_count,
            "share_count": self.share_count,
            "bookmark_count": self.bookmark_count,
            "comment_count": self.comment_count,
            "cover_image_url": self.cover_image_url,
            "reading_time_minutes": self.reading_time_minutes,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_content:
            data["content"] = self.content
        
        if include_author and self.author:
            data["author"] = {
                "id": str(self.author.id),
                "username": self.author.username,
                "full_name": self.author.full_name,
                "avatar_url": self.author.avatar_url,
            }
        
        # 添加标签和分类
        if self.tags:
            data["tags"] = self.tags
        
        if self.seo_title:
            data["seo_title"] = self.seo_title
        if self.seo_description:
            data["seo_description"] = self.seo_description
        if self.seo_keywords:
            data["seo_keywords"] = self.seo_keywords
        
        return data
    
    def __repr__(self):
        return f"<Content(id={self.id}, title='{self.title[:30]}...', status='{self.status}')>"


class ContentVersion(Base):
    """
    内容版本历史模型
    追踪内容的历史版本
    """
    __tablename__ = "content_versions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    content_id = Column(PG_UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    content = relationship("Content", back_populates="versions")
    author = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("content_id", "version_number", name="content_version_unique"),
    )
    
    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "content_id": str(self.content_id),
            "version_number": self.version_number,
            "title": self.title,
            "change_description": self.change_description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_content:
            data["content"] = self.content
        
        if self.author:
            data["author"] = {
                "id": str(self.author.id),
                "username": self.author.username,
                "full_name": self.author.full_name,
            }
        
        return data
    
    def __repr__(self):
        return f"<ContentVersion(id={self.id}, content_id={self.content_id}, version={self.version_number})>"


class Comment(Base):
    """
    评论模型
    支持嵌套评论和评论互动
    """
    __tablename__ = "comments"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    content_id = Column(PG_UUID(as_uuid=True), ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(PG_UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    content = Column(Text, nullable=False)
    
    # 状态管理
    status = Column(String(20), default="published")
    is_edited = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    
    # 元数据
    metadata = Column(JSONB, default=dict)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    # 统计
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    content_obj = relationship("Content", back_populates="comments")
    author = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    likes = relationship("CommentLike", back_populates="comment", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'published', 'hidden', 'deleted')", name="comment_status_enum"),
        CheckConstraint("length(content) >= 1 AND length(content) <= 5000", name="chk_comment_content"),
    )
    
    @hybrid_property
    def is_deleted(self) -> bool:
        """检查评论是否被删除"""
        return self.deleted_at is not None or self.status == "deleted"
    
    @hybrid_property
    def is_visible(self) -> bool:
        """检查评论是否可见"""
        return self.status == "published" and not self.is_deleted
    
    def increment_like_count(self):
        """增加点赞计数"""
        self.like_count += 1
    
    def decrement_like_count(self):
        """减少点赞计数"""
        if self.like_count > 0:
            self.like_count -= 1
    
    def increment_reply_count(self):
        """增加回复计数"""
        self.reply_count += 1
    
    def decrement_reply_count(self):
        """减少回复计数"""
        if self.reply_count > 0:
            self.reply_count -= 1
    
    def mark_as_edited(self):
        """标记为已编辑"""
        self.is_edited = True
    
    def to_dict(self, include_replies: bool = False, max_replies: int = 10) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "content_id": str(self.content_id),
            "content": self.content,
            "status": self.status,
            "is_edited": self.is_edited,
            "is_pinned": self.is_pinned,
            "like_count": self.like_count,
            "reply_count": self.reply_count,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if self.author:
            data["author"] = {
                "id": str(self.author.id),
                "username": self.author.username,
                "full_name": self.author.full_name,
                "avatar_url": self.author.avatar_url,
            }
        
        if include_replies and self.replies:
            data["replies"] = [
                reply.to_dict(include_replies=False) 
                for reply in sorted(self.replies, key=lambda x: x.created_at)[:max_replies]
                if reply.is_visible
            ]
        
        return data
    
    def __repr__(self):
        return f"<Comment(id={self.id}, user_id={self.user_id}, content_id={self.content_id})>"


class CommentLike(Base):
    """
    评论点赞关联表
    多对多关系
    """
    __tablename__ = "comment_likes"
    
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    comment_id = Column(PG_UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User")
    comment = relationship("Comment", back_populates="likes")
    
    def __repr__(self):
        return f"<CommentLike(user_id={self.user_id}, comment_id={self.comment_id})>"