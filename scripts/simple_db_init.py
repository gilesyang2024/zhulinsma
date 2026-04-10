#!/usr/bin/env python3
"""
简化的数据库初始化脚本
用于快速测试数据库连接和表创建
"""

import asyncio
import os
import sys
import logging

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """初始化数据库"""
    try:
        # 动态导入
        from src.core.database import Database, Base
        from src.core.config import settings
        
        logger.info(f"项目: {settings.PROJECT_NAME}")
        logger.info(f"数据库URL: {settings.DATABASE_URL}")
        
        # 创建数据库实例
        db = Database(settings.DATABASE_URL)
        
        # 连接数据库
        await db.connect()
        logger.info("数据库连接成功")
        
        # 创建所有表
        async with db._engine.begin() as conn:
            # 导入所有模型
            from src.models.user import User, Role, UserRole, UserSettings, UserStatistics
            from src.models.content import Content, Comment, Tag, ContentTag, Category, ContentCategory, ContentVersion, CommentLike
            from src.models.media import Media, MediaProcessTask, AuditLog
            
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            logger.info("所有数据库表创建成功")
        
        # 插入基础数据
        async with db._engine.begin() as conn:
            # 插入基础角色
            roles = [
                {"name": "admin", "description": "系统管理员", "permissions": "all"},
                {"name": "user", "description": "普通用户", "permissions": "basic"},
                {"name": "editor", "description": "内容编辑", "permissions": "content_manage"},
                {"name": "auditor", "description": "内容审核员", "permissions": "content_review"},
            ]
            
            for role_data in roles:
                await conn.execute(
                    text("""
                    INSERT INTO roles (name, description, permissions, created_at, updated_at)
                    VALUES (:name, :description, :permissions, NOW(), NOW())
                    ON CONFLICT (name) DO NOTHING
                    """),
                    role_data
                )
            
            logger.info("基础角色数据插入成功")
            
            # 创建默认管理员用户（如果不存在）
            admin_data = {
                "username": "admin",
                "email": "admin@example.com",
                "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 密码: admin123
                "full_name": "系统管理员",
                "is_active": True,
                "is_superuser": True,
            }
            
            await conn.execute(
                text("""
                INSERT INTO users (username, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
                VALUES (:username, :email, :hashed_password, :full_name, :is_active, :is_superuser, NOW(), NOW())
                ON CONFLICT (email) DO NOTHING
                """),
                admin_data
            )
            
            # 将管理员用户关联到admin角色
            await conn.execute(
                text("""
                INSERT INTO user_roles (user_id, role_id, created_at)
                SELECT u.id, r.id, NOW()
                FROM users u, roles r
                WHERE u.username = 'admin' AND r.name = 'admin'
                ON CONFLICT (user_id, role_id) DO NOTHING
                """)
            )
            
            logger.info("管理员用户创建成功")
        
        logger.info("数据库初始化完成！")
        
        # 断开数据库连接
        await db.disconnect()
        logger.info("数据库连接已断开")
        
        return True
        
    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        logger.info("请确保在项目根目录运行此脚本")
        return False
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


async def test_database_connection():
    """测试数据库连接"""
    try:
        from src.core.database import Database
        from src.core.config import settings
        
        db = Database(settings.DATABASE_URL)
        await db.connect()
        
        # 执行简单查询测试连接
        async with db._engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            data = result.scalar()
            logger.info(f"数据库连接测试成功: {data}")
        
        await db.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False


async def run_alembic_migration():
    """运行Alembic迁移"""
    try:
        import subprocess
        import sys
        
        # 运行alembic升级命令
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Alembic迁移成功")
            logger.info(result.stdout)
            return True
        else:
            logger.error(f"Alembic迁移失败: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"运行Alembic迁移失败: {e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库初始化工具")
    parser.add_argument("--test", action="store_true", help="仅测试数据库连接")
    parser.add_argument("--migrate", action="store_true", help="运行Alembic迁移")
    parser.add_argument("--init", action="store_true", help="初始化数据库（创建表并插入数据）")
    parser.add_argument("--all", action="store_true", help="执行所有操作")
    
    args = parser.parse_args()
    
    # 如果没有指定任何参数，默认执行所有操作
    if not any([args.test, args.migrate, args.init, args.all]):
        args.all = True
    
    results = {}
    
    # 运行测试
    if args.test or args.all:
        print("\n" + "="*50)
        print("测试数据库连接...")
        print("="*50)
        results["test"] = asyncio.run(test_database_connection())
    
    # 运行迁移
    if args.migrate or args.all:
        print("\n" + "="*50)
        print("运行Alembic迁移...")
        print("="*50)
        results["migrate"] = asyncio.run(run_alembic_migration())
    
    # 初始化数据库
    if args.init or args.all:
        print("\n" + "="*50)
        print("初始化数据库...")
        print("="*50)
        results["init"] = asyncio.run(init_database())
    
    # 输出结果摘要
    print("\n" + "="*50)
    print("操作结果摘要")
    print("="*50)
    
    all_success = True
    for operation, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{operation:15} {status}")
        if not success:
            all_success = False
    
    if all_success:
        print("\n所有操作完成成功！")
        print("可以启动后端服务了。")
    else:
        print("\n部分操作失败，请检查错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    main()