"""
用户相关的Pydantic模型
用于API请求和响应验证
"""

from datetime import date, datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
import re


# ==================== 基础模型 ====================

class UserBase(BaseModel):
    """用户基础模型"""
    
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9_]+$')
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=500)
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名格式"""
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('用户名只能包含小写字母、数字和下划线')
        return v.lower()
    
    @validator('avatar_url')
    def validate_avatar_url(cls, v):
        """验证头像URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('头像URL必须以http://或https://开头')
        return v


class UserCreate(UserBase):
    """用户创建模型"""
    
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, pattern=r'^(male|female|other|prefer_not_to_say)$')
    birth_date: Optional[date] = None
    location: Optional[Dict[str, str]] = None
    website_url: Optional[str] = Field(None, max_length=500)
    
    @validator('phone')
    def validate_phone(cls, v):
        """验证手机号格式"""
        if v and not re.match(r'^\+?[1-9]\d{1,14}$', v):
            raise ValueError('手机号格式无效')
        return v
    
    @validator('website_url')
    def validate_website_url(cls, v):
        """验证网站URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('网站URL必须以http://或https://开头')
        return v


class UserUpdate(BaseModel):
    """用户更新模型"""
    
    full_name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, pattern=r'^(male|female|other|prefer_not_to_say)$')
    birth_date: Optional[date] = None
    location: Optional[Dict[str, str]] = None
    website_url: Optional[str] = Field(None, max_length=500)
    social_links: Optional[Dict[str, str]] = None
    
    @validator('avatar_url')
    def validate_avatar_url(cls, v):
        """验证头像URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('头像URL必须以http://或https://开头')
        return v
    
    @validator('website_url')
    def validate_website_url(cls, v):
        """验证网站URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('网站URL必须以http://或https://开头')
        return v


class UserProfileUpdate(BaseModel):
    """用户个人资料更新模型"""
    
    full_name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=500)
    gender: Optional[str] = Field(None, pattern=r'^(male|female|other|prefer_not_to_say)$')
    birth_date: Optional[date] = None
    location: Optional[Dict[str, str]] = None
    website_url: Optional[str] = Field(None, max_length=500)
    
    @validator('avatar_url')
    def validate_avatar_url(cls, v):
        """验证头像URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('头像URL必须以http://或https://开头')
        return v
    
    @validator('website_url')
    def validate_website_url(cls, v):
        """验证网站URL"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('网站URL必须以http://或https://开头')
        return v


class UserPasswordUpdate(BaseModel):
    """用户密码更新模型"""
    
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('confirm_password')
    def validate_password_confirmation(cls, v, values):
        """验证密码确认"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('新密码与确认密码不匹配')
        return v


class UserEmailUpdate(BaseModel):
    """用户邮箱更新模型"""
    
    email: EmailStr
    current_password: str = Field(..., min_length=1)


# ==================== 响应模型 ====================

class UserPublic(BaseModel):
    """公开用户信息"""
    
    id: UUID
    username: str
    full_name: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_verified: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserPrivate(UserPublic):
    """私有用户信息"""
    
    email: str
    phone: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    location: Optional[Dict[str, str]] = None
    website_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    is_email_verified: bool = False
    is_phone_verified: bool = False
    last_login_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class UserDetail(UserPrivate):
    """用户详细信息"""
    
    is_active: bool = True
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 设置模型 ====================

class UserSettingsBase(BaseModel):
    """用户设置基础模型"""
    
    email_notifications: Optional[bool] = True
    push_notifications: Optional[bool] = True
    privacy_level: Optional[str] = Field("public", pattern=r'^(private|friends_only|public)$')
    language: Optional[str] = Field("zh-CN", max_length=10)
    timezone: Optional[str] = Field("Asia/Shanghai", max_length=50)
    theme: Optional[str] = Field("light", pattern=r'^(light|dark|auto)$')


class UserSettingsCreate(UserSettingsBase):
    """用户设置创建模型"""
    pass


class UserSettingsUpdate(UserSettingsBase):
    """用户设置更新模型"""
    pass


class UserSettingsResponse(UserSettingsBase):
    """用户设置响应模型"""
    
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 统计模型 ====================

class UserStatisticsResponse(BaseModel):
    """用户统计响应模型"""
    
    user_id: UUID
    content_count: int = 0
    comment_count: int = 0
    like_count_received: int = 0
    follower_count: int = 0
    following_count: int = 0
    total_view_count: int = 0
    last_active_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 角色模型 ====================

class RoleBase(BaseModel):
    """角色基础模型"""
    
    name: str = Field(..., min_length=2, max_length=50, pattern=r'^[a-z_]+$')
    description: Optional[str] = Field(None, max_length=255)
    permissions: Dict[str, Any] = Field(default_factory=dict)
    is_system: bool = False
    is_default: bool = False
    
    @validator('name')
    def validate_role_name(cls, v):
        """验证角色名格式"""
        if not re.match(r'^[a-z_]+$', v):
            raise ValueError('角色名只能包含小写字母和下划线')
        return v


class RoleCreate(RoleBase):
    """角色创建模型"""
    pass


class RoleUpdate(BaseModel):
    """角色更新模型"""
    
    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class RoleResponse(RoleBase):
    """角色响应模型"""
    
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserRoleAssign(BaseModel):
    """用户角色分配模型"""
    
    role_id: UUID
    expires_at: Optional[datetime] = None


class UserRoleResponse(BaseModel):
    """用户角色响应模型"""
    
    id: UUID
    user_id: UUID
    role_id: UUID
    role_name: str
    assigned_by: Optional[UUID] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 批量操作模型 ====================

class UserBulkAction(BaseModel):
    """用户批量操作模型"""
    
    user_ids: List[UUID]
    action: str = Field(..., pattern=r'^(activate|deactivate|verify|unverify|delete|restore)$')


# ==================== 查询参数模型 ====================

class UserQueryParams(BaseModel):
    """用户查询参数模型"""
    
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    created_from: Optional[date] = None
    created_to: Optional[date] = None
    last_login_from: Optional[datetime] = None
    last_login_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
    sort_by: str = Field("created_at", pattern=r'^(created_at|username|last_login_at)$')
    sort_order: str = Field("desc", pattern=r'^(asc|desc)$')


class RoleQueryParams(BaseModel):
    """角色查询参数模型"""
    
    name: Optional[str] = None
    is_system: Optional[bool] = None
    is_default: Optional[bool] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


# ==================== 分页响应模型 ====================

class PaginatedResponse(BaseModel):
    """分页响应基础模型"""
    
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class UserListResponse(PaginatedResponse):
    """用户列表响应模型"""
    
    items: List[UserPublic]


class RoleListResponse(PaginatedResponse):
    """角色列表响应模型"""
    
    items: List[RoleResponse]