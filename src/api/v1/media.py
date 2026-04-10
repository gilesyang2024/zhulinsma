"""
媒体管理API路由模块

处理媒体文件的上传、下载、管理和处理任务等功能。
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Query, Path, Body, File, UploadFile, Form
)
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from src.core.database import get_db
from src.core.security import get_current_user
from src.core.config import settings
from src.models.user import User
from src.models.media import Media, MediaProcessTask
from src.schemas.v1.media import (
    MediaCreate, MediaUpdate, MediaResponse, MediaDetailResponse,
    MediaListResponse, MediaUploadRequest, MediaUploadResponse,
    MediaQueryParams, MediaProcessTaskCreate, MediaProcessTaskUpdate,
    MediaProcessTaskResponse, MediaProcessTaskListResponse,
    MediaProcessTaskQueryParams, MultipartUploadInit,
    MultipartUploadInitResponse, MultipartUploadComplete
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

# 确保上传目录存在
UPLOAD_DIR = Path(settings.UPLOAD_DIR) if hasattr(settings, 'UPLOAD_DIR') else Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ==================== 依赖函数 ====================

async def get_media_or_404(
    media_id: UUID = Path(..., description="媒体ID"),
    db: Session = Depends(get_db)
) -> Media:
    """获取媒体或返回404"""
    media = db.query(Media).filter(Media.id == media_id).first()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"媒体 {media_id} 不存在"
        )
    return media


async def get_media_process_task_or_404(
    task_id: UUID = Path(..., description="任务ID"),
    db: Session = Depends(get_db)
) -> MediaProcessTask:
    """获取媒体处理任务或返回404"""
    task = db.query(MediaProcessTask).filter(MediaProcessTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"媒体处理任务 {task_id} 不存在"
        )
    return task


async def check_media_permission(
    media: Media = Depends(get_media_or_404),
    current_user: dict = Depends(get_current_user)
) -> Media:
    """检查用户是否有权限访问媒体"""
    user_id = UUID(current_user["sub"])
    
    # 管理员可以访问所有媒体
    if current_user.get("is_admin", False) or current_user.get("is_superuser", False):
        return media
    
    # 公开媒体任何人都可以访问
    if media.is_public:
        return media
    
    # 用户只能访问自己上传的私有媒体
    if str(media.uploaded_by) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此媒体"
        )
    
    return media


# ==================== 媒体管理接口 ====================

@router.get("/", response_model=MediaListResponse)
async def list_media(
    params: MediaQueryParams = Depends(),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取媒体列表
    """
    user_id = UUID(current_user["sub"])
    is_admin = current_user.get("is_admin", False) or current_user.get("is_superuser", False)
    
    # 构建查询
    query = db.query(Media)
    
    # 权限过滤：非管理员只能查看公开媒体或自己上传的媒体
    if not is_admin:
        query = query.filter(
            or_(
                Media.is_public == True,
                Media.uploaded_by == user_id
            )
        )
    
    # 应用过滤条件
    if params.file_type:
        query = query.filter(Media.file_type == params.file_type)
    
    if params.is_public is not None:
        query = query.filter(Media.is_public == params.is_public)
    
    if params.is_processed is not None:
        query = query.filter(Media.is_processed == params.is_processed)
    
    if params.tags:
        # 使用PostgreSQL的数组包含操作符
        query = query.filter(Media.tags.contains(params.tags))
    
    if params.uploaded_by:
        query = query.filter(Media.uploaded_by == params.uploaded_by)
    
    if params.start_date:
        query = query.filter(Media.created_at >= params.start_date)
    
    if params.end_date:
        query = query.filter(Media.created_at <= params.end_date)
    
    if params.search:
        search_pattern = f"%{params.search}%"
        query = query.filter(
            or_(
                Media.filename.ilike(search_pattern),
                Media.original_filename.ilike(search_pattern)
            )
        )
    
    # 计算总数
    total = query.count()
    
    # 应用排序
    order_column = getattr(Media, params.order_by, Media.created_at)
    order_func = desc if params.order == "desc" else asc
    query = query.order_by(order_func(order_column))
    
    # 分页
    items = query.offset((params.page - 1) * params.page_size).limit(params.page_size).all()
    
    # 计算总页数
    total_pages = (total + params.page_size - 1) // params.page_size
    
    return MediaListResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages
    )


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(..., description="媒体文件"),
    is_public: bool = Form(default=True),
    tags: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传媒体文件
    """
    user_id = UUID(current_user["sub"])
    
    try:
        # 生成唯一文件名
        file_ext = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid4().hex}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 解析标签和元数据
        tags_list = tags.split(",") if tags else []
        metadata_dict = eval(metadata) if metadata else {}  # 简单实现，生产环境需要安全解析
        
        # 创建媒体记录
        media = Media(
            id=uuid4(),
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path.relative_to(Path.cwd())),
            file_size=file_path.stat().st_size,
            file_type=file_ext[1:] if file_ext.startswith(".") else file_ext,
            mime_type=file.content_type or "application/octet-stream",
            storage_type="local",
            is_public=is_public,
            tags=tags_list,
            metadata=metadata_dict,
            uploaded_by=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(media)
        db.commit()
        db.refresh(media)
        
        # 记录上传日志
        logger.info(f"用户 {user_id} 上传了媒体文件: {file.filename} ({media.id})")
        
        return MediaUploadResponse(
            id=media.id,
            filename=media.filename,
            original_filename=media.original_filename,
            file_size=media.file_size,
            file_type=media.file_type,
            mime_type=media.mime_type,
            thumbnail_url=None,  # 需要后续处理生成
            preview_url=None,   # 需要后续处理生成
            upload_url=f"/api/v1/media/{media.id}/download",
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
    except Exception as e:
        logger.error(f"上传媒体文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


@router.get("/{media_id}", response_model=MediaDetailResponse)
async def get_media_detail(
    media: Media = Depends(check_media_permission),
    db: Session = Depends(get_db)
):
    """
    获取媒体详情
    """
    # 加载上传用户信息
    media_with_user = (
        db.query(Media)
        .options(joinedload(Media.uploader))
        .filter(Media.id == media.id)
        .first()
    )
    
    return MediaDetailResponse.from_orm(media_with_user)


@router.get("/{media_id}/download")
async def download_media(
    media: Media = Depends(check_media_permission),
    db: Session = Depends(get_db)
):
    """
    下载媒体文件
    """
    file_path = Path(media.file_path)
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="媒体文件不存在"
        )
    
    # 更新下载计数（如果有此字段）
    if hasattr(media, 'download_count'):
        media.download_count += 1
        media.updated_at = datetime.now()
        db.commit()
    
    return FileResponse(
        path=file_path,
        filename=media.original_filename,
        media_type=media.mime_type
    )


@router.put("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_update: MediaUpdate,
    media: Media = Depends(get_media_or_404),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新媒体信息
    """
    user_id = UUID(current_user["sub"])
    
    # 检查权限：只有管理员或上传者可以更新
    if (not current_user.get("is_admin", False) and 
        not current_user.get("is_superuser", False) and
        str(media.uploaded_by) != current_user["sub"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限更新此媒体"
        )
    
    # 更新字段
    update_data = media_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(media, field, value)
    
    media.updated_at = datetime.now()
    db.commit()
    db.refresh(media)
    
    return MediaResponse.from_orm(media)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media: Media = Depends(get_media_or_404),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除媒体
    """
    user_id = UUID(current_user["sub"])
    
    # 检查权限：只有管理员或上传者可以删除
    if (not current_user.get("is_admin", False) and 
        not current_user.get("is_superuser", False) and
        str(media.uploaded_by) != current_user["sub"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此媒体"
        )
    
    # 删除文件
    file_path = Path(media.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # 删除数据库记录
    db.delete(media)
    db.commit()
    
    logger.info(f"用户 {user_id} 删除了媒体文件: {media.id}")


# ==================== 媒体处理任务接口 ====================

@router.get("/tasks/", response_model=MediaProcessTaskListResponse)
async def list_media_process_tasks(
    params: MediaProcessTaskQueryParams = Depends(),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取媒体处理任务列表
    """
    user_id = UUID(current_user["sub"])
    is_admin = current_user.get("is_admin", False) or current_user.get("is_superuser", False)
    
    # 构建查询
    query = db.query(MediaProcessTask).join(Media)
    
    # 权限过滤：非管理员只能查看自己媒体的处理任务
    if not is_admin:
        query = query.filter(Media.uploaded_by == user_id)
    
    # 应用过滤条件
    if params.media_id:
        query = query.filter(MediaProcessTask.media_id == params.media_id)
    
    if params.task_type:
        query = query.filter(MediaProcessTask.task_type == params.task_type)
    
    if params.status:
        query = query.filter(MediaProcessTask.status == params.status)
    
    if params.priority:
        query = query.filter(MediaProcessTask.priority == params.priority)
    
    if params.start_date:
        query = query.filter(MediaProcessTask.created_at >= params.start_date)
    
    if params.end_date:
        query = query.filter(MediaProcessTask.created_at <= params.end_date)
    
    # 计算总数
    total = query.count()
    
    # 应用排序
    order_column = getattr(MediaProcessTask, params.order_by, MediaProcessTask.created_at)
    order_func = desc if params.order == "desc" else asc
    query = query.order_by(order_func(order_column))
    
    # 分页
    items = query.offset((params.page - 1) * params.page_size).limit(params.page_size).all()
    
    # 计算总页数
    total_pages = (total + params.page_size - 1) // params.page_size
    
    return MediaProcessTaskListResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages
    )


@router.post("/{media_id}/tasks", response_model=MediaProcessTaskResponse)
async def create_media_process_task(
    media_id: UUID = Path(..., description="媒体ID"),
    task_create: MediaProcessTaskCreate = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建媒体处理任务
    """
    # 检查媒体是否存在
    media = await get_media_or_404(media_id, db)
    
    # 检查权限：只有管理员或上传者可以创建处理任务
    if (not current_user.get("is_admin", False) and 
        not current_user.get("is_superuser", False) and
        str(media.uploaded_by) != current_user["sub"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限为此媒体创建处理任务"
        )
    
    # 创建处理任务
    task = MediaProcessTask(
        id=uuid4(),
        media_id=media_id,
        task_type=task_create.task_type,
        status="pending",
        priority=task_create.priority,
        parameters=task_create.parameters,
        retry_count=0,
        max_retries=3,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    logger.info(f"为媒体 {media_id} 创建了处理任务: {task.id} ({task.task_type})")
    
    return MediaProcessTaskResponse.from_orm(task)


@router.get("/tasks/{task_id}", response_model=MediaProcessTaskResponse)
async def get_media_process_task(
    task: MediaProcessTask = Depends(get_media_process_task_or_404),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取媒体处理任务详情
    """
    # 检查权限：只有管理员或媒体上传者可以查看
    media = await get_media_or_404(task.media_id, db)
    
    if (not current_user.get("is_admin", False) and 
        not current_user.get("is_superuser", False) and
        str(media.uploaded_by) != current_user["sub"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限查看此处理任务"
        )
    
    return MediaProcessTaskResponse.from_orm(task)


@router.put("/tasks/{task_id}", response_model=MediaProcessTaskResponse)
async def update_media_process_task(
    task_update: MediaProcessTaskUpdate,
    task: MediaProcessTask = Depends(get_media_process_task_or_404),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新媒体处理任务
    """
    # 检查权限：只有管理员可以更新处理任务
    if not current_user.get("is_admin", False) and not current_user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    # 更新字段
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    task.updated_at = datetime.now()
    db.commit()
    db.refresh(task)
    
    return MediaProcessTaskResponse.from_orm(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media_process_task(
    task: MediaProcessTask = Depends(get_media_process_task_or_404),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除媒体处理任务
    """
    # 检查权限：只有管理员可以删除处理任务
    if not current_user.get("is_admin", False) and not current_user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    db.delete(task)
    db.commit()
    
    logger.info(f"删除了媒体处理任务: {task.id}")