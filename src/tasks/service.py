"""
任务服务
管理异步任务的创建、执行和监控
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.task_queue import TaskQueue, TaskWorker, QueueConfig
from src.task_queue.config import get_queue_config
from src.task_queue.models import MessageStatus

from .models import (
    TaskCreateRequest,
    TaskResponse,
    TaskStatus,
    TaskPriority,
    TaskUpdateRequest,
    TaskFilter,
)

logger = logging.getLogger(__name__)


class TaskService:
    """任务服务"""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or get_queue_config()
        self.queue = TaskQueue(self.config)
        self.worker: Optional[TaskWorker] = None
        self.task_store: Dict[str, Dict[str, Any]] = {}  # 内存存储任务状态
        
    async def enqueue_task(
        self,
        name: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
        timeout: int = 300
    ) -> str:
        """将任务加入队列"""
        try:
            task_id = str(uuid4())
            
            # 创建任务记录
            task_data = {
                "id": task_id,
                "name": name,
                "args": args or [],
                "kwargs": kwargs or {},
                "priority": priority.value,
                "status": TaskStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
                "max_retries": max_retries,
                "timeout": timeout,
                "retry_count": 0,
                "progress": 0,
                "metadata": {},
            }
            
            # 存储任务状态
            self.task_store[task_id] = task_data
            
            # 将任务加入队列
            await self.queue.enqueue(
                name,
                *task_data["args"],
                **task_data["kwargs"]
            )
            
            logger.info(f"任务已加入队列: {task_id}, 名称: {name}")
            return task_id
            
        except Exception as e:
            logger.error(f"加入任务队列失败: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """获取任务详情"""
        task_data = self.task_store.get(task_id)
        if not task_data:
            return None
        
        return TaskResponse(**task_data)
    
    async def get_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TaskResponse]:
        """获取任务列表"""
        try:
            tasks = []
            filtered_tasks = []
            
            # 应用状态过滤
            for task_data in self.task_store.values():
                if status is None or task_data.get("status") == status:
                    filtered_tasks.append(task_data)
            
            # 按创建时间排序（最新的在前）
            sorted_tasks = sorted(
                filtered_tasks,
                key=lambda x: x.get("created_at", ""),
                reverse=True
            )
            
            # 应用分页
            paginated_tasks = sorted_tasks[offset:offset + limit]
            
            for task_data in paginated_tasks:
                tasks.append(TaskResponse(**task_data))
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []
    
    async def update_task(
        self,
        task_id: str,
        update_data: TaskUpdateRequest
    ) -> Optional[TaskResponse]:
        """更新任务状态"""
        task_data = self.task_store.get(task_id)
        if not task_data:
            return None
        
        # 更新任务数据
        if update_data.status is not None:
            task_data["status"] = update_data.status.value
        
        if update_data.progress is not None:
            task_data["progress"] = update_data.progress
            
            # 如果进度为100%，自动标记为完成
            if update_data.progress == 100 and task_data["status"] == TaskStatus.PROCESSING.value:
                task_data["status"] = TaskStatus.COMPLETED.value
                task_data["completed_at"] = datetime.utcnow().isoformat()
        
        if update_data.result is not None:
            task_data["result"] = update_data.result
        
        if update_data.error is not None:
            task_data["error"] = update_data.error
            task_data["status"] = TaskStatus.FAILED.value
        
        if update_data.metadata is not None:
            task_data["metadata"].update(update_data.metadata)
        
        self.task_store[task_id] = task_data
        return TaskResponse(**task_data)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task_data = self.task_store.get(task_id)
        if not task_data:
            return False
        
        # 只能取消待处理的任务
        if task_data["status"] not in [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]:
            return False
        
        task_data["status"] = TaskStatus.CANCELLED.value
        task_data["completed_at"] = datetime.utcnow().isoformat()
        self.task_store[task_id] = task_data
        
        logger.info(f"任务已取消: {task_id}")
        return True
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        try:
            queue_stats = await self.queue.task_stats()
            
            # 计算任务统计
            task_stats = {
                "total_tasks": len(self.task_store),
                "pending_tasks": sum(1 for t in self.task_store.values() 
                                   if t.get("status") == TaskStatus.PENDING.value),
                "processing_tasks": sum(1 for t in self.task_store.values() 
                                      if t.get("status") == TaskStatus.PROCESSING.value),
                "completed_tasks": sum(1 for t in self.task_store.values() 
                                     if t.get("status") == TaskStatus.COMPLETED.value),
                "failed_tasks": sum(1 for t in self.task_store.values() 
                                  if t.get("status") == TaskStatus.FAILED.value),
                "cancelled_tasks": sum(1 for t in self.task_store.values() 
                                     if t.get("status") == TaskStatus.CANCELLED.value),
            }
            
            # 计算平均处理时间
            completed_tasks = [
                t for t in self.task_store.values() 
                if t.get("status") == TaskStatus.COMPLETED.value 
                and t.get("created_at") and t.get("completed_at")
            ]
            
            if completed_tasks:
                total_time = 0
                for task in completed_tasks:
                    created_at = datetime.fromisoformat(task["created_at"])
                    completed_at = datetime.fromisoformat(task["completed_at"])
                    total_time += (completed_at - created_at).total_seconds()
                
                task_stats["avg_processing_time"] = total_time / len(completed_tasks)
                
                # 计算成功率
                total_completed = len(completed_tasks)
                total_failed = task_stats["failed_tasks"]
                total_processed = total_completed + total_failed
                
                if total_processed > 0:
                    task_stats["success_rate"] = (total_completed / total_processed) * 100
            
            return {
                "queue": queue_stats,
                "tasks": task_stats,
            }
            
        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            return {"queue": {}, "tasks": {}, "error": str(e)}
    
    async def get_worker_stats(self) -> Dict[str, Any]:
        """获取工作器统计信息"""
        if not self.worker:
            return {"worker": None, "message": "工作器未启动"}
        
        try:
            return {
                "worker": self.worker.get_stats(),
                "worker_running": self.worker.running,
            }
        except Exception as e:
            logger.error(f"获取工作器统计失败: {e}")
            return {"worker": None, "error": str(e)}
    
    async def cleanup_old_tasks(self, days_old: int = 30) -> int:
        """清理旧任务"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            cutoff_iso = cutoff_date.isoformat()
            
            removed_count = 0
            task_ids_to_remove = []
            
            for task_id, task_data in self.task_store.items():
                created_at = task_data.get("created_at", "")
                status = task_data.get("status", "")
                
                # 只清理已完成、失败或取消的旧任务
                if (created_at < cutoff_iso and 
                    status in [TaskStatus.COMPLETED.value, 
                              TaskStatus.FAILED.value, 
                              TaskStatus.CANCELLED.value]):
                    task_ids_to_remove.append(task_id)
            
            # 删除任务
            for task_id in task_ids_to_remove:
                del self.task_store[task_id]
                removed_count += 1
            
            logger.info(f"清理了 {removed_count} 个 {days_old} 天前的任务")
            return removed_count
            
        except Exception as e:
            logger.error(f"清理旧任务失败: {e}")
            return 0
    
    async def retry_failed_tasks(self) -> int:
        """重试失败的任务"""
        try:
            retry_count = 0
            
            for task_id, task_data in self.task_store.items():
                status = task_data.get("status", "")
                retry_count_val = task_data.get("retry_count", 0)
                max_retries = task_data.get("max_retries", 3)
                
                # 重试失败的任务
                if status == TaskStatus.FAILED.value and retry_count_val < max_retries:
                    task_data["status"] = TaskStatus.PENDING.value
                    task_data["retry_count"] = retry_count_val + 1
                    task_data["error"] = None
                    
                    # 重新加入队列
                    await self.queue.enqueue(
                        task_data["name"],
                        *task_data["args"],
                        **task_data["kwargs"]
                    )
                    
                    retry_count += 1
            
            logger.info(f"重新排队了 {retry_count} 个失败任务")
            return retry_count
            
        except Exception as e:
            logger.error(f"重试失败任务失败: {e}")
            return 0
    
    async def start_worker(self):
        """启动任务工作器"""
        if self.worker and self.worker.running:
            logger.warning("任务工作器已经在运行")
            return
        
        try:
            self.worker = TaskWorker(self.config)
            # 这里可以注册任务处理器
            
            # 在工作线程中启动工作器
            loop = asyncio.get_event_loop()
            loop.create_task(self.worker.start())
            
            logger.info("任务工作器已启动")
            
        except Exception as e:
            logger.error(f"启动任务工作器失败: {e}")
            raise
    
    async def stop_worker(self):
        """停止任务工作器"""
        if not self.worker or not self.worker.running:
            logger.warning("任务工作器未在运行")
            return
        
        try:
            await self.worker.stop()
            logger.info("任务工作器已停止")
            
        except Exception as e:
            logger.error(f"停止任务工作器失败: {e}")
            raise


# 依赖注入函数
_task_service: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """获取任务服务实例"""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service