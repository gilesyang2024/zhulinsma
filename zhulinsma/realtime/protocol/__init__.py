"""
实时数据协议定义
定义WebSocket消息格式和协议
"""
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class MessageType(Enum):
    """消息类型枚举"""
    # 客户端 -> 服务端
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    HEARTBEAT = "heartbeat"
    AUTH = "auth"
    
    # 服务端 -> 客户端
    REALTIME = "realtime"
    ALERT = "alert"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    CONNECTED = "connected"


class ChannelType(Enum):
    """订阅频道类型"""
    STOCK = "stock"           # 股票行情
    ALERT = "alert"           # 预警通知
    ANALYSIS = "analysis"     # 实时分析


class AlertType(Enum):
    """预警类型"""
    RSI_OVERBOUGHT = "rsi_overbought"      # RSI超买
    RSI_OVERSOLD = "rsi_oversold"           # RSI超卖
    GOLDEN_CROSS = "golden_cross"           # 金叉
    DEATH_CROSS = "death_cross"             # 死叉
    VOLUME_SPIKE = "volume_spike"          # 成交量异动
    PRICE_BREAK = "price_break"            # 突破支撑/阻力
    DEVIATION_ALERT = "deviation_alert"     # 均线偏离预警


@dataclass
class SubscribeRequest:
    """订阅请求"""
    type: str = "subscribe"
    stock_codes: List[str] = None
    channels: List[str] = None
    alerts: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.stock_codes is None:
            self.stock_codes = []
        if self.channels is None:
            self.channels = ["realtime"]
            
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SubscribeRequest':
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class RealtimeData:
    """实时行情数据"""
    stock_code: str
    price: float
    change: float
    change_pct: float
    volume: int
    open: float
    high: float
    low: float
    amount: float
    timestamp: str
    # 技术指标
    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_30: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RealtimeData':
        return cls(**data)


@dataclass
class RealtimeMessage:
    """实时数据消息"""
    type: str = "realtime"
    stock_code: str = ""
    data: RealtimeData = None
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "stock_code": self.stock_code,
            "data": self.data.to_dict() if self.data else None
        })
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RealtimeMessage':
        return cls(
            type=data.get("type"),
            stock_code=data.get("stock_code"),
            data=RealtimeData.from_dict(data["data"]) if data.get("data") else None
        )


@dataclass
class AlertData:
    """预警数据"""
    alert_type: str
    stock_code: str
    message: str
    value: float
    threshold: float
    timestamp: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertMessage:
    """预警消息"""
    type: str = "alert"
    alert_type: str = ""
    stock_code: str = ""
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: str = ""
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AlertMessage':
        return cls(**data)


@dataclass
class ErrorMessage:
    """错误消息"""
    type: str = "error"
    code: int = 0
    message: str = ""
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


class MessageParser:
    """消息解析器"""
    
    @staticmethod
    def parse(data: str) -> dict:
        """解析JSON消息"""
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {"type": "error", "message": "Invalid JSON"}
    
    @staticmethod
    def create_realtime(stock_code: str, data: RealtimeData) -> str:
        """创建实时数据消息"""
        msg = RealtimeMessage(type="realtime", stock_code=stock_code, data=data)
        return msg.to_json()
    
    @staticmethod
    def create_alert(alert: AlertData) -> str:
        """创建预警消息"""
        msg = AlertMessage(
            type="alert",
            alert_type=alert.alert_type,
            stock_code=alert.stock_code,
            message=alert.message,
            value=alert.value,
            threshold=alert.threshold,
            timestamp=alert.timestamp
        )
        return msg.to_json()
    
    @staticmethod
    def create_error(code: int, message: str) -> str:
        """创建错误消息"""
        msg = ErrorMessage(type="error", code=code, message=message)
        return msg.to_json()
    
    @staticmethod
    def create_heartbeat() -> str:
        """创建心跳响应"""
        return json.dumps({"type": "heartbeat_ack", "status": "ok"})
    
    @staticmethod
    def create_connected() -> str:
        """创建连接成功消息"""
        return json.dumps({"type": "connected", "status": "ok"})


# 导出
__all__ = [
    'MessageType',
    'ChannelType', 
    'AlertType',
    'SubscribeRequest',
    'RealtimeData',
    'RealtimeMessage',
    'AlertData',
    'AlertMessage',
    'ErrorMessage',
    'MessageParser'
]