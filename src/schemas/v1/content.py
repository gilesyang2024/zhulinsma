"""
内容相关的Pydantic模型
用于API请求和响应验证
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator, ConfigDict
import re


# ==================== 基础模型 ====================

class ContentBase(BaseModel):
    """内容基础模型"""
    
    title: str = Field(..., min_length=1, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    content: str = Field(..., min_length=1)
    content_type: str = Field("article", pattern=r'^(article|video|audio|image|document|link)$')
    format: str = Field("markdown", pattern=r'^(markdown|html|plaintext)$')
    status: str = Field("draft", pattern=r'^(draft|review|published|archived|deleted)$')
    visibility: str = Field("public", pattern=r'^(public|private|unlisted|members_only)$')
    
    tags: Optional[List[str]] = []
    cover_image_url: Optional[str] = Field(None, max_length=500)
    seo_title: Optional[str] = Field(None, max_length=255)
    seo_description: Optional[str] = Field(None, max_length=500)
    seo_keywords: Optional[List[str]] = []
    
    is_featured: bool = False
    is_sticky: bool = False
    is_commentable: bool = True
    
    @validator('title')
    def validate_title(cls, v):
        """验证标题"""
        if not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()
    
    @validator('cover_image_url')
    def validate_cover_image_url(cls, v):
        """验证封面图片URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('封面图片URL必须以http://或https://开头')
        return v


class ContentCreate(ContentBase):
    """内容创建模型"""
    pass


class ContentUpdate(BaseModel):
    """内容更新模型"""
    
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    content_type: Optional[str] = Field(None, pattern=r'^(article|video|audio|image|document|link)$')
    format: Optional[str] = Field(None, pattern=r'^(markdown|html|plaintext)$')
    status: Optional[str] = Field(None, pattern=r'^(draft|review|published|archived|deleted)$')
    visibility: Optional[str] = Field(None, pattern=r'^(public|private|unlisted|members_only)$')
    
    tags: Optional[List[str]] = None
    cover_image_url: Optional[str] = Field(None, max_length=500)
    seo_title: Optional[str] = Field(None, max_length=255)
    seo_description: Optional[str] = Field(None, max_length=500)
    seo_keywords: Optional[List[str]] = None
    
    is_featured: Optional[bool] = None
    is_sticky: Optional[bool] = None
    is_commentable: Optional[bool] = None


class ContentPublish(BaseModel):
    """内容发布模型"""
    
    publish_now: bool = True
    scheduled_at: Optional[datetime] = None


# ==================== 响应模型 ====================

class AuthorInfo(BaseModel):
    """作者信息"""
    
    id: UUID
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ContentPublic(BaseModel):
    """公开内容信息"""
    
    id: UUID
    slug: str
    title: str
    excerpt: Optional[str] = None
    content_type: str
    format: str
    status: str
    visibility: str
    
    tags: List[str] = []
    cover_image_url: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    seo_keywords: List[str] = []
    
    is_featured: bool = False
    is_sticky: bool = False
    is_commentable: bool = True
    
    view_count: int = 0
    unique_view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    bookmark_count: int = 0
    comment_count: int = 0
    
    reading_time_minutes: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    author: AuthorInfo
    
    model_config = ConfigDict(from_attributes=True)


class ContentDetail(ContentPublic):
    """内容详细信息"""
    
    content: str
    metadata: Dict[str, Any] = {}
    
    model_config = ConfigDict(from_attributes=True)


class ContentAdmin(BaseModel):
    """管理内容信息"""
    
    id: UUID
    slug: str
    title: str
    content_type: str
    status: str
    visibility: str
    
    author_id: UUID
    owner_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    
    is_featured: bool = False
    is_sticky: bool = False
    is_commentable: bool = True
    
    view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    bookmark_count: int = 0
    comment_count: int = 0
    
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 评论模型 ====================

class CommentBase(BaseModel):
    """评论基础模型"""
    
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[UUID] = None
    status: str = Field("published", pattern=r'^(pending|published|hidden|deleted)$')
    
    @validator('content')
    def validate_content(cls, v):
        """验证评论内容"""
        if not v.strip():
            raise ValueError('评论内容不能为空')
        return v.strip()


class CommentCreate(CommentBase):
    """评论创建模型"""
    pass


class CommentUpdate(BaseModel):
    """评论更新模型"""
    
    content: Optional[str] = Field(None, min_length=1, max_length=5000)
    status: Optional[str] = Field(None, pattern=r'^(pending|published|hidden|deleted)$')
    is_pinned: Optional[bool] = None


class CommentPublic(BaseModel):
    """公开评论信息"""
    
    id: UUID
    content: str
    status: str
    is_edited: bool = False
    is_pinned: bool = False
    like_count: int = 0
    reply_count: int = 0
    parent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    author: AuthorInfo
    
    model_config = ConfigDict(from_attributes=True)


class CommentDetail(CommentPublic):
    """评论详细信息"""
    
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 标签和分类模型 ====================

class TagBase(BaseModel):
    """标签基础模型"""
    
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon_url: Optional[str] = Field(None, max_length=500)
    
    @validator('name')
    def validate_name(cls, v):
        """验证标签名"""
        return v.strip()


class TagCreate(TagBase):
    """标签创建模型"""
    pass


class TagUpdate(BaseModel):
    """标签更新模型"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon_url: Optional[str] = Field(None, max_length=500)


class TagResponse(TagBase):
    """标签响应模型"""
    
    id: UUID
    slug: str
    usage_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    """分类基础模型"""
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[UUID] = None
    icon_url: Optional[str] = Field(None, max_length=500)
    sort_order: int = 0
    is_featured: bool = False
    
    @validator('name')
    def validate_name(cls, v):
        """验证分类名"""
        return v.strip()


class CategoryCreate(CategoryBase):
    """分类创建模型"""
    pass


class CategoryUpdate(BaseModel):
    """分类更新模型"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[UUID] = None
    icon_url: Optional[str] = Field(None, max_length=500)
    sort_order: Optional[int] = None
    is_featured: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """分类响应模型"""
    
    id: UUID
    slug: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class CategoryTree(CategoryResponse):
    """分类树响应模型"""
    
    children: List["CategoryTree"] = []
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 查询参数模型 ====================

class ContentQueryParams(BaseModel):
    """内容查询参数模型"""
    
    q: Optional[str] = None  # 搜索关键词
    content_type: Optional[str] = Field(None, pattern=r'^(article|video|audio|image|document|link)$')
    status: Optional[str] = Field(None, pattern=r'^(draft|review|published|archived|deleted)$')
    visibility: Optional[str] = Field(None, pattern=r'^(public|private|unlisted|members_only)$')
    author_id: Optional[UUID] = None
    tag: Optional[str] = None
    category_id: Optional[UUID] = None
    is_featured: Optional[bool] = None
    is_sticky: Optional[bool] = None
    is_commentable: Optional[bool] = None
    
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    published_from: Optional[datetime] = None
    published_to: Optional[datetime] = None
    
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    sort_by: str = Field("created_at", pattern=r'^(created_at|updated_at|published_at|view_count|like_count|comment_count)$')
    sort_order: str = Field("desc", pattern=r'^(asc|desc)$')


class CommentQueryParams(BaseModel):
    """评论查询参数模型"""
    
    content_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern=r'^(pending|published|hidden|deleted)$')
    parent_id: Optional[UUID] = None
    is_pinned: Optional[bool] = None
    
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)
    sort_by: str = Field("created_at", pattern=r'^(created_at|updated_at|like_count)$')
    sort_order: str = Field("desc", pattern=r'^(asc|desc)$')


class TagQueryParams(BaseModel):
    """标签查询参数模型"""
    
    q: Optional[str] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)
    sort_by: str = Field("usage_count", pattern=r'^(name|usage_count|created_at)$')
    sort_order: str = Field("desc", pattern=r'^(asc|desc)$')


class CategoryQueryParams(BaseModel):
    """分类查询参数模型"""
    
    q: Optional[str] = None
    parent_id: Optional[UUID] = None
    is_featured: Optional[bool] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=200)
    sort_by: str = Field("sort_order", pattern=r'^(name|sort_order|created_at)$')
    sort_order: str = Field("asc", pattern=r'^(asc|desc)$')


# ==================== 分页响应模型 ====================

class ContentListResponse(BaseModel):
    """内容列表响应模型"""
    
    items: List[ContentPublic]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CommentListResponse(BaseModel):
    """评论列表响应模型"""
    
    items: List[CommentPublic]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class TagListResponse(BaseModel):
    """标签列表响应模型"""
    
    items: List[TagResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class CategoryListResponse(BaseModel):
    """分类列表响应模型"""
    
    items: List[CategoryResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


# ==================== 统计模型 ====================

class ContentStatistics(BaseModel):
    """内容统计"""
    
    content_id: UUID
    view_count: int = 0
    unique_view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    bookmark_count: int = 0
    comment_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)


class ContentAnalytics(BaseModel):
    """内容分析"""
    
    date: str
    views: int = 0
    unique_views: int = 0
    likes: int = 0
    shares: int = 0
    comments: int = 0