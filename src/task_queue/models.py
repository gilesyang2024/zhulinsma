"""
消息队列数据模型定义
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    """消息状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


class Message(BaseModel):
    """基础消息模型"""
    id: UUID = Field(default_factory=uuid4)
    queue_name: str
    body: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class Task(BaseModel):
    """任务模型"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    args: list = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    status: MessageStatus = MessageStatus.PENDING
    progress: int = 0  # 0-100
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    timeout: int = 300  # 秒

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class QueueMessage(BaseModel):
    """队列消息模型"""
    id: str
    queue: str
    body: bytes
    attributes: Dict[str, Any] = Field(default_factory=dict)
    receipt_handle: Optional[str] = None  # 用于AWS SQS等

    class Config:
        arbitrary_types_allowed = True