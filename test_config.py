#!/usr/bin/env python3
"""
简化的配置测试
"""

import os
import sys

# 设置环境变量
os.environ.update({
    'APP_SECRET_KEY': 'test-secret-key-32-chars-long-123456',
    'JWT_SECRET_KEY': 'test-jwt-key-32-chars-long-789012',
    'APP_ALLOWED_HOSTS': 'localhost,127.0.0.1',
    'APP_CORS_ORIGINS': 'http://localhost:8000',
    'DATABASE_URL': 'postgresql://zhulin:password@localhost:5432/zhulinsma',
    'LOG_FORMAT': 'json',
    'APP_ENV': 'development',
    'APP_DEBUG': 'true',
    'APP_NAME': '竹林司马测试',
    'APP_VERSION': '1.0.0',
    'PROJECT_NAME': '测试项目',
    'API_V1_STR': '/api/v1',
    'API_PREFIX': '/api',
})

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # 导入配置
    from src.core.config import settings
    
    print("="*60)
    print("配置测试结果")
    print("="*60)
    print(f"✅ 配置加载成功")
    print(f"   项目: {settings.PROJECT_NAME}")
    print(f"   版本: {settings.VERSION}")
    print(f"   环境: {settings.APP_ENV}")
    print(f"   调试: {settings.APP_DEBUG}")
    print(f"   数据库URL: {settings.DATABASE_URL}")
    print(f"   API前缀: {settings.API_PREFIX}")
    
    # 测试计算属性
    print(f"   允许的主机列表: {settings.allowed_hosts_list}")
    print(f"   CORS来源列表: {settings.cors_origins_list}")
    print(f"   是否开发环境: {settings.is_development}")
    
    print("\n✅ 所有配置测试通过！")
    
except Exception as e:
    print(f"❌ 配置测试失败: {e}")
    import traceback
    traceback.print_exc()