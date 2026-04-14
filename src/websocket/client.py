"""
WebSocket客户端和连接管理器
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket
from pydantic import ValidationError

from .models import (
    ConnectionInfo,
    RoomInfo,
    WebSocketMessage,
    MessageType,
    HeartbeatMessage,
    ErrorMessage,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_info: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # 用户ID -> 连接ID集合
        self.room_connections: Dict[str, Set[str]] = {}  # 房间ID -> 连接ID集合
        
    async def connect(self, websocket: WebSocket, connection_id: str = None):
        """建立WebSocket连接"""
        if connection_id is None:
            connection_id = str(uuid4())
        
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        # 创建连接信息
        self.connection_info[connection_id] = ConnectionInfo(
            connection_id=connection_id,
            connected_at=time.time()
        )
        
        logger.info(f"WebSocket连接建立: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """断开WebSocket连接"""
        if connection_id in self.active_connections:
            # 从用户连接中移除
            connection_info = self.connection_info.get(connection_id)
            if connection_info and connection_info.user_id:
                user_id = connection_info.user_id
                if user_id in self.user_connections:
                    self.user_connections[user_id].discard(connection_id)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
            
            # 从房间连接中移除
            for room_id, connections in self.room_connections.items():
                if connection_id in connections:
                    connections.discard(connection_id)
            
            # 清理连接记录
            del self.active_connections[connection_id]
            if connection_id in self.connection_info:
                del self.connection_info[connection_id]
            
            logger.info(f"WebSocket连接断开: {connection_id}")
    
    def authenticate(self, connection_id: str, user_id: str, user_info: Dict[str, Any] = None):
        """认证连接，关联用户ID"""
        if connection_id in self.connection_info:
            conn_info = self.connection_info[connection_id]
            conn_info.user_id = user_id
            
            if user_info:
                conn_info.metadata.update(user_info)
            
            # 更新用户连接映射
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            logger.info(f"连接认证: {connection_id} -> 用户 {user_id}")
            return True
        return False
    
    def join_room(self, connection_id: str, room_id: str):
        """加入房间"""
        if connection_id in self.connection_info:
            conn_info = self.connection_info[connection_id]
            if room_id not in conn_info.rooms:
                conn_info.rooms.append(room_id)
            
            # 更新房间连接映射
            if room_id not in self.room_connections:
                self.room_connections[room_id] = set()
            self.room_connections[room_id].add(connection_id)
            
            logger.info(f"连接 {connection_id} 加入房间 {room_id}")
            return True
        return False
    
    def leave_room(self, connection_id: str, room_id: str):
        """离开房间"""
        if connection_id in self.connection_info:
            conn_info = self.connection_info[connection_id]
            if room_id in conn_info.rooms:
                conn_info.rooms.remove(room_id)
            
            # 更新房间连接映射
            if room_id in self.room_connections and connection_id in self.room_connections[room_id]:
                self.room_connections[room_id].discard(connection_id)
                
                # 如果房间为空，清理房间
                if not self.room_connections[room_id]:
                    del self.room_connections[room_id]
            
            logger.info(f"连接 {connection_id} 离开房间 {room_id}")
            return True
        return False
    
    async def send_personal_message(self, message: WebSocketMessage, connection_id: str):
        """发送个人消息到指定连接"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message.dict())
                return True
            except Exception as e:
                logger.error(f"发送个人消息失败: {e}")
                return False
        return False
    
    async def send_user_message(self, message: WebSocketMessage, user_id: str):
        """发送消息给指定用户的所有连接"""
        if user_id in self.user_connections:
            sent_count = 0
            for connection_id in self.user_connections[user_id]:
                if await self.send_personal_message(message, connection_id):
                    sent_count += 1
            return sent_count > 0
        return False
    
    async def broadcast_to_room(self, message: WebSocketMessage, room_id: str, exclude_connection_id: str = None):
        """向房间内所有连接广播消息"""
        if room_id in self.room_connections:
            sent_count = 0
            for connection_id in self.room_connections[room_id]:
                if connection_id != exclude_connection_id:
                    if await self.send_personal_message(message, connection_id):
                        sent_count += 1
            logger.info(f"向房间 {room_id} 广播消息，发送给 {sent_count} 个连接")
            return sent_count
        return 0
    
    async def broadcast(self, message: WebSocketMessage, exclude_connection_id: str = None):
        """向所有连接广播消息"""
        sent_count = 0
        for connection_id, websocket in self.active_connections.items():
            if connection_id != exclude_connection_id:
                try:
                    await websocket.send_json(message.dict())
                    sent_count += 1
                except Exception as e:
                    logger.error(f"广播消息失败: {e}")
        logger.info(f"全局广播消息，发送给 {sent_count} 个连接")
        return sent_count
    
    def get_connection_count(self) -> int:
        """获取活动连接数"""
        return len(self.active_connections)
    
    def get_user_connection_count(self, user_id: str) -> int:
        """获取用户的活动连接数"""
        if user_id in self.user_connections:
            return len(self.user_connections[user_id])
        return 0
    
    def get_room_connection_count(self, room_id: str) -> int:
        """获取房间内的连接数"""
        if room_id in self.room_connections:
            return len(self.room_connections[room_id])
        return 0
    
    def get_connection_info(self, connection_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self.connection_info.get(connection_id)
    
    def update_activity(self, connection_id: str):
        """更新连接活动时间"""
        if connection_id in self.connection_info:
            self.connection_info[connection_id].last_active_at = time.time()


class WebSocketManager:
    """WebSocket管理器"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.rooms: Dict[str, RoomInfo] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self.inactive_timeout = 120  # 不活动超时（秒）
        
    async def handle_connection(self, websocket: WebSocket):
        """处理WebSocket连接"""
        connection_id = await self.connection_manager.connect(websocket)
        
        try:
            # 发送连接确认消息
            welcome_message = WebSocketMessage(
                type=MessageType.SYSTEM,
                content={
                    "message": "连接已建立",
                    "connection_id": connection_id,
                    "heartbeat_interval": self.heartbeat_interval
                }
            )
            await self.connection_manager.send_personal_message(welcome_message, connection_id)
            
            # 主消息循环
            while True:
                try:
                    # 接收消息
                    data = await websocket.receive_json(timeout=self.heartbeat_interval + 5)
                    
                    # 更新活动时间
                    self.connection_manager.update_activity(connection_id)
                    
                    # 处理消息
                    await self.handle_message(data, connection_id)
                    
                except asyncio.TimeoutError:
                    # 发送心跳
                    heartbeat = HeartbeatMessage(
                        connection_id=connection_id,
                        timestamp=time.time()
                    )
                    heartbeat_msg = WebSocketMessage(
                        type=MessageType.HEARTBEAT,
                        content=heartbeat.dict()
                    )
                    await self.connection_manager.send_personal_message(heartbeat_msg, connection_id)
                    
                except Exception as e:
                    if "1000" in str(e) or "1001" in str(e):  # 正常关闭
                        break
                    logger.error(f"处理消息异常: {e}")
                    error_msg = ErrorMessage(
                        code="message_error",
                        message="消息处理失败",
                        details={"error": str(e)}
                    )
                    error_ws_msg = WebSocketMessage(
                        type=MessageType.ERROR,
                        content=error_msg.dict()
                    )
                    await self.connection_manager.send_personal_message(error_ws_msg, connection_id)
        
        except Exception as e:
            logger.error(f"WebSocket连接处理异常: {e}")
        finally:
            # 清理连接
            self.connection_manager.disconnect(connection_id)
    
    async def handle_message(self, data: Dict[str, Any], connection_id: str):
        """处理接收到的消息"""
        try:
            # 验证消息格式
            message = WebSocketMessage(**data)
            
            # 根据消息类型处理
            if message.type == MessageType.TEXT:
                await self.handle_text_message(message, connection_id)
            elif message.type == MessageType.NOTIFICATION:
                await self.handle_notification_message(message, connection_id)
            elif message.type == MessageType.COMMAND:
                await self.handle_command_message(message, connection_id)
            elif message.type == MessageType.HEARTBEAT:
                await self.handle_heartbeat_message(message, connection_id)
            else:
                logger.warning(f"未知消息类型: {message.type}")
                
        except ValidationError as e:
            logger.error(f"消息验证失败: {e}")
            error_msg = ErrorMessage(
                code="validation_error",
                message="消息格式错误",
                details={"errors": e.errors()}
            )
            error_ws_msg = WebSocketMessage(
                type=MessageType.ERROR,
                content=error_msg.dict()
            )
            await self.connection_manager.send_personal_message(error_ws_msg, connection_id)
    
    async def handle_text_message(self, message: WebSocketMessage, connection_id: str):
        """处理文本消息"""
        conn_info = self.connection_manager.get_connection_info(connection_id)
        
        # 如果是房间消息
        if message.room_id:
            # 检查是否在房间中
            if message.room_id in conn_info.rooms:
                # 广播给房间内的其他用户
                await self.connection_manager.broadcast_to_room(
                    message,
                    message.room_id,
                    exclude_connection_id=connection_id
                )
            else:
                error_msg = ErrorMessage(
                    code="not_in_room",
                    message="你不在该房间中",
                    details={"room_id": message.room_id}
                )
                error_ws_msg = WebSocketMessage(
                    type=MessageType.ERROR,
                    content=error_msg.dict()
                )
                await self.connection_manager.send_personal_message(error_ws_msg, connection_id)
        
        # 如果是私聊消息
        elif message.receiver_id:
            await self.connection_manager.send_user_message(message, message.receiver_id)
    
    async def handle_notification_message(self, message: WebSocketMessage, connection_id: str):
        """处理通知消息"""
        # 这里可以添加通知处理逻辑
        logger.info(f"收到通知消息: {message.content}")
    
    async def handle_command_message(self, message: WebSocketMessage, connection_id: str):
        """处理命令消息"""
        command = message.content.get("command")
        
        if command == "join_room":
            room_id = message.content.get("room_id")
            if room_id:
                success = self.connection_manager.join_room(connection_id, room_id)
                response = WebSocketMessage(
                    type=MessageType.SYSTEM,
                    content={
                        "command": "join_room",
                        "success": success,
                        "room_id": room_id
                    }
                )
                await self.connection_manager.send_personal_message(response, connection_id)
        
        elif command == "leave_room":
            room_id = message.content.get("room_id")
            if room_id:
                success = self.connection_manager.leave_room(connection_id, room_id)
                response = WebSocketMessage(
                    type=MessageType.SYSTEM,
                    content={
                        "command": "leave_room",
                        "success": success,
                        "room_id": room_id
                    }
                )
                await self.connection_manager.send_personal_message(response, connection_id)
        
        elif command == "authenticate":
            user_id = message.content.get("user_id")
            if user_id:
                success = self.connection_manager.authenticate(
                    connection_id,
                    user_id,
                    message.content.get("user_info")
                )
                response = WebSocketMessage(
                    type=MessageType.SYSTEM,
                    content={
                        "command": "authenticate",
                        "success": success,
                        "user_id": user_id
                    }
                )
                await self.connection_manager.send_personal_message(response, connection_id)
    
    async def handle_heartbeat_message(self, message: WebSocketMessage, connection_id: str):
        """处理心跳消息"""
        # 更新活动时间
        self.connection_manager.update_activity(connection_id)
        
        # 回复心跳确认
        heartbeat_ack = WebSocketMessage(
            type=MessageType.HEARTBEAT,
            content={
                "timestamp": time.time(),
                "status": "ack"
            }
        )
        await self.connection_manager.send_personal_message(heartbeat_ack, connection_id)
    
    def create_room(self, room_id: str, name: str = None, creator_id: str = None, is_private: bool = False) -> RoomInfo:
        """创建房间"""
        room_info = RoomInfo(
            room_id=room_id,
            name=name,
            creator_id=creator_id,
            is_private=is_private,
            created_at=time.time()
        )
        self.rooms[room_id] = room_info
        logger.info(f"房间创建: {room_id}")
        return room_info
    
    def delete_room(self, room_id: str) -> bool:
        """删除房间"""
        if room_id in self.rooms:
            # 断开房间内所有连接
            if room_id in self.connection_manager.room_connections:
                for connection_id in list(self.connection_manager.room_connections[room_id]):
                    self.connection_manager.leave_room(connection_id, room_id)
            
            del self.rooms[room_id]
            logger.info(f"房间删除: {room_id}")
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取WebSocket管理器统计信息"""
        return {
            "total_connections": self.connection_manager.get_connection_count(),
            "total_rooms": len(self.rooms),
            "total_users": len(self.connection_manager.user_connections),
            "rooms": {
                room_id: {
                    "name": room_info.name,
                    "member_count": len(room_info.member_ids),
                    "connection_count": self.connection_manager.get_room_connection_count(room_id),
                    "is_private": room_info.is_private
                }
                for room_id, room_info in self.rooms.items()
            }
        }


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()