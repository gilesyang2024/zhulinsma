"""
用户管理API路由模块

处理用户相关的CRUD操作、角色管理、用户统计等功能。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from fastapi.security import HTTPBearer
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.security import security, get_current_user
from src.core.exceptions import (
    AuthenticationError, AuthorizationError, AlreadyExistsError, 
    NotFoundError, ValidationError
)

from src.models.user import User, Role, UserRole, UserSettings, UserStatistics
from src.schemas.v1.user import (
    UserCreate, UserUpdate, UserProfileUpdate, UserPasswordUpdate, UserEmailUpdate,
    UserPublic, UserPrivate, UserDetail, UserSettingsCreate, UserSettingsUpdate, 
    UserSettingsResponse, UserStatisticsResponse, RoleCreate, RoleUpdate, RoleResponse,
    UserRoleAssign, UserRoleResponse, UserBulkAction, UserQueryParams, RoleQueryParams,
    UserListResponse, RoleListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])
security_bearer = HTTPBearer(auto_error=False)


# ==================== 依赖函数 ====================

async def get_user_or_404(
    user_id: UUID = Path(..., description="用户ID"),
    db: Session = Depends(get_db)
) -> User:
    """获取用户或返回404"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 {user_id} 不存在"
        )
    return user


async def get_role_or_404(
    role_id: UUID = Path(..., description="角色ID"),
    db: Session = Depends(get_db)
) -> Role:
    """获取角色或返回404"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色 {role_id} 不存在"
        )
    return role


# ==================== 权限检查函数 ====================

async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if not current_user.get("is_admin", False):
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


# ==================== 用户管理接口 ====================

@router.get("/me", response_model=UserPrivate)
async def get_current_user_info(
    current_user_dict: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户信息
    """
    user_id = UUID(current_user_dict["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 更新最后活跃时间
    user.last_active_at = datetime.now()
    db.commit()
    db.refresh(user)
    
    return UserPrivate.from_orm(user)


@router.put("/me/profile", response_model=UserPrivate)
@rate_limit("user:update:me", limit=30, period=60)
@audit_log(action="update_profile", resource_type="user")
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户个人资料
    """
    # 更新用户信息
    update_data = profile_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.now()
    db.commit()
    db.refresh(current_user)
    
    return UserPrivate.from_orm(current_user)


@router.put("/me/password")
@rate_limit("user:update:password", limit=10, period=60)
@audit_log(action="change_password", resource_type="user")
async def change_current_user_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改当前用户密码
    """
    # 验证当前密码
    if not current_user.verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确"
        )
    
    # 验证新密码强度
    from src.core.security import security
    validation = security.validate_password_strength(password_data.new_password)
    if not validation["is_valid"]:
        errors = ", ".join(validation["errors"])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码强度不足: {errors}"
        )
    
    # 设置新密码
    current_user.set_password(password_data.new_password)
    current_user.updated_at = datetime.now()
    db.commit()
    
    return {"message": "密码修改成功"}


