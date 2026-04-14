"""
消息队列客户端
支持多种消息队列后端
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import redis
from pydantic import ValidationError

from .config import QueueConfig, QueueType, get_queue_config
from .models import Message, MessageStatus, QueueMessage, Task

logger = logging.getLogger(__name__)


class BaseQueueClient(ABC):
    """基础队列客户端接口"""
    
    @abstractmethod
    async def send_message(self, queue_name: str, message_body: Union[str, Dict], **kwargs) -> str:
        """发送消息到队列"""
        pass
    
    @abstractmethod
    async def receive_message(self, queue_name: str, **kwargs) -> Optional[QueueMessage]:
        """从队列接收消息"""
        pass
    
    @abstractmethod
    async def delete_message(self, queue_name: str, message_id: str, **kwargs) -> bool:
        """从队列删除消息"""
        pass
    
    @abstractmethod
    async def get_queue_length(self, queue_name: str) -> int:
        """获取队列长度"""
        pass
    
    @abstractmethod
    async def purge_queue(self, queue_name: str) -> bool:
        """清空队列"""
        pass


class RedisQueueClient(BaseQueueClient):
    """Redis队列客户端"""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self._client: Optional[redis.Redis] = None
    
    @property
    def client(self) -> redis.Redis:
        """获取Redis客户端连接"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password,
                decode_responses=False,  # 保持二进制数据
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        return self._client
    
    def _get_queue_key(self, queue_name: str) -> str:
        """获取队列键名"""
        return f"queue:{queue_name}"
    
    async def send_message(self, queue_name: str, message_body: Union[str, Dict], **kwargs) -> str:
        """发送消息到Redis队列"""
        try:
            if isinstance(message_body, dict):
                message_body = json.dumps(message_body, ensure_ascii=False)
            
            message_id = self.client.lpush(
                self._get_queue_key(queue_name),
                message_body
            )
            
            logger.info(f"消息已发送到队列 {queue_name}, 消息ID: {message_id}")
            return str(message_id)
        except Exception as e:
            logger.error(f"发送消息到Redis队列失败: {e}")
            raise
    
    async def receive_message(self, queue_name: str, **kwargs) -> Optional[QueueMessage]:
        """从Redis队列接收消息"""
        try:
            timeout = kwargs.get("timeout", self.config.visibility_timeout)
            
            # 使用BRPOP命令，支持阻塞等待
            result = self.client.brpop(
                self._get_queue_key(queue_name),
                timeout=timeout
            )
            
            if result:
                queue_key, message_body = result
                return QueueMessage(
                    id=str(hash(message_body)),  # 使用消息内容的哈希作为ID
                    queue=queue_name,
                    body=message_body,
                    attributes={"source": "redis"}
                )
            return None
        except Exception as e:
            logger.error(f"从Redis队列接收消息失败: {e}")
            return None
    
    async def delete_message(self, queue_name: str, message_id: str, **kwargs) -> bool:
        """Redis队列不需要单独删除消息，因为消息被消费后就自动删除了"""
        return True
    
    async def get_queue_length(self, queue_name: str) -> int:
        """获取Redis队列长度"""
        try:
            return self.client.llen(self._get_queue_key(queue_name))
        except Exception as e:
            logger.error(f"获取Redis队列长度失败: {e}")
            return 0
    
    async def purge_queue(self, queue_name: str) -> bool:
        """清空Redis队列"""
        try:
            self.client.delete(self._get_queue_key(queue_name))
            logger.info(f"Redis队列 {queue_name} 已清空")
            return True
        except Exception as e:
            logger.error(f"清空Redis队列失败: {e}")
            return False


class MemoryQueueClient(BaseQueueClient):
    """内存队列客户端（用于测试）"""
    
    def __init__(self, config: QueueConfig):
        self.config = config
        self._queues: Dict[str, List[bytes]] = {}
        self._processed_messages: Dict[str, List[str]] = {}
    
    async def send_message(self, queue_name: str, message_body: Union[str, Dict], **kwargs) -> str:
        """发送消息到内存队列"""
        if queue_name not in self._queues:
            self._queues[queue_name] = []
        
        if isinstance(message_body, dict):
            message_body = json.dumps(message_body, ensure_ascii=False).encode('utf-8')
        elif isinstance(message_body, str):
            message_body = message_body.encode('utf-8')
        
        self._queues[queue_name].append(message_body)
        message_id = f"mem_{len(self._queues[queue_name])}"
        
        logger.debug(f"消息已发送到内存队列 {queue_name}, 消息ID: {message_id}")
        return message_id
    
    async def receive_message(self, queue_name: str, **kwargs) -> Optional[QueueMessage]:
        """从内存队列接收消息"""
        if queue_name not in self._queues or not self._queues[queue_name]:
            return None
        
        message_body = self._queues[queue_name].pop(0)
        message_id = f"mem_{hash(message_body)}"
        
        # 记录已处理的消息
        if queue_name not in self._processed_messages:
            self._processed_messages[queue_name] = []
        self._processed_messages[queue_name].append(message_id)
        
        return QueueMessage(
            id=message_id,
            queue=queue_name,
            body=message_body,
            attributes={"source": "memory"}
        )
    
    async def delete_message(self, queue_name: str, message_id: str, **kwargs) -> bool:
        """内存队列中删除消息"""
        # 内存队列中消息被消费后就自动删除了，这里不需要额外操作
        return True
    
    async def get_queue_length(self, queue_name: str) -> int:
        """获取内存队列长度"""
        return len(self._queues.get(queue_name, []))
    
    async def purge_queue(self, queue_name: str) -> bool:
        """清空内存队列"""
        if queue_name in self._queues:
            self._queues[queue_name] = []
            logger.info(f"内存队列 {queue_name} 已清空")
        return True


class MessageQueue:
    """消息队列管理器"""
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or get_queue_config()
        self._client: Optional[BaseQueueClient] = None
    
    @property
    def client(self) -> BaseQueueClient:
        """获取队列客户端"""
        if self._client is None:
            if self.config.queue_type == QueueType.REDIS:
                self._client = RedisQueueClient(self.config)
            elif self.config.queue_type == QueueType.MEMORY:
                self._client = MemoryQueueClient(self.config)
            else:
                raise ValueError(f"不支持的队列类型: {self.config.queue_type}")
        return self._client
    
    async def send(self, queue_name: str, message: Union[Message, Dict, str], **kwargs) -> str:
        """发送消息"""
        try:
            # 如果是Message对象，转换为字典
            if isinstance(message, Message):
                message_dict = message.dict()
                message_body = json.dumps(message_dict, ensure_ascii=False)
            elif isinstance(message, dict):
                message_body = json.dumps(message, ensure_ascii=False)
            else:
                message_body = str(message)
            
            return await self.client.send_message(queue_name, message_body, **kwargs)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            raise
    
    async def receive(self, queue_name: str, **kwargs) -> Optional[Message]:
        """接收消息"""
        try:
            queue_message = await self.client.receive_message(queue_name, **kwargs)
            if queue_message:
                # 解析消息体
                message_dict = json.loads(queue_message.body.decode('utf-8'))
                return Message(**message_dict)
            return None
        except Exception as e:
            logger.error(f"接收消息失败: {e}")
            return None
    
    async def ack(self, queue_name: str, message_id: str, **kwargs) -> bool:
        """确认消息处理完成"""
        return await self.client.delete_message(queue_name, message_id, **kwargs)
    
    async def queue_stats(self, queue_name: str) -> Dict[str, Any]:
        """获取队列统计信息"""
        length = await self.client.get_queue_length(queue_name)
        return {
            "queue_name": queue_name,
            "length": length,
            "queue_type": self.config.queue_type.value,
            "status": "active"
        }
    
    async def purge(self, queue_name: str) -> bool:
        """清空队列"""
        return await self.client.purge_queue(queue_name)


class TaskQueue(MessageQueue):
    """任务队列"""
    
    async def enqueue(self, task_name: str, *args, **kwargs) -> str:
        """入队任务"""
        task = Task(
            name=task_name,
            args=list(args),
            kwargs=kwargs
        )
        return await self.send("tasks", task.dict())
    
    async def dequeue(self) -> Optional[Task]:
        """出队任务"""
        return await self.receive("tasks")
    
    async def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务（注意：Redis队列不支持查看所有任务，只返回队列长度）"""
        # 在实际应用中，可能需要使用Redis的列表操作来查看所有任务
        # 这里简化处理，只返回空列表
        return []
    
    async def task_stats(self) -> Dict[str, Any]:
        """获取任务队列统计"""
        stats = await self.queue_stats("tasks")
        stats["queue_type"] = "task_queue"
        return stats