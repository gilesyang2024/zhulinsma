#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 性能基准测试
量化评估各指标计算的加速效果
"""

import time
import numpy as np
from typing import Callable, Dict, List, Optional


class PerformanceBenchmark:
    """
    性能基准测试器

    使用方式：
        bench = PerformanceBenchmark()
        report = bench.运行全量基准测试(数据量=10000)
        bench.打印报告(report)
    """

    def __init__(self, 重复次数: int = 5):
        self.重复次数 = 重复次数

    def 测量函数(self, func: Callable, *args, **kwargs) -> float:
        """测量函数执行时间（毫秒），取最小值以减少系统抖动影响"""
        时间列表 = []
        for _ in range(self.重复次数):
            t0 = time.perf_counter()
            func(*args, **kwargs)
            时间列表.append((time.perf_counter() - t0) * 1000)
        return min(时间列表)

    def 运行全量基准测试(self, 数据量: int = 10000) -> Dict:
        """
        运行全量基准测试，对比传统实现与向量化实现

        返回:
            包含各指标加速倍数的报告字典
        """
        from .vectorized_engine import VectorizedEngine as VE
        from ..indicators.technical_indicators import TechnicalIndicators

        np.random.seed(42)
        收盘价 = np.cumsum(np.random.randn(数据量)) + 100
        最高价 = 收盘价 + np.abs(np.random.randn(数据量)) * 0.5
        最低价 = 收盘价 - np.abs(np.random.randn(数据量)) * 0.5
        成交量 = np.abs(np.random.randn(数据量)) * 1000000 + 500000

        传统 = TechnicalIndicators(验证模式=False)
        报告 = {"数据量": 数据量, "重复次数": self.重复次数, "指标结果": {}}

        # SMA 对比
        传统时间 = self.测量函数(传统.SMA, 收盘价, 20)
        向量时间 = self.测量函数(VE.sma, 收盘价, 20)
        报告["指标结果"]["SMA20"] = self._构造结果(传统时间, 向量时间)

        # RSI 对比
        传统时间 = self.测量函数(传统.RSI, 收盘价, 14)
        向量时间 = self.测量函数(VE.rsi, 收盘价, 14)
        报告["指标结果"]["RSI14"] = self._构造结果(传统时间, 向量时间)

        # MACD 对比
        传统时间 = self.测量函数(传统.MACD, 收盘价)
        向量时间 = self.测量函数(VE.macd, 收盘价)
        报告["指标结果"]["MACD"] = self._构造结果(传统时间, 向量时间)

        # 布林带对比
        传统时间 = self.测量函数(传统.BollingerBands, 收盘价)
        向量时间 = self.测量函数(VE.bollinger_bands, 收盘价)
        报告["指标结果"]["布林带"] = self._构造结果(传统时间, 向量时间)

        # ATR 对比
        传统时间 = self.测量函数(传统.ATR, 最高价, 最低价, 收盘价)
        向量时间 = self.测量函数(VE.atr, 最高价, 最低价, 收盘价)
        报告["指标结果"]["ATR14"] = self._构造结果(传统时间, 向量时间)

        # 综合统计
        加速列表 = [v["加速倍数"] for v in 报告["指标结果"].values()]
        报告["综合统计"] = {
            "平均加速倍数": round(np.mean(加速列表), 1),
            "最大加速倍数": round(max(加速列表), 1),
            "最小加速倍数": round(min(加速列表), 1),
        }

        return 报告

    def 打印报告(self, 报告: Dict) -> None:
        """格式化打印基准测试报告"""
        print(f"\n{'='*60}")
        print(f"  竹林司马 (Zhulinsma) 性能基准测试报告")
        print(f"  数据量: {报告['数据量']:,} 条 | 重复: {报告['重复次数']} 次")
        print(f"{'='*60}")
        print(f"{'指标':<12} {'传统(ms)':<12} {'向量化(ms)':<14} {'加速倍数'}")
        print(f"{'-'*60}")
        for 指标, 数据 in 报告["指标结果"].items():
            print(
                f"{指标:<12} {数据['传统实现ms']:<12.3f} "
                f"{数据['向量化ms']:<14.3f} {数据['加速倍数']:.1f}x"
            )
        统计 = 报告["综合统计"]
        print(f"{'='*60}")
        print(f"  平均加速: {统计['平均加速倍数']}x | 最大: {统计['最大加速倍数']}x")
        print(f"{'='*60}\n")

    @staticmethod
    def _构造结果(传统ms: float, 向量ms: float) -> Dict:
        加速 = 传统ms / (向量ms + 1e-6)
        return {
            "传统实现ms": round(传统ms, 4),
            "向量化ms": round(向量ms, 4),
            "加速倍数": round(加速, 1),
        }
