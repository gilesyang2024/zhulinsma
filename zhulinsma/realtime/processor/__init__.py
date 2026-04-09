"""
增量计算引擎 - 只计算新增数据，高效更新技术指标
"""
import numpy as np
from typing import Dict, Optional, List, Tuple
from collections import deque
from dataclasses import dataclass, field
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """价格数据"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass 
class IndicatorResult:
    """指标计算结果"""
    stock_code: str
    timestamp: str
    current_price: float
    # 移动平均线
    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_30: Optional[float] = None
    sma_60: Optional[float] = None
    # 指数移动平均线
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    # RSI
    rsi: Optional[float] = None
    # MACD
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    # 布林带
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    # 偏离度
    deviation_5: Optional[float] = None
    deviation_10: Optional[float] = None
    deviation_20: Optional[float] = None
    # 信号
    golden_cross: bool = False
    death_cross: bool = False
    trend: str = "neutral"  # up, down, neutral
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "timestamp": self.timestamp,
            "current_price": self.current_price,
            "sma_5": self.sma_5,
            "sma_10": self.sma_10,
            "sma_20": self.sma_20,
            "sma_30": self.sma_30,
            "sma_60": self.sma_60,
            "ema_12": self.ema_12,
            "ema_26": self.ema_26,
            "rsi": self.rsi,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_hist": self.macd_hist,
            "boll_upper": self.boll_upper,
            "boll_mid": self.boll_mid,
            "boll_lower": self.boll_lower,
            "deviation_5": self.deviation_5,
            "deviation_10": self.deviation_10,
            "deviation_20": self.deviation_20,
            "golden_cross": self.golden_cross,
            "death_cross": self.death_cross,
            "trend": self.trend
        }


class IncrementalEngine:
    """增量计算引擎 - 只计算新增数据"""
    
    def __init__(
        self,
        max_window_size: int = 100,
        enable_sma: bool = True,
        enable_ema: bool = True,
        enable_rsi: bool = True,
        enable_macd: bool = True,
        enable_boll: bool = True
    ):
        self.max_window_size = max_window_size
        
        # 是否启用各项指标
        self.enable_sma = enable_sma
        self.enable_ema = enable_ema
        self.enable_rsi = enable_rsi
        self.enable_macd = enable_macd
        self.enable_boll = enable_boll
        
        # 价格历史缓存
        self._price_history: Dict[str, deque] = {}
        self._close_prices: Dict[str, List[float]] = {}
        
        # EMA状态缓存
        self._ema_12_prev: Dict[str, float] = {}
        self._ema_26_prev: Dict[str, float] = {}
        self._macd_signal_prev: Dict[str, float] = {}
        
        # RSI状态缓存
        self._rsi_prev: Dict[str, float] = {}
        self._gain_history: Dict[str, deque] = {}
        self._loss_history: Dict[str, deque] = {}
        
        # 布林带状态缓存
        self._boll_std_prev: Dict[str, float] = {}
        
        # 金叉死叉状态
        self._prev_sma_5: Dict[str, float] = {}
        self._prev_sma_10: Dict[str, float] = {}
        
        # 性能统计
        self._calc_count = 0
        self._total_time = 0.0
    
    def update(self, stock_code: str, price_data: PriceData) -> IndicatorResult:
        """增量更新技术指标"""
        start_time = time.time()
        
        # 初始化历史数据
        if stock_code not in self._price_history:
            self._price_history[stock_code] = deque(maxlen=self.max_window_size)
            self._close_prices[stock_code] = []
        
        # 添加新数据
        self._price_history[stock_code].append(price_data)
        self._close_prices[stock_code].append(price_data.close)
        
        # 获取历史数据
        history = list(self._price_history[stock_code])
        closes = self._close_prices[stock_code]
        
        if len(closes) < 5:
            # 数据不足，返回基本信息
            return IndicatorResult(
                stock_code=stock_code,
                timestamp=price_data.timestamp,
                current_price=price_data.close,
                trend="neutral"
            )
        
        # 计算各项指标
        result = IndicatorResult(
            stock_code=stock_code,
            timestamp=price_data.timestamp,
            current_price=price_data.close
        )
        
        # 计算SMA
        if self.enable_sma:
            result.sma_5 = self._calc_sma(closes, 5)
            result.sma_10 = self._calc_sma(closes, 10)
            result.sma_20 = self._calc_sma(closes, 20)
            result.sma_30 = self._calc_sma(closes, 30) if len(closes) >= 30 else None
            result.sma_60 = self._calc_sma(closes, 60) if len(closes) >= 60 else None
            
            # 计算偏离度
            if result.sma_5:
                result.deviation_5 = (price_data.close - result.sma_5) / result.sma_5 * 100
            if result.sma_10:
                result.deviation_10 = (price_data.close - result.sma_10) / result.sma_10 * 100
            if result.sma_20:
                result.deviation_20 = (price_data.close - result.sma_20) / result.sma_20 * 100
            
            # 金叉死叉检测
            self._check_crossover(stock_code, result)
            
            # 趋势判断
            result.trend = self._determine_trend(result)
        
        # 计算EMA
        if self.enable_ema and len(closes) >= 26:
            result.ema_12 = self._calc_ema_incremental(stock_code, closes, 12)
            result.ema_26 = self._calc_ema_incremental(stock_code, closes, 26)
        
        # 计算MACD
        if self.enable_macd and result.ema_12 and result.ema_26:
            macd = result.ema_12 - result.ema_26
            result.macd = macd
            result.macd_signal = self._calc_macd_signal_incremental(stock_code, macd)
            if result.macd_signal:
                result.macd_hist = macd - result.macd_signal
        
        # 计算RSI
        if self.enable_rsi:
            result.rsi = self._calc_rsi_incremental(stock_code, closes)
        
        # 计算布林带
        if self.enable_boll and len(closes) >= 20:
            upper, mid, lower = self._calc_boll_incremental(stock_code, closes)
            result.boll_upper = upper
            result.boll_mid = mid
            result.boll_lower = lower
        
        # 统计性能
        self._calc_count += 1
        self._total_time += (time.time() - start_time)
        
        return result
    
    def _calc_sma(self, closes: List[float], period: int) -> Optional[float]:
        """计算简单移动平均"""
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period
    
    def _calc_ema_incremental(self, stock_code: str, closes: List[float], period: int) -> Optional[float]:
        """增量计算EMA"""
        if len(closes) < period:
            return None
        
        multiplier = 2 / (period + 1)
        
        if len(closes) == period:
            # 首次计算，使用SMA初始化
            ema = sum(closes[:period]) / period
        else:
            # 增量计算
            prev_ema = self._ema_12_prev.get(stock_code) if period == 12 else self._ema_26_prev.get(stock_code)
            if prev_ema is None:
                # 如果没有缓存，重新计算
                ema = sum(closes[:period]) / period
            else:
                ema = (closes[-1] - prev_ema) * multiplier + prev_ema
        
        # 缓存当前值
        if period == 12:
            self._ema_12_prev[stock_code] = ema
        else:
            self._ema_26_prev[stock_code] = ema
            
        return ema
    
    def _calc_macd_signal_incremental(self, stock_code: str, macd: float) -> Optional[float]:
        """增量计算MACD信号线"""
        prev_signal = self._macd_signal_prev.get(stock_code)
        
        if prev_signal is None:
            # 首次计算
            signal = macd
        else:
            # 增量计算 (9日EMA)
            signal = (macd - prev_signal) * (2 / 10) + prev_signal
            
        self._macd_signal_prev[stock_code] = signal
        return signal
    
    def _calc_rsi_incremental(self, stock_code: str, closes: List[float]) -> Optional[float]:
        """增量计算RSI"""
        if len(closes) < 2:
            return None
        
        # 计算当前价格变化
        change = closes[-1] - closes[-2]
        
        # 初始化gain/loss历史
        if stock_code not in self._gain_history:
            self._gain_history[stock_code] = deque(maxlen=14)
            self._loss_history[stock_code] = deque(maxlen=14)
        
        gain = max(change, 0) if change > 0 else 0
        loss = abs(min(change, 0)) if change < 0 else 0
        
        self._gain_history[stock_code].append(gain)
        self._loss_history[stock_code].append(loss)
        
        # 需要至少14个数据点
        if len(self._gain_history[stock_code]) < 14:
            return None
        
        # 计算平均增益和平均损失
        avg_gain = sum(self._gain_history[stock_code]) / 14
        avg_loss = sum(self._loss_history[stock_code]) / 14
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        self._rsi_prev[stock_code] = rsi
        return rsi
    
    def _calc_boll_incremental(self, stock_code: str, closes: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """增量计算布林带"""
        if len(closes) < 20:
            return None, None, None
        
        # 取20日数据
        recent_closes = closes[-20:]
        
        # 计算中轨（SMA20）
        mid = sum(recent_closes) / 20
        
        # 计算标准差
        std = np.std(recent_closes)
        
        upper = mid + 2 * std
        lower = mid - 2 * std
        
        # 缓存
        self._boll_std_prev[stock_code] = std
        
        return upper, mid, lower
    
    def _check_crossover(self, stock_code: str, result: IndicatorResult):
        """检测金叉死叉"""
        prev_5 = self._prev_sma_5.get(stock_code)
        prev_10 = self._prev_sma_10.get(stock_code)
        
        current_5 = result.sma_5
        current_10 = result.sma_10
        
        if prev_5 is not None and prev_10 is not None and current_5 and current_10:
            # 金叉：5日均线上穿10日均线
            if prev_5 <= prev_10 and current_5 > current_10:
                result.golden_cross = True
            # 死叉：5日均线下穿10日均线
            elif prev_5 >= prev_10 and current_5 < current_10:
                result.death_cross = True
        
        # 更新状态
        self._prev_sma_5[stock_code] = current_5
        self._prev_sma_10[stock_code] = current_10
    
    def _determine_trend(self, result: IndicatorResult) -> str:
        """判断趋势"""
        if not result.sma_5 or not result.sma_20:
            return "neutral"
        
        # 多头排列：5日 > 10日 > 20日
        if result.sma_5 > result.sma_10 > result.sma_20:
            return "up"
        # 空头排列：5日 < 10日 < 20日
        elif result.sma_5 < result.sma_10 < result.sma_20:
            return "down"
        else:
            return "neutral"
    
    def batch_update(self, stock_code: str, price_data_list: List[PriceData]) -> List[IndicatorResult]:
        """批量更新（用于初始化）"""
        results = []
        for pd in price_data_list:
            result = self.update(stock_code, pd)
            results.append(result)
        return results
    
    def reset(self, stock_code: str):
        """重置指定股票的计算状态"""
        self._price_history.pop(stock_code, None)
        self._close_prices.pop(stock_code, None)
        self._ema_12_prev.pop(stock_code, None)
        self._ema_26_prev.pop(stock_code, None)
        self._macd_signal_prev.pop(stock_code, None)
        self._rsi_prev.pop(stock_code, None)
        self._gain_history.pop(stock_code, None)
        self._loss_history.pop(stock_code, None)
        self._boll_std_prev.pop(stock_code, None)
        self._prev_sma_5.pop(stock_code, None)
        self._prev_sma_10.pop(stock_code, None)
        logger.info(f"重置股票 {stock_code} 的增量计算状态")
    
    def get_performance_stats(self) -> dict:
        """获取性能统计"""
        avg_time = self._total_time / self._calc_count if self._calc_count > 0 else 0
        return {
            "total_calculations": self._calc_count,
            "total_time_ms": round(self._total_time * 1000, 2),
            "avg_time_ms": round(avg_time * 1000, 4)
        }
    
    def get_stock_count(self) -> int:
        """获取当前跟踪的股票数量"""
        return len(self._price_history)


# 导出
__all__ = ['IncrementalEngine', 'IndicatorResult', 'PriceData']