#!/usr/bin/env python3
"""
TechnicalIndicators - A股技术指标核心引擎
竹林司马 · 竹林司马AI选股分析引擎

支持：
  - 移动平均线（SMA / EMA / WMA）
  - MACD（标准参数 12,26,9）
  - KDJ（标准参数 9,3,3）
  - RSI（标准参数 14）
  - 布林带（标准参数 20,2）
  - ATR / OBV / WR / CCI / DMI
  - 趋势识别 / 背离检测
"""

from __future__ import annotations

import sys
import os
import math
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# 数据结构定义
# ─────────────────────────────────────────────


@dataclass
class MACDResult:
    macd: float
    signal: float
    histogram: float
    bullish: bool  # MACD柱 > 0
    golden_cross: bool  # MACD上穿signal（金叉）
    death_cross: bool  # MACD下穿signal（死叉）
    divergence: Optional[str] = None  # 顶背离/底背离/无


@dataclass
class KDJResult:
    k: float
    d: float
    j: float
    golden_cross: bool
    death_cross: bool
    overbought: bool  # KDJ > 80
    oversold: bool  # KDJ < 20
    status: str  # 超买/超卖/中性


@dataclass
class RSIResult:
    rsi: float
    status: str  # 超买(>70)/超卖(<30)/中性


@dataclass
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    position: float  # 价格在布林带中的位置(0~1)
    squeeze: bool  # 布林收口（带宽创N日新低）


@dataclass
class MAResult:
    ma5: Optional[float]
    ma10: Optional[float]
    ma20: Optional[float]
    ma60: Optional[float]
    ma120: Optional[float]
    golden_fan: bool  # 多头排列（5>10>20>60）
    bearish_fan: bool  # 空头排列
    trend: str  # 多头/空头/震荡


@dataclass
class IndicatorsBundle:
    """所有指标的聚合结果"""
    # 价格数据
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    prev_close: float
    change_pct: float
    volume: float
    amount: float
    # K线基础
    amplitude: float
    turnover: float
    # 均线
    ma: MAResult
    # MACD
    macd: MACDResult
    # KDJ
    kdj: KDJResult
    # RSI
    rsi: RSIResult
    # 布林带
    bollinger: BollingerResult
    # 辅助
    atr: float
    obv_trend: str
    # 评级
    tech_score: float  # 技术面评分 0~100
    tech_grade: str   # A/B/C/D


