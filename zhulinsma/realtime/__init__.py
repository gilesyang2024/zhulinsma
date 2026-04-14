#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - realtime 子包入口
整合 collector / gateway / processor / trigger / protocol 五大模块
"""

from .protocol import (
    MessageType, AlertType,
    TickData, BarData, AlertMessage, WsMessage,
)
from .collector import RealtimeCollector
from .processor import IncrementalProcessor
from .trigger import AlertTrigger
from .gateway import RealtimeGateway, ConnectionManager

__all__ = [
    # 协议
    "MessageType", "AlertType",
    "TickData", "BarData", "AlertMessage", "WsMessage",
    # 模块
    "RealtimeCollector",
    "IncrementalProcessor",
    "AlertTrigger",
    "RealtimeGateway",
    "ConnectionManager",
]