@router.put("/me/email")
@rate_limit("user:update:email", limit=5, period=60)
@audit_log(action="change_email", resource_type="user")
async def change_current_user_email(
    email_data: UserEmailUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改当前用户邮箱
    """
    # 验证当前密码
    if not current_user.verify_password(email_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确"
        )
    
    # 检查邮箱是否已被使用
    existing_user = db.query(User).filter(User.email == email_data.email).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被其他用户使用"
        )
    
    # 更新邮箱
    current_user.email = email_data.email
    current_user.is_email_verified = False
    current_user.updated_at = datetime.now()
    db.commit()
    
    # TODO: 发送邮箱验证邮件
    
    return {"message": "邮箱修改成功，请验证新邮箱"}


@router.get("/me/settings", response_model=UserSettingsResponse)
@rate_limit("user:read:settings", limit=60, period=60)
async def get_current_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户设置
    """
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not settings:
        # 如果用户设置不存在，创建默认设置
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return UserSettingsResponse.from_orm(settings)


@router.put("/me/settings", response_model=UserSettingsResponse)
@rate_limit("user:update:settings", limit=30, period=60)
@audit_log(action="update_settings", resource_type="user")
async def update_current_user_settings(
    settings_data: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户设置
    """
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not settings:
        # 如果用户设置不存在，创建新的设置
        settings = UserSettings(user_id=current_user.id, **settings_data.dict(exclude_unset=True))
        db.add(settings)
    else:
        # 更新现有设置
        update_data = settings_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)
        settings.updated_at = datetime.now()
    
    db.commit()
    db.refresh(settings)
    
    return UserSettingsResponse.from_orm(settings)


@router.get("/me/statistics", response_model=UserStatisticsResponse)
@rate_limit("user:read:statistics", limit=60, period=60)
async def get_current_user_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户统计信息
    """
    stats = db.query(UserStatistics).filter(UserStatistics.user_id == current_user.id).first()
    if not stats:
        # 如果用户统计不存在，创建默认统计
        stats = UserStatistics(user_id=current_user.id)
        db.add(stats)
        db.commit()
        db.refresh(stats)
    
    return UserStatisticsResponse.from_orm(stats)


# ==================== 公开用户接口 ====================

@router.get("/{user_id}", response_model=UserPublic)
@rate_limit("user:read", limit=100, period=60)
async def get_user_public(
    user: User = Depends(get_user_or_404)
):
    """
    获取用户公开信息
    """
    # 只返回公开信息
    return UserPublic.from_orm(user)


@router.get("", response_model=UserListResponse)
@rate_limit("user:list", limit=100, period=60)
async def list_users(
    query_params: UserQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取用户列表（支持分页和过滤）
    """
    # 构建查询
    query = db.query(User)
    
    # 应用过滤条件
    if query_params.username:
        query = query.filter(User.username.ilike(f"%{query_params.username}%"))
    if query_params.email and current_user and current_user.has_permission("user:read:email"):
        query = query.filter(User.email.ilike(f"%{query_params.email}%"))
    if query_params.phone and current_user and current_user.has_permission("user:read:phone"):
        query = query.filter(User.phone.ilike(f"%{query_params.phone}%"))
    if query_params.is_active is not None:
        query = query.filter(User.is_active == query_params.is_active)
    if query_params.is_verified is not None:
        query = query.filter(User.is_verified == query_params.is_verified)
    if query_params.created_from:
        query = query.filter(User.created_at >= query_params.created_from)
    if query_params.created_to:
        query = query.filter(User.created_at <= query_params.created_to)
    if query_params.last_login_from:
        query = query.filter(User.last_login_at >= query_params.last_login_from)
    if query_params.last_login_to:
        query = query.filter(User.last_login_at <= query_params.last_login_to)
    
    # 获取总数
    total = query.count()
    
    # 应用排序
    if query_params.sort_by == "username":
        order_by = User.username if query_params.sort_order == "asc" else User.username.desc()
    elif query_params.sort_by == "last_login_at":
        order_by = User.last_login_at if query_params.sort_order == "asc" else User.last_login_at.desc()
    else:  # created_at
        order_by = User.created_at if query_params.sort_order == "asc" else User.created_at.desc()
    
    query = query.order_by(order_by)
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    users = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return UserListResponse(
        items=[UserPublic.from_orm(user) for user in users],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


# ==================== 管理员用户接口 ====================

@router.post("", response_model=UserPrivate)
@rate_limit("user:create", limit=30, period=60)
@audit_log(action="create_user", resource_type="user")
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    创建新用户（管理员权限）
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在"
        )
    
    # 检查手机号是否已存在
    if user_data.phone:
        existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号已存在"
            )
    
    # 创建用户
    user_dict = user_data.dict(exclude={"password"})
    user = User(**user_dict)
    user.set_password(user_data.password)
    
    # 创建用户设置和统计
    settings = UserSettings(user_id=user.id)
    statistics = UserStatistics(user_id=user.id)
    
    db.add(user)
    db.add(settings)
    db.add(statistics)
    db.commit()
    db.refresh(user)
    
    # TODO: 发送欢迎邮件
    
    return UserPrivate.from_orm(user)


@router.get("/{user_id}/detail", response_model=UserDetail)
@rate_limit("user:read:detail", limit=60, period=60)
async def get_user_detail(
    user: User = Depends(get_user_or_404),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取用户详细信息（管理员权限）
    """
    return UserDetail.from_orm(user)


@router.put("/{user_id}", response_model=UserDetail)
@rate_limit("user:update", limit=30, period=60)
@audit_log(action="update_user", resource_type="user")
async def update_user(
    user_data: UserUpdate,
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    更新用户信息（管理员权限）
    """
    # 检查邮箱是否已被其他用户使用
    if user_data.email and user_data.email != user.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email and existing_email.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户使用"
            )
    
    # 检查手机号是否已被其他用户使用
    if user_data.phone and user_data.phone != user.phone:
        existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
        if existing_phone and existing_phone.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="手机号已被其他用户使用"
            )
    
    # 更新用户信息
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.now()
    db.commit()
    db.refresh(user)
    
    return UserDetail.from_orm(user)


@router.patch("/{user_id}/activate")
@rate_limit("user:activate", limit=30, period=60)
@audit_log(action="activate_user", resource_type="user")
async def activate_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    激活用户账号（管理员权限）
    """
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账号已激活"
        )
    
    user.is_active = True
    user.updated_at = datetime.now()
    db.commit()
    
    return {"message": "用户账号已激活"}


@router.patch("/{user_id}/deactivate")
@rate_limit("user:deactivate", limit=30, period=60)
@audit_log(action="deactivate_user", resource_type="user")
async def deactivate_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    停用用户账号（管理员权限）
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账号已停用"
        )
    
    user.is_active = False
    user.updated_at = datetime.now()
    db.commit()
    
    return {"message": "用户账号已停用"}


@router.patch("/{user_id}/verify")
@rate_limit("user:verify", limit=30, period=60)
@audit_log(action="verify_user", resource_type="user")
async def verify_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    验证用户账号（管理员权限）
    """
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账号已验证"
        )
    
    user.is_verified = True
    user.updated_at = datetime.now()
    db.commit()
    
    return {"message": "用户账号已验证"}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@rate_limit("user:delete", limit=10, period=60)
@audit_log(action="delete_user", resource_type="user")
async def delete_user(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    删除用户账号（超级管理员权限）
    """
    # 软删除
    user.deleted_at = datetime.now()
    user.is_active = False
    db.commit()


@router.post("/bulk-action")
@rate_limit("user:bulk", limit=10, period=60)
@audit_log(action="bulk_user_action", resource_type="user")
async def bulk_user_action(
    action_data: UserBulkAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    批量操作用户（超级管理员权限）
    """
    users = db.query(User).filter(User.id.in_(action_data.user_ids)).all()
    
    if action_data.action == "activate":
        for user in users:
            user.is_active = True
            user.updated_at = datetime.now()
    elif action_data.action == "deactivate":
        for user in users:
            user.is_active = False
            user.updated_at = datetime.now()
    elif action_data.action == "verify":
        for user in users:
            user.is_verified = True
            user.updated_at = datetime.now()
    elif action_data.action == "unverify":
        for user in users:
            user.is_verified = False
            user.updated_at = datetime.now()
    elif action_data.action == "delete":
        for user in users:
            user.deleted_at = datetime.now()
            user.is_active = False
            user.updated_at = datetime.now()
    elif action_data.action == "restore":
        for user in users:
            user.deleted_at = None
            user.is_active = True
            user.updated_at = datetime.now()
    
    db.commit()
    
    return {"message": f"成功处理 {len(users)} 个用户"}


# ==================== 角色管理接口 ====================

@router.get("/roles", response_model=RoleListResponse)
@rate_limit("role:list", limit=60, period=60)
async def list_roles(
    query_params: RoleQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取角色列表（管理员权限）
    """
    # 构建查询
    query = db.query(Role)
    
    # 应用过滤条件
    if query_params.name:
        query = query.filter(Role.name.ilike(f"%{query_params.name}%"))
    if query_params.is_system is not None:
        query = query.filter(Role.is_system == query_params.is_system)
    if query_params.is_default is not None:
        query = query.filter(Role.is_default == query_params.is_default)
    
    # 获取总数
    total = query.count()
    
    # 应用分页
    offset = (query_params.page - 1) * query_params.per_page
    roles = query.offset(offset).limit(query_params.per_page).all()
    
    # 计算分页信息
    total_pages = (total + query_params.per_page - 1) // query_params.per_page
    has_next = query_params.page < total_pages
    has_prev = query_params.page > 1
    
    return RoleListResponse(
        items=[RoleResponse.from_orm(role) for role in roles],
        total=total,
        page=query_params.page,
        per_page=query_params.per_page,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("/roles", response_model=RoleResponse)
@rate_limit("role:create", limit=30, period=60)
@audit_log(action="create_role", resource_type="role")
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    创建新角色（超级管理员权限）
    """
    # 检查角色名是否已存在
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名已存在"
        )
    
    # 创建角色
    role = Role(**role_data.dict())
    db.add(role)
    db.commit()
    db.refresh(role)
    
    return RoleResponse.from_orm(role)


@router.get("/roles/{role_id}", response_model=RoleResponse)
@rate_limit("role:read", limit=60, period=60)
async def get_role(
    role: Role = Depends(get_role_or_404),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取角色详情（管理员权限）
    """
    return RoleResponse.from_orm(role)


@router.put("/roles/{role_id}", response_model=RoleResponse)
@rate_limit("role:update", limit=30, period=60)
@audit_log(action="update_role", resource_type="role")
async def update_role(
    role_data: RoleUpdate,
    role: Role = Depends(get_role_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    更新角色信息（超级管理员权限）
    """
    # 检查是否为系统角色
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统角色不可修改"
        )
    
    # 更新角色信息
    update_data = role_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)
    
    role.updated_at = datetime.now()
    db.commit()
    db.refresh(role)
    
    return RoleResponse.from_orm(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@rate_limit("role:delete", limit=10, period=60)
@audit_log(action="delete_role", resource_type="role")
async def delete_role(
    role: Role = Depends(get_role_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    删除角色（超级管理员权限）
    """
    # 检查是否为系统角色
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统角色不可删除"
        )
    
    # 检查是否被用户使用
    user_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"角色已被 {user_count} 个用户使用，无法删除"
        )
    
    db.delete(role)
    db.commit()


# ==================== 用户角色管理接口 ====================

@router.get("/{user_id}/roles", response_model=List[UserRoleResponse])
@rate_limit("user_role:list", limit=60, period=60)
async def get_user_roles(
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    获取用户角色列表（管理员权限）
    """
    user_roles = (
        db.query(UserRole, Role.name)
        .join(Role, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    
    result = []
    for user_role, role_name in user_roles:
        role_data = UserRoleResponse.from_orm(user_role)
        role_data.role_name = role_name
        result.append(role_data)
    
    return result


@router.post("/{user_id}/roles", response_model=UserRoleResponse)
@rate_limit("user_role:assign", limit=30, period=60)
@audit_log(action="assign_role", resource_type="user_role")
async def assign_role_to_user(
    role_data: UserRoleAssign,
    user: User = Depends(get_user_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    为用户分配角色（超级管理员权限）
    """
    # 检查角色是否存在
    role = db.query(Role).filter(Role.id == role_data.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"角色 {role_data.role_id} 不存在"
        )
    
    # 检查是否已分配该角色
    existing_assignment = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role_id == role_data.role_id
    ).first()
    
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已拥有该角色"
        )
    
    # 分配角色
    user_role = UserRole(
        user_id=user.id,
        role_id=role_data.role_id,
        assigned_by=current_user.id,
        expires_at=role_data.expires_at
    )
    
    db.add(user_role)
    db.commit()
    db.refresh(user_role)
    
    # 创建响应
    response = UserRoleResponse.from_orm(user_role)
    response.role_name = role.name
    return response


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
@rate_limit("user_role:remove", limit=30, period=60)
@audit_log(action="remove_role", resource_type="user_role")
async def remove_role_from_user(
    user: User = Depends(get_user_or_404),
    role: Role = Depends(get_role_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    移除用户角色（超级管理员权限）
    """
    # 查找用户角色分配
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user.id,
        UserRole.role_id == role.id
    ).first()
    
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未拥有该角色"
        )
    
    # 检查是否为系统角色
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统角色不可移除"
        )
    
    db.delete(user_role)
    db.commit()