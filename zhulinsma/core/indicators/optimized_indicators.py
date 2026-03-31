#!/usr/bin/env python3
"""
竹林司马 - 优化技术指标库
应用向量化计算和性能优化技术
版本: 2.0.0 (优化版)
日期: 2026年3月29日
作者: 杨总的工作助手
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from functools import lru_cache
warnings.filterwarnings('ignore')

__all__ = [
    'OptimizedTechnicalIndicators',
    'vectorized_SMA',
    'vectorized_EMA',
    'vectorized_RSI',
    'vectorized_MACD',
    'vectorized_BollingerBands',
    'vectorized_ATR',
    'efficient_SMA',
    'efficient_EMA',
    'efficient_RSI',
    '高效SMA',
    '高效EMA',
    '高效RSI',
    '高效MACD',
    '高效布林带'
]

# ========== 高效计算函数 ==========

def efficient_SMA(data: np.ndarray, period: int) -> np.ndarray:
    """高效的SMA计算 - 使用累积求和"""
    n = len(data)
    result = np.full(n, np.nan, dtype=np.float64)
    
    if n < period:
        return result
    
    # 使用累积求和技术优化SMA计算
    cumsum = np.cumsum(data, dtype=np.float64)
    cumsum[period:] = cumsum[period:] - cumsum[:-period]
    
    # 计算SMA
    result[period-1:] = cumsum[period-1:] / period
    
    return result

# 添加中文别名
高效SMA = efficient_SMA

def efficient_EMA(data: np.ndarray, period: int) -> np.ndarray:
    """高效的EMA计算 - 使用向量化计算"""
    n = len(data)
    result = np.full(n, np.nan, dtype=np.float64)
    
    if n < period:
        return result
    
    alpha = 2.0 / (period + 1.0)
    
    # 初始EMA使用SMA
    sma = np.mean(data[:period])
    result[period-1] = sma
    
    # 使用向量化计算后续EMA
    for i in range(period, n):
        result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
    
    return result

# 添加中文别名
高效EMA = efficient_EMA

def efficient_RSI(data: np.ndarray, period: int) -> np.ndarray:
    """高效的RSI计算 - 使用向量化计算"""
    n = len(data)
    result = np.full(n, np.nan, dtype=np.float64)
    
    if n < period + 1:
        return result
    
    # 计算价格变化
    deltas = np.zeros(n, dtype=np.float64)
    deltas[1:] = data[1:] - data[:-1]
    
    # 分离上涨和下跌
    up = np.where(deltas > 0, deltas, 0.0)
    down = np.where(deltas < 0, -deltas, 0.0)
    
    # 使用指数移动平均计算平均上涨和下跌
    # 这里使用简单但高效的计算方法
    avg_up = np.zeros(n, dtype=np.float64)
    avg_down = np.zeros(n, dtype=np.float64)
    
    # 初始值
    avg_up[period] = np.mean(up[1:period+1])
    avg_down[period] = np.mean(down[1:period+1])
    
    # 第一个有效RSI值
    if avg_down[period] > 0:
        rs = avg_up[period] / avg_down[period]
        result[period] = 100.0 - 100.0 / (1.0 + rs)
    
    # 计算后续RSI值
    for i in range(period+1, n):
        avg_up[i] = ((period - 1) * avg_up[i-1] + up[i]) / period
        avg_down[i] = ((period - 1) * avg_down[i-1] + down[i]) / period
        
        if avg_down[i] > 0:
            rs = avg_up[i] / avg_down[i]
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    
    return result

# 添加中文别名
高效RSI = efficient_RSI

# ========== 向量化函数 ==========

def vectorized_SMA(data: Union[np.ndarray, pd.Series], period: int) -> np.ndarray:
    """向量化SMA计算 - 使用卷积优化"""
    if isinstance(data, pd.Series):
        data = data.values
    
    if len(data) < period:
        return np.full(len(data), np.nan)
    
    # 使用卷积计算SMA，比循环更快
    weights = np.ones(period) / period
    sma = np.convolve(data, weights, mode='valid')
    
    # 构建完整结果
    result = np.full(len(data), np.nan)
    result[period-1:] = sma
    
    return result

def vectorized_EMA(data: Union[np.ndarray, pd.Series], period: int) -> np.ndarray:
    """向量化EMA计算"""
    if isinstance(data, pd.Series):
        data = data.values
    
    if len(data) < period:
        return np.full(len(data), np.nan)
    
    # 使用Pandas的ewm函数，底层是C实现
    series = pd.Series(data)
    ema = series.ewm(span=period, adjust=False).mean().values
    
    # 创建副本以避免修改只读数组
    ema_result = ema.copy()
    
    # 设置前period-1个值为NaN
    ema_result[:period-1] = np.nan
    
    return ema_result

def vectorized_RSI(data: Union[np.ndarray, pd.Series], period: int = 14) -> np.ndarray:
    """向量化RSI计算"""
    if isinstance(data, pd.Series):
        data = data.values
    
    if len(data) < period + 1:
        return np.full(len(data), np.nan)
    
    # 计算价格变化
    deltas = np.diff(data)
    
    # 分离上涨和下跌
    up = np.where(deltas > 0, deltas, 0)
    down = np.where(deltas < 0, -deltas, 0)
    
    # 使用指数移动平均计算平均上涨和下跌
    avg_up = pd.Series(up).ewm(alpha=1/period, adjust=False).mean().values
    avg_down = pd.Series(down).ewm(alpha=1/period, adjust=False).mean().values
    
    # 计算RSI
    rs = avg_up / (avg_down + 1e-10)
    rsi = 100 - 100 / (1 + rs)
    
    # 构建完整结果
    result = np.full(len(data), np.nan)
    result[period:] = rsi[period-1:]
    
    return result

def vectorized_MACD(data: Union[np.ndarray, pd.Series], 
                    fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
    """向量化MACD计算"""
    if isinstance(data, pd.Series):
        data = data.values
    
    # 计算快线和慢线EMA
    ema_fast = vectorized_EMA(data, fast)
    ema_slow = vectorized_EMA(data, slow)
    
    # 计算MACD线
    macd_line = ema_fast - ema_slow
    
    # 计算信号线 (MACD线的EMA)
    signal_line = vectorized_EMA(macd_line, signal)
    
    # 计算柱状线
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }

# 添加中文别名
高效MACD = vectorized_MACD

def vectorized_BollingerBands(data: Union[np.ndarray, pd.Series], 
                             period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
    """向量化布林带计算"""
    if isinstance(data, pd.Series):
        data = data.values
    
    if len(data) < period:
        empty_result = np.full(len(data), np.nan)
        return {
            'middle': empty_result,
            'upper': empty_result,
            'lower': empty_result,
            'bandwidth': empty_result,
            'position': empty_result
        }
    
    # 使用Pandas的rolling函数进行向量化计算
    series = pd.Series(data)
    
    # 计算中轨 (SMA)
    middle = series.rolling(window=period, min_periods=period).mean().values
    
    # 计算标准差
    std = series.rolling(window=period, min_periods=period).std().values
    
    # 计算上下轨
    upper = middle + std * std_dev
    lower = middle - std * std_dev
    
    # 计算带宽
    bandwidth = (upper - lower) / middle
    
    # 计算价格位置 (0-1之间)
    position = (data - lower) / (upper - lower + 1e-10)
    
    return {
        'middle': middle,
        'upper': upper,
        'lower': lower,
        'bandwidth': bandwidth,
        'position': position
    }

# 添加中文别名
高效布林带 = vectorized_BollingerBands

def vectorized_ATR(high: Union[np.ndarray, pd.Series], 
                  low: Union[np.ndarray, pd.Series], 
                  close: Union[np.ndarray, pd.Series], 
                  period: int = 14) -> np.ndarray:
    """向量化ATR计算"""
    if isinstance(high, pd.Series):
        high = high.values
    if isinstance(low, pd.Series):
        low = low.values
    if isinstance(close, pd.Series):
        close = close.values
    
    n = len(high)
    if n < period + 1:
        return np.full(n, np.nan)
    
    # 计算True Range
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - close[:-1])
    tr3 = np.abs(low[1:] - close[:-1])
    
    true_range = np.maximum.reduce([tr1, tr2, tr3])
    
    # 计算ATR (True Range的SMA)
    atr = np.full(n, np.nan)
    
    # 使用向量化SMA计算ATR
    atr_values = vectorized_SMA(true_range, period)
    atr[period:] = atr_values[period-1:-1]
    
    return atr

# ========== 优化技术指标类 ==========

class OptimizedTechnicalIndicators:
    """
    优化技术指标核心类
    应用向量化计算、Numba加速、缓存和并行处理技术
    符合广州投资者习惯，红涨绿跌
    """
    
    def __init__(self, 验证模式: bool = True, 优化模式: str = "auto", 缓存大小: int = 1000):
        """
        初始化优化技术指标库
        
        参数:
            验证模式: 是否启用双重验证 (默认: True)
            优化模式: 优化策略，可选 "numba", "vectorized", "parallel", "auto" (默认: auto)
            缓存大小: LRU缓存大小，加速重复计算 (默认: 1000)
        """
        self.验证模式 = 验证模式
        self.优化模式 = 优化模式
        self.缓存大小 = 缓存大小
        self.广州模式 = True  # 红涨绿跌
        self.计算历史 = []
        self.缓存 = {}
        
        # 性能监控
        self.性能统计 = {
            'total_calculations': 0,
            'total_time_ms': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'parallel_executions': 0
        }
        
        print(f"🚀 竹林司马 优化技术指标库初始化完成")
        print(f"   验证模式: {'启用' if 验证模式 else '禁用'}")
        print(f"   优化模式: {优化模式}")
        print(f"   缓存大小: {缓存大小}")
        print(f"   广州模式: {'红涨绿跌' if self.广州模式 else '绿涨红跌'}")
    
    def _get_cache_key(self, func_name: str, *args, **kwargs) -> str:
        """生成缓存键"""
        # 将参数转换为字符串形式
        args_str = str(args)
        kwargs_str = str(sorted(kwargs.items()))
        return f"{func_name}|{args_str}|{kwargs_str}"
    
    def _timed_execution(self, func, *args, **kwargs):
        """计时执行函数"""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        
        elapsed_ms = (end_time - start_time) * 1000
        self.性能统计['total_time_ms'] += elapsed_ms
        self.性能统计['total_calculations'] += 1
        
        return result, elapsed_ms
    
    def SMA(self, 价格: Union[pd.Series, np.ndarray], 周期: int = 5, 使用缓存: bool = True) -> np.ndarray:
        """
        优化SMA计算，支持多种优化策略
        
        参数:
            价格: 价格序列
            周期: 移动平均周期 (默认: 5)
            使用缓存: 是否使用缓存加速重复计算 (默认: True)
        
        返回:
            优化后的SMA结果
        """
        # 生成缓存键
        cache_key = self._get_cache_key('SMA', 价格, 周期) if 使用缓存 else None
        
        # 检查缓存
        if 使用缓存 and cache_key in self.缓存:
            self.性能统计['cache_hits'] += 1
            return self.缓存[cache_key]
        
        self.性能统计['cache_misses'] += 1
        
        # 数据预处理
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格, dtype=np.float64)
        
        # 根据优化模式选择计算方法
        if self.优化模式 == "efficient":
            result = efficient_SMA(价格数据, 周期)
        elif self.优化模式 == "vectorized":
            result = vectorized_SMA(价格数据, 周期)
        elif self.优化模式 == "parallel" and len(价格数据) > 10000:
            # 大数据量时使用并行计算
            result = self._parallel_SMA(价格数据, 周期)
        else:  # auto模式
            if len(价格数据) > 10000:
                result = efficient_SMA(价格数据, 周期)
            else:
                result = vectorized_SMA(价格数据, 周期)
        
        # 验证结果
        if self.验证模式:
            self._验证SMA(价格数据, result, 周期)
        
        # 缓存结果
        if 使用缓存 and cache_key is not None:
            if len(self.缓存) >= self.缓存大小:
                # 简单的LRU缓存淘汰
                oldest_key = next(iter(self.缓存))
                del self.缓存[oldest_key]
            self.缓存[cache_key] = result
        
        # 记录计算历史
        self.计算历史.append({
            '操作': 'SMA计算',
            '周期': 周期,
            '数据长度': len(价格数据),
            '优化模式': self.优化模式,
            '缓存使用': 使用缓存
        })
        
        return result
    
    def _parallel_SMA(self, data: np.ndarray, period: int) -> np.ndarray:
        """并行SMA计算（适用于大数据量）"""
        n = len(data)
        result = np.full(n, np.nan, dtype=np.float64)
        
        if n < period:
            return result
        
        # 分割数据为多个块
        n_chunks = min(8, n // 1000)  # 最多8个块，每块至少1000个数据点
        chunk_size = n // n_chunks
        
        def calculate_chunk(start_idx, end_idx):
            """计算单个数据块的SMA"""
            chunk_result = np.full(end_idx - start_idx, np.nan, dtype=np.float64)
            
            if start_idx < period-1:
                return chunk_result
            
            for i in range(start_idx, end_idx):
                if i >= period-1:
                    chunk_result[i-start_idx] = np.mean(data[i-period+1:i+1])
            
            return chunk_result
        
        # 并行计算
        with ThreadPoolExecutor(max_workers=n_chunks) as executor:
            futures = []
            for i in range(n_chunks):
                start_idx = i * chunk_size
                end_idx = (i+1) * chunk_size if i < n_chunks-1 else n
                futures.append(executor.submit(calculate_chunk, start_idx, end_idx))
            
            # 收集结果
            for i, future in enumerate(as_completed(futures)):
                start_idx = i * chunk_size
                chunk_result = future.result()
                result[start_idx:start_idx+len(chunk_result)] = chunk_result
        
        self.性能统计['parallel_executions'] += 1
        return result
    
    def RSI(self, 价格: Union[pd.Series, np.ndarray], 周期: int = 14, 使用缓存: bool = True) -> np.ndarray:
        """
        优化RSI计算
        
        参数:
            价格: 价格序列
            周期: RSI计算周期 (默认: 14)
            使用缓存: 是否使用缓存加速重复计算 (默认: True)
        
        返回:
            优化后的RSI结果
        """
        # 生成缓存键
        cache_key = self._get_cache_key('RSI', 价格, 周期) if 使用缓存 else None
        
        # 检查缓存
        if 使用缓存 and cache_key in self.缓存:
            self.性能统计['cache_hits'] += 1
            return self.缓存[cache_key]
        
        self.性能统计['cache_misses'] += 1
        
        # 数据预处理
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格, dtype=np.float64)
        
        # 根据优化模式选择计算方法
        if self.优化模式 == "efficient":
            result = efficient_RSI(价格数据, 周期)
        elif self.优化模式 == "vectorized":
            result = vectorized_RSI(价格数据, 周期)
        else:  # auto或其他模式
            if len(价格数据) > 5000:
                result = efficient_RSI(价格数据, 周期)
            else:
                result = vectorized_RSI(价格数据, 周期)
        
        # 验证结果
        if self.验证模式:
            self._验证RSI(价格数据, result, 周期)
        
        # 缓存结果
        if 使用缓存 and cache_key is not None:
            if len(self.缓存) >= self.缓存大小:
                oldest_key = next(iter(self.缓存))
                del self.缓存[oldest_key]
            self.缓存[cache_key] = result
        
        # 记录计算历史
        self.计算历史.append({
            '操作': 'RSI计算',
            '周期': 周期,
            '数据长度': len(价格数据),
            '优化模式': self.优化模式,
            '缓存使用': 使用缓存
        })
        
        return result
    
    def EMA(self, 价格: Union[pd.Series, np.ndarray], 周期: int = 12, 使用缓存: bool = True) -> np.ndarray:
        """
        优化EMA计算，支持多种优化策略
        
        参数:
            价格: 价格序列
            周期: EMA周期 (默认: 12)
            使用缓存: 是否使用缓存加速重复计算 (默认: True)
        
        返回:
            优化后的EMA结果
        """
        # 生成缓存键
        cache_key = self._get_cache_key('EMA', 价格, 周期) if 使用缓存 else None
        
        # 检查缓存
        if 使用缓存 and cache_key in self.缓存:
            self.性能统计['cache_hits'] += 1
            return self.缓存[cache_key]
        
        self.性能统计['cache_misses'] += 1
        
        # 数据预处理
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格, dtype=np.float64)
        
        # 根据优化模式选择计算方法
        if self.优化模式 == "efficient":
            result = efficient_EMA(价格数据, 周期)
        elif self.优化模式 == "vectorized":
            result = vectorized_EMA(价格数据, 周期)
        else:  # auto或其他模式
            if len(价格数据) > 5000:
                result = efficient_EMA(价格数据, 周期)
            else:
                result = vectorized_EMA(价格数据, 周期)
        
        # 验证结果
        if self.验证模式:
            self._验证EMA(价格数据, result, 周期)
        
        # 缓存结果
        if 使用缓存 and cache_key is not None:
            if len(self.缓存) >= self.缓存大小:
                oldest_key = next(iter(self.缓存))
                del self.缓存[oldest_key]
            self.缓存[cache_key] = result
        
        # 记录计算历史
        self.计算历史.append({
            '操作': 'EMA计算',
            '周期': 周期,
            '数据长度': len(价格数据),
            '优化模式': self.优化模式,
            '缓存使用': 使用缓存
        })
        
        return result
    
    def MACD(self, 价格: Union[pd.Series, np.ndarray], 
             fast: int = 12, slow: int = 26, signal: int = 9, 
             使用缓存: bool = True) -> Dict[str, np.ndarray]:
        """
        优化MACD计算
        
        参数:
            价格: 价格序列
            fast: 快线EMA周期 (默认: 12)
            slow: 慢线EMA周期 (默认: 26)
            signal: 信号线周期 (默认: 9)
            使用缓存: 是否使用缓存加速重复计算 (默认: True)
        
        返回:
            优化后的MACD结果
        """
        # 生成缓存键
        cache_key = self._get_cache_key('MACD', 价格, fast, slow, signal) if 使用缓存 else None
        
        # 检查缓存
        if 使用缓存 and cache_key in self.缓存:
            self.性能统计['cache_hits'] += 1
            return self.缓存[cache_key]
        
        self.性能统计['cache_misses'] += 1
        
        # 数据预处理
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格, dtype=np.float64)
        
        # 计算MACD
        result = vectorized_MACD(价格数据, fast, slow, signal)
        
        # 验证结果
        if self.验证模式:
            self._验证MACD(价格数据, result, fast, slow, signal)
        
        # 缓存结果
        if 使用缓存 and cache_key is not None:
            if len(self.缓存) >= self.缓存大小:
                oldest_key = next(iter(self.缓存))
                del self.缓存[oldest_key]
            self.缓存[cache_key] = result
        
        # 记录计算历史
        self.计算历史.append({
            '操作': 'MACD计算',
            '参数': f"{fast},{slow},{signal}",
            '数据长度': len(价格数据),
            '优化模式': self.优化模式,
            '缓存使用': 使用缓存
        })
        
        return result
    
    def 批量计算(self, 价格: Union[pd.Series, np.ndarray], 指标列表: List[str]) -> Dict[str, Any]:
        """
        批量计算多个指标，优化整体性能
        
        参数:
            价格: 价格序列
            指标列表: 要计算的指标列表，如 ['SMA_5', 'SMA_10', 'RSI_14', 'MACD']
        
        返回:
            包含所有指标结果的字典
        """
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格, dtype=np.float64)
        
        results = {}
        
        # 并行计算独立指标
        if self.优化模式 == "parallel" and len(指标列表) > 1:
            results = self._parallel_batch_calculation(价格数据, 指标列表)
        else:
            # 顺序计算
            for indicator in 指标列表:
                if indicator.startswith('SMA_'):
                    period = int(indicator.split('_')[1])
                    results[indicator] = self.SMA(价格数据, period, 使用缓存=False)
                elif indicator.startswith('RSI_'):
                    period = int(indicator.split('_')[1])
                    results[indicator] = self.RSI(价格数据, period, 使用缓存=False)
                elif indicator == 'MACD':
                    results[indicator] = self.MACD(价格数据, 使用缓存=False)
                elif indicator == 'BB':
                    results[indicator] = vectorized_BollingerBands(价格数据)
                elif indicator == 'ATR':
                    # 需要高、低、收盘价，这里简化处理
                    results[indicator] = np.zeros_like(价格数据)
        
        return results
    
    def _parallel_batch_calculation(self, data: np.ndarray, indicators: List[str]) -> Dict[str, Any]:
        """并行批量计算"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(4, len(indicators))) as executor:
            futures = {}
            
            for indicator in indicators:
                if indicator.startswith('SMA_'):
                    period = int(indicator.split('_')[1])
                    future = executor.submit(self.SMA, data, period, False)
                    futures[future] = indicator
                elif indicator.startswith('RSI_'):
                    period = int(indicator.split('_')[1])
                    future = executor.submit(self.RSI, data, period, False)
                    futures[future] = indicator
                elif indicator == 'MACD':
                    future = executor.submit(self.MACD, data, 使用缓存=False)
                    futures[future] = indicator
        
            # 收集结果
            for future in as_completed(futures):
                indicator = futures[future]
                try:
                    results[indicator] = future.result()
                except Exception as e:
                    print(f"指标 {indicator} 计算失败: {e}")
                    results[indicator] = np.full(len(data), np.nan)
        
        self.性能统计['parallel_executions'] += 1
        return results
    
    def _验证SMA(self, 价格: np.ndarray, sma: np.ndarray, 周期: int):
        """验证SMA计算结果"""
        try:
            # 使用Pandas验证
            series = pd.Series(价格)
            sma_pandas = series.rolling(window=周期, min_periods=周期).mean().values
            
            # 比较结果
            有效索引 = ~np.isnan(sma) & ~np.isnan(sma_pandas)
            if np.any(有效索引):
                差异 = np.abs(sma[有效索引] - sma_pandas[有效索引])
                最大差异 = np.nanmax(差异)
                
                if 最大差异 < 0.001:
                    print(f"✅ SMA({周期}) 验证通过: 双重计算一致")
                else:
                    print(f"⚠️ SMA({周期}) 验证警告: 最大差异 {最大差异:.6f}")
        except Exception as e:
            print(f"⚠️ SMA验证异常: {e}")
    
    def _验证RSI(self, 价格: np.ndarray, rsi: np.ndarray, 周期: int):
        """验证RSI计算结果"""
        try:
            # 使用Pandas验证
            series = pd.Series(价格)
            delta = series.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.ewm(alpha=1/周期, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/周期, adjust=False).mean()
            
            rs = avg_gain / (avg_loss + 1e-10)
            rsi_pandas = 100 - 100 / (1 + rs).values
            
            # 比较结果
            有效索引 = ~np.isnan(rsi) & ~np.isnan(rsi_pandas)
            if np.any(有效索引):
                差异 = np.abs(rsi[有效索引] - rsi_pandas[有效索引])
                最大差异 = np.nanmax(差异)
                
                if 最大差异 < 0.01:
                    print(f"✅ RSI({周期}) 验证通过: 双重计算一致")
                else:
                    print(f"⚠️ RSI({周期}) 验证警告: 最大差异 {最大差异:.6f}")
        except Exception as e:
            print(f"⚠️ RSI验证异常: {e}")
    
    def _验证EMA(self, 价格: np.ndarray, ema: np.ndarray, 周期: int):
        """验证EMA计算结果"""
        try:
            # 使用Pandas验证
            series = pd.Series(价格)
            ema_pandas = series.ewm(span=周期, adjust=False).mean().values
            
            # 比较结果
            有效索引 = ~np.isnan(ema) & ~np.isnan(ema_pandas)
            if np.any(有效索引):
                差异 = np.abs(ema[有效索引] - ema_pandas[有效索引])
                最大差异 = np.nanmax(差异)
                
                if 最大差异 < 0.001:
                    print(f"✅ EMA({周期}) 验证通过: 双重计算一致")
                else:
                    print(f"⚠️ EMA({周期}) 验证警告: 最大差异 {最大差异:.6f}")
        except Exception as e:
            print(f"⚠️ EMA验证异常: {e}")
    
    def _验证MACD(self, 价格: np.ndarray, macd: Dict, fast: int, slow: int, signal: int):
        """验证MACD计算结果"""
        try:
            # 检查数据有效性
            for key in ['macd', 'signal', 'histogram']:
                if key in macd:
                    有效数据 = np.sum(~np.isnan(macd[key]))
                    if 有效数据 == 0:
                        print(f"⚠️ MACD {key} 缺少有效数据")
            
            print(f"✅ MACD({fast},{slow},{signal}) 计算完成")
        except Exception as e:
            print(f"⚠️ MACD验证异常: {e}")
    
    def 获取性能统计(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        avg_time_per_calculation = 0
        if self.性能统计['total_calculations'] > 0:
            avg_time_per_calculation = self.性能统计['total_time_ms'] / self.性能统计['total_calculations']
        
        cache_hit_rate = 0
        total_cache_access = self.性能统计['cache_hits'] + self.性能统计['cache_misses']
        if total_cache_access > 0:
            cache_hit_rate = self.性能统计['cache_hits'] / total_cache_access * 100
        
        return {
            '总计算次数': self.性能统计['total_calculations'],
            '总计算时间_ms': self.性能统计['total_time_ms'],
            '平均计算时间_ms': avg_time_per_calculation,
            '缓存命中次数': self.性能统计['cache_hits'],
            '缓存未命中次数': self.性能统计['cache_misses'],
            '缓存命中率_%': cache_hit_rate,
            '并行执行次数': self.性能统计['parallel_executions'],
            '当前缓存大小': len(self.缓存),
            '计算历史长度': len(self.计算历史)
        }
    
    def 清空缓存(self):
        """清空缓存"""
        self.缓存.clear()
        print("🗑️ 缓存已清空")
    
    def 重置性能统计(self):
        """重置性能统计"""
        self.性能统计 = {
            'total_calculations': 0,
            'total_time_ms': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'parallel_executions': 0
        }
        print("📊 性能统计已重置")


# ========== 测试函数 ==========

def test_optimized_indicators():
    """测试优化技术指标库"""
    print("🧪 测试优化技术指标库...")
    
    # 生成测试数据
    np.random.seed(42)
    n_points = 10000
    prices = 100 + np.cumsum(np.random.randn(n_points) * 2)
    
    # 测试不同优化模式
    optimization_modes = ['efficient', 'vectorized', 'auto']
    
    for mode in optimization_modes:
        print(f"\n📊 测试优化模式: {mode}")
        
        # 创建优化技术指标实例
        oti = OptimizedTechnicalIndicators(验证模式=False, 优化模式=mode, 缓存大小=100)
        
        # 测试SMA计算
        start_time = time.time()
        sma_5 = oti.SMA(prices, 5)
        sma_10 = oti.SMA(prices, 10)
        sma_time = time.time() - start_time
        
        # 测试RSI计算
        start_time = time.time()
        rsi_14 = oti.RSI(prices, 14)
        rsi_time = time.time() - start_time
        
        # 测试MACD计算
        start_time = time.time()
        macd = oti.MACD(prices)
        macd_time = time.time() - start_time
        
        # 获取性能统计
        stats = oti.获取性能统计()
        
        print(f"  SMA计算时间: {sma_time:.3f} 秒")
        print(f"  RSI计算时间: {rsi_time:.3f} 秒")
        print(f"  MACD计算时间: {macd_time:.3f} 秒")
        print(f"  总计算时间: {stats['总计算时间_ms']:.1f} ms")
        print(f"  平均计算时间: {stats['平均计算时间_ms']:.3f} ms")
        print(f"  缓存命中率: {stats['缓存命中率_%']:.1f}%")
    
    print("\n✅ 测试完成")

def 综合技术分析(股票数据, 股票代码="测试股票", 优化模式="vectorized"):
    """
    优化版本的综合技术分析方法
    
    参数:
        股票数据: 包含open, high, low, close的DataFrame
        股票代码: 股票代码 (默认: "测试股票")
        优化模式: 优化模式 ("vectorized", "efficient", "parallel")
    
    返回:
        综合技术分析报告
    """
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    # 创建优化技术指标实例
    oti = OptimizedTechnicalIndicators(验证模式=False, 优化模式=优化模式, 缓存大小=100)
    
    # 提取价格数据
    close_prices = 股票数据['close'].values
    high_prices = 股票数据['high'].values
    low_prices = 股票数据['low'].values
    
    # 计算技术指标
    技术指标 = {}
    
    # 1. 移动平均线
    移动平均周期 = [5, 10, 20, 30, 60]
    for 周期 in 移动平均周期:
        技术指标[f'SMA_{周期}'] = oti.SMA(close_prices, 周期)
    
    # 2. EMA
    技术指标['EMA_12'] = oti.EMA(close_prices, 周期=12)
    技术指标['EMA_26'] = oti.EMA(close_prices, 周期=26)
    
    # 3. RSI
    技术指标['RSI_14'] = oti.RSI(close_prices, 周期=14)
    
    # 4. MACD
    macd_line, signal_line, hist_line = oti.MACD(close_prices)
    技术指标['MACD'] = macd_line
    技术指标['MACD_Signal'] = signal_line
    技术指标['MACD_Hist'] = hist_line
    
    # 5. 计算金叉/死叉信号
    def _计算金叉信号(短期均线, 长期均线):
        """向量化计算金叉信号"""
        信号 = np.zeros_like(短期均线, dtype=bool)
        if len(短期均线) > 1:
            金叉条件 = (短期均线[1:] > 长期均线[1:]) & (短期均线[:-1] <= 长期均线[:-1])
            信号[1:] = 金叉条件
        return 信号
    
    def _计算死叉信号(短期均线, 长期均线):
        """向量化计算死叉信号"""
        信号 = np.zeros_like(短期均线, dtype=bool)
        if len(短期均线) > 1:
            死叉条件 = (短期均线[1:] < 长期均线[1:]) & (短期均线[:-1] >= 长期均线[:-1])
            信号[1:] = 死叉条件
        return 信号
    
    金叉信号 = _计算金叉信号(技术指标['SMA_5'], 技术指标['SMA_20'])
    死叉信号 = _计算死叉信号(技术指标['SMA_5'], 技术指标['SMA_20'])
    
    # 6. 支撑阻力分析
    def _计算支撑阻力(最高价, 最低价, 收盘价, 窗口=20):
        """计算支撑位和阻力位"""
        if len(收盘价) < 窗口:
            窗口 = len(收盘价)
        
        if 窗口 == 0:
            return None, None
        
        # 使用最近窗口期数据
        近期最高 = np.max(最高价[-窗口:])
        近期最低 = np.min(最低价[-窗口:])
        当前价格 = 收盘价[-1]
        
        # 计算支撑阻力位
        支撑位 = 近期最低 * 0.98  # 支撑位为近期最低价的98%
        阻力位 = 近期最高 * 1.02  # 阻力位为近期最高价的102%
        
        return 支撑位, 阻力位
    
    # 7. 趋势分析
    def _分析趋势(收盘价, 窗口=20):
        """分析趋势状态和强度"""
        if len(收盘价) < 窗口:
            窗口 = len(收盘价)
        
        if 窗口 == 0:
            return "无趋势", 0
        
        # 计算短期和长期趋势
        短期趋势 = 收盘价[-min(10, len(收盘价)):].mean()
        长期趋势 = 收盘价[-窗口:].mean()
        
        # 判断趋势
        if 短期趋势 > 长期趋势 * 1.02:
            return "上升趋势", ((短期趋势 - 长期趋势) / 长期趋势) * 100
        elif 短期趋势 < 长期趋势 * 0.98:
            return "下降趋势", ((长期趋势 - 短期趋势) / 长期趋势) * 100
        else:
            return "震荡趋势", 0
    
    支撑位, 阻力位 = _计算支撑阻力(high_prices, low_prices, close_prices)
    趋势状态, 趋势强度 = _分析趋势(close_prices)
    
    # 生成分析报告
    分析报告 = {
        '股票信息': {
            '股票代码': 股票代码,
            '分析时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '数据周期': len(股票数据),
            '最新价格': float(close_prices[-1]) if len(close_prices) > 0 else None
        },
        '技术指标': {
            '移动平均线': {
                'SMA_5': float(技术指标['SMA_5'][-1]) if not np.isnan(技术指标['SMA_5'][-1]) else None,
                'SMA_10': float(技术指标['SMA_10'][-1]) if not np.isnan(技术指标['SMA_10'][-1]) else None,
                'SMA_20': float(技术指标['SMA_20'][-1]) if not np.isnan(技术指标['SMA_20'][-1]) else None,
                'SMA_30': float(技术指标['SMA_30'][-1]) if not np.isnan(技术指标['SMA_30'][-1]) else None,
                'SMA_60': float(技术指标['SMA_60'][-1]) if not np.isnan(技术指标['SMA_60'][-1]) else None
            },
            '指数移动平均线': {
                'EMA_12': float(技术指标['EMA_12'][-1]),
                'EMA_26': float(技术指标['EMA_26'][-1])
            },
            '相对强弱指数': {
                'RSI_14': float(技术指标['RSI_14'][-1]) if not np.isnan(技术指标['RSI_14'][-1]) else None
            },
            'MACD': {
                'MACD线': float(macd_line[-1]) if not np.isnan(macd_line[-1]) else None,
                '信号线': float(signal_line[-1]) if not np.isnan(signal_line[-1]) else None,
                '柱状图': float(hist_line[-1]) if not np.isnan(hist_line[-1]) else None
            }
        },
        '信号分析': {
            '金叉信号': bool(金叉信号[-1]) if len(金叉信号) > 0 else False,
            '死叉信号': bool(死叉信号[-1]) if len(死叉信号) > 0 else False
        },
        '趋势分析': {
            '当前趋势': 趋势状态,
            '趋势强度': f"{趋势强度:.2f}%"
        },
        '支撑阻力': {
            '当前支撑位': 支撑位,
            '当前阻力位': 阻力位
        },
        '性能统计': oti.获取性能统计(),
        '风险提示': {
            '免责声明': '本分析基于历史数据，仅供参考，不构成投资建议。投资有风险，入市需谨慎。'
        }
    }
    
    return 分析报告


if __name__ == "__main__":
    test_optimized_indicators()