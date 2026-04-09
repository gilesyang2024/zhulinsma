"""
WebSocket网关 - 实时数据推送服务器
支持连接管理、消息路由、流量控制
"""
import asyncio
import logging
import weakref
import time
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json

import websockets
from websockets.server import WebSocketServerProtocol

from ..protocol import (
    MessageParser, SubscribeRequest, 
    MessageType, ChannelType
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    """客户端会话"""
    client_id: str
    websocket: WebSocketServerProtocol
    subscribed_stocks: Set[str] = field(default_factory=set)
    subscribed_channels: Set[str] = field(default_factory=set)
    alert_config: Dict[str, float] = field(default_factory=dict)
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    is_authenticated: bool = False
    
    def is_alive(self, timeout: float = 30.0) -> bool:
        """检查连接是否存活"""
        return (time.time() - self.last_heartbeat) < timeout


class ConnectionManager:
    """连接管理器 - 管理所有WebSocket连接"""
    
    def __init__(self):
        # 使用弱引用避免内存泄漏
        self._clients: weakref.WeakSet = set()
        self._sessions: Dict[str, ClientSession] = {}
        self._stock_subscriptions: Dict[str, Set[str]] = {}  # 股票代码 -> 客户端ID集合
        
    def add_client(self, session: ClientSession):
        """添加客户端"""
        self._clients.add(session.websocket)
        self._sessions[session.client_id] = session
        logger.info(f"客户端连接: {session.client_id}, 当前连接数: {len(self._sessions)}")
        
    def remove_client(self, client_id: str):
        """移除客户端"""
        if client_id in self._sessions:
            session = self._sessions.pop(client_id)
            self._clients.discard(session.websocket)
            
            # 清理股票订阅
            for stock_code in session.subscribed_stocks:
                if stock_code in self._stock_subscriptions:
                    self._stock_subscriptions[stock_code].discard(client_id)
                    if not self._stock_subscriptions[stock_code]:
                        del self._stock_subscriptions[stock_code]
            
            logger.info(f"客户端断开: {client_id}, 剩余连接数: {len(self._sessions)}")
    
    def subscribe_stock(self, client_id: str, stock_code: str):
        """订阅股票"""
        if client_id not in self._sessions:
            return
            
        session = self._sessions[client_id]
        session.subscribed_stocks.add(stock_code)
        
        if stock_code not in self._stock_subscriptions:
            self._stock_subscriptions[stock_code] = set()
        self._stock_subscriptions[stock_code].add(client_id)
        
        logger.debug(f"客户端 {client_id} 订阅股票 {stock_code}")
    
    def unsubscribe_stock(self, client_id: str, stock_code: str):
        """取消订阅股票"""
        if client_id not in self._sessions:
            return
            
        session = self._sessions[client_id]
        session.subscribed_stocks.discard(stock_code)
        
        if stock_code in self._stock_subscriptions:
            self._stock_subscriptions[stock_code].discard(client_id)
            if not self._stock_subscriptions[stock_code]:
                del self._stock_subscriptions[stock_code]
    
    def get_subscribers(self, stock_code: str) -> Set[str]:
        """获取股票订阅者"""
        return self._stock_subscriptions.get(stock_code, set())
    
    def get_all_sessions(self) -> Dict[str, ClientSession]:
        """获取所有会话"""
        return self._sessions.copy()
    
    def get_connection_count(self) -> int:
        """获取连接数"""
        return len(self._sessions)
    
    def cleanup_dead_connections(self, timeout: float = 30.0):
        """清理死连接"""
        dead_clients = [
            client_id for client_id, session in self._sessions.items()
            if not session.is_alive(timeout)
        ]
        for client_id in dead_clients:
            self.remove_client(client_id)
        return len(dead_clients)


class RateLimiter:
    """流量控制器"""
    
    def __init__(self, max_messages_per_second: int = 100, max_connections: int = 100):
        self.max_messages_per_second = max_messages_per_second
        self.max_connections = max_connections
        self._message_counts: Dict[str, int] = {}
        self._last_reset = time.time()
        
    def check_rate_limit(self, client_id: str) -> bool:
        """检查是否超过速率限制"""
        now = time.time()
        
        # 每秒重置计数器
        if now - self._last_reset > 1.0:
            self._message_counts.clear()
            self._last_reset = now
            
        count = self._message_counts.get(client_id, 0)
        if count >= self.max_messages_per_second:
            return False
            
        self._message_counts[client_id] = count + 1
        return True
    
    def check_connection_limit(self, current_count: int) -> bool:
        """检查连接数限制"""
        return current_count < self.max_connections


class RealtimeGateway:
    """WebSocket实时数据推送网关"""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        heartbeat_interval: float = 15.0,
        connection_timeout: float = 30.0
    ):
        self.host = host
        self.port = port
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        
        # 核心组件
        self.connection_manager = ConnectionManager()
        self.rate_limiter = RateLimiter()
        
        # 回调函数
        self.on_subscribe: Optional[Callable] = None
        self.on_unsubscribe: Optional[Callable] = None
        self.on_message: Optional[Callable] = None
        
        # 任务
        self._server = None
        self._heartbeat_task = None
        self._cleanup_task = None
        self._running = False
        
        # 客户端ID生成器
        self._client_id_counter = 0
        
    def _generate_client_id(self) -> str:
        """生成客户端ID"""
        self._client_id_counter += 1
        return f"client_{self._client_id_counter}_{int(time.time() * 1000)}"
    
    async def start(self):
        """启动WebSocket服务器"""
        if self._running:
            logger.warning("服务器已在运行")
            return
            
        self._running = True
        
        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # 检查连接数限制
        if not self.rate_limiter.check_connection_limit(0):
            logger.error("连接数已达上限")
            return
            
        # 启动WebSocket服务器
        try:
            self._server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=None  # 我们自己实现心跳
            )
            logger.info(f"WebSocket服务器启动: ws://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            self._running = False
            raise
    
    async def stop(self):
        """停止WebSocket服务器"""
        self._running = False
        
        # 取消后台任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        # 关闭服务器
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            
        logger.info("WebSocket服务器已停止")
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """处理客户端连接"""
        client_id = self._generate_client_id()
        session = ClientSession(client_id=client_id, websocket=websocket)
        self.connection_manager.add_client(session)
        
        # 发送连接成功消息
        await websocket.send(MessageParser.create_connected())
        
        try:
            # 处理消息
            async for message in websocket:
                if not self._running:
                    break
                    
                # 速率限制检查
                if not self.rate_limiter.check_rate_limit(client_id):
                    await websocket.send(MessageParser.create_error(429, "Rate limit exceeded"))
                    continue
                    
                await self._process_message(session, message)
                
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"客户端断开连接: {client_id}, 原因: {e.reason}")
        except Exception as e:
            logger.error(f"处理客户端消息出错: {e}")
        finally:
            self.connection_manager.remove_client(client_id)
    
    async def _process_message(self, session: ClientSession, message: str):
        """处理客户端消息"""
        try:
            data = MessageParser.parse(message)
            msg_type = data.get("type")
            
            if msg_type == MessageType.SUBSCRIBE.value:
                await self._handle_subscribe(session, data)
                
            elif msg_type == MessageType.UNSUBSCRIBE.value:
                await self._handle_unsubscribe(session, data)
                
            elif msg_type == MessageType.HEARTBEAT.value:
                session.last_heartbeat = time.time()
                await session.websocket.send(MessageParser.create_heartbeat())
                
            elif msg_type == MessageType.AUTH.value:
                # 简单认证（可以扩展）
                session.is_authenticated = True
                
            else:
                logger.warning(f"未知消息类型: {msg_type}")
                
        except Exception as e:
            logger.error(f"处理消息出错: {e}")
            await session.websocket.send(MessageParser.create_error(500, str(e)))
    
    async def _handle_subscribe(self, session: ClientSession, data: dict):
        """处理订阅请求"""
        try:
            # 解析订阅请求
            stock_codes = data.get("stock_codes", [])
            channels = data.get("channels", ["realtime"])
            alerts = data.get("alerts", {})
            
            # 保存预警配置
            session.alert_config = alerts
            session.subscribed_channels = set(channels)
            
            # 订阅股票
            for stock_code in stock_codes:
                self.connection_manager.subscribe_stock(session.client_id, stock_code)
            
            # 触发回调
            if self.on_subscribe:
                await self.on_subscribe(session.client_id, stock_codes, alerts)
                
            # 发送确认
            await session.websocket.send(json.dumps({
                "type": "subscribe_ack",
                "stock_codes": stock_codes,
                "channels": channels
            }))
            
            logger.info(f"客户端 {session.client_id} 订阅: {stock_codes}")
            
        except Exception as e:
            logger.error(f"处理订阅请求出错: {e}")
    
    async def _handle_unsubscribe(self, session: ClientSession, data: dict):
        """处理取消订阅请求"""
        stock_codes = data.get("stock_codes", [])
        
        for stock_code in stock_codes:
            self.connection_manager.unsubscribe_stock(session.client_id, stock_code)
            
        # 触发回调
        if self.on_unsubscribe:
            await self.on_unsubscribe(session.client_id, stock_codes)
            
        await session.websocket.send(json.dumps({
            "type": "unsubscribe_ack",
            "stock_codes": stock_codes
        }))
    
    async def _heartbeat_loop(self):
        """心跳检测循环"""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # 检查所有连接
                for client_id, session in self.connection_manager.get_all_sessions().items():
                    if not session.is_alive(self.connection_timeout):
                        logger.warning(f"客户端超时: {client_id}")
                        try:
                            await session.websocket.close(1008, "Heartbeat timeout")
                        except:
                            pass
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳检测出错: {e}")
    
    async def _cleanup_loop(self):
        """清理死连接循环"""
        while self._running:
            try:
                await asyncio.sleep(10)
                dead_count = self.connection_manager.cleanup_dead_connections()
                if dead_count > 0:
                    logger.info(f"清理了 {dead_count} 个死连接")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
    
    async def push_realtime_data(self, stock_code: str, data: dict):
        """推送实时数据到订阅者"""
        message = MessageParser.create_realtime(stock_code, data)
        
        subscribers = self.connection_manager.get_subscribers(stock_code)
        
        for client_id in subscribers:
            session = self.connection_manager.get_all_sessions().get(client_id)
            if session and session.websocket.open:
                try:
                    await session.websocket.send(message)
                except Exception as e:
                    logger.error(f"推送数据到 {client_id} 失败: {e}")
    
    async def push_alert(self, stock_code: str, alert_data: dict):
        """推送预警到订阅者"""
        message = MessageParser.create_alert(alert_data)
        
        subscribers = self.connection_manager.get_subscribers(stock_code)
        
        for client_id in subscribers:
            session = self.connection_manager.get_all_sessions().get(client_id)
            if session and session.websocket.open:
                # 检查是否配置了该类型预警
                alert_type = alert_data.get("alert_type")
                if session.alert_config.get(alert_type):
                    try:
                        await session.websocket.send(message)
                    except Exception as e:
                        logger.error(f"推送预警到 {client_id} 失败: {e}")
    
    def get_status(self) -> dict:
        """获取服务器状态"""
        uptime = 0
        if self._server and hasattr(self._server, 'start_time'):
            uptime = time.time() - self._server.start_time
        return {
            "running": self._running,
            "connections": self.connection_manager.get_connection_count(),
            "subscriptions": len(self.connection_manager._stock_subscriptions),
            "uptime": uptime
        }


# 导出
__all__ = ['RealtimeGateway', 'ClientSession', 'ConnectionManager', 'RateLimiter']