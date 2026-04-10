"""
用户系统模型
包含 User, Role, UserRole 等核心模型
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, DateTime, Date, Integer, ForeignKey, JSON, CheckConstraint, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from passlib.context import CryptContext

from src.core.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 兼容SQLite的UUID列
def UUIDColumn():
    """创建兼容SQLite的UUID列"""
    import os
    from sqlalchemy import String
    from sqlalchemy.dialects.postgresql import UUID
    
    # 检查是否使用SQLite
    from src.core.config import settings
    if "sqlite" in settings.DATABASE_URL:
        return Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    else:
        return Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)


class Role(Base):
    """
    角色模型
    用于RBAC权限控制
    """
    __tablename__ = "roles"
    
    id = UUIDColumn()
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255))
    permissions = Column(JSONB, nullable=False, default=dict)  # 权限配置
    is_system = Column(Boolean, default=False)  # 是否为系统角色
    is_default = Column(Boolean, default=False)  # 是否为默认角色
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    users = relationship("User", secondary="user_roles", back_populates="roles", viewonly=True)
    
    __table_args__ = (
        CheckConstraint("name = lower(name)", name="role_name_lowercase"),
    )
    
    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"


class UserRole(Base):
    """
    用户角色关联表
    多对多关系
    """
    __tablename__ = "user_roles"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", foreign_keys=[user_id], back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by], remote_side="User.id")
    
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="user_role_unique"),
    )
    
    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class User(Base):
    """
    用户核心模型
    支持多角色、多权限、用户统计等功能
    """
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    nickname = Column(String(50))
    avatar_url = Column(String(500))
    bio = Column(String(500))
    gender = Column(String(10), nullable=True)
    birth_date = Column(Date, nullable=True)
    location = Column(JSONB, nullable=True)  # {city: '广州', country: '中国'}
    website_url = Column(String(500))
    social_links = Column(JSONB, default=dict)  # {github: '...', twitter: '...'}
    
    # 状态标志
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    
    # 安全相关
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv4或IPv6
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    roles = relationship("Role", secondary="user_roles", back_populates="users", viewonly=True)
    settings = relationship("UserSettings", uselist=False, back_populates="user", cascade="all, delete-orphan")
    statistics = relationship("UserStatistics", uselist=False, back_populates="user", cascade="all, delete-orphan")
    created_content = relationship("Content", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    media_items = relationship("Media", back_populates="uploader", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("username = lower(username)", name="username_lowercase"),
        CheckConstraint("length(username) >= 3", name="username_min_length"),
        CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name="email_format"),
        CheckConstraint("gender IN ('male', 'female', 'other', 'prefer_not_to_say')", name="gender_enum"),
    )
    
    @validates('username')
    def validate_username(self, key, username):
        """验证用户名"""
        if not username or len(username.strip()) < 3:
            raise ValueError("用户名长度必须大于等于3")
        return username.strip().lower()
    
    @validates('email')
    def validate_email(self, key, email):
        """验证邮箱格式"""
        import re
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not re.match(pattern, email):
            raise ValueError("邮箱格式无效")
        return email.lower()
    
    @hybrid_property
    def is_locked(self):
        """检查账号是否被锁定"""
        if self.account_locked_until:
            return datetime.now(self.account_locked_until.tzinfo) < self.account_locked_until
        return False
    
    def set_password(self, password: str):
        """设置密码哈希"""
        self.password_hash = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(password, self.password_hash)
    
    def increment_failed_attempts(self):
        """增加失败登录尝试次数"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.account_locked_until = datetime.now() + timedelta(minutes=30)
    
    def reset_failed_attempts(self):
        """重置失败登录尝试"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
    
    def has_role(self, role_name: str) -> bool:
        """检查用户是否具有特定角色"""
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission: str) -> bool:
        """检查用户是否具有特定权限"""
        for role in self.roles:
            if permission in role.permissions.get('allowed', []):
                return True
        return False
    
    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_private:
            data.update({
                "phone": self.phone,
                "gender": self.gender,
                "birth_date": self.birth_date.isoformat() if self.birth_date else None,
                "location": self.location,
                "website_url": self.website_url,
                "social_links": self.social_links,
                "is_email_verified": self.is_email_verified,
                "is_phone_verified": self.is_phone_verified,
                "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            })
        
        return data
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserSettings(Base):
    """
    用户配置模型
    存储用户的个性化设置
    """
    __tablename__ = "user_settings"
    
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    privacy_level = Column(String(20), default="public")
    language = Column(String(10), default="zh-CN")
    timezone = Column(String(50), default="Asia/Shanghai")
    theme = Column(String(20), default="light")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="settings")
    
    __table_args__ = (
        CheckConstraint("privacy_level IN ('private', 'friends_only', 'public')", name="privacy_level_enum"),
        CheckConstraint("theme IN ('light', 'dark', 'auto')", name="theme_enum"),
    )
    
    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id})>"


class UserStatistics(Base):
    """
    用户统计模型
    存储用户的统计信息
    """
    __tablename__ = "user_statistics"
    
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    content_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    like_count_received = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    total_view_count = Column(Integer, default=0)
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="statistics")
    
    def increment_content_count(self, amount: int = 1):
        """增加内容计数"""
        self.content_count += amount
    
    def increment_comment_count(self, amount: int = 1):
        """增加评论计数"""
        self.comment_count += amount
    
    def increment_like_count(self, amount: int = 1):
        """增加点赞计数"""
        self.like_count_received += amount
    
    def increment_follower_count(self, amount: int = 1):
        """增加粉丝计数"""
        self.follower_count += amount
    
    def increment_following_count(self, amount: int = 1):
        """增加关注计数"""
        self.following_count += amount
    
    def increment_view_count(self, amount: int = 1):
        """增加查看计数"""
        self.total_view_count += amount
    
    def update_last_active(self):
        """更新最后活跃时间"""
        self.last_active_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": str(self.user_id),
            "content_count": self.content_count,
            "comment_count": self.comment_count,
            "like_count_received": self.like_count_received,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "total_view_count": self.total_view_count,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f"<UserStatistics(user_id={self.user_id}, content_count={self.content_count})>"