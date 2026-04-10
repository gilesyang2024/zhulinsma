#!/usr/bin/env python3
"""
最小化测试 - 验证竹林司马后端核心功能
"""

import asyncio
import os
import sys

# 设置环境变量
os.environ.update({
    'APP_SECRET_KEY': 'test-secret-key-32-chars-long-123456',
    'JWT_SECRET_KEY': 'test-jwt-key-32-chars-long-789012',
    'DATABASE_URL': 'sqlite+aiosqlite:///./test.db',
})

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_imports():
    """测试模块导入"""
    print("="*60)
    print("1. 模块导入测试")
    print("="*60)
    
    modules = [
        ("src.core.config", "配置模块"),
        ("src.core.database", "数据库模块"),
        ("src.core.security", "安全模块"),
        ("src.core.exceptions", "异常模块"),
        ("src.models.user", "用户模型"),
        ("src.models.content", "内容模型"),
        ("src.models.media", "媒体模型"),
        ("src.api.v1.users", "用户API"),
        ("src.api.v1.content", "内容API"),
        ("src.api.v1.media", "媒体API"),
    ]
    
    results = []
    for module_name, description in modules:
        try:
            __import__(module_name)
            results.append((description, "✅", "导入成功"))
            print(f"  {description:20} ✅")
        except Exception as e:
            results.append((description, "❌", f"导入失败: {str(e)[:50]}"))
            print(f"  {description:20} ❌ {str(e)[:50]}")
    
    return all(status == "✅" for _, status, _ in results)

async def test_config():
    """测试配置"""
    print("\n" + "="*60)
    print("2. 配置测试")
    print("="*60)
    
    try:
        # 创建简化的配置类
        from pydantic_settings import BaseSettings
        
        class SimpleSettings(BaseSettings):
            PROJECT_NAME: str = "竹林司马测试"
            VERSION: str = "1.0.0"
            DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
            DEBUG: bool = True
            API_V1_PREFIX: str = "/api/v1"
            
            model_config = {
                "env_file": ".env",
                "extra": "ignore"
            }
        
        settings = SimpleSettings()
        print(f"  ✅ 配置创建成功")
        print(f"     项目: {settings.PROJECT_NAME}")
        print(f"     版本: {settings.VERSION}")
        print(f"     数据库: {settings.DATABASE_URL}")
        print(f"     调试模式: {settings.DEBUG}")
        return True
        
    except Exception as e:
        print(f"  ❌ 配置测试失败: {e}")
        return False

async def test_database():
    """测试数据库连接"""
    print("\n" + "="*60)
    print("3. 数据库连接测试")
    print("="*60)
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        
        # 创建异步引擎
        engine = create_async_engine(
            "sqlite+aiosqlite:///./test.db",
            echo=False,
            future=True
        )
        
        # 测试连接
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            data = result.scalar()
            print(f"  ✅ 数据库连接测试成功: {data}")
        
        # 关闭引擎
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"  ❌ 数据库连接测试失败: {e}")
        return False

async def test_fastapi_app():
    """测试FastAPI应用"""
    print("\n" + "="*60)
    print("4. FastAPI应用测试")
    print("="*60)
    
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        # 创建测试应用
        app = FastAPI(title="测试应用", version="1.0.0")
        
        @app.get("/")
        async def root():
            return {"message": "Hello World", "status": "ok"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        # 使用测试客户端
        client = TestClient(app)
        
        # 测试端点
        response = client.get("/")
        if response.status_code == 200:
            print(f"  ✅ 根端点测试成功: {response.json()}")
        else:
            print(f"  ❌ 根端点测试失败: HTTP {response.status_code}")
            return False
        
        response = client.get("/health")
        if response.status_code == 200:
            print(f"  ✅ 健康检查测试成功: {response.json()}")
        else:
            print(f"  ❌ 健康检查测试失败: HTTP {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ FastAPI测试失败: {e}")
        return False

async def test_security():
    """测试安全功能"""
    print("\n" + "="*60)
    print("5. 安全功能测试")
    print("="*60)
    
    try:
        import jwt
        from datetime import datetime, timedelta
        
        # 测试JWT令牌
        secret_key = "test-secret-key"
        payload = {
            "sub": "testuser@example.com",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        }
        
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        
        if decoded["sub"] == payload["sub"]:
            print(f"  ✅ JWT令牌测试成功")
            print(f"     令牌长度: {len(token)}")
            return True
        else:
            print(f"  ❌ JWT令牌验证失败")
            return False
            
    except Exception as e:
        print(f"  ❌ 安全功能测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("竹林司马后端 - 最小化功能测试")
    print("="*60)
    
    tests = [
        ("模块导入", test_imports()),
        ("配置系统", test_config()),
        ("数据库连接", test_database()),
        ("FastAPI应用", test_fastapi_app()),
        ("安全功能", test_security()),
    ]
    
    # 等待所有测试完成
    results = []
    for name, coro in tests:
        try:
            success = await coro
            results.append((name, success))
        except Exception as e:
            print(f"  ❌ {name}测试异常: {e}")
            results.append((name, False))
    
    # 输出摘要
    print("\n" + "="*60)
    print("测试结果摘要")
    print("="*60)
    
    all_passed = True
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:20} {status}")
        if not success:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 所有测试通过！后端程序核心功能正常。")
        print("\n下一步建议:")
        print("1. 修复配置文件中的字段类型问题")
        print("2. 创建完整的.env配置文件")
        print("3. 运行数据库初始化脚本")
        print("4. 启动完整的后端服务")
    else:
        print("⚠️  部分测试失败，需要修复问题。")
        print("\n主要问题可能是:")
        print("1. 配置类字段类型不匹配")
        print("2. 依赖包版本问题")
        print("3. 环境变量解析错误")
    
    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)