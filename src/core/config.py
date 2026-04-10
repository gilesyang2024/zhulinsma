"""
应用配置管理模块

基于Pydantic Settings管理所有环境变量和配置。
"""

import os
from typing import List, Optional, Literal
from pydantic import AnyHttpUrl, Field, PostgresDsn, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "竹林司马后端"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str = Field(..., min_length=32)
    APP_ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    
    # CORS配置
    APP_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    # API配置
    API_V1_STR: str = "/api/v1"
    API_PREFIX: str = "/api"
    PROJECT_NAME: str = "竹林司马API"
    
    # 数据库配置
    DATABASE_URL: PostgresDsn = "postgresql://zhulin:password@localhost:5432/zhulinsma"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_SIZE: int = 10
    
    # 消息队列配置
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # JWT配置
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 文件上传配置
    FILE_UPLOAD_MAX_SIZE: int = 100 * 1024 * 1024  # 100MB
    FILE_STORAGE_PROVIDER: Literal["local", "s3", "minio"] = "local"
    FILE_STORAGE_PATH: str = "./uploads"
    
    # AWS S3配置
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: str = "zhulinsma"
    AWS_S3_REGION: str = "ap-guangzhou"
    
    # MinIO配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    
    # 邮件配置
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@zhulinsma.com"
    SMTP_USE_TLS: bool = True
    
    # 监控配置
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_METRICS_PORT: int = 9090
    GRAFANA_URL: str = "http://localhost:3000"
    
    # 第三方API配置
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "20/5minutes"
    
    # 安全配置
    SECURE_COOKIES: bool = False
    CSP_ENABLED: bool = False
    HSTS_ENABLED: bool = False
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"
    
    @validator("APP_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """处理CORS来源配置"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    @validator("APP_ALLOWED_HOSTS", pre=True)
    def assemble_allowed_hosts(cls, v):
        """处理允许的主机配置"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
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
            "url": str(self.DATABASE_URL),
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "echo": self.DATABASE_ECHO,
        }
    
    @property
    def redis_config(self) -> dict:
        """Redis配置字典"""
        return {
            "url": self.REDIS_URL,
            "password": self.REDIS_PASSWORD,
            "pool_size": self.REDIS_POOL_SIZE,
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
    
    @property
    def storage_config(self) -> dict:
        """文件存储配置字典"""
        return {
            "provider": self.FILE_STORAGE_PROVIDER,
            "local_path": self.FILE_STORAGE_PATH,
            "max_size": self.FILE_UPLOAD_MAX_SIZE,
            "aws_access_key_id": self.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": self.AWS_SECRET_ACCESS_KEY,
            "aws_s3_bucket": self.AWS_S3_BUCKET,
            "aws_s3_region": self.AWS_S3_REGION,
            "minio_endpoint": self.MINIO_ENDPOINT,
            "minio_access_key": self.MINIO_ACCESS_KEY,
            "minio_secret_key": self.MINIO_SECRET_KEY,
            "minio_secure": self.MINIO_SECURE,
        }
    
    @property
    def rate_limit_config(self) -> dict:
        """速率限制配置字典"""
        return {
            "enabled": self.RATE_LIMIT_ENABLED,
            "default": self.RATE_LIMIT_DEFAULT,
            "auth": self.RATE_LIMIT_AUTH,
            "upload": self.RATE_LIMIT_UPLOAD,
        }


# 全局配置实例
settings = Settings()

# 环境变量覆盖（用于测试）
if os.getenv("APP_ENV") == "test":
    settings.DATABASE_URL = "postgresql://test:test@localhost:5432/zhulinsma_test"
    settings.REDIS_URL = "redis://localhost:6379/15"  # 使用不同的数据库
    settings.APP_DEBUG = True
    settings.RATE_LIMIT_ENABLED = False