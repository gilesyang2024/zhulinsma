"""
消息队列模块
支持多种消息队列后端（Redis/RabbitMQ/SQS等）
提供统一的异步任务处理接口
"""
from .client import MessageQueue, TaskQueue, QueueConfig
from .models import Message, Task, QueueMessage
from .worker import Worker, TaskWorker, QueueWorker

__all__ = [
    "MessageQueue",
    "TaskQueue",
    "QueueConfig",
    "Message",
    "Task",
    "QueueMessage",
    "Worker",
    "TaskWorker",
    "QueueWorker",
]