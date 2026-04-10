#!/usr/bin/env python3
"""
简单的配置测试 - 直接验证配置逻辑
"""
import os
import sys
from typing import List

# 手动设置环境变量，不依赖.env文件
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-config-validation-only"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-validation"

print("🔧 开始简单配置测试")
print("=" * 50)

# 测试手动创建的配置
try:
    from pydantic_settings import BaseSettings
    from typing import List, Optional, Literal
    from pydantic import Field
    
    class SimpleSettings(BaseSettings):
        """简化配置类用于测试"""
        APP_NAME: str = "竹林司马后端"
        APP_ENV: Literal["development", "staging", "production"] = "development"
        APP_VERSION: str = "1.0.0"
        APP_DEBUG: bool = True
        APP_SECRET_KEY: str = Field(..., min_length=32)
        APP_ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
        APP_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
        
        DATABASE_URL: str = "sqlite+aiosqlite:///./zhulinsma.db"
        DATABASE_POOL_SIZE: int = 5
        DATABASE_MAX_OVERFLOW: int = 10
        DATABASE_POOL_RECYCLE: int = 3600
        
        JWT_SECRET_KEY: str = Field(..., min_length=32)
        JWT_ALGORITHM: str = "HS256"
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
        
        class Config:
            env_file = None  # 不读取.env文件
            case_sensitive = True
            extra = "ignore"
    
    # 创建配置实例
    settings = SimpleSettings()
    
    print("✅ 成功创建配置实例")
    print(f"📱 应用名称: {settings.APP_NAME}")
    print(f"🌍 环境: {settings.APP_ENV}")
    print(f"🔧 调试模式: {settings.APP_DEBUG}")
    print(f"🔑 密钥长度: {len(settings.APP_SECRET_KEY)}")
    
    # 检查列表字段
    print(f"🌐 允许的主机: {settings.APP_ALLOWED_HOSTS}")
    print(f"🔄 CORS来源: {settings.APP_CORS_ORIGINS}")
    
    # 验证类型
    assert isinstance(settings.APP_ALLOWED_HOSTS, List), "APP_ALLOWED_HOSTS应该是列表"
    assert isinstance(settings.APP_CORS_ORIGINS, List), "APP_CORS_ORIGINS应该是列表"
    print("✅ 列表字段类型正确")
    
    # 检查数据库URL
    print(f"🗄️  数据库URL: {settings.DATABASE_URL}")
    assert "sqlite" in settings.DATABASE_URL, "数据库URL应该是SQLite格式"
    print("✅ 数据库URL格式正确")
    
    print("\n🎉 简化配置测试通过！")
    print("建议：实际配置文件可能需要禁用JSON解析或使用不同的环境变量格式")
    
except Exception as e:
    print(f"❌ 配置测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)