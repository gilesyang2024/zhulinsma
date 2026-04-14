"""
WebSocket数据模型定义
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    NOTIFICATION = "notification"
    COMMAND = "command"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """消息状态"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""
    id: UUID = Field(default_factory=uuid4)
    type: MessageType = MessageType.TEXT
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    room_id: Optional[str] = None
    content: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: MessageStatus = MessageStatus.SENT
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class ConnectionInfo(BaseModel):
    """连接信息"""
    connection_id: str
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    rooms: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoomInfo(BaseModel):
    """房间信息"""
    room_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    creator_id: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list)
    connection_ids: List[str] = Field(default_factory=list)
    is_private: bool = False
    max_members: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """聊天消息"""
    id: UUID = Field(default_factory=uuid4)
    room_id: str
    sender_id: str
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    edited: bool = False
    edited_at: Optional[datetime] = None
    reply_to: Optional[UUID] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Notification(BaseModel):
    """通知消息"""
    id: UUID = Field(default_factory=uuid4)
    user_id: str
    title: str
    content: str
    notification_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    priority: str = "normal"  # low, normal, high, urgent


class HeartbeatMessage(BaseModel):
    """心跳消息"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    connection_id: str
    latency_ms: Optional[int] = None


class ErrorMessage(BaseModel):
    """错误消息"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)