"""
WebSocket API接口
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse

from .client import websocket_manager
from .models import (
    RoomInfo,
    ConnectionInfo,
    WebSocketMessage,
    MessageType,
    ErrorMessage,
)

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = logging.getLogger(__name__)


# WebSocket测试页面
@router.get("/test", response_class=HTMLResponse)
async def websocket_test_page():
    """WebSocket测试页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>竹林司马 - WebSocket测试</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .container {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .connection-panel {
                background: #f5f5f5;
                padding: 15px;
                border-radius: 8px;
            }
            .message-panel {
                background: #fff;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
            }
            .messages {
                height: 300px;
                overflow-y: auto;
                border: 1px solid #ddd;
                padding: 10px;
                margin-bottom: 10px;
                background: #f9f9f9;
            }
            .message {
                margin-bottom: 8px;
                padding: 8px;
                background: white;
                border-radius: 4px;
                border-left: 4px solid #007bff;
            }
            .system-message {
                border-left-color: #28a745;
                background: #e8f5e8;
            }
            .error-message {
                border-left-color: #dc3545;
                background: #f8d7da;
            }
            .input-group {
                display: flex;
                gap: 10px;
            }
            input, select, button {
                padding: 8px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            input[type="text"] {
                flex: 1;
            }
            button {
                background: #007bff;
                color: white;
                border: none;
                cursor: pointer;
            }
            button:hover {
                background: #0056b3;
            }
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            .status {
                margin-top: 10px;
                padding: 10px;
                border-radius: 4px;
                background: #e7f3ff;
            }
            .connected {
                background: #d4edda;
            }
            .disconnected {
                background: #f8d7da;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>竹林司马 - WebSocket实时通信测试</h1>
            
            <div class="connection-panel">
                <h3>连接控制</h3>
                <div class="input-group">
                    <button id="connectBtn" onclick="connectWebSocket()">连接</button>
                    <button id="disconnectBtn" onclick="disconnectWebSocket()" disabled>断开</button>
                    <input type="text" id="userId" placeholder="用户ID (可选)">
                    <button onclick="authenticate()">认证</button>
                </div>
                <div id="connectionStatus" class="status disconnected">
                    状态: 未连接
                </div>
            </div>
            
            <div class="connection-panel">
                <h3>房间管理</h3>
                <div class="input-group">
                    <input type="text" id="roomId" placeholder="房间ID" value="general">
                    <button onclick="joinRoom()">加入房间</button>
                    <button onclick="leaveRoom()">离开房间</button>
                    <button onclick="createRoom()">创建房间</button>
                </div>
                <div id="roomStatus">
                    当前房间: 无
                </div>
            </div>
            
            <div class="message-panel">
                <h3>消息通信</h3>
                <div id="messages" class="messages"></div>
                <div class="input-group">
                    <select id="messageType">
                        <option value="text">文本</option>
                        <option value="notification">通知</option>
                        <option value="command">命令</option>
                    </select>
                    <input type="text" id="messageInput" placeholder="输入消息内容">
                    <button onclick="sendMessage()">发送</button>
                    <button onclick="sendHeartbeat()">心跳</button>
                </div>
                <div class="input-group">
                    <input type="text" id="receiverId" placeholder="接收者ID (私聊)">
                    <input type="text" id="targetRoomId" placeholder="目标房间ID">
                </div>
            </div>
            
            <div class="connection-panel">
                <h3>系统信息</h3>
                <div id="systemInfo">
                    连接数: 0 | 房间数: 0 | 用户数: 0
                </div>
                <button onclick="getStats()">刷新统计</button>
            </div>
        </div>
        
        <script>
            let ws = null;
            let connectionId = null;
            let currentRoom = null;
            
            function connectWebSocket() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    alert('已经连接');
                    return;
                }
                
                // 连接WebSocket
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/connect`;
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    updateStatus('connected', '已连接');
                    document.getElementById('connectBtn').disabled = true;
                    document.getElementById('disconnectBtn').disabled = false;
                    addMessage('系统', 'WebSocket连接已建立', 'system');
                };
                
                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        handleWebSocketMessage(data);
                    } catch (e) {
                        console.error('解析消息失败:', e);
                    }
                };
                
                ws.onerror = function(event) {
                    console.error('WebSocket错误:', event);
                    addMessage('系统', '连接错误', 'error');
                };
                
                ws.onclose = function(event) {
                    updateStatus('disconnected', '连接已断开');
                    document.getElementById('connectBtn').disabled = false;
                    document.getElementById('disconnectBtn').disabled = true;
                    addMessage('系统', '连接已关闭', 'system');
                    ws = null;
                    connectionId = null;
                    currentRoom = null;
                };
            }
            
            function disconnectWebSocket() {
                if (ws) {
                    ws.close();
                }
            }
            
            function authenticate() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('请先连接WebSocket');
                    return;
                }
                
                const userId = document.getElementById('userId').value || 'test_user_' + Date.now();
                const message = {
                    type: 'command',
                    content: {
                        command: 'authenticate',
                        user_id: userId,
                        user_info: {
                            username: '测试用户'
                        }
                    }
                };
                
                ws.send(JSON.stringify(message));
            }
            
            function joinRoom() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('请先连接WebSocket');
                    return;
                }
                
                const roomId = document.getElementById('roomId').value;
                if (!roomId) {
                    alert('请输入房间ID');
                    return;
                }
                
                const message = {
                    type: 'command',
                    content: {
                        command: 'join_room',
                        room_id: roomId
                    }
                };
                
                ws.send(JSON.stringify(message));
                currentRoom = roomId;
                document.getElementById('roomStatus').textContent = `当前房间: ${roomId}`;
            }
            
            function leaveRoom() {
                if (!ws || ws.readyState !== WebSocket.OPEN || !currentRoom) {
                    alert('未加入任何房间');
                    return;
                }
                
                const message = {
                    type: 'command',
                    content: {
                        command: 'leave_room',
                        room_id: currentRoom
                    }
                };
                
                ws.send(JSON.stringify(message));
                currentRoom = null;
                document.getElementById('roomStatus').textContent = '当前房间: 无';
            }
            
            function createRoom() {
                const roomId = document.getElementById('roomId').value;
                if (!roomId) {
                    alert('请输入房间ID');
                    return;
                }
                
                // 发送创建房间命令
                const message = {
                    type: 'command',
                    content: {
                        command: 'join_room',
                        room_id: roomId
                    }
                };
                
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify(message));
                    currentRoom = roomId;
                    document.getElementById('roomStatus').textContent = `当前房间: ${roomId}`;
                }
            }
            
            function sendMessage() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('请先连接WebSocket');
                    return;
                }
                
                const messageInput = document.getElementById('messageInput');
                const messageType = document.getElementById('messageType').value;
                const receiverId = document.getElementById('receiverId').value;
                const targetRoomId = document.getElementById('targetRoomId').value;
                
                if (!messageInput.value.trim()) {
                    alert('请输入消息内容');
                    return;
                }
                
                const message = {
                    type: messageType,
                    content: messageInput.value,
                    receiver_id: receiverId || null,
                    room_id: targetRoomId || currentRoom || null
                };
                
                ws.send(JSON.stringify(message));
                addMessage('我', messageInput.value, 'text');
                messageInput.value = '';
            }
            
            function sendHeartbeat() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    alert('请先连接WebSocket');
                    return;
                }
                
                const message = {
                    type: 'heartbeat',
                    content: {
                        timestamp: Date.now()
                    }
                };
                
                ws.send(JSON.stringify(message));
            }
            
            function getStats() {
                fetch('/api/v1/ws/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('systemInfo').textContent = 
                            `连接数: ${data.total_connections} | 房间数: ${data.total_rooms} | 用户数: ${data.total_users}`;
                    })
                    .catch(error => {
                        console.error('获取统计失败:', error);
                    });
            }
            
            function handleWebSocketMessage(data) {
                console.log('收到消息:', data);
                
                const sender = data.sender_id || '系统';
                const messageType = data.type || 'text';
                
                if (messageType === 'system') {
                    addMessage(sender, JSON.stringify(data.content), 'system');
                    
                    // 处理连接确认
                    if (data.content && data.content.connection_id) {
                        connectionId = data.content.connection_id;
                        updateStatus('connected', `已连接 (ID: ${connectionId})`);
                    }
                } 
                else if (messageType === 'error') {
                    addMessage(sender, data.content.message || '错误', 'error');
                }
                else if (messageType === 'heartbeat') {
                    addMessage(sender, '心跳确认', 'system');
                }
                else {
                    addMessage(sender, data.content, 'text');
                }
            }
            
            function addMessage(sender, content, type) {
                const messagesDiv = document.getElementById('messages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}-message`;
                
                const time = new Date().toLocaleTimeString();
                messageDiv.innerHTML = `<strong>${sender}</strong> [${time}]: ${content}`;
                
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function updateStatus(statusClass, message) {
                const statusDiv = document.getElementById('connectionStatus');
                statusDiv.className = `status ${statusClass}`;
                statusDiv.textContent = `状态: ${message}`;
            }
            
            // 页面加载时自动获取统计
            window.onload = function() {
                getStats();
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# WebSocket连接端点
@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    await websocket_manager.handle_connection(websocket)


# REST API端点
@router.get("/stats", response_model=Dict[str, Any])
async def get_websocket_stats():
    """获取WebSocket统计信息"""
    try:
        stats = websocket_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"获取WebSocket统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计失败: {str(e)}"
        )


@router.get("/connections", response_model=List[Dict[str, Any]])
async def get_connections(
    user_id: Optional[str] = Query(None, description="按用户ID过滤"),
    room_id: Optional[str] = Query(None, description="按房间ID过滤")
):
    """获取连接列表"""
    try:
        connections = []
        
        for conn_id, conn_info in websocket_manager.connection_manager.connection_info.items():
            # 应用过滤器
            if user_id and conn_info.user_id != user_id:
                continue
            if room_id and room_id not in conn_info.rooms:
                continue
            
            connections.append({
                "connection_id": conn_id,
                "user_id": conn_info.user_id,
                "rooms": conn_info.rooms,
                "connected_at": conn_info.connected_at,
                "last_active_at": conn_info.last_active_at,
                "is_active": conn_id in websocket_manager.connection_manager.active_connections
            })
        
        return connections
    except Exception as e:
        logger.error(f"获取连接列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取连接列表失败: {str(e)}"
        )


@router.get("/rooms", response_model=List[Dict[str, Any]])
async def get_rooms(
    is_private: Optional[bool] = Query(None, description="按隐私状态过滤")
):
    """获取房间列表"""
    try:
        rooms = []
        
        for room_id, room_info in websocket_manager.rooms.items():
            # 应用过滤器
            if is_private is not None and room_info.is_private != is_private:
                continue
            
            connection_count = websocket_manager.connection_manager.get_room_connection_count(room_id)
            
            rooms.append({
                "room_id": room_id,
                "name": room_info.name,
                "creator_id": room_info.creator_id,
                "is_private": room_info.is_private,
                "created_at": room_info.created_at,
                "member_count": len(room_info.member_ids),
                "connection_count": connection_count,
                "max_members": room_info.max_members
            })
        
        return rooms
    except Exception as e:
        logger.error(f"获取房间列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取房间列表失败: {str(e)}"
        )


@router.post("/rooms", response_model=Dict[str, Any])
async def create_room(
    room_id: str,
    name: Optional[str] = None,
    creator_id: Optional[str] = None,
    is_private: bool = False,
    max_members: Optional[int] = None
):
    """创建房间"""
    try:
        room_info = websocket_manager.create_room(room_id, name, creator_id, is_private)
        
        # 设置最大成员数
        if max_members:
            room_info.max_members = max_members
        
        return {
            "success": True,
            "room_id": room_id,
            "name": name,
            "message": "房间创建成功"
        }
    except Exception as e:
        logger.error(f"创建房间失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建房间失败: {str(e)}"
        )


@router.delete("/rooms/{room_id}", response_model=Dict[str, Any])
async def delete_room(room_id: str):
    """删除房间"""
    try:
        success = websocket_manager.delete_room(room_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="房间不存在"
            )
        
        return {
            "success": True,
            "message": f"房间 {room_id} 已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除房间失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除房间失败: {str(e)}"
        )


@router.post("/broadcast", response_model=Dict[str, Any])
async def broadcast_message(
    content: str,
    message_type: MessageType = MessageType.TEXT,
    exclude_connection_id: Optional[str] = None
):
    """广播消息到所有连接"""
    try:
        message = WebSocketMessage(
            type=message_type,
            content=content,
            sender_id="system"
        )
        
        sent_count = await websocket_manager.connection_manager.broadcast(
            message,
            exclude_connection_id=exclude_connection_id
        )
        
        return {
            "success": True,
            "sent_count": sent_count,
            "message": f"消息已广播给 {sent_count} 个连接"
        }
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"广播消息失败: {str(e)}"
        )


@router.post("/rooms/{room_id}/broadcast", response_model=Dict[str, Any])
async def broadcast_to_room(
    room_id: str,
    content: str,
    message_type: MessageType = MessageType.TEXT,
    exclude_connection_id: Optional[str] = None
):
    """广播消息到指定房间"""
    try:
        if room_id not in websocket_manager.rooms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="房间不存在"
            )
        
        message = WebSocketMessage(
            type=message_type,
            content=content,
            sender_id="system",
            room_id=room_id
        )
        
        sent_count = await websocket_manager.connection_manager.broadcast_to_room(
            message,
            room_id,
            exclude_connection_id=exclude_connection_id
        )
        
        return {
            "success": True,
            "sent_count": sent_count,
            "message": f"消息已广播给房间 {room_id} 的 {sent_count} 个连接"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"广播房间消息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"广播房间消息失败: {str(e)}"
        )


@router.post("/users/{user_id}/send", response_model=Dict[str, Any])
async def send_to_user(
    user_id: str,
    content: str,
    message_type: MessageType = MessageType.TEXT
):
    """发送消息给指定用户"""
    try:
        message = WebSocketMessage(
            type=message_type,
            content=content,
            sender_id="system",
            receiver_id=user_id
        )
        
        success = await websocket_manager.connection_manager.send_user_message(
            message,
            user_id
        )
        
        return {
            "success": success,
            "message": f"消息已发送给用户 {user_id}" if success else f"用户 {user_id} 不在线"
        }
    except Exception as e:
        logger.error(f"发送用户消息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送用户消息失败: {str(e)}"
        )