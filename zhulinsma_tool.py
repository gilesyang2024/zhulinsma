#!/usr/bin/env python3
"""
竹林司马核心工具模块 - 桥接层
版本: 1.0.0
日期: 2026年4月14日
作者: 杨总的技术团队
位置: 广州

本模块作为 TechnicalAPI 的桥接层，将 zhulinsma.core 的实际实现
适配为 TechnicalAPI 期望的接口签名。

竹林司马(V1) → TechnicalIndicators (基础版)
竹林司马V2(V2) → OptimizedTechnicalIndicators (优化版)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any

# 导入核心指标模块
from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
from zhulinsma.core.indicators.optimized_indicators import (
    OptimizedTechnicalIndicators,
    vectorized_BollingerBands
)


class 竹林司马:
    """
    竹林司马核心工具 V1
    
    桥接 TechnicalIndicators 到 TechnicalAPI 期望的接口:
    - SMA(价格数组, 周期=N, 验证=bool) → TechnicalIndicators.SMA
    - EMA(价格数组, 周期=N, 验证=bool) → TechnicalIndicators.EMA
    """

    def __init__(self, 验证模式: bool = True):
        self._engine = TechnicalIndicators(验证模式=验证模式, 严格模式=True)
        self.验证模式 = 验证模式

    # ---------- SMA ----------
    def SMA(self, 价格: np.ndarray, 周期: int = 20, 验证: bool = None) -> np.ndarray:
        """简单移动平均线 - 桥接到 TechnicalIndicators.SMA"""
        return self._engine.SMA(价格, period=周期)

    # ---------- EMA ----------
    def EMA(self, 价格: np.ndarray, 周期: int = 12, 验证: bool = None) -> np.ndarray:
        """指数移动平均线 - 桥接到 TechnicalIndicators.EMA"""
        return self._engine.EMA(价格, period=周期)

    # ---------- RSI (V1 也提供) ----------
    def RSI(self, 价格: np.ndarray, 周期: int = 14, 验证: bool = None) -> np.ndarray:
        """相对强弱指数 - 桥接到 TechnicalIndicators.RSI"""
        return self._engine.RSI(价格, 周期=周期)

    # ---------- MACD (V1 也提供) ----------
    def MACD(self, 价格: np.ndarray, fast_period: int = 12, slow_period: int = 26,
             signal_period: int = 9, 验证: bool = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD - 桥接并返回三元组"""
        result = self._engine.MACD(价格, fast=fast_period, slow=slow_period, signal=signal_period)
        return result['macd'], result['signal'], result['histogram']

    # ---------- 布林带 (V1 也提供) ----------
    def 布林带(self, 价格: np.ndarray, 周期: int = 20, 标准差倍数: float = 2.0,
               验证: bool = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """布林带 - 桥接并返回三元组 (中轨, 上轨, 下轨)"""
        result = self._engine.BollingerBands(价格, period=周期, std_dev=标准差倍数)
        return result['middle'], result['upper'], result['lower']


class 竹林司马V2:
    """
    竹林司马核心工具 V2 (优化版)
    
    桥接 OptimizedTechnicalIndicators 到 TechnicalAPI 期望的接口:
    - RSI(价格数组, 周期=N, 验证=bool) → OptimizedTechnicalIndicators.RSI
    - MACD(价格数组, fast_period, slow_period, signal_period, 验证) → 返回三元组
    - 布林带(价格数组, 周期, 标准差倍数, 验证) → 返回三元组
    """

    def __init__(self, 验证模式: bool = True):
        self._engine = OptimizedTechnicalIndicators(
            验证模式=验证模式,
            优化模式='auto',
            缓存大小=1000
        )
        self.验证模式 = 验证模式

    # ---------- SMA ----------
    def SMA(self, 价格: np.ndarray, 周期: int = 20, 验证: bool = None) -> np.ndarray:
        """SMA - 桥接到优化版"""
        return self._engine.SMA(价格, 周期=周期, 使用缓存=True)

    # ---------- EMA ----------
    def EMA(self, 价格: np.ndarray, 周期: int = 12, 验证: bool = None) -> np.ndarray:
        """EMA - 桥接到优化版"""
        return self._engine.EMA(价格, 周期=周期, 使用缓存=True)

    # ---------- RSI ----------
    def RSI(self, 价格: np.ndarray, 周期: int = 14, 验证: bool = None) -> np.ndarray:
        """RSI - 桥接到优化版"""
        return self._engine.RSI(价格, 周期=周期, 使用缓存=True)

    # ---------- MACD ----------
    def MACD(self, 价格: np.ndarray, fast_period: int = 12, slow_period: int = 26,
             signal_period: int = 9, 验证: bool = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD - 桥接并返回三元组 (MACD线, 信号线, 柱状图)"""
        result = self._engine.MACD(价格, fast=fast_period, slow=slow_period, signal=signal_period)
        return result['macd'], result['signal'], result['histogram']

    # ---------- 布林带 ----------
    def 布林带(self, 价格: np.ndarray, 周期: int = 20, 标准差倍数: float = 2.0,
               验证: bool = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """布林带 - 桥接并返回三元组 (中轨, 上轨, 下轨)"""
        result = vectorized_BollingerBands(价格, period=周期, std_dev=标准差倍数)
        return result['middle'], result['upper'], result['lower']

    # ---------- 批量计算 ----------
    def 批量计算(self, 价格: np.ndarray, 指标列表: List[str]) -> Dict[str, Any]:
        """批量计算多个指标"""
        return self._engine.批量计算(价格, 指标列表)

    # ---------- 性能统计 ----------
    def 获取性能统计(self) -> Dict[str, Any]:
        """获取性能统计"""
        return self._engine.获取性能统计()


# ========== 模块测试 ==========

if __name__ == "__main__":
    print("🧪 竹林司马核心工具模块测试")
    print("=" * 60)

    # 生成测试数据
    np.random.seed(42)
    测试价格 = (100 + np.random.randn(100).cumsum()).tolist()

    # 测试 V1
    print("\n--- V1 基础版 ---")
    工具 = 竹林司马(验证模式=False)
    sma = 工具.SMA(np.array(测试价格), 周期=20, 验证=False)
    ema = 工具.EMA(np.array(测试价格), 周期=12, 验证=False)
    rsi = 工具.RSI(np.array(测试价格), 周期=14, 验证=False)
    macd线, 信号线, 柱状图 = 工具.MACD(np.array(测试价格), fast_period=12, slow_period=26, signal_period=9, 验证=False)
    中轨, 上轨, 下轨 = 工具.布林带(np.array(测试价格), 周期=20, 标准差倍数=2.0, 验证=False)

    print(f"  SMA(20) 最新值: {sma[-1]:.2f}")
    print(f"  EMA(12) 最新值: {ema[-1]:.2f}")
    print(f"  RSI(14)  最新值: {rsi[-1]:.2f}")
    print(f"  MACD     最新值: {macd线[-1]:.4f}")
    print(f"  布林带中轨最新值: {中轨[-1]:.2f}")

    # 测试 V2
    print("\n--- V2 优化版 ---")
    工具V2 = 竹林司马V2(验证模式=False)
    sma2 = 工具V2.SMA(np.array(测试价格), 周期=20)
    rsi2 = 工具V2.RSI(np.array(测试价格), 周期=14)
    macd线2, 信号线2, 柱状图2 = 工具V2.MACD(np.array(测试价格), fast_period=12, slow_period=26, signal_period=9)
    中轨2, 上轨2, 下轨2 = 工具V2.布林带(np.array(测试价格), 周期=20, 标准差倍数=2.0)

    print(f"  SMA(20) 最新值: {sma2[-1]:.2f}")
    print(f"  RSI(14)  最新值: {rsi2[-1]:.2f}")
    print(f"  MACD     最新值: {macd线2[-1]:.4f}")
    print(f"  布林带中轨最新值: {中轨2[-1]:.2f}")

    # 验证 V1/V2 结果一致性
    print("\n--- V1 vs V2 一致性验证 ---")
    sma_diff = np.nanmax(np.abs(sma - sma2))
    rsi_diff = np.nanmax(np.abs(rsi - rsi2))
    macd_diff = np.nanmax(np.abs(macd线 - macd线2))
    bb_diff = np.nanmax(np.abs(中轨 - 中轨2))
    print(f"  SMA 差异: {sma_diff:.6f} {'✅' if sma_diff < 0.01 else '⚠️'}")
    print(f"  RSI 差异: {rsi_diff:.6f} {'✅' if rsi_diff < 0.5 else '⚠️'}")
    print(f"  MACD 差异: {macd_diff:.6f} {'✅' if macd_diff < 0.01 else '⚠️'}")
    print(f"  布林带差异: {bb_diff:.6f} {'✅' if bb_diff < 0.01 else '⚠️'}")

    print("\n🎉 竹林司马核心工具模块测试完成!")
