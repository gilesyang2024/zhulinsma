"""
简化的应用配置管理模块

不使用pydantic-settings，避免JSON解析问题。
使用python-dotenv直接读取环境变量。
"""
import os
from typing import List, Optional, Literal
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class Settings:
    """应用配置"""
    
    def __init__(self):
        # 应用基础配置
        self.APP_NAME = self._get_env("APP_NAME", "竹林司马后端")
        self.APP_ENV = self._get_env("APP_ENV", "development")
        self.APP_VERSION = self._get_env("APP_VERSION", "1.0.0")
        self.APP_DEBUG = self._get_env_bool("APP_DEBUG", True)
        self.APP_SECRET_KEY = self._get_env("APP_SECRET_KEY", "development-secret-key-must-be-32-chars-long")
        
        # 处理列表字段
        self.APP_ALLOWED_HOSTS = self._get_env_list("APP_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
        self.APP_CORS_ORIGINS = self._get_env_list("APP_CORS_ORIGINS", ["http://localhost:3000", "http://localhost:8000"])
        
        # API配置
        self.API_V1_STR = self._get_env("API_V1_STR", "/api/v1")
        self.API_PREFIX = self._get_env("API_PREFIX", "/api")
        self.PROJECT_NAME = self._get_env("PROJECT_NAME", "竹林司马API")
        
        # 数据库配置
        self.DATABASE_URL = self._get_env("DATABASE_URL", "sqlite+aiosqlite:///./zhulinsma.db")
        self.DATABASE_POOL_SIZE = self._get_env_int("DATABASE_POOL_SIZE", 5)
        self.DATABASE_MAX_OVERFLOW = self._get_env_int("DATABASE_MAX_OVERFLOW", 10)
        self.DATABASE_POOL_RECYCLE = self._get_env_int("DATABASE_POOL_RECYCLE", 3600)
        self.DATABASE_ECHO = self._get_env_bool("DATABASE_ECHO", False)
        
        # Redis配置
        self.REDIS_URL = self._get_env("REDIS_URL", "redis://localhost:6379/0")
        self.REDIS_PASSWORD = self._get_env("REDIS_PASSWORD", None)
        self.REDIS_POOL_SIZE = self._get_env_int("REDIS_POOL_SIZE", 5)
        
        # Redis集群配置（可选，默认单节点模式）
        self.REDIS_CLUSTER_ENABLED = self._get_env_bool("REDIS_CLUSTER_ENABLED", False)
        self.REDIS_CLUSTER_NODES = self._get_env_list("REDIS_CLUSTER_NODES", [])
        
        # JWT配置
        self.JWT_SECRET_KEY = self._get_env("JWT_SECRET_KEY", "development-jwt-secret-key-must-be-32-chars")
        self.JWT_ALGORITHM = self._get_env("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = self._get_env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
        self.JWT_REFRESH_TOKEN_EXPIRE_DAYS = self._get_env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)
        
        # 文件上传配置
        self.FILE_UPLOAD_MAX_SIZE = self._get_env_int("FILE_UPLOAD_MAX_SIZE", 10485760)  # 10MB
        self.FILE_STORAGE_PROVIDER = self._get_env("FILE_STORAGE_PROVIDER", "local")
        self.FILE_STORAGE_PATH = self._get_env("FILE_STORAGE_PATH", "./uploads")
        
        # 日志配置
        self.LOG_LEVEL = self._get_env("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = self._get_env("LOG_FORMAT", "json")
        self.LOG_FILE = self._get_env("LOG_FILE", "./logs/app.log")
        
        # 速率限制配置
        self.RATE_LIMIT_ENABLED = self._get_env_bool("RATE_LIMIT_ENABLED", False)
        self.RATE_LIMIT_DEFAULT = self._get_env("RATE_LIMIT_DEFAULT", "60/minute")
        self.RATE_LIMIT_AUTH = self._get_env("RATE_LIMIT_AUTH", "5/minute")
        self.RATE_LIMIT_UPLOAD = self._get_env("RATE_LIMIT_UPLOAD", "10/minute")
        
        # LLM 大模型配置
        self.LLM_PROVIDER = self._get_env("LLM_PROVIDER", "deepseek")  # deepseek/openai/qwen/glm/ollama
        self.LLM_API_KEY = self._get_env("LLM_API_KEY", "")
        self.LLM_MODEL = self._get_env("LLM_MODEL", "deepseek-chat")
        self.LLM_TEMPERATURE = self._get_env_float("LLM_TEMPERATURE", 0.3)
        self.LLM_MAX_TOKENS = self._get_env_int("LLM_MAX_TOKENS", 4096)
        self.LLM_TIMEOUT = self._get_env_int("LLM_TIMEOUT", 60)
        self.LLM_CACHE_ENABLED = self._get_env_bool("LLM_CACHE_ENABLED", True)
        
        # 验证密钥长度
        if len(self.APP_SECRET_KEY) < 32:
            raise ValueError(f"APP_SECRET_KEY必须至少32个字符，当前{len(self.APP_SECRET_KEY)}个字符")
        
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError(f"JWT_SECRET_KEY必须至少32个字符，当前{len(self.JWT_SECRET_KEY)}个字符")
    
    def _get_env(self, key: str, default: Optional[str] = None) -> str:
        """获取环境变量"""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ValueError(f"环境变量{key}未设置")
            return default
        return value
    
    def _get_env_int(self, key: str, default: int) -> int:
        """获取整数环境变量"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
    
    def _get_env_bool(self, key: str, default: bool) -> bool:
        """获取布尔环境变量"""
        value = os.getenv(key)
        if value is None:
            return default
        value_lower = value.lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off"):
            return False
        return default
    
    def _get_env_list(self, key: str, default: List[str]) -> List[str]:
        """获取列表环境变量（逗号分隔）"""
        value = os.getenv(key)
        if value is None:
            return default
        
        # 移除可能的引号
        value = value.strip('"').strip("'")
        
        # 分割为列表
        if not value:
            return []
        
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _get_env_float(self, key: str, default: float) -> float:
        """获取浮点数环境变量"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default
    
    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.APP_ENV == "production"
    
    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.APP_ENV == "development"
    
    @property
    def is_staging(self) -> bool:
        """是否预发布环境"""
        return self.APP_ENV == "staging"
    
    @property
    def database_config(self) -> dict:
        """数据库配置字典"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "echo": self.DATABASE_ECHO,
        }
    
    @property
    def jwt_config(self) -> dict:
        """JWT配置字典"""
        return {
            "secret_key": self.JWT_SECRET_KEY,
            "algorithm": self.JWT_ALGORITHM,
            "access_token_expire_minutes": self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": self.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        }


# 全局配置实例
settings = Settings()

# 环境变量覆盖（用于测试）
if os.getenv("APP_ENV") == "test":
    settings.DATABASE_URL = "postgresql://test:test@localhost:5432/zhulinsma_test"
    settings.REDIS_URL = "redis://localhost:6379/15"
    settings.APP_DEBUG = True