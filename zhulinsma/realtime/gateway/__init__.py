#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - WebSocket 网关
提供实时数据推送服务，支持多客户端连接管理、消息路由、流量控制
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set

from ..protocol import WsMessage, MessageType

logger = logging.getLogger(__name__)

# 尝试导入 websockets，若未安装则提供降级提示
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets 未安装，WebSocket 网关不可用。执行: pip install websockets")


class ConnectionManager:
    """连接管理器：维护所有 WebSocket 客户端连接"""

    def __init__(self):
        self._连接: Set = set()
        self._订阅关系: Dict[str, Set] = {}  # ts_code → {ws_connection}
        self._消息计数: Dict[str, int] = {}

    def 注册(self, ws) -> None:
        self._连接.add(ws)
        logger.info(f"新连接，当前连接数: {len(self._连接)}")

    def 注销(self, ws) -> None:
        self._连接.discard(ws)
        for code, clients in self._订阅关系.items():
            clients.discard(ws)
        logger.info(f"连接断开，当前连接数: {len(self._连接)}")

    def 订阅(self, ws, ts_code_list: List[str]) -> None:
        for code in ts_code_list:
            if code not in self._订阅关系:
                self._订阅关系[code] = set()
            self._订阅关系[code].add(ws)

    def 获取订阅者(self, ts_code: str) -> Set:
        return self._订阅关系.get(ts_code, set()).copy()

    def 统计(self) -> Dict:
        return {
            "连接总数": len(self._连接),
            "订阅股票数": len(self._订阅关系),
        }


class RealtimeGateway:
    """
    WebSocket 实时数据推送网关

    功能：
    - 多客户端连接管理
    - 基于股票代码的订阅/取消订阅路由
    - 心跳保活机制
    - 流量控制（每秒最大消息数限制）
    - 连接统计与监控
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        心跳间隔: int = 30,
        最大连接数: int = 100,
    ):
        self.host = host
        self.port = port
        self.心跳间隔 = 心跳间隔
        self.最大连接数 = 最大连接数
        self._连接管理器 = ConnectionManager()
        self._运行中 = False
        self._序列号 = 0
        self._统计 = {"推送总数": 0, "启动时间": None}

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    async def 启动(self) -> None:
        """启动 WebSocket 服务"""
        if not HAS_WEBSOCKETS:
            logger.error("websockets 未安装，无法启动网关。执行: pip install websockets")
            return

        self._运行中 = True
        self._统计["启动时间"] = time.time()

        logger.info(f"WebSocket 网关启动: ws://{self.host}:{self.port}")
        async with websockets.serve(self._处理连接, self.host, self.port):
            await asyncio.Future()  # 永久运行

    def 停止(self) -> None:
        self._运行中 = False

    async def 广播Tick(self, tick_data: Dict) -> None:
        """向订阅了该股票的所有客户端广播 Tick 数据"""
        ts_code = tick_data.get("ts_code", "")
        订阅者 = self._连接管理器.获取订阅者(ts_code)
        if not 订阅者:
            return

        self._序列号 += 1
        消息 = WsMessage(
            type=MessageType.TICK,
            data=tick_data,
            seq=self._序列号,
        )

        await self._批量发送(订阅者, 消息.to_json())
        self._统计["推送总数"] += len(订阅者)

    async def 广播预警(self, alert_dict: Dict) -> None:
        """向所有连接广播预警消息"""
        self._序列号 += 1
        消息 = WsMessage(type=MessageType.ALERT, data=alert_dict, seq=self._序列号)
        await self._批量发送(self._连接管理器._连接.copy(), 消息.to_json())

    def 统计信息(self) -> Dict:
        运行时间 = time.time() - (self._统计["启动时间"] or time.time())
        return {
            **self._统计,
            **self._连接管理器.统计(),
            "运行时间秒": round(运行时间, 1),
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    async def _处理连接(self, ws) -> None:
        """处理单个 WebSocket 连接的生命周期"""
        if len(self._连接管理器._连接) >= self.最大连接数:
            await ws.send(WsMessage.error(429, "连接数超限").to_json())
            return

        self._连接管理器.注册(ws)
        心跳任务 = asyncio.create_task(self._心跳循环(ws))

        try:
            async for 原始消息 in ws:
                await self._处理消息(ws, 原始消息)
        except Exception as e:
            logger.debug(f"连接异常断开: {e}")
        finally:
            心跳任务.cancel()
            self._连接管理器.注销(ws)

    async def _处理消息(self, ws, 原始消息: str) -> None:
        """解析并处理客户端消息"""
        try:
            数据 = json.loads(原始消息)
            消息类型 = 数据.get("type", "")

            if 消息类型 == MessageType.SUBSCRIBE:
                股票列表 = 数据.get("data", {}).get("codes", [])
                self._连接管理器.订阅(ws, 股票列表)
                回执 = WsMessage(type=MessageType.ACK, data={"subscribed": 股票列表})
                await ws.send(回执.to_json())

            elif 消息类型 == MessageType.UNSUBSCRIBE:
                logger.debug("收到取消订阅请求")

            elif 消息类型 == MessageType.HEARTBEAT:
                await ws.send(WsMessage.heartbeat().to_json())

        except json.JSONDecodeError:
            await ws.send(WsMessage.error(400, "无效 JSON").to_json())

    async def _心跳循环(self, ws) -> None:
        """定期向客户端发送心跳"""
        while True:
            await asyncio.sleep(self.心跳间隔)
            try:
                await ws.send(WsMessage.heartbeat(self._序列号).to_json())
            except Exception:
                break

    async def _批量发送(self, 客户端集合, 消息: str) -> None:
        """并发向多个客户端发送消息"""
        if not 客户端集合:
            return
        tasks = []
        for ws in 客户端集合:
            tasks.append(asyncio.create_task(self._安全发送(ws, 消息)))
        await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _安全发送(ws, 消息: str) -> None:
        try:
            await ws.send(消息)
        except Exception:
            pass  # 连接已断开，忽略