class TechnicalIndicators:
    """
    技术指标计算引擎

    参数:
        验证模式: 是否启用严格参数验证（默认关闭以提高性能）
        严格模式: 是否使用严格的数据质量检查（默认关闭）
    """

    def __init__(self, 验证模式: bool = False, 严格模式: bool = False):
        self.验证模式 = 验证模式
        self.严格模式 = 严格模式

    # ─────────────────────────────────────────
    # 底层数学工具
    # ─────────────────────────────────────────

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均（NumPy向量化，效率高于pandas）"""
        data = np.asarray(data, dtype=float)
        k = 2.0 / (period + 1)
        n = len(data)
        ema = np.empty(n)
        ema[0] = data[0]
        for i in range(1, n):
            ema[i] = data[i] * k + ema[i - 1] * (1 - k)
        return ema

    @staticmethod
    def _sma(data: np.ndarray, period: int) -> np.ndarray:
        """简单移动平均（NumPy向量化）"""
        data = np.asarray(data, dtype=float)
        n = len(data)
        if n < period:
            return np.full(n, np.nan)
        sma = np.empty(n)
        window = period - 1
        sma[:window] = np.nan
        for i in range(window, n):
            sma[i] = np.mean(data[i - window:i + 1])
        return sma

    @staticmethod
    def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range"""
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        n = len(close)
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr2[0] = high[0] - low[0]
        tr3[0] = high[0] - low[0]
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        k = 2.0 / (period + 1)
        atr = np.empty(n)
        atr[0] = tr[0]
        for i in range(1, n):
            atr[i] = tr[i] * k + atr[i - 1] * (1 - k)
        return atr

    @staticmethod
    def _obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """On-Balance Volume"""
        direction = np.where(np.diff(close, prepend=close[0]) > 0, 1, -1)
        return np.cumsum(direction * np.asarray(volume, dtype=float))

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        """RSI 相对强弱指标"""
        close = np.asarray(close, dtype=float)
        deltas = np.diff(close, prepend=close[0])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = TechnicalIndicators._ema(gains, period)
        avg_loss = TechnicalIndicators._ema(losses, period)
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (rs + 1))

    @staticmethod
    def _kdj(
        high: np.ndarray, low: np.ndarray, close: np.ndarray,
        n: int = 9, m1: int = 3, m2: int = 3
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """KDJ 随机指标"""
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        n = min(n, len(close) - 1)
        rsv = np.full_like(close, np.nan)
        for i in range(n, len(close)):
            window_high = np.max(high[i - n + 1:i + 1])
            window_low = np.min(low[i - n + 1:i + 1])
            if window_high != window_low:
                rsv[i] = (close[i] - window_low) / (window_high - window_low) * 100
            else:
                rsv[i] = 50
        k = np.full_like(close, 50.0)
        d = np.full_like(close, 50.0)
        k[n] = 2 / m1 * rsv[n] + (m1 - 2) / m1 * 50
        d[n] = 2 / m2 * k[n] + (m2 - 2) / m2 * 50
        for i in range(n + 1, len(close)):
            k[i] = 2 / m1 * rsv[i] + (m1 - 2) / m1 * k[i - 1]
            d[i] = 2 / m2 * k[i] + (m2 - 2) / m2 * d[i - 1]
        j = 3 * k - 2 * d
        return k, d, j

    # ─────────────────────────────────────────
    # 公开接口
    # ─────────────────────────────────────────

    def SMA(self, data: np.ndarray, period: int) -> np.ndarray:
        """简单移动平均 SMA"""
        return self._sma(data, period)

    def EMA(self, data: np.ndarray, period: int) -> np.ndarray:
        """指数移动平均 EMA"""
        return self._ema(data, period)

    def MACD(
        self,
        close: np.ndarray,
        fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        MACD (Moving Average Convergence Divergence)
        返回: (macd线, signal线, histogram柱)
        """
        close = np.asarray(close, dtype=float)
        ema_fast = self._ema(close, fast)
        ema_slow = self._ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def KDJ(
        self,
        high: np.ndarray, low: np.ndarray, close: np.ndarray,
        n: int = 9, m1: int = 3, m2: int = 3
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """KDJ 随机指标"""
        return self._kdj(high, low, close, n, m1, m2)

    def RSI(self, close: np.ndarray, period: int = 14) -> np.ndarray:
        """RSI 相对强弱指标"""
        return self._rsi(close, period)

    def BOLL(
        self, close: np.ndarray, period: int = 20, std_dev: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        布林带
        返回: (上轨, 中轨, 下轨, 带宽)
        """
        close = np.asarray(close, dtype=float)
        middle = self._sma(close, period)
        rolling_std = pd.Series(close).rolling(period).std().values
        upper = middle + std_dev * rolling_std
        lower = middle - std_dev * rolling_std
        bandwidth = (upper - lower) / (middle + 1e-10)
        return upper, middle, lower, bandwidth

    def ATR(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """ATR 平均真实波幅"""
        return self._atr(high, low, close, period)

    def DMI(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        DMI 趋向指标
        返回: (+DI, -DI, ADX)
        """
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        n = len(close)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)
        for i in range(1, n):
            up = high[i] - high[i - 1]
            down = low[i - 1] - low[i]
            plus_dm[i] = up if up > down and up > 0 else 0
            minus_dm[i] = down if down > up and down > 0 else 0
        tr = self._atr(high, low, close, period)
        plus_di = self._ema(plus_dm / (tr + 1e-10) * 100, period)
        minus_di = self._ema(minus_dm / (tr + 1e-10) * 100, period)
        dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        adx = self._ema(dx, period)
        return plus_di, minus_di, adx

    def CCI(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """CCI 商品通道指标"""
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        tp = (high + low + close) / 3
        sma_tp = self._sma(tp, period)
        mad = np.array([np.mean(np.abs(tp[max(0, i-period+1):i+1] - sma_tp[i]))
                        if not np.isnan(sma_tp[i]) else 0 for i in range(len(tp))])
        cci = (tp - sma_tp) / (0.015 * mad + 1e-10)
        return cci

    def WR(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Williams %R 威廉指标"""
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        wr = np.full_like(close, -50.0)
        for i in range(period - 1, len(close)):
            hh = np.max(high[i - period + 1:i + 1])
            ll = np.min(low[i - period + 1:i + 1])
            if hh != ll:
                wr[i] = (hh - close[i]) / (hh - ll) * -100
        return wr

    # ─────────────────────────────────────────
    # 综合计算：给定DataFrame → IndicatorsBundle
    # ─────────────────────────────────────────

    def compute_all(self, df: pd.DataFrame) -> IndicatorsBundle:
        """
        主入口：给定日K DataFrame，计算所有指标并返回聚合结果

        参数:
            df: 包含 date/open/high/low/close/volume 列的 DataFrame（按时间升序）

        返回:
            IndicatorsBundle 包含所有指标和评分
        """
        n = len(df)
        if n < 60:
            raise ValueError(f"数据不足：需要至少60日数据，当前仅{n}日")

        close = np.array(df["close"].values, dtype=float)
        high = np.array(df["high"].values, dtype=float)
        low = np.array(df["low"].values, dtype=float)
        open_arr = np.array(df["open"].values, dtype=float)
        volume = np.array(df["volume"].values, dtype=float)

        # ── 基础价格数据 ──────────────────────
        current_price = float(close[-1])
        open_price = float(open_arr[-1])
        high_price = float(high[-1])
        low_price = float(low[-1])
        prev_close = float(close[-2]) if n >= 2 else current_price
        change_pct = float((current_price - prev_close) / prev_close * 100)
        vol = float(volume[-1])
        amount = float(df["amount"].values[-1]) if "amount" in df.columns else vol * current_price

        amplitude = float((high_price - low_price) / (prev_close + 1e-10) * 100)
        turnover = float(vol / (float(df["float_share"].values[-1])
                                if "float_share" in df.columns
                                else float(df["volume"].values[-60:-1].mean()) + 1) * 100) if n >= 60 else 0.0

        # ── 均线 ─────────────────────────────
        ma5 = float(self._sma(close, 5)[-1]) if n >= 5 else None
        ma10 = float(self._sma(close, 10)[-1]) if n >= 10 else None
        ma20 = float(self._sma(close, 20)[-1]) if n >= 20 else None
        ma60 = float(self._sma(close, 60)[-1]) if n >= 60 else None
        ma120 = float(self._sma(close, 120)[-1]) if n >= 120 else None
        golden_fan = bool(ma5 > ma10 > ma20 > ma60) if all(x is not None for x in [ma5, ma10, ma20, ma60]) else False
        bearish_fan = bool(ma5 < ma10 < ma20 < ma60) if all(x is not None for x in [ma5, ma10, ma20, ma60]) else False
        if golden_fan:
            ma_trend = "多头"
        elif bearish_fan:
            ma_trend = "空头"
        else:
            ma_trend = "震荡"
        ma_result = MAResult(
            ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60, ma120=ma120,
            golden_fan=golden_fan, bearish_fan=bearish_fan, trend=ma_trend
        )

        # ── MACD ─────────────────────────────
        macd_line, signal_line, histogram = self.MACD(close, 12, 26, 9)
        macd_val = float(macd_line[-1])
        signal_val = float(signal_line[-1])
        hist_val = float(histogram[-1])
        hist_prev = float(histogram[-2]) if n >= 2 else 0.0
        golden_cross = bool(hist_val > 0 and hist_prev <= 0)
        death_cross = bool(hist_val < 0 and hist_prev >= 0)
        bullish = bool(hist_val > 0)

        # 背离检测（简化版：看最近20天）
        divergence = self._detect_divergence(close, histogram, lookback=20)

        macd_result = MACDResult(
            macd=macd_val, signal=signal_val, histogram=hist_val,
            bullish=bullish, golden_cross=golden_cross,
            death_cross=death_cross, divergence=divergence
        )

        # ── KDJ ──────────────────────────────
        k_arr, d_arr, j_arr = self.KDJ(high, low, close, 9, 3, 3)
        k = float(k_arr[-1])
        d = float(d_arr[-1])
        j = float(j_arr[-1])
        k_prev = float(k_arr[-2]) if n >= 2 else k
        d_prev = float(d_arr[-2]) if n >= 2 else d
        kd_golden = bool(k > d and k_prev <= d_prev)
        kd_death = bool(k < d and k_prev >= d_prev)
        overbought = bool(k > 80 or d > 80 or j > 100)
        oversold = bool(k < 20 or d < 20 or j < -20)
        if overbought:
            kdj_status = "超买"
        elif oversold:
            kdj_status = "超卖"
        else:
            kdj_status = "中性"

        kdj_result = KDJResult(
            k=k, d=d, j=j,
            golden_cross=kd_golden, death_cross=kd_death,
            overbought=overbought, oversold=oversold, status=kdj_status
        )

        # ── RSI ──────────────────────────────
        rsi_arr = self.RSI(close, 14)
        rsi = float(rsi_arr[-1])
        if rsi > 70:
            rsi_status = "超买"
        elif rsi < 30:
            rsi_status = "超卖"
        else:
            rsi_status = "中性"

        rsi_result = RSIResult(rsi=rsi, status=rsi_status)

        # ── 布林带 ───────────────────────────
        boll_upper, boll_mid, boll_lower, boll_bw = self.BOLL(close, 20, 2.0)
        b_upper = float(boll_upper[-1])
        b_mid = float(boll_mid[-1])
        b_lower = float(boll_lower[-1])
        b_bw = float(boll_bw[-1])
        # 布林位置
        if b_upper != b_lower:
            boll_pos = float((current_price - b_lower) / (b_upper - b_lower))
        else:
            boll_pos = 0.5
        # 收口检测：最近20天带宽是否创最低
        bw_20d = boll_bw[-20:] if n >= 20 else boll_bw
        bw_min_idx = np.argmin(bw_20d)
        squeeze = bool(bw_min_idx == len(bw_20d) - 1 and b_bw < np.nanmean(bw_20d))

        boll_result = BollingerResult(
            upper=b_upper, middle=b_mid, lower=b_lower,
            bandwidth=b_bw, position=boll_pos, squeeze=squeeze
        )

        # ── ATR ──────────────────────────────
        atr_arr = self.ATR(high, low, close, 14)
        atr = float(atr_arr[-1])

        # ── OBV趋势 ───────────────────────────
        obv = self._obv(close, volume)
        obv_10d_before = float(obv[-11]) if n >= 11 else float(obv[0])
        obv_trend = "上升" if float(obv[-1]) > obv_10d_before else "下降"

        # ── 技术面评分 ───────────────────────
        score, grade = self._calc_tech_score(
            ma_result, macd_result, kdj_result, rsi_result,
            boll_result, change_pct, close, high, low, volume, n
        )

        return IndicatorsBundle(
            current_price=current_price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            prev_close=prev_close,
            change_pct=change_pct,
            volume=vol,
            amount=amount,
            amplitude=amplitude,
            turnover=turnover,
            ma=ma_result,
            macd=macd_result,
            kdj=kdj_result,
            rsi=rsi_result,
            bollinger=boll_result,
            atr=atr,
            obv_trend=obv_trend,
            tech_score=score,
            tech_grade=grade,
        )

    # ─────────────────────────────────────────
    # 技术面评分（0~100）
    # ─────────────────────────────────────────

    def _calc_tech_score(
        self,
        ma: MAResult,
        macd: MACDResult,
        kdj: KDJResult,
        rsi: RSIResult,
        boll: BollingerResult,
        change_pct: float,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        n: int,
    ) -> Tuple[float, str]:
        """
        技术面综合评分算法
        权重：均线30% + MACD25% + KDJ20% + RSI15% + 布林10%
        """
        score = 0.0

        # ① 均线（30分）
        if ma.golden_fan:
            score += 30
        elif ma.trend == "震荡":
            score += 15
        # 趋势方向加分
        if ma.ma5 is not None and ma.ma60 is not None:
            if close[-1] > ma.ma5 > ma.ma60:
                score += 5  # 价格在所有均线上方
            if close[-1] > close[-20] if n >= 20 else False:
                score += 3  # 20日趋势向上

        # ② MACD（25分）
        if macd.bullish:
            score += 15
        if macd.golden_cross:
            score += 8  # 金叉额外加分
        if macd.histogram > 0 and (len(close) >= 2 and np.diff(close[-2:]).mean() > 0):
            score += 2  # MACD柱扩张

        # ③ KDJ（20分）
        if kdj.golden_cross:
            score += 10
        if kdj.status == "中性":
            score += 8
        if kdj.overbought:
            score -= 5  # 超买扣分
        if kdj.oversold:
            score += 5  # 超卖低位金叉加分

        # ④ RSI（15分）
        if 40 <= rsi.rsi <= 60:
            score += 10  # 中性健康区间
        elif 30 <= rsi.rsi < 40:
            score += 7
        elif rsi.rsi > 70:
            score -= 5
        elif rsi.rsi < 30:
            score -= 3

        # ⑤ 布林带（10分）
        if boll.position < 0.5:  # 价格在中轨下方（低位）
            score += 5
        if boll.squeeze:
            score += 3  # 收口蓄势加分
        if boll.position > 0.9:  # 接近上轨
            score -= 4

        # 今日涨跌修正
        if change_pct > 5:
            score -= 5  # 涨幅过大短线风险
        elif change_pct > 2:
            score -= 2

        score = max(0, min(100, score))

        # 评级
        if score >= 75:
            grade = "A"
        elif score >= 60:
            grade = "B"
        elif score >= 40:
            grade = "C"
        else:
            grade = "D"

        return round(score, 1), grade

    # ─────────────────────────────────────────
    # 背离检测
    # ─────────────────────────────────────────

    def _detect_divergence(
        self,
        close: np.ndarray,
        histogram: np.ndarray,
        lookback: int = 20,
    ) -> Optional[str]:
        """
        简化背离检测
        顶背离：价格创N日新高，但MACD柱未创新高 → 看跌
        底背离：价格创N日新低，但MACD柱未创新低 → 看涨
        """
        n = len(close)
        if n < lookback + 5:
            return None

        window = close[-lookback:]
        h_window = histogram[-lookback:]

        # 价格是否创窗口期新高/新低
        price_new_high = bool(close[-1] >= np.max(close[-lookback:-1]))
        price_new_low = bool(close[-1] <= np.min(close[-lookback:-1]))
        macd_new_high = bool(histogram[-1] >= np.max(h_window[:-1]))
        macd_new_low = bool(histogram[-1] <= np.min(h_window[:-1]))

        if price_new_high and not macd_new_high:
            return "顶背离"
        if price_new_low and not macd_new_low:
            return "底背离"
        return None
