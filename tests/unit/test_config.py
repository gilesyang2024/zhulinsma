"""测试配置模块"""
import pytest
from unittest.mock import patch, mock_open
from src.core.config import Settings, get_settings


class TestSettings:
    """测试Settings类"""
    
    def test_default_values(self):
        """测试默认值"""
        settings = Settings()
        
        # 测试默认值
        assert settings.DEBUG is False
        assert settings.API_V1_PREFIX == "/api/v1"
        assert settings.PROJECT_NAME == "竹林司马"
        assert settings.VERSION == "1.0.0"
        
    def test_database_url_construction(self):
        """测试数据库URL构造"""
        settings = Settings()
        
        # SQLite测试URL
        assert "sqlite+aiosqlite" in settings.DATABASE_URL
        
    def test_security_defaults(self):
        """测试安全配置默认值"""
        settings = Settings()
        
        # JWT配置
        assert settings.SECRET_KEY is not None
        assert settings.ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        
    def test_cors_origins(self):
        """测试CORS配置"""
        settings = Settings()
        assert isinstance(settings.BACKEND_CORS_ORIGINS, list)
        assert "*" not in settings.BACKEND_CORS_ORIGINS  # 生产环境不应允许所有来源
        
    def test_environment_variables(self):
        """测试环境变量覆盖"""
        with patch.dict('os.environ', {
            'PROJECT_NAME': '测试项目',
            'DEBUG': 'true',
            'SECRET_KEY': 'test_secret_key_123',
        }):
            settings = Settings()
            
            assert settings.PROJECT_NAME == '测试项目'
            assert settings.DEBUG is True
            assert settings.SECRET_KEY == 'test_secret_key_123'


class TestGetSettings:
    """测试get_settings函数"""
    
    def test_get_settings_returns_singleton(self):
        """测试get_settings返回单例"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
        
    def test_settings_attributes_accessible(self):
        """测试设置属性可访问"""
        settings = get_settings()
        
        # 测试关键属性存在
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'SECRET_KEY')
        assert hasattr(settings, 'DEBUG')
        assert hasattr(settings, 'PROJECT_NAME')
        
    def test_logging_config_present(self):
        """测试日志配置存在"""
        settings = get_settings()
        
        assert hasattr(settings, 'LOGGING_CONFIG')
        assert isinstance(settings.LOGGING_CONFIG, dict)
        
        # 验证基本日志配置结构
        assert 'version' in settings.LOGGING_CONFIG
        assert 'formatters' in settings.LOGGING_CONFIG
        assert 'handlers' in settings.LOGGING_CONFIG
        assert 'loggers' in settings.LOGGING_CONFIG
        
    def test_redis_config(self):
        """测试Redis配置"""
        settings = get_settings()
        
        assert hasattr(settings, 'REDIS_HOST')
        assert hasattr(settings, 'REDIS_PORT')
        assert hasattr(settings, 'REDIS_DB')
        
    def test_email_config(self):
        """测试邮件配置"""
        settings = get_settings()
        
        assert hasattr(settings, 'SMTP_HOST')
        assert hasattr(settings, 'SMTP_PORT')
        assert hasattr(settings, 'EMAILS_FROM_EMAIL')
        
    def test_file_storage_config(self):
        """测试文件存储配置"""
        settings = get_settings()
        
        assert hasattr(settings, 'UPLOAD_DIR')
        assert hasattr(settings, 'MAX_UPLOAD_SIZE')
        assert hasattr(settings, 'ALLOWED_FILE_TYPES')
        
        # 验证上传目录路径
        assert settings.UPLOAD_DIR.endswith('uploads')
        
    def test_api_rate_limits(self):
        """测试API速率限制配置"""
        settings = get_settings()
        
        assert hasattr(settings, 'RATE_LIMIT_REQUESTS')
        assert hasattr(settings, 'RATE_LIMIT_PERIOD')
        
        # 验证默认值
        assert settings.RATE_LIMIT_REQUESTS == 100
        assert settings.RATE_LIMIT_PERIOD == 60  # 1分钟