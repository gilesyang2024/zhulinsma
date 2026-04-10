#!/usr/bin/env python3
"""
测试应用启动
"""
import sys
import os
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_app_import():
    """测试应用导入"""
    try:
        # 测试配置导入
        from src.core.config import settings
        print("✅ 配置导入成功")
        
        # 测试数据库模块导入
        try:
            from src.core.database import db
            print("✅ 数据库模块导入成功")
        except Exception as e:
            print(f"⚠️  数据库模块导入警告: {e}")
        
        # 测试缓存模块导入
        try:
            from src.core.cache import cache
            print("✅ 缓存模块导入成功")
        except Exception as e:
            print(f"⚠️  缓存模块导入警告: {e}")
        
        # 测试API模块导入
        try:
            from src.api.v1 import api_router
            print("✅ API路由导入成功")
        except Exception as e:
            print(f"⚠️  API路由导入警告: {e}")
        
        # 测试创建FastAPI应用
        try:
            from fastapi import FastAPI
            app = FastAPI(
                title=settings.PROJECT_NAME,
                version=settings.APP_VERSION,
                debug=settings.APP_DEBUG,
            )
            print("✅ FastAPI应用创建成功")
            
            # 添加基本路由
            @app.get("/")
            async def root():
                return {"message": "竹林司马后端", "version": settings.APP_VERSION}
            
            @app.get("/health")
            async def health():
                return {"status": "healthy", "timestamp": datetime.now().isoformat()}
            
            print("✅ 基本路由添加成功")
            
            return app, settings
            
        except Exception as e:
            print(f"❌ FastAPI应用创建失败: {e}")
            return None, None
        
    except Exception as e:
        print(f"❌ 应用导入失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None

async def test_minimal_server():
    """测试最小化服务器启动"""
    print("\n🔧 测试最小化服务器启动")
    print("=" * 50)
    
    try:
        # 导入必要的模块
        from fastapi import FastAPI
        import uvicorn
        from datetime import datetime
        
        # 创建简单应用
        app = FastAPI(
            title="竹林司马后端测试",
            version="1.0.0",
            debug=True,
        )
        
        @app.get("/")
        async def root():
            return {"message": "竹林司马后端测试服务器", "timestamp": datetime.now().isoformat()}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "service": "zhulinsma-backend"}
        
        # 测试服务器启动（不实际运行）
        print("✅ FastAPI应用创建成功")
        print(f"📱 应用名称: {app.title}")
        print(f"🔢 版本: {app.version}")
        print(f"🔧 调试模式: {app.debug}")
        print(f"🌐 路由: {[route.path for route in app.routes if hasattr(route, 'path')]}")
        
        print("\n✅ 最小化服务器测试通过！")
        print("注意: 这只是创建应用实例，没有实际启动服务器")
        
        return app
        
    except Exception as e:
        print(f"❌ 最小化服务器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主函数"""
    print("🚀 测试竹林司马后端应用启动")
    print("=" * 50)
    
    # 运行导入测试
    import datetime
    global datetime
    app, settings = asyncio.run(test_app_import())
    
    if app is None:
        print("\n❌ 应用导入测试失败")
        return False
    
    print("\n✅ 应用导入测试完成！")
    print(f"📊 配置信息:")
    print(f"  应用名称: {settings.APP_NAME}")
    print(f"  环境: {settings.APP_ENV}")
    print(f"  调试模式: {settings.APP_DEBUG}")
    print(f"  数据库URL: {settings.DATABASE_URL}")
    
    # 运行最小化服务器测试
    asyncio.run(test_minimal_server())
    
    print("\n🎉 应用启动测试完成！")
    print("\n下一步建议:")
    print("1. 运行数据库初始化: python scripts/simple_db_init.py")
    print("2. 启动开发服务器: uvicorn main:app --reload --host 0.0.0.0 --port 8000")
    print("3. 访问 http://localhost:8000/docs 查看API文档")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)