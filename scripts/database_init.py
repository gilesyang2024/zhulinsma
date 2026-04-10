#!/usr/bin/env python3
"""
数据库初始化脚本
用于在开发环境中快速设置数据库和插入测试数据
"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4, UUID

from sqlalchemy import text

from src.core.database import Database
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables(db: Database):
    """创建所有数据库表"""
    try:
        from src.core.database import Base
        from src.models.user import User, Role, UserRole, UserSettings, UserStatistics
        from src.models.content import Content, Comment, Tag, ContentTag, Category, ContentCategory, ContentVersion, CommentLike
        from src.models.media import Media, MediaProcessTask, AuditLog
        
        # 创建所有表
        async with db._engine.begin() as conn:
            # 删除现有表（开发环境）
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("已删除现有表")
            
            # 创建新表
            await conn.run_sync(Base.metadata.create_all)
            logger.info("已创建所有表")
            
    except Exception as e:
        logger.error(f"创建表失败: {e}")
        raise


async def insert_initial_data(db: Database):
    """插入初始测试数据"""
    try:
        async with db.session() as session:
            # 插入系统角色
            roles_data = [
                {
                    "name": "superuser",
                    "description": "超级管理员",
                    "permissions": ["*"],
                    "is_system": True,
                    "is_default": False
                },
                {
                    "name": "admin",
                    "description": "管理员",
                    "permissions": ["user:read", "user:write", "content:read", "content:write", "media:read", "media:write"],
                    "is_system": True,
                    "is_default": False
                },
                {
                    "name": "user",
                    "description": "普通用户",
                    "permissions": ["content:read", "content:write:self", "media:read", "media:write:self"],
                    "is_system": True,
                    "is_default": True
                },
                {
                    "name": "guest",
                    "description": "访客",
                    "permissions": ["content:read"],
                    "is_system": True,
                    "is_default": False
                }
            ]
            
            roles = []
            for role_data in roles_data:
                role = Role(
                    id=uuid4(),
                    name=role_data["name"],
                    description=role_data["description"],
                    permissions=role_data["permissions"],
                    is_system=role_data["is_system"],
                    is_default=role_data["is_default"],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                roles.append(role)
                session.add(role)
            
            await session.commit()
            logger.info(f"已插入 {len(roles)} 个角色")
            
            # 插入测试用户
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            users_data = [
                {
                    "username": "admin_user",
                    "email": "admin@example.com",
                    "full_name": "管理员",
                    "is_superuser": True,
                    "is_admin": True,
                    "is_active": True,
                    "is_verified": True
                },
                {
                    "username": "test_user",
                    "email": "user@example.com",
                    "full_name": "测试用户",
                    "is_superuser": False,
                    "is_admin": False,
                    "is_active": True,
                    "is_verified": True
                }
            ]
            
            users = []
            for i, user_data in enumerate(users_data):
                user_id = uuid4()
                user = User(
                    id=user_id,
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=pwd_context.hash("password123"),
                    full_name=user_data["full_name"],
                    is_superuser=user_data["is_superuser"],
                    is_admin=user_data["is_admin"],
                    is_active=user_data["is_active"],
                    is_verified=user_data["is_verified"],
                    last_active_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                users.append(user)
                session.add(user)
                
                # 插入用户设置
                settings = UserSettings(
                    user_id=user_id,
                    theme="dark",
                    language="zh-CN",
                    notifications_enabled=True,
                    email_notifications=True,
                    privacy_level=1,
                    timezone="Asia/Shanghai",
                    date_format="YYYY-MM-DD",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(settings)
                
                # 插入用户统计
                stats = UserStatistics(
                    user_id=user_id,
                    total_content=0,
                    total_comments=0,
                    total_likes_received=0,
                    total_followers=0,
                    total_following=0,
                    total_login_count=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(stats)
                
                # 分配角色
                role = roles[0] if i == 0 else roles[2]  # 第一个用户分配superuser，第二个分配user
                user_role = UserRole(
                    user_id=user_id,
                    role_id=role.id,
                    assigned_at=datetime.now()
                )
                session.add(user_role)
            
            await session.commit()
            logger.info(f"已插入 {len(users)} 个测试用户")
            
            # 插入测试分类和标签
            categories_data = [
                {"name": "技术", "slug": "technology", "description": "技术相关文章"},
                {"name": "生活", "slug": "life", "description": "生活随笔"},
                {"name": "旅行", "slug": "travel", "description": "旅行游记"},
                {"name": "美食", "slug": "food", "description": "美食分享"}
            ]
            
            tags_data = [
                {"name": "Python", "slug": "python"},
                {"name": "FastAPI", "slug": "fastapi"},
                {"name": "数据库", "slug": "database"},
                {"name": "开发", "slug": "development"},
                {"name": "生活技巧", "slug": "life-tips"}
            ]
            
            categories = []
            for cat_data in categories_data:
                category = Category(
                    id=uuid4(),
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    description=cat_data["description"],
                    is_active=True,
                    display_order=1,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                categories.append(category)
                session.add(category)
            
            tags = []
            for tag_data in tags_data:
                tag = Tag(
                    id=uuid4(),
                    name=tag_data["name"],
                    slug=tag_data["slug"],
                    description=f"{tag_data['name']}相关文章",
                    usage_count=0,
                    is_featured=False,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                tags.append(tag)
                session.add(tag)
            
            await session.commit()
            logger.info(f"已插入 {len(categories)} 个分类和 {len(tags)} 个标签")
            
            # 插入测试内容
            if users and categories and tags:
                content = Content(
                    id=uuid4(),
                    title="欢迎来到竹林司马",
                    slug="welcome-to-zhulinsima",
                    excerpt="这是第一篇测试文章，用于展示系统功能",
                    content="""
# 欢迎来到竹林司马！

这是一篇测试文章，展示系统的内容管理功能。

## 功能特点

1. **用户管理**: 支持用户注册、登录、权限管理
2. **内容发布**: 支持富文本内容、分类、标签
3. **媒体管理**: 支持图片、文件上传和处理
4. **评论系统**: 支持嵌套评论和点赞
5. **审计日志**: 记录所有重要操作

## 技术栈

- **后端**: FastAPI + PostgreSQL
- **前端**: 即将开发
- **部署**: Docker + Nginx

欢迎测试系统功能！
                    """,
                    content_type="article",
                    status="published",
                    visibility="public",
                    author_id=users[0].id,
                    like_count=10,
                    comment_count=5,
                    view_count=100,
                    is_featured=True,
                    is_commentable=True,
                    published_at=datetime.now(),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(content)
                await session.commit()
                logger.info("已插入测试内容")
                
                # 关联分类和标签
                content_category = ContentCategory(
                    content_id=content.id,
                    category_id=categories[0].id,
                    assigned_at=datetime.now()
                )
                session.add(content_category)
                
                content_tag = ContentTag(
                    content_id=content.id,
                    tag_id=tags[0].id,
                    assigned_at=datetime.now()
                )
                session.add(content_tag)
                
                await session.commit()
                logger.info("已关联分类和标签")
            
    except Exception as e:
        logger.error(f"插入初始数据失败: {e}")
        raise


async def main():
    """主函数"""
    logger.info("开始数据库初始化...")
    
    # 初始化数据库连接
    db = Database()
    await db.connect()
    
    try:
        # 创建表
        await create_tables(db)
        
        # 插入初始数据
        await insert_initial_data(db)
        
        logger.info("数据库初始化完成！")
        
    finally:
        # 关闭连接
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())