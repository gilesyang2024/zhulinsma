#!/usr/bin/env python3
"""
TrendAnalyzer - 趋势分析引擎
竹林司马 · 竹林司马AI选股分析引擎
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import numpy as np
import pandas as pd

from ..indicators.technical_indicators import TechnicalIndicators, IndicatorsBundle


@dataclass
class TrendReport:
    long_trend: str
    medium_trend: str
    short_trend: str
    trend_strength: float
    trend_grade: str
    support_levels: List[float]
    resistance_levels: List[float]
    current_position: float
    momentum: str
    description: str


class TrendAnalyzer:
    def __init__(self):
        self.ti = TechnicalIndicators()

    def analyze(self, df: pd.DataFrame, indicators: IndicatorsBundle) -> TrendReport:
        n = len(df)
        if n < 60:
            raise ValueError(f"趋势分析需要至少60日数据，当前仅{n}日")

        close = np.array(df["close"].values, dtype=float)
        high = np.array(df["high"].values, dtype=float)
        low = np.array(df["low"].values, dtype=float)
        current_price = indicators.current_price
        ma5 = indicators.ma.ma5
        ma10 = indicators.ma.ma10
        ma20 = indicators.ma.ma20
        ma60 = indicators.ma.ma60
        ma120 = indicators.ma.ma120

        # 长期趋势
        long_trend = "震荡"
        if ma120 and ma60:
            if current_price > ma120 > ma60:
                long_trend = "上升"
            elif current_price < ma120 < ma60:
                long_trend = "下降"

        # 中期趋势
        close_20 = close[-20:]
        slope_20 = (close_20[-1] - close_20[0]) / (close_20[0] + 1e-10) * 100
        medium_trend = "上升" if slope_20 > 5 else ("下降" if slope_20 < -5 else "震荡")

        # 短期趋势
        close_10 = close[-10:]
        slope_10 = (close_10[-1] - close_10[0]) / (close_10[0] + 1e-10) * 100
        short_trend = "上升" if slope_10 > 3 else ("下降" if slope_10 < -3 else "震荡")

        # 趋势强度
        trend_strength = self._calc_trend_strength(close[-20:])
        grade = "A" if trend_strength >= 80 else ("B" if trend_strength >= 60 else ("C" if trend_strength >= 40 else "D"))

        # 支撑阻力位
        support_levels, resistance_levels = [], []
        for ma_val in [ma5, ma10, ma20, ma60]:
            if ma_val:
                (support_levels if ma_val < current_price
                 else resistance_levels).append(round(ma_val, 2))
        support_levels.append(round(indicators.bollinger.lower, 2))
        resistance_levels.append(round(indicators.bollinger.upper, 2))

        # 近期高低点
        recent_highs = sorted(high[-60:])[-5:]
        recent_lows = sorted(low[-60:])[:5]
        for h in recent_highs:
            if h > current_price * 1.02:
                resistance_levels.append(round(h, 2))
                break
        for lo in reversed(recent_lows):
            if lo < current_price * 0.98:
                support_levels.append(round(lo, 2))
                break

        support_levels = sorted(set(support_levels), reverse=True)[:4]
        resistance_levels = sorted(set(resistance_levels))[:4]

        # 区间位置
        low_60, high_60 = float(np.min(close[-60:])), float(np.max(close[-60:]))
        position = (current_price - low_60) / (high_60 - low_60) * 100 if high_60 != low_60 else 50.0

        # 动量
        slope_5 = float((close[-1] - close[-6]) / (close[-6] + 1e-10) * 100) if n >= 6 else 0
        slope_prev = float((close[-6] - close[-11]) / (close[-11] + 1e-10) * 100) if n >= 11 else 0
        momentum = "加速" if slope_5 > slope_prev * 1.2 else ("减速" if slope_5 < slope_prev * 0.8 else "平稳")

        return TrendReport(
            long_trend=long_trend,
            medium_trend=medium_trend,
            short_trend=short_trend,
            trend_strength=round(trend_strength, 1),
            trend_grade=grade,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            current_position=round(position, 1),
            momentum=momentum,
            description=f"中长期{'多头' if medium_trend=='上升' else '空头' if medium_trend=='下降' else '震荡'}，"
                        f"60日区间{position:.0f}%分位，短期动量{momentum}，趋势{trend_strength:.0f}分",
        )

    def _calc_trend_strength(self, prices: np.ndarray) -> float:
        if len(prices) < 5:
            return 30.0
        x = np.arange(len(prices))
        try:
            coeffs = np.polyfit(x, prices, 1)
            fit = np.polyval(coeffs, x)
            ss_res = np.sum((prices - fit) ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r2 = 1 - ss_res / (ss_tot + 1e-10)
            return max(0.0, min(100.0, r2 * 100))
        except Exception:
            return 30.0
