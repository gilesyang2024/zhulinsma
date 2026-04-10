"""
认证API路由模块

处理用户注册、登录、令牌刷新等认证相关操作。
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, validator

from src.core.security import (
    security, 
    get_current_user, 
    get_current_user_optional,
    validate_password_complexity,
)
from src.core.exceptions import (
    AuthenticationError,
    AlreadyExistsError,
    ValidationError,
    business_error,
)
from src.core.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    
    username: str = Field(..., min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        validation = security.validate_password_strength(v)
        if not validation["is_valid"]:
            errors = ", ".join(validation["errors"])
            raise ValueError(f"密码强度不足: {errors}")
        return v


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class TokenResponse(BaseModel):
    """令牌响应"""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(BaseModel):
    """令牌刷新请求"""
    
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """密码重置请求"""
    
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """密码重置确认请求"""
    
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        validate_password_complexity(v)
        return v


class UserResponse(BaseModel):
    """用户响应"""
    
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: str


# ==================== 业务函数 ====================

async def register_user_service(user_data: UserRegisterRequest) -> dict:
    """用户注册服务
    
    Args:
        user_data: 用户注册数据
        
    Returns:
        注册成功的用户信息
        
    Raises:
        AlreadyExistsError: 用户名或邮箱已存在
        BusinessLogicError: 业务逻辑错误
    """
    # 这里应该实现实际的用户创建逻辑
    # 包括检查用户名/邮箱是否已存在、创建用户记录、发送验证邮件等
    
    # 模拟用户创建
    user_id = "user_" + user_data.username  # 实际应使用UUID
    
    return {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email,
        "full_name": user_data.full_name,
        "is_active": True,
        "is_verified": False,
        "created_at": "2026-04-09T21:30:00Z",
    }


async def authenticate_user_service(username: str, password: str) -> Optional[dict]:
    """用户认证服务
    
    Args:
        username: 用户名或邮箱
        password: 密码
        
    Returns:
        认证成功的用户信息或None
    """
    # 这里应该实现实际的用户认证逻辑
    # 包括查询用户、验证密码、检查账户状态等
    
    # 模拟用户认证
    if username == "testuser" and password == "Test123!":
        return {
            "id": "user_testuser",
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "is_verified": True,
        }
    
    return None


async def send_verification_email(user_email: str, verification_token: str):
    """发送验证邮件
    
    Args:
        user_email: 用户邮箱
        verification_token: 验证令牌
    """
    # 这里应该实现实际的邮件发送逻辑
    logger.info(f"发送验证邮件到: {user_email}, 令牌: {verification_token}")
    # 实际应用中应该使用邮件服务发送


async def send_password_reset_email(user_email: str, reset_token: str):
    """发送密码重置邮件
    
    Args:
        user_email: 用户邮箱
        reset_token: 重置令牌
    """
    # 这里应该实现实际的邮件发送逻辑
    logger.info(f"发送密码重置邮件到: {user_email}, 令牌: {reset_token}")
    # 实际应用中应该使用邮件服务发送


# ==================== API路由 ====================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: UserRegisterRequest,
    background_tasks: BackgroundTasks,
):
    """用户注册
    
    Args:
        request: 注册请求数据
        background_tasks: 后台任务管理器
        
    Returns:
        注册成功的用户信息
    """
    try:
        logger.info(f"用户注册请求: {request.username}")
        
        # 验证密码复杂度
        validate_password_complexity(request.password)
        
        # 检查用户名和邮箱是否已存在
        # 实际应用中应该查询数据库
        if request.username in ["existing_user", "testuser"]:
            raise AlreadyExistsError("用户", request.username)
        
        if request.email in ["existing@example.com", "test@example.com"]:
            raise AlreadyExistsError("邮箱", request.email)
        
        # 创建用户
        user = await register_user_service(request)
        
        # 生成验证令牌
        verification_token = security.create_access_token(
            user["id"],
            expires_delta=timedelta(days=1),
            type="verification",
        )
        
        # 后台发送验证邮件
        background_tasks.add_task(
            send_verification_email,
            user["email"],
            verification_token,
        )
        
        # 缓存用户信息（可选）
        await cache.cache_user(user["id"], user)
        
        logger.info(f"用户注册成功: {user['username']} ({user['id']})")
        return user
        
    except AlreadyExistsError:
        raise
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"用户注册失败: {e}")
        raise business_error("用户注册失败")


@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: UserLoginRequest,
):
    """用户登录
    
    Args:
        request: 登录请求数据
        
    Returns:
        访问令牌和刷新令牌
    """
    try:
        logger.info(f"用户登录请求: {request.username}")
        
        # 认证用户
        user = await authenticate_user_service(request.username, request.password)
        
        if user is None:
            logger.warning(f"用户认证失败: {request.username}")
            raise AuthenticationError("用户名或密码错误")
        
        # 检查用户状态
        if not user.get("is_active", True):
            raise AuthenticationError("用户账户已被禁用")
        
        # 生成令牌
        access_token = security.create_access_token(
            user["id"],
            username=user["username"],
            email=user["email"],
        )
        
        refresh_token = security.create_refresh_token(user["id"])
        
        # 缓存用户信息
        await cache.cache_user(user["id"], user)
        
        # 记录登录（实际应用中应该更新数据库）
        logger.info(f"用户登录成功: {user['username']} ({user['id']})")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        raise business_error("用户登录失败")


@router.post("/login/form", response_model=TokenResponse)
async def login_user_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """用户登录（OAuth2表单格式）
    
    Args:
        form_data: OAuth2密码请求表单
        
    Returns:
        访问令牌和刷新令牌
    """
    try:
        # 使用相同的登录逻辑
        request = UserLoginRequest(
            username=form_data.username,
            password=form_data.password,
        )
        
        return await login_user(request)
        
    except Exception as e:
        logger.error(f"表单登录失败: {e}")
        raise


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: TokenRefreshRequest,
):
    """刷新访问令牌
    
    Args:
        request: 令牌刷新请求
        
    Returns:
        新的访问令牌
    """
    try:
        logger.info("令牌刷新请求")
        
        # 验证刷新令牌并生成新的访问令牌
        new_access_token = security.refresh_access_token(request.refresh_token)
        
        # 从刷新令牌中提取用户信息
        payload = security.verify_token(request.refresh_token)
        
        # 获取用户信息（实际应用中应该从数据库或缓存获取）
        user = await cache.get_user(payload.sub)
        if user is None:
            # 如果缓存中没有，从数据库获取
            # user = await get_user_from_database(payload.sub)
            user = {"id": payload.sub, "username": "unknown"}
        
        # 生成新的刷新令牌（可选，实现刷新令牌轮换）
        new_refresh_token = security.create_refresh_token(payload.sub)
        
        logger.info(f"令牌刷新成功: user_id={payload.sub}")
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"令牌刷新失败: {e}")
        raise business_error("令牌刷新失败")


@router.post("/logout")
async def logout_user(
    current_user: dict = Depends(get_current_user),
):
    """用户登出
    
    Args:
        current_user: 当前用户
        
    Returns:
        登出成功消息
    """
    try:
        user_id = current_user["id"]
        logger.info(f"用户登出: {user_id}")
        
        # 使令牌失效（实际应用中应该将令牌加入黑名单）
        # 或者依赖短令牌过期时间
        
        # 清除用户缓存
        await cache.invalidate_user_cache(user_id)
        
        return {"success": True, "message": "登出成功"}
        
    except Exception as e:
        logger.error(f"用户登出失败: {e}")
        raise business_error("用户登出失败")


@router.post("/password/reset-request")
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
):
    """请求密码重置
    
    Args:
        request: 密码重置请求
        background_tasks: 后台任务管理器
        
    Returns:
        请求成功消息
    """
    try:
        logger.info(f"密码重置请求: {request.email}")
        
        # 检查邮箱是否存在（实际应用中应该查询数据库）
        user_exists = request.email in ["user@example.com", "test@example.com"]
        
        if not user_exists:
            # 即使邮箱不存在，也返回成功以避免邮箱枚举攻击
            logger.warning(f"密码重置请求：邮箱不存在: {request.email}")
            return {
                "success": True,
                "message": "如果邮箱存在，重置链接已发送",
            }
        
        # 生成重置令牌
        reset_token = security.create_access_token(
            "password_reset",  # 实际应使用用户ID
            expires_delta=timedelta(hours=1),
            type="password_reset",
            email=request.email,
        )
        
        # 后台发送重置邮件
        background_tasks.add_task(
            send_password_reset_email,
            request.email,
            reset_token,
        )
        
        logger.info(f"密码重置邮件已发送: {request.email}")
        return {
            "success": True,
            "message": "如果邮箱存在，重置链接已发送",
        }
        
    except Exception as e:
        logger.error(f"密码重置请求失败: {e}")
        raise business_error("密码重置请求失败")


@router.post("/password/reset")
async def reset_password(
    request: PasswordResetConfirmRequest,
):
    """重置密码
    
    Args:
        request: 密码重置确认请求
        
    Returns:
        重置成功消息
    """
    try:
        logger.info("密码重置确认")
        
        # 验证重置令牌
        try:
            payload = security.verify_token(request.token)
            
            # 确保是密码重置令牌
            if payload.type != "password_reset":
                raise AuthenticationError("无效的重置令牌")
            
        except Exception as e:
            logger.warning(f"密码重置令牌验证失败: {e}")
            raise AuthenticationError("无效或过期的重置令牌")
        
        # 验证新密码复杂度
        validate_password_complexity(request.new_password)
        
        # 更新用户密码（实际应用中应该更新数据库）
        # user_email = payload.extra.get("email")
        # await update_user_password(user_email, request.new_password)
        
        # 使所有用户令牌失效（可选）
        # await invalidate_all_user_tokens(payload.sub)
        
        logger.info(f"密码重置成功: user_id={payload.sub}")
        return {
            "success": True,
            "message": "密码重置成功",
        }
        
    except AuthenticationError:
        raise
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"密码重置失败: {e}")
        raise business_error("密码重置失败")


@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
):
    """验证邮箱
    
    Args:
        token: 验证令牌
        
    Returns:
        验证成功消息
    """
    try:
        logger.info("邮箱验证请求")
        
        # 验证令牌
        try:
            payload = security.verify_token(token)
            
            # 确保是验证令牌
            if payload.type != "verification":
                raise AuthenticationError("无效的验证令牌")
            
        except Exception as e:
            logger.warning(f"邮箱验证令牌验证失败: {e}")
            raise AuthenticationError("无效或过期的验证令牌")
        
        # 更新用户验证状态（实际应用中应该更新数据库）
        # user_id = payload.sub
        # await mark_user_as_verified(user_id)
        
        # 清除用户缓存
        await cache.invalidate_user_cache(payload.sub)
        
        logger.info(f"邮箱验证成功: user_id={payload.sub}")
        return {
            "success": True,
            "message": "邮箱验证成功",
        }
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"邮箱验证失败: {e}")
        raise business_error("邮箱验证失败")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户信息
    
    Args:
        current_user: 当前用户
        
    Returns:
        当前用户信息
    """
    try:
        user_id = current_user["id"]
        
        # 尝试从缓存获取
        user = await cache.get_user(user_id)
        
        if user is None:
            # 从数据库获取（实际应用中）
            # user = await get_user_from_database(user_id)
            
            # 模拟用户数据
            user = {
                "id": user_id,
                "username": "current_user",
                "email": "user@example.com",
                "full_name": "当前用户",
                "is_active": True,
                "is_verified": True,
                "created_at": "2026-04-09T21:30:00Z",
            }
            
            # 缓存用户信息
            await cache.cache_user(user_id, user)
        
        return user
        
    except Exception as e:
        logger.error(f"获取当前用户信息失败: {e}")
        raise business_error("获取用户信息失败")


# ==================== 测试端点（仅开发环境） ====================

if settings.is_development:
    
    @router.get("/test/token")
    async def test_token_generation():
        """测试令牌生成（仅开发环境）"""
        test_user = {
            "id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
        }
        
        access_token = security.create_access_token(
            test_user["id"],
            username=test_user["username"],
            email=test_user["email"],
        )
        
        refresh_token = security.create_refresh_token(test_user["id"])
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": test_user,
            "note": "仅用于开发测试",
        }