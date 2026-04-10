"""
内容管理API路由模块

处理内容相关的CRUD操作、评论、标签、分类等功能。
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.content import Content, Comment, Tag, Category
from src.models.user import UserStatistics
from src.schemas.v1.content import (
    ContentCreate, ContentUpdate, ContentPublish, ContentPublic, ContentDetail,
    ContentAdmin, CommentCreate, CommentUpdate, CommentPublic, CommentDetail,
    TagCreate, TagUpdate, TagResponse, CategoryCreate, CategoryUpdate, CategoryResponse,
    ContentQueryParams, CommentQueryParams, TagQueryParams, CategoryQueryParams,
    ContentListResponse, CommentListResponse, TagListResponse, CategoryListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])


# ==================== 依赖函数 ====================

async def get_content_or_404(
    content_id: UUID = Path(..., description="内容ID"),
    db: Session = Depends(get_db)
) -> Content:
    """获取内容或返回404"""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"内容 {content_id} 不存在"
        )
    return content


async def get_comment_or_404(
    comment_id: UUID = Path(..., description="评论ID"),
    db: Session = Depends(get_db)
) -> Comment:
    """获取评论或返回404"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"评论 {comment_id} 不存在"
        )
    return comment


async def get_tag_or_404(
    tag_id: UUID = Path(..., description="标签ID"),
    db: Session = Depends(get_db)
) -> Tag:
    """获取标签或返回404"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 {tag_id} 不存在"
        )
    return tag


async def get_category_or_404(
    category_id: UUID = Path(..., description="分类ID"),
    db: Session = Depends(get_db)
) -> Category:
    """获取分类或返回404"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分类 {category_id} 不存在"
        )
    return category


# ==================== 公开内容接口 ====================

@router.get("", response_model=ContentListResponse)
async def list_contents(
    query_params: ContentQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    获取内容列表（支持分页和过滤）
    """
    # 构建查询 - 只显示已发布且公开的内容
    query = db.query(Content).filter(
        Content.status == "published",
        Content.visibility == "public",
        Content.deleted_at.is_(None)
    )
    
    # 应用过滤条件
    if query_params.q:
        query = query.filter(
            or_(
                Content.title.ilike(f"%{query_params.q}%"),
                Content.excerpt.ilike(f"%{query_params.q}%"),
                Content.content.ilike(f"%{query_params.q}%")
            )
        )
    
    if query_params.content_type:
        query = query.filter(Content.content_type == query_params.content_type)
    
    if query_params.author_id:
        query = query.filter(Content.author_id == query_params.author_id)
    
    if query_params.tag:
        query = query.filter(Content.tags.contains([query_params.tag]))
    
    if query_params.category_id:
        from src.models.content import ContentCategory
        query = query.join(ContentCategory).filter(
            ContentCategory.category_id == query_params.category_id
        )
    
    if query_params.is_featured is not None:
        query = query.filter(Content.is_featured == query_params.is_featured)
    
    if query_params.is_sticky is not None:
        query = query.filter(Content.is_sticky == query_params.is_sticky)
    
    if query_params.is_commentable is not None:
        query = query.filter(Content.is_commentable == query_params.is_commentable)
    
    if query_params.created_from:
        query = query.filter(Content.created_at >= query_params.created_from)
    
    if query_params.created_to:
        query = query.filter(Content.created_at <= query_params.created_to)
    
    if query_params.published_from:
        query = query.filter(Content.published_at >= query_params.published_from)
    
    if query_params.published_to:
        query = query.filter(Content.published_at <= query_params.published_to)
    
    # 获取总数
    total = query.count()
    
    # 应用排序
    if query_params.sort_by == "updated_at":
        order_by = Content.updated_at if query_params.sort_order == "asc" else Content.updated_at.desc()
    elif query_params.sort_by == "published_at":
        order_by = Content.published_at if query_params.sort_order == "asc" else Content.published_at.desc()
    elif query_params.sort_by == "view_count":
        order_by = Content.view_count if query_params.sort_order == "asc" else Content.view_count.desc()
    elif query_params.sort_by == "like_count":
        order_by = Content.like_count if query_params.sort_order == "asc" else Content.like_count.desc()
    elif query_params.sort_by == "comment_count":
        order_by = Content.comment_count if query_params.sort_order == "asc" else Content.comment_count.desc()
    else:  # created_at
        order_by = Content.created_at if query_params.sort_order == "asc" else Content.created_at.desc()
    
    query = query.order_by(order_by)
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    contents = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return ContentListResponse(
        items=[ContentPublic.from_orm(content) for content in contents],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.get("/{content_id}", response_model=ContentPublic)
async def get_content(
    content: Content = Depends(get_content_or_404),
    db: Session = Depends(get_db)
):
    """
    获取内容详情
    """
    # 检查内容是否可见
    if content.status != "published" or content.visibility != "public":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="内容不存在或不可访问"
        )
    
    # 增加查看计数
    content.increment_view_count(is_unique=True)
    db.commit()
    
    return ContentPublic.from_orm(content)


# ==================== 内容管理接口（需要认证） ====================

@router.post("", response_model=ContentDetail)
async def create_content(
    content_data: ContentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    创建新内容
    """
    user_id = UUID(current_user["sub"])
    
    # 生成slug
    import re
    from unidecode import unidecode
    
    slug_base = re.sub(r'[^\w\s-]', '', content_data.title.lower())
    slug_base = unidecode(slug_base)
    slug = re.sub(r'[-\s]+', '-', slug_base).strip('-')
    
    # 确保slug唯一
    counter = 1
    original_slug = slug
    while db.query(Content).filter(Content.slug == slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1
    
    # 计算阅读时间（假设每分钟阅读200字）
    word_count = len(content_data.content.split())
    reading_time = max(1, word_count // 200)
    
    # 创建内容
    content_dict = content_data.dict()
    content = Content(
        **content_dict,
        slug=slug,
        author_id=user_id,
        reading_time_minutes=reading_time,
        tags=content_dict.get("tags", []) or []
    )
    
    db.add(content)
    db.commit()
    db.refresh(content)
    
    # 更新作者的内容计数
    stats = db.query(UserStatistics).filter(UserStatistics.user_id == user_id).first()
    if stats:
        stats.increment_content_count()
        db.commit()
    
    return ContentDetail.from_orm(content)


@router.put("/{content_id}", response_model=ContentDetail)
async def update_content(
    content_data: ContentUpdate,
    content: Content = Depends(get_content_or_404),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    更新内容
    """
    user_id = UUID(current_user["sub"])
    
    # 检查权限
    if content.author_id != user_id and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此内容"
        )
    
    # 更新内容
    update_data = content_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)
    
    # 如果内容有更新，计算新的阅读时间
    if "content" in update_data:
        word_count = len(content.content.split())
        content.reading_time_minutes = max(1, word_count // 200)
    
    content.updated_at = datetime.now()
    db.commit()
    db.refresh(content)
    
    return ContentDetail.from_orm(content)


@router.post("/{content_id}/publish")
async def publish_content(
    publish_data: ContentPublish,
    content: Content = Depends(get_content_or_404),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    发布内容
    """
    user_id = UUID(current_user["sub"])
    
    # 检查权限
    if content.author_id != user_id and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权发布此内容"
        )
    
    if publish_data.publish_now:
        content.status = "published"
        content.published_at = datetime.now()
    elif publish_data.scheduled_at:
        content.status = "review"  # 待发布状态
        content.scheduled_at = publish_data.scheduled_at
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请指定发布时间"
        )
    
    content.updated_at = datetime.now()
    db.commit()
    
    return {"message": "内容已发布"}


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content: Content = Depends(get_content_or_404),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    删除内容（软删除）
    """
    user_id = UUID(current_user["sub"])
    
    # 检查权限
    if content.author_id != user_id and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此内容"
        )
    
    content.status = "deleted"
    content.deleted_at = datetime.now()
    db.commit()


# ==================== 评论接口 ====================

@router.get("/{content_id}/comments", response_model=CommentListResponse)
async def list_comments(
    content: Content = Depends(get_content_or_404),
    query_params: CommentQueryParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    获取内容评论列表
    """
    # 构建查询
    query = db.query(Comment).filter(
        Comment.content_id == content.id,
        Comment.status == "published",
        Comment.deleted_at.is_(None)
    )
    
    # 只显示顶级评论
    query = query.filter(Comment.parent_id.is_(None))
    
    # 获取总数
    total = query.count()
    
    # 应用排序
    if query_params.sort_by == "updated_at":
        order_by = Comment.updated_at if query_params.sort_order == "asc" else Comment.updated_at.desc()
    elif query_params.sort_by == "like_count":
        order_by = Comment.like_count if query_params.sort_order == "asc" else Comment.like_count.desc()
    else:  # created_at
        order_by = Comment.created_at if query_params.sort_order == "asc" else Comment.created_at.desc()
    
    query = query.order_by(order_by)
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    comments = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return CommentListResponse(
        items=[CommentPublic.from_orm(comment) for comment in comments],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/{content_id}/comments", response_model=CommentPublic)
async def create_comment(
    comment_data: CommentCreate,
    content: Content = Depends(get_content_or_404),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    创建评论
    """
    user_id = UUID(current_user["sub"])
    
    # 检查内容是否允许评论
    if not content.is_commentable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此内容不允许评论"
        )
    
    # 检查父评论是否存在
    if comment_data.parent_id:
        parent = db.query(Comment).filter(Comment.id == comment_data.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="父评论不存在"
            )
        
        # 增加父评论的回复计数
        parent.increment_reply_count()
    
    # 创建评论
    comment = Comment(
        **comment_data.dict(),
        content_id=content.id,
        user_id=user_id
    )
    
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    # 更新内容的评论计数
    content.update_comment_count()
    
    # 更新作者的评论计数
    stats = db.query(UserStatistics).filter(UserStatistics.user_id == user_id).first()
    if stats:
        stats.increment_comment_count()
    
    db.commit()
    
    return CommentPublic.from_orm(comment)


# ==================== 标签接口 ====================

@router.get("/tags", response_model=TagListResponse)
async def list_tags(
    query_params: TagQueryParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    获取标签列表
    """
    query = db.query(Tag)
    
    if query_params.q:
        query = query.filter(
            or_(
                Tag.name.ilike(f"%{query_params.q}%"),
                Tag.description.ilike(f"%{query_params.q}%")
            )
        )
    
    # 获取总数
    total = query.count()
    
    # 应用排序
    if query_params.sort_by == "name":
        order_by = Tag.name if query_params.sort_order == "asc" else Tag.name.desc()
    elif query_params.sort_by == "created_at":
        order_by = Tag.created_at if query_params.sort_order == "asc" else Tag.created_at.desc()
    else:  # usage_count
        order_by = Tag.usage_count if query_params.sort_order == "asc" else Tag.usage_count.desc()
    
    query = query.order_by(order_by)
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    tags = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return TagListResponse(
        items=[TagResponse.from_orm(tag) for tag in tags],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


# ==================== 分类接口 ====================

@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    query_params: CategoryQueryParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    获取分类列表
    """
    query = db.query(Category)
    
    if query_params.q:
        query = query.filter(
            or_(
                Category.name.ilike(f"%{query_params.q}%"),
                Category.description.ilike(f"%{query_params.q}%")
            )
        )
    
    if query_params.parent_id:
        query = query.filter(Category.parent_id == query_params.parent_id)
    else:
        query = query.filter(Category.parent_id.is_(None))  # 只显示顶级分类
    
    if query_params.is_featured is not None:
        query = query.filter(Category.is_featured == query_params.is_featured)
    
    # 获取总数
    total = query.count()
    
    # 应用排序
    if query_params.sort_by == "name":
        order_by = Category.name if query_params.sort_order == "asc" else Category.name.desc()
    elif query_params.sort_by == "created_at":
        order_by = Category.created_at if query_params.sort_order == "asc" else Category.created_at.desc()
    else:  # sort_order
        order_by = Category.sort_order if query_params.sort_order == "asc" else Category.sort_order.desc()
    
    query = query.order_by(order_by)
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    categories = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return CategoryListResponse(
        items=[CategoryResponse.from_orm(category) for category in categories],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )