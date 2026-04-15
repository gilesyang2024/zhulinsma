#!/usr/bin/env python3
"""
策略基类 - 所有选股策略的抽象基类
定义统一的接口和数据结构
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


class SignalType(str, Enum):
    """信号类型枚举"""
    BUY = "buy"              # 买入信号
    SELL = "sell"            # 卖出信号
    HOLD = "hold"            # 持有
    WATCH = "watch"          # 观望
    STRONG_BUY = "strong_buy"  # 强烈买入
    ALERT = "alert"          # 预警


class StrategyType(str, Enum):
    """策略类型枚举"""
    FIVE_STEP = "five_step"      # 五步选股法
    LOCKUP_KLINE = "lockup_kline"  # 锁仓K线
    WEAK_TO_STRONG = "weak_to_strong"  # 竞价弱转强
    BLADE_OUT = "blade_out"      # 利刃出鞘
    LIMIT_UP = "limit_up"        # 涨停版法
    MULTIFACTOR = "multifactor"  # 多因子打分


@dataclass
class Signal:
    """策略信号数据结构"""
    # 基础信息
    code: str                           # 股票代码
    name: str = ""                      # 股票名称
    strategy: str = ""                  # 策略名称
    strategy_type: StrategyType = StrategyType.FIVE_STEP
    signal_type: SignalType = SignalType.WATCH
    
    # 价格信息
    current_price: float = 0.0          # 当前价格
    entry_price: Optional[float] = None  # 建议买入价
    stop_loss: Optional[float] = None   # 止损价
    target_price: Optional[float] = None  # 目标价
    
    # 信号强度
    confidence: float = 0.0             # 置信度 (0-1)
    score: float = 0.0                  # 评分 (0-10)
    
    # 时间信息
    timestamp: datetime = field(default_factory=datetime.now)
    holding_days: Optional[str] = None  # 建议持仓周期
    
    # 详细数据
    details: Dict[str, Any] = field(default_factory=dict)  # 详细指标
    signals: Dict[str, bool] = field(default_factory=dict)  # 各条件触发情况
    risk_factors: List[str] = field(default_factory=list)  # 风险因素
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "code": self.code,
            "name": self.name,
            "strategy": self.strategy,
            "strategy_type": self.strategy_type.value,
            "signal_type": self.signal_type.value,
            "current_price": self.current_price,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "confidence": self.confidence,
            "score": self.score,
            "timestamp": self.timestamp.isoformat(),
            "holding_days": self.holding_days,
            "details": self.details,
            "signals": self.signals,
            "risk_factors": self.risk_factors,
        }
    
    @property
    def rating_stars(self) -> str:
        """星级评分显示"""
        if self.score >= 9.0:
            return "★★★★★"
        elif self.score >= 7.5:
            return "★★★★"
        elif self.score >= 6.0:
            return "★★★"
        elif self.score >= 4.0:
            return "★★"
        else:
            return "★"
    
    @property
    def action_text(self) -> str:
        """操作建议文本"""
        if self.score >= 8.0:
            return "强烈买入"
        elif self.score >= 7.0:
            return "买入"
        elif self.score >= 6.0:
            return "观察/轻仓"
        elif self.score >= 5.0:
            return "观望"
        else:
            return "回避"


@dataclass
class StockData:
    """标准化股票数据结构"""
    code: str
    name: str = ""
    df: Optional[pd.DataFrame] = None   # 日线数据
    
    # 价格序列
    close: Optional[np.ndarray] = None
    open: Optional[np.ndarray] = None
    high: Optional[np.ndarray] = None
    low: Optional[np.ndarray] = None
    volume: Optional[np.ndarray] = None
    amount: Optional[np.ndarray] = None
    
    # 基本信息
    pe: Optional[float] = None
    pb: Optional[float] = None
    market_cap: Optional[float] = None
    
    def __post_init__(self):
        """从DataFrame提取数据"""
        if self.df is not None and not self.df.empty:
            if 'close' in self.df.columns:
                self.close = self.df['close'].values
            if 'open' in self.df.columns:
                self.open = self.df['open'].values
            if 'high' in self.df.columns:
                self.high = self.df['high'].values
            if 'low' in self.df.columns:
                self.low = self.df['low'].values
            if 'volume' in self.df.columns:
                self.volume = self.df['volume'].values
            if 'amount' in self.df.columns:
                self.amount = self.df['amount'].values


class BaseStrategy(ABC):
    """
    策略基类
    
    所有选股策略必须继承此类，实现以下接口：
    - analyze(): 分析单只股票
    - scan(): 扫描多只股票
    - get_name(): 获取策略名称
    - get_description(): 获取策略描述
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化策略
        
        Args:
            config: 策略配置参数
        """
        self.config = config or {}
        self.name = self.get_name()
        self.description = self.get_description()
        self.version = "1.0.0"
        
    @abstractmethod
    def get_name(self) -> str:
        """返回策略名称"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """返回策略描述"""
        pass
    
    @abstractmethod
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """
        分析单只股票
        
        Args:
            stock_data: 股票数据
            
        Returns:
            Signal对象，如果不满足条件返回None
        """
        pass
    
    def scan(self, stock_list: List[StockData]) -> List[Signal]:
        """
        扫描多只股票
        
        Args:
            stock_list: 股票数据列表
            
        Returns:
            信号列表
        """
        signals = []
        for stock in stock_list:
            try:
                signal = self.analyze(stock)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                print(f"分析 {stock.code} 时出错: {e}")
        return signals
    
    def validate_data(self, stock_data: StockData) -> bool:
        """
        验证数据有效性
        
        Args:
            stock_data: 股票数据
            
        Returns:
            数据是否有效
        """
        if stock_data.close is None or len(stock_data.close) < 20:
            return False
        if stock_data.volume is None or len(stock_data.volume) < 20:
            return False
        return True
    
    def calculate_ma(self, prices: np.ndarray, period: int) -> np.ndarray:
        """计算简单移动平均"""
        return pd.Series(prices).rolling(window=period, min_periods=1).mean().values
    
    def calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        return pd.Series(prices).ewm(span=period, adjust=False).mean().values
    
    def calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """计算RSI"""
        delta = np.diff(prices)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = pd.Series(gain).rolling(window=period, min_periods=1).mean().values
        avg_loss = pd.Series(loss).rolling(window=period, min_periods=1).mean().values
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        # 补齐长度
        result = np.full(len(prices), np.nan)
        result[1:] = rsi
        return result
    
    def calculate_macd(self, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """计算MACD"""
        ema_fast = self.calculate_ema(prices, fast)
        ema_slow = self.calculate_ema(prices, slow)
        dif = ema_fast - ema_slow
        dea = self.calculate_ema(dif, signal)
        macd_hist = (dif - dea) * 2
        
        return {
            "dif": dif,
            "dea": dea,
            "hist": macd_hist
        }
    
    def calculate_bollinger(self, prices: np.ndarray, period: int = 20, num_std: int = 2) -> Dict[str, np.ndarray]:
        """计算布林带"""
        ma = self.calculate_ma(prices, period)
        std = pd.Series(prices).rolling(window=period, min_periods=1).std().values
        
        return {
            "upper": ma + num_std * std,
            "middle": ma,
            "lower": ma - num_std * std
        }
