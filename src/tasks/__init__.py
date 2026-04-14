"""
任务模块
集成消息队列，提供异步任务处理能力
"""
from .api import router as tasks_router
from .service import TaskService, get_task_service
from .handlers import (
    send_email_task,
    process_image_task,
    generate_report_task,
    cleanup_expired_data_task,
    backup_database_task,
    send_notification_task,
)

__all__ = [
    "tasks_router",
    "TaskService",
    "get_task_service",
    "send_email_task",
    "process_image_task", 
    "generate_report_task",
    "cleanup_expired_data_task",
    "backup_database_task",
    "send_notification_task",
]