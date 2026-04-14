"""
消息队列工作器
处理队列中的消息和任务
"""
import asyncio
import inspect
import logging
import signal
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type
from uuid import UUID

from .client import MessageQueue, TaskQueue
from .config import QueueConfig, get_queue_config
from .models import Message, MessageStatus, Task

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """基础工作器"""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or get_queue_config()
        self.running = False
        self.processed_count = 0
        self.error_count = 0
        
    @abstractmethod
    async def start(self):
        """启动工作器"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止工作器"""
        pass
    
    @abstractmethod
    async def process_message(self, message: Message) -> bool:
        """处理消息"""
        pass


class Worker(BaseWorker):
    """通用消息工作器"""
    
    def __init__(self, queue_name: str, config: Optional[QueueConfig] = None):
        super().__init__(config)
        self.queue_name = queue_name
        self.queue = MessageQueue(config)
        self.handlers: Dict[str, Callable] = {}
        
    def register_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        self.handlers[message_type] = handler
        logger.info(f"注册消息处理器: {message_type}")
    
    async def start(self):
        """启动工作器"""
        self.running = True
        logger.info(f"启动消息工作器，队列: {self.queue_name}")
        
        while self.running:
            try:
                # 接收消息
                message = await self.queue.receive(self.queue_name, timeout=1)
                
                if message:
                    logger.info(f"收到消息: {message.id}, 类型: {message.body.get('type', 'unknown')}")
                    
                    # 处理消息
                    success = await self.process_message(message)
                    
                    if success:
                        # 确认消息处理完成
                        await self.queue.ack(self.queue_name, str(message.id))
                        self.processed_count += 1
                    else:
                        logger.warning(f"消息处理失败: {message.id}")
                        self.error_count += 1
                
                # 短暂休眠，避免CPU占用过高
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info("工作器被取消")
                break
            except Exception as e:
                logger.error(f"工作器运行异常: {e}")
                self.error_count += 1
                await asyncio.sleep(1)  # 异常后等待1秒
    
    async def stop(self):
        """停止工作器"""
        self.running = False
        logger.info("停止消息工作器")
    
    async def process_message(self, message: Message) -> bool:
        """处理消息"""
        try:
            message_type = message.body.get("type", "default")
            
            if message_type in self.handlers:
                handler = self.handlers[message_type]
                
                # 根据处理函数的签名调用
                if inspect.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                
                return True
            else:
                logger.warning(f"未找到消息类型的处理器: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工作器统计信息"""
        return {
            "queue_name": self.queue_name,
            "running": self.running,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "handlers": list(self.handlers.keys()),
        }


class TaskWorker(BaseWorker):
    """任务工作器"""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        super().__init__(config)
        self.queue = TaskQueue(config)
        self.tasks: Dict[str, Callable] = {}
        
    def register_task(self, task_name: str, task_func: Callable):
        """注册任务处理器"""
        self.tasks[task_name] = task_func
        logger.info(f"注册任务处理器: {task_name}")
    
    async def start(self):
        """启动任务工作器"""
        self.running = True
        logger.info("启动任务工作器")
        
        while self.running:
            try:
                # 接收任务
                task = await self.queue.dequeue()
                
                if task:
                    logger.info(f"收到任务: {task.id}, 名称: {task.name}")
                    
                    # 处理任务
                    success = await self.process_task(task)
                    
                    if success:
                        # 确认任务处理完成
                        await self.queue.ack("tasks", str(task.id))
                        self.processed_count += 1
                    else:
                        logger.warning(f"任务处理失败: {task.id}")
                        self.error_count += 1
                
                # 短暂休眠
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info("任务工作器被取消")
                break
            except Exception as e:
                logger.error(f"任务工作器运行异常: {e}")
                self.error_count += 1
                await asyncio.sleep(1)
    
    async def stop(self):
        """停止任务工作器"""
        self.running = False
        logger.info("停止任务工作器")
    
    async def process_task(self, task: Task) -> bool:
        """处理任务"""
        try:
            task_name = task.name
            
            if task_name in self.tasks:
                task_func = self.tasks[task_name]
                
                # 调用任务函数
                if inspect.iscoroutinefunction(task_func):
                    result = await task_func(*task.args, **task.kwargs)
                else:
                    result = task_func(*task.args, **task.kwargs)
                
                # 更新任务结果
                task.result = result
                task.status = MessageStatus.COMPLETED
                task.completed_at = time.time()
                
                logger.info(f"任务完成: {task.id}, 结果: {result}")
                return True
            else:
                logger.warning(f"未找到任务处理器: {task_name}")
                task.status = MessageStatus.FAILED
                task.error = f"未注册的任务: {task_name}"
                return False
                
        except Exception as e:
            logger.error(f"处理任务失败: {e}")
            task.status = MessageStatus.FAILED
            task.error = str(e)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取任务工作器统计信息"""
        return {
            "running": self.running,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "registered_tasks": list(self.tasks.keys()),
        }


class QueueWorker:
    """队列工作器管理器"""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or get_queue_config()
        self.workers: List[BaseWorker] = []
        self.running = False
        
    def add_worker(self, worker: BaseWorker):
        """添加工作器"""
        self.workers.append(worker)
    
    async def start(self):
        """启动所有工作器"""
        self.running = True
        
        # 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        
        logger.info(f"启动队列工作器管理器，共 {len(self.workers)} 个工作器")
        
        # 启动所有工作器
        tasks = []
        for worker in self.workers:
            task = asyncio.create_task(worker.start())
            tasks.append(task)
        
        # 等待所有工作器完成
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("队列工作器管理器被取消")
    
    async def stop(self):
        """停止所有工作器"""
        self.running = False
        logger.info("停止队列工作器管理器")
        
        for worker in self.workers:
            await worker.stop()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有工作器统计信息"""
        stats = {
            "total_workers": len(self.workers),
            "running": self.running,
            "workers": []
        }
        
        for i, worker in enumerate(self.workers):
            worker_stats = worker.get_stats()
            worker_stats["worker_index"] = i
            stats["workers"].append(worker_stats)
        
        return stats