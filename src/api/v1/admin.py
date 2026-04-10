"""
管理后台API路由模块

提供系统管理员使用的管理功能，包括用户管理、内容审核、系统监控等。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Query, Path, Body, BackgroundTasks
)
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User, Role, UserRole, UserSettings, UserStatistics
from src.models.content import Content, Comment, Tag, Category
from src.models.media import Media, AuditLog
from src.schemas.v1.user import (
    UserPublic, UserDetail, UserUpdate, RoleCreate, RoleUpdate, 
    RoleResponse, UserRoleAssign, UserRoleResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== 依赖函数 ====================

async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if not current_user.get("is_admin", False) and not current_user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def require_superuser(current_user: dict = Depends(get_current_user)) -> dict:
    """要求超级管理员权限"""
    if not current_user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user


# ==================== 系统统计接口 ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    获取管理后台仪表盘统计信息
    """
    try:
        # 用户统计
        total_users = db.query(func.count(User.id)).scalar()
        active_users = db.query(func.count(User.id)).filter(
            User.is_active == True,
            User.last_active_at >= datetime.now() - timedelta(days=30)
        ).scalar()
        new_users_today = db.query(func.count(User.id)).filter(
            User.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).scalar()
        
        # 内容统计
        total_content = db.query(func.count(Content.id)).scalar()
        published_content = db.query(func.count(Content.id)).filter(
            Content.status == "published"
        ).scalar()
        new_content_today = db.query(func.count(Content.id)).filter(
            Content.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).scalar()
        
        # 媒体统计
        total_media = db.query(func.count(Media.id)).scalar()
        media_size = db.query(func.sum(Media.file_size)).scalar() or 0
        
        # 评论统计
        total_comments = db.query(func.count(Comment.id)).scalar()
        new_comments_today = db.query(func.count(Comment.id)).filter(
            Comment.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).scalar()
        
        # 待审核内容
        pending_content = db.query(func.count(Content.id)).filter(
            Content.status == "pending_review"
        ).scalar()
        pending_comments = db.query(func.count(Comment.id)).filter(
            Comment.status == "pending_review"
        ).scalar()
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "new_today": new_users_today
            },
            "content": {
                "total": total_content,
                "published": published_content,
                "new_today": new_content_today,
                "pending_review": pending_content
            },
            "media": {
                "total": total_media,
                "total_size_bytes": media_size,
                "total_size_mb": round(media_size / (1024 * 1024), 2) if media_size else 0
            },
            "comments": {
                "total": total_comments,
                "new_today": new_comments_today,
                "pending_review": pending_comments
            },
            "system": {
                "timestamp": datetime.now().isoformat(),
                "uptime_days": 0  # 实际实现中应该从系统启动时间计算
            }
        }
        
    except Exception as e:
        logger.error(f"获取仪表盘统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}"
        )


# ==================== 用户管理接口 ====================

@router.get("/users", response_model=List[UserDetail])
async def admin_list_users(
    search: Optional[str] = Query(None, description="搜索用户名或邮箱"),
    status: Optional[str] = Query(None, description="用户状态: active, inactive, locked"),
    role: Optional[str] = Query(None, description="角色名称"),
    start_date: Optional[datetime] = Query(None, description="注册开始日期"),
    end_date: Optional[datetime] = Query(None, description="注册结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    管理员查看用户列表
    """
    query = db.query(User)
    
    # 应用过滤条件
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "inactive":
        query = query.filter(User.is_active == False)
    elif status == "locked":
        query = query.filter(User.locked_until.isnot(None))
    
    if role:
        query = query.join(UserRole).join(Role).filter(Role.name == role)
    
    if start_date:
        query = query.filter(User.created_at >= start_date)
    
    if end_date:
        query = query.filter(User.created_at <= end_date)
    
    # 分页
    users = query.order_by(desc(User.created_at)) \
                .offset((page - 1) * page_size) \
                .limit(page_size) \
                .all()
    
    return [UserDetail.from_orm(user) for user in users]


@router.put("/users/{user_id}/activate")
async def admin_activate_user(
    user_id: UUID = Path(..., description="用户ID"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    管理员激活用户
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.is_active = True
    user.locked_until = None
    user.failed_login_attempts = 0
    user.updated_at = datetime.now()
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_activate_user",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"activated_by": current_user.get("username")},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"管理员 {current_user.get('username')} 激活了用户 {user.username}")
    
    return {"message": "用户已激活"}


@router.put("/users/{user_id}/deactivate")
async def admin_deactivate_user(
    user_id: UUID = Path(..., description="用户ID"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    管理员停用用户
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.is_active = False
    user.updated_at = datetime.now()
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_deactivate_user",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"deactivated_by": current_user.get("username")},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"管理员 {current_user.get('username')} 停用了用户 {user.username}")
    
    return {"message": "用户已停用"}


@router.put("/users/{user_id}/unlock")
async def admin_unlock_user(
    user_id: UUID = Path(..., description="用户ID"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    管理员解锁用户
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.locked_until = None
    user.failed_login_attempts = 0
    user.updated_at = datetime.now()
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_unlock_user",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"unlocked_by": current_user.get("username")},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"管理员 {current_user.get('username')} 解锁了用户 {user.username}")
    
    return {"message": "用户已解锁"}


# ==================== 内容审核接口 ====================

@router.get("/content/pending-review", response_model=List[Any])  # 简化响应模型
async def get_pending_content_review(
    content_type: Optional[str] = Query(None, description="内容类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    获取待审核内容列表
    """
    query = db.query(Content).filter(Content.status == "pending_review")
    
    if content_type:
        query = query.filter(Content.content_type == content_type)
    
    content_items = query.order_by(Content.created_at) \
                        .offset((page - 1) * page_size) \
                        .limit(page_size) \
                        .all()
    
    # 简化响应
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "author": db.query(User).filter(User.id == item.author_id).first().username if item.author_id else None,
            "content_type": item.content_type,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "excerpt": item.excerpt[:100] + "..." if item.excerpt and len(item.excerpt) > 100 else item.excerpt
        }
        for item in content_items
    ]


@router.put("/content/{content_id}/approve")
async def approve_content(
    content_id: UUID = Path(..., description="内容ID"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    批准内容
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="内容不存在"
        )
    
    if content.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="内容不在待审核状态"
        )
    
    content.status = "published"
    content.updated_at = datetime.now()
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_approve_content",
        resource_type="content",
        resource_id=str(content_id),
        metadata={
            "approved_by": current_user.get("username"),
            "content_title": content.title
        },
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"管理员 {current_user.get('username')} 批准了内容: {content.title}")
    
    return {"message": "内容已批准"}


@router.put("/content/{content_id}/reject")
async def reject_content(
    content_id: UUID = Path(..., description="内容ID"),
    reason: str = Body(..., embed=True, description="拒绝原因"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    拒绝内容
    """
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="内容不存在"
        )
    
    if content.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="内容不在待审核状态"
        )
    
    content.status = "rejected"
    content.updated_at = datetime.now()
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_reject_content",
        resource_type="content",
        resource_id=str(content_id),
        metadata={
            "rejected_by": current_user.get("username"),
            "content_title": content.title,
            "reason": reason
        },
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"管理员 {current_user.get('username')} 拒绝了内容: {content.title}, 原因: {reason}")
    
    return {"message": "内容已拒绝"}


# ==================== 角色管理接口 ====================

@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_create: RoleCreate,
    current_user: dict = Depends(require_superuser),
    db: Session = Depends(get_db)
):
    """
    创建新角色（仅超级管理员）
    """
    # 检查角色名是否已存在
    existing_role = db.query(Role).filter(Role.name == role_create.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名已存在"
        )
    
    # 创建角色
    role = Role(
        id=uuid4(),
        name=role_create.name,
        description=role_create.description,
        permissions=role_create.permissions,
        is_default=role_create.is_default,
        is_system=False,  # 用户创建的角色不是系统角色
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(role)
    db.commit()
    db.refresh(role)
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_create_role",
        resource_type="role",
        resource_id=str(role.id),
        metadata={"created_by": current_user.get("username"), "role_name": role.name},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"超级管理员 {current_user.get('username')} 创建了角色: {role.name}")
    
    return RoleResponse.from_orm(role)


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID = Path(..., description="角色ID"),
    role_update: RoleUpdate = Body(...),
    current_user: dict = Depends(require_superuser),
    db: Session = Depends(get_db)
):
    """
    更新角色信息（仅超级管理员）
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 不能修改系统角色
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改系统角色"
        )
    
    # 检查角色名是否重复
    if role_update.name and role_update.name != role.name:
        existing_role = db.query(Role).filter(Role.name == role_update.name).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色名已存在"
            )
    
    # 更新字段
    update_data = role_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)
    
    role.updated_at = datetime.now()
    db.commit()
    db.refresh(role)
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_update_role",
        resource_type="role",
        resource_id=str(role_id),
        metadata={"updated_by": current_user.get("username"), "role_name": role.name},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"超级管理员 {current_user.get('username')} 更新了角色: {role.name}")
    
    return RoleResponse.from_orm(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID = Path(..., description="角色ID"),
    current_user: dict = Depends(require_superuser),
    db: Session = Depends(get_db)
):
    """
    删除角色（仅超级管理员）
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 不能删除系统角色
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除系统角色"
        )
    
    # 检查是否有用户使用此角色
    user_count = db.query(func.count(UserRole.user_id)).filter(UserRole.role_id == role_id).scalar()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"此角色有 {user_count} 个用户在使用，不能删除"
        )
    
    db.delete(role)
    db.commit()
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_delete_role",
        resource_type="role",
        resource_id=str(role_id),
        metadata={"deleted_by": current_user.get("username"), "role_name": role.name},
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"超级管理员 {current_user.get('username')} 删除了角色: {role.name}")


# ==================== 系统监控接口 ====================

@router.get("/audit-logs")
async def get_audit_logs(
    action: Optional[str] = Query(None, description="操作类型"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    user_id: Optional[UUID] = Query(None, description="用户ID"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页大小"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    获取审计日志
    """
    query = db.query(AuditLog)
    
    if action:
        query = query.filter(AuditLog.action == action)
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    
    # 获取总数
    total = query.count()
    
    # 分页
    logs = query.options(joinedload(AuditLog.user)) \
                .order_by(desc(AuditLog.created_at)) \
                .offset((page - 1) * page_size) \
                .limit(page_size) \
                .all()
    
    # 构建响应
    log_items = []
    for log in logs:
        log_items.append({
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "user": {
                "id": str(log.user_id) if log.user_id else None,
                "username": log.user.username if log.user else None
            },
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "metadata": log.metadata,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })
    
    return {
        "items": log_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.post("/system/cleanup")
async def system_cleanup(
    background_tasks: BackgroundTasks,
    older_than_days: int = Body(30, embed=True, description="清理多少天前的数据"),
    cleanup_types: List[str] = Body(["audit_logs"], embed=True, description="清理类型"),
    current_user: dict = Depends(require_superuser),
    db: Session = Depends(get_db)
):
    """
    系统数据清理（仅超级管理员）
    """
    cleanup_date = datetime.now() - timedelta(days=older_than_days)
    results = {}
    
    if "audit_logs" in cleanup_types:
        # 清理旧审计日志
        deleted_count = db.query(AuditLog).filter(AuditLog.created_at < cleanup_date).delete()
        db.commit()
        results["audit_logs"] = {"deleted": deleted_count}
        logger.info(f"清理了 {deleted_count} 条审计日志")
    
    # 这里可以添加其他类型的清理
    
    # 记录审计日志
    audit_log = AuditLog(
        id=uuid4(),
        user_id=UUID(current_user["sub"]),
        action="admin_system_cleanup",
        resource_type="system",
        resource_id="system",
        metadata={
            "cleaned_by": current_user.get("username"),
            "older_than_days": older_than_days,
            "cleanup_types": cleanup_types,
            "results": results
        },
        created_at=datetime.now()
    )
    db.add(audit_log)
    db.commit()
    
    logger.info(f"超级管理员 {current_user.get('username')} 执行了系统清理")
    
    return {
        "message": "系统清理任务已提交",
        "results": results,
        "cleanup_date": cleanup_date.isoformat()
    }