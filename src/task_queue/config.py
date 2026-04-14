"""
消息队列配置
"""
from enum import Enum
from typing import Dict, Optional, Union
from pydantic import BaseModel, Field


class QueueType(str, Enum):
    """队列类型"""
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    AWS_SQS = "aws_sqs"
    AZURE_SB = "azure_sb"
    GOOGLE_PUBSUB = "google_pubsub"
    MEMORY = "memory"


class QueueConfig(BaseModel):
    """队列配置"""
    queue_type: QueueType = QueueType.REDIS
    connection_url: Optional[str] = None
    queue_name: str = "default"
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # RabbitMQ配置
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    
    # AWS SQS配置
    aws_region: str = "us-east-1"
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    
    # 通用配置
    max_retries: int = 3
    retry_delay: int = 60  # 秒
    visibility_timeout: int = 30  # 秒
    message_timeout: int = 300  # 秒
    batch_size: int = 10
    concurrent_workers: int = 4
    
    class Config:
        env_prefix = "QUEUE_"
        case_sensitive = False


# 默认配置
default_config = QueueConfig()


def get_queue_config() -> QueueConfig:
    """获取队列配置"""
    from src.core.config import Settings
    settings = Settings()
    
    return QueueConfig(
        queue_type=QueueType(settings.QUEUE_TYPE.lower()) if hasattr(settings, "QUEUE_TYPE") else QueueType.REDIS,
        connection_url=getattr(settings, "QUEUE_CONNECTION_URL", None),
        redis_host=getattr(settings, "REDIS_HOST", "localhost"),
        redis_port=getattr(settings, "REDIS_PORT", 6379),
        redis_db=getattr(settings, "REDIS_DB", 0),
        redis_password=getattr(settings, "REDIS_PASSWORD", None),
        max_retries=getattr(settings, "QUEUE_MAX_RETRIES", 3),
        retry_delay=getattr(settings, "QUEUE_RETRY_DELAY", 60),
    )