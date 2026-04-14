"""
任务数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    name: str = Field(..., description="任务名称")
    args: List[Any] = Field(default_factory=list, description="任务参数")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="任务关键字参数")
    priority: TaskPriority = TaskPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3
    timeout: int = 300  # 秒


class TaskResponse(BaseModel):
    """任务响应"""
    id: UUID
    name: str
    status: TaskStatus
    priority: TaskPriority
    args: List[Any]
    kwargs: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: int = Field(0, ge=0, le=100)
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout: int = 300
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class TaskStats(BaseModel):
    """任务统计信息"""
    total_tasks: int = 0
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    avg_processing_time: float = 0.0  # 秒
    success_rate: float = 0.0  # 百分比
    queue_size: int = 0


class WorkerStats(BaseModel):
    """工作器统计信息"""
    worker_id: str
    running: bool
    processed_count: int = 0
    error_count: int = 0
    queue_name: str
    registered_tasks: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None


class QueueStats(BaseModel):
    """队列统计信息"""
    queue_name: str
    queue_type: str
    length: int = 0
    memory_usage: Optional[int] = None  # 字节
    pending_messages: int = 0
    processed_messages: int = 0
    failed_messages: int = 0
    last_cleaned_at: Optional[datetime] = None


class TaskUpdateRequest(BaseModel):
    """任务更新请求"""
    status: Optional[TaskStatus] = None
    progress: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskFilter(BaseModel):
    """任务过滤器"""
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    name: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    completed_after: Optional[datetime] = None
    completed_before: Optional[datetime] = None