#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 实时数据协议定义
定义 WebSocket 消息格式、数据帧结构和事件类型
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from enum import Enum
import time
import json


class MessageType(str, Enum):
    """消息类型枚举"""
    # 行情数据
    TICK = "tick"                   # 实时报价
    BAR = "bar"                     # K线数据
    DEPTH = "depth"                 # 盘口深度

    # 控制消息
    SUBSCRIBE = "subscribe"         # 订阅请求
    UNSUBSCRIBE = "unsubscribe"     # 取消订阅
    HEARTBEAT = "heartbeat"         # 心跳
    ACK = "ack"                     # 确认回执
    ERROR = "error"                 # 错误通知

    # 预警消息
    ALERT = "alert"                 # 技术指标预警
    SIGNAL = "signal"               # 交易信号


class AlertType(str, Enum):
    """预警类型枚举"""
    RSI_OVERBOUGHT = "rsi_overbought"       # RSI超买
    RSI_OVERSOLD = "rsi_oversold"           # RSI超卖
    MACD_GOLDEN_CROSS = "macd_golden"       # MACD金叉
    MACD_DEATH_CROSS = "macd_death"         # MACD死叉
    MA_DEVIATION = "ma_deviation"           # 均线偏离
    VOLUME_SURGE = "volume_surge"           # 成交量异动
    PRICE_BREAKOUT = "price_breakout"       # 价格突破


@dataclass
class TickData:
    """实时报价数据帧"""
    ts_code: str                    # 股票代码
    price: float                    # 最新价
    volume: float                   # 成交量
    amount: float                   # 成交额
    bid: float = 0.0                # 买一价
    ask: float = 0.0                # 卖一价
    open: float = 0.0               # 今开
    high: float = 0.0               # 最高
    low: float = 0.0                # 最低
    prev_close: float = 0.0         # 昨收
    timestamp: float = field(default_factory=time.time)

    @property
    def pct_chg(self) -> float:
        if self.prev_close > 0:
            return (self.price - self.prev_close) / self.prev_close * 100
        return 0.0

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["pct_chg"] = round(self.pct_chg, 4)
        return d


@dataclass
class BarData:
    """K线数据帧"""
    ts_code: str
    freq: str                       # 1min / 5min / 15min / 30min / 60min / D
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AlertMessage:
    """预警消息"""
    alert_type: str                 # AlertType 枚举值
    ts_code: str
    title: str
    description: str
    value: float                    # 触发值（如RSI=75）
    threshold: float                # 阈值
    severity: str = "INFO"          # INFO / WARN / ALERT / CRITICAL
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class WsMessage:
    """WebSocket 消息标准封装"""
    type: str                       # MessageType 枚举值
    data: Any
    seq: int = 0                    # 序列号，用于消息去重
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        payload = {
            "type": self.type,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "data": self.data if not hasattr(self.data, "to_dict") else self.data.to_dict(),
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def heartbeat(cls, seq: int = 0) -> "WsMessage":
        return cls(type=MessageType.HEARTBEAT, data={"ping": time.time()}, seq=seq)

    @classmethod
    def error(cls, code: int, message: str) -> "WsMessage":
        return cls(type=MessageType.ERROR, data={"code": code, "message": message})
