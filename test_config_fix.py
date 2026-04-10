#!/usr/bin/env python3
"""
测试配置修复后的功能
"""
import sys
import os
from typing import List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_import():
    """测试配置导入"""
    try:
        from src.core.config import settings
        print("✅ 成功导入配置模块")
        
        # 检查配置值
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
        
        # 检查配置属性
        print(f"🏭 是否开发环境: {settings.is_development}")
        print(f"📊 数据库配置: {settings.database_config}")
        print(f"🔐 JWT配置: {settings.jwt_config}")
        
        print("\n🎉 所有配置测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔧 测试竹林司马后端配置修复")
    print("=" * 50)
    
    # 测试环境变量
    print("📝 当前环境变量:")
    print(f"  APP_ALLOWED_HOSTS: {os.getenv('APP_ALLOWED_HOSTS', '未设置')}")
    print(f"  APP_CORS_ORIGINS: {os.getenv('APP_CORS_ORIGINS', '未设置')}")
    print(f"  DATABASE_URL: {os.getenv('DATABASE_URL', '未设置')}")
    print()
    
    # 运行测试
    success = test_config_import()
    
    if success:
        print("\n✅ 配置修复成功！应用现在可以正常启动了。")
    else:
        print("\n❌ 配置修复失败，请检查错误信息。")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)