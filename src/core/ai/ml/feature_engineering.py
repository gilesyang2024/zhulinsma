#!/usr/bin/env python3
"""
MLFeatureEngine - 特征工程引擎
将日K线原始数据 → 100+维ML特征向量

竹林司马 AI驱动A股技术分析引擎 · ML预测模块
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class MLFeatureVector:
    """单只股票单日ML特征向量"""
    stock_code: str
    date: str
    close: float
    features: Dict[str, float] = field(default_factory=dict)

    def to_array(self) -> np.ndarray:
        keys = sorted(self.features.keys())
        return np.array([self.features[k] for k in keys], dtype=np.float32)

    def feature_names(self) -> List[str]:
        return sorted(self.features.keys())


class MLFeatureEngine:
    """
    特征工程引擎

    生成 100+ 维特征，分为6大类：
    1. 趋势类（M001-M005扩展）
    2. 动量类（M006-M010扩展）
    3. 量价类（M011-M015扩展）
    4. 波动类（M016-M020扩展）
    5. 形态类（K线模式）
    6. 市场情绪类

    使用方式：
        engine = MLFeatureEngine()
        df_features = engine.build_features(df_daily)  # df: date,open,high,low,close,volume
    """

    def __init__(self, lookback: int = 120):
        self.lookback = lookback

    def build_features(
        self,
        df: pd.DataFrame,
        stock_code: str = "UNKNOWN",
        index_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        主入口：从日K DataFrame 生成完整特征表

        参数:
            df:         日K数据，必须含列 date/open/high/low/close/volume
            stock_code: 股票代码
            index_df:   大盘指数日K（用于计算相对强弱），可选

        返回:
            DataFrame，每行对应一个交易日，列=特征名
        """
        df = df.copy()
        df = df.sort_values("date").tail(self.lookback).reset_index(drop=True)

        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        low   = df["low"].values.astype(float)
        open_ = df["open"].values.astype(float)
        vol   = df["volume"].values.astype(float)

        n = len(close)
        if n < 30:
            raise ValueError(f"数据不足，需要至少30天数据，当前仅{n}天")

        result: Dict[str, List] = {
            "stock_code": [stock_code] * n,
            "date":       df["date"].values.tolist(),
            "close":      close.tolist(),
        }

        # ──────────────────────────────────────────
        # 1. 趋势类特征
        # ──────────────────────────────────────────
        for period in [5, 10, 20, 60]:
            if n >= period:
                ma = self._sma(close, period)
                result[f"ma{period}"]              = ma.tolist()
                result[f"ma{period}_slope"]        = self._slope(ma).tolist()
                result[f"price_ma{period}_dist"]   = ((close - ma) / (ma + 1e-10)).tolist()
            else:
                result[f"ma{period}"]              = [np.nan] * n
                result[f"ma{period}_slope"]        = [np.nan] * n
                result[f"price_ma{period}_dist"]   = [np.nan] * n

        result["ma多头排列"]    = self._ma_bull_arrangement(close, n).tolist()
        result["ma空头排列"]    = self._ma_bear_arrangement(close, n).tolist()
        result["ma_golden_cross"] = self._golden_cross(close).tolist()
        result["ma_death_cross"]  = self._death_cross(close).tolist()

        if n >= 20:
            adx = self._adx(high, low, close, 14)
            result["adx"]         = adx.tolist()
            result["adx_slope"]   = self._slope(adx).tolist()
        else:
            result["adx"]         = [np.nan] * n
            result["adx_slope"]   = [np.nan] * n

        # ──────────────────────────────────────────
        # 2. 动量类特征
        # ──────────────────────────────────────────
        for period in [6, 12, 24]:
            rsi = self._rsi(close, period)
            result[f"rsi_{period}"]     = rsi.tolist()
            result[f"rsi_{period}_delta"] = self._diff(rsi).tolist()

        macd, signal, hist = self._macd(close)
        result["macd"]               = macd.tolist()
        result["macd_signal"]        = signal.tolist()
        result["macd_histogram"]     = hist.tolist()
        result["macd_histogram_chg"] = self._diff(hist).tolist()
        result["macd_cross"]          = self._macd_cross(macd, signal).tolist()
        result["macd_divergence"]    = self._divergence(close, macd).tolist()

        k, d, j = self._kdj(high, low, close)
        result["kdj_k"]           = k.tolist()
        result["kdj_d"]           = d.tolist()
        result["kdj_j"]           = j.tolist()
        result["kdj_overbought"]   = (k > 80).astype(float).tolist()
        result["kdj_oversold"]    = (k < 20).astype(float).tolist()
        result["kdj_diverge"]     = self._kdj_diverge(close, k).tolist()

        for period in [5, 10, 20]:
            ret = np.full(n, np.nan)
            for i in range(period, n):
                ret[i] = (close[i] / (close[i - period] + 1e-10) - 1) * 100
            result[f"momentum_{period}d"] = ret.tolist()

        if n >= 20:
            cci = self._cci(high, low, close, 20)
            result["cci"]          = cci.tolist()
            result["cci_deviate"] = self._diff(cci).tolist()
        else:
            result["cci"]          = [np.nan] * n
            result["cci_deviate"] = [np.nan] * n

        # ──────────────────────────────────────────
        # 3. 量价类特征
        # ──────────────────────────────────────────
        for period in [5, 10, 20]:
            vol_ma = self._sma(vol, period)
            result[f"vol_ma{period}"]      = vol_ma.tolist()
            result[f"vol_ratio_{period}d"] = (vol / (vol_ma + 1e-10)).tolist()

        result["vol_cv_20d"]          = self._rolling_cv(vol, 20).tolist()
        result["vol_price_corr_20d"]  = self._rolling_corr(vol, close, 20).tolist()
        result["obv"]                 = self._obv(close, vol).tolist()
        result["obv_slope_10d"]       = self._slope(self._obv(close, vol)).tolist()
        result["price_vol_div"]       = self._price_vol_divergence(close, vol).tolist()
        result["vol_shrink_5d"]        = self._vol_shrink(close, vol, 5).tolist()

        # ──────────────────────────────────────────
        # 4. 波动类特征
        # ──────────────────────────────────────────
        for period in [10, 20]:
            if n >= period:
                std = self._rolling_std(close, period)
                ma  = self._sma(close, period)
                bw  = (std * 2) / (ma + 1e-10)
                result[f"bollinger_width_{period}d"] = bw.tolist()
            else:
                result[f"bollinger_width_{period}d"] = [np.nan] * n

        for period in [5, 10, 20]:
            vola = self._rolling_std(close, period) / (self._sma(close, period) + 1e-10)
            result[f"volatility_{period}d"] = vola.tolist()

        if n >= 14:
            atr = self._atr(high, low, close, 14)
            result["atr"]      = atr.tolist()
            result["atr_norm"] = (atr / (close + 1e-10)).tolist()
        else:
            result["atr"]      = [np.nan] * n
            result["atr_norm"] = [np.nan] * n

        result["high_low_ratio_5d"] = ((high - low) / (close + 1e-10)).tolist()

        # ──────────────────────────────────────────
        # 5. 形态类特征
        # ──────────────────────────────────────────
        body     = np.abs(close - open_)
        u_shadow = high - np.maximum(close, open_)
        l_shadow = np.minimum(close, open_) - low
        total_r  = high - low + 1e-10

        result["body_ratio"]     = (body / total_r).tolist()
        result["u_shadow_ratio"] = (u_shadow / total_r).tolist()
        result["l_shadow_ratio"] = (l_shadow / total_r).tolist()
        result["is_bullish"]     = (close > open_).astype(float).tolist()
        result["is_doji"]        = ((body / total_r) < 0.1).astype(float).tolist()
        result["is_hammer"]     = (
            ((l_shadow > body * 2) & (u_shadow / total_r < 0.2))
        ).astype(float).tolist()
        result["is_shooting"]    = (
            ((u_shadow > body * 2) & (l_shadow / total_r < 0.2))
        ).astype(float).tolist()

        # ──────────────────────────────────────────
        # 6. 市场情绪 / 相对强弱
        # ──────────────────────────────────────────
        if index_df is not None and len(index_df) >= n:
            idx_close = index_df["close"].values.astype(float)[-n:]
            result["index_corr_20d"] = self._rolling_corr(close, idx_close, min(20, n)).tolist()
            stock_ret = np.full(n, np.nan)
            idx_ret   = np.full(n, np.nan)
            for i in range(1, n):
                stock_ret[i] = close[i] / (close[i - 1] + 1e-10) - 1
                idx_ret[i]   = idx_close[i] / (idx_close[i - 1] + 1e-10) - 1
            rs = stock_ret / (np.abs(idx_ret) + 1e-10)
            result["relative_strength"] = rs.tolist()
        else:
            result["index_corr_20d"]     = [np.nan] * n
            result["relative_strength"]  = [np.nan] * n

        # ──────────────────────────────────────────
        # 7. 统计类特征
        # ──────────────────────────────────────────
        ret1 = np.full(n, 0.0)
        for i in range(1, n):
            ret1[i] = (close[i] - close[i - 1]) / (close[i - 1] + 1e-10) * 100
        result["returns_1d"]   = ret1.tolist()
        result["returns_5d"]  = self._rolling_return(close, 5).tolist()
        result["skewness_20d"] = self._rolling_skew(close, 20).tolist()
        result["kurtosis_20d"]  = self._rolling_kurt(close, 20).tolist()

        # ──────────────────────────────────────────
        # 组装DataFrame（丢弃前60天warmup）
        # ──────────────────────────────────────────
        out = pd.DataFrame(result)
        warmup = 60
        return out.iloc[warmup:].reset_index(drop=True)

    # ================================================================
    # 基础指标计算（纯numpy实现，无需talib）
    # ================================================================

    @staticmethod
    def _sma(x: np.ndarray, period: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        if n < period:
            return result
        result[period - 1:] = np.convolve(x, np.ones(period) / period, mode="valid")
        return result

    @staticmethod
    def _slope(x: np.ndarray) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(5, n):
            y = x[max(0, i - 5):i + 1]
            t = np.arange(len(y))
            if len(t) > 1:
                slope = np.polyfit(t, y, 1)[0]
                result[i] = slope / (np.mean(y) + 1e-10)
        return result

    @staticmethod
    def _diff(x: np.ndarray) -> np.ndarray:
        return np.diff(x, prepend=x[0])

    @staticmethod
    def _rolling_std(x: np.ndarray, window: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(window, n):
            result[i] = np.std(x[i - window + 1:i + 1])
        return result

    @staticmethod
    def _rolling_cv(x: np.ndarray, window: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(window, n):
            seg = x[i - window + 1:i + 1]
            result[i] = np.std(seg) / (np.mean(seg) + 1e-10)
        return result

    @staticmethod
    def _rolling_corr(x: np.ndarray, y: np.ndarray, window: int) -> np.ndarray:
        n = min(len(x), len(y))
        result = np.full(n, np.nan)
        for i in range(window, n):
            xw = x[i - window + 1:i + 1]
            yw = y[i - window + 1:i + 1]
            if np.std(xw) > 1e-10 and np.std(yw) > 1e-10:
                result[i] = np.corrcoef(xw, yw)[0, 1]
        return result

    @staticmethod
    def _rolling_return(x: np.ndarray, period: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(period, n):
            result[i] = (x[i] / (x[i - period] + 1e-10) - 1) * 100
        return result

    @staticmethod
    def _rolling_skew(x: np.ndarray, window: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(window, n):
            seg = x[i - window + 1:i + 1]
            m = np.mean(seg)
            s = np.std(seg) + 1e-10
            result[i] = np.mean(((seg - m) / s) ** 3)
        return result

    @staticmethod
    def _rolling_kurt(x: np.ndarray, window: int) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        for i in range(window, n):
            seg = x[i - window + 1:i + 1]
            m = np.mean(seg)
            s = np.std(seg) + 1e-10
            result[i] = np.mean(((seg - m) / s) ** 4) - 3
        return result

    @staticmethod
    def _rsi(x: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(x)
        result = np.full(n, np.nan)
        deltas = np.diff(x, prepend=x[0])
        for i in range(period, n):
            gains = deltas[i - period + 1:i + 1]
            losses = deltas[i - period + 1:i + 1]
            gain = np.mean(gains[gains > 0])
            loss = -np.mean(losses[losses < 0])
            if loss == 0:
                result[i] = 100.0
            else:
                result[i] = 100 - 100 / (1 + gain / (loss + 1e-10))
        return result

    @staticmethod
    def _macd(x: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        n = len(x)
        alpha_f = 2 / (fast + 1)
        alpha_s = 2 / (slow + 1)
        alpha_sig = 2 / (signal + 1)
        ema_f = np.full(n, np.nan)
        ema_s = np.full(n, np.nan)
        ema_f[0] = ema_s[0] = x[0]
        for i in range(1, n):
            ema_f[i] = alpha_f * x[i] + (1 - alpha_f) * ema_f[i - 1]
            ema_s[i] = alpha_s * x[i] + (1 - alpha_s) * ema_s[i - 1]
        macd_line = ema_f - ema_s
        sig = np.full(n, macd_line[0])
        for i in range(1, n):
            sig[i] = alpha_sig * macd_line[i] + (1 - alpha_sig) * sig[i - 1]
        return macd_line, sig, macd_line - sig

    @staticmethod
    def _kdj(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 9) -> tuple:
        n = len(c)
        k = np.full(n, 50.0)
        d = np.full(n, 50.0)
        for i in range(period, n):
            wh = np.max(h[i - period + 1:i + 1])
            wl = np.min(l[i - period + 1:i + 1])
            rsv = (c[i] - wl) / (wh - wl + 1e-10) * 100
            k[i] = 2 / 3 * k[i - 1] + 1 / 3 * rsv
            d[i] = 2 / 3 * d[i - 1] + 1 / 3 * k[i]
        return k, d, 3 * k - 2 * d

    @staticmethod
    def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(c)
        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(
                h[i] - l[i],
                abs(h[i] - c[i - 1]),
                abs(l[i] - c[i - 1]),
            )
        tr[0] = h[0] - l[0]
        return MLFeatureEngine._sma(tr, period)

    @staticmethod
    def _adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(c)
        adx_out = np.full(n, np.nan)
        if n < period * 2:
            return adx_out
        plus_dm  = np.maximum(h[1:] - h[:-1], 0.0)
        minus_dm = np.maximum(l[:-1] - l[1:], 0.0)
        tr_arr   = np.maximum(
            h[1:] - l[1:],
            np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1]))
        )
        plus_di  = MLFeatureEngine._sma(plus_dm, period) / (MLFeatureEngine._sma(tr_arr, period) + 1e-10) * 100
        minus_di = MLFeatureEngine._sma(minus_dm, period) / (MLFeatureEngine._sma(tr_arr, period) + 1e-10) * 100
        dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        # _sma 返回与输入同长数组，有效值从 period-1 开始
        # dx 有效部分从 index period-1 开始，故 adx 有效部分从 2*(period-1) 开始
        adx_valid = MLFeatureEngine._sma(dx, period)
        adx_out[period * 2:] = adx_valid[period * 2 - 1:]
        return adx_out

    @staticmethod
    def _cci(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 20) -> np.ndarray:
        n = len(c)
        tp = (h + l + c) / 3
        result = np.full(n, np.nan)
        for i in range(period, n):
            window = tp[i - period + 1:i + 1]
            sma = np.mean(window)
            mad = np.mean(np.abs(window - sma)) + 1e-10
            result[i] = (tp[i] - sma) / (0.015 * mad)
        return result

    @staticmethod
    def _obv(c: np.ndarray, v: np.ndarray) -> np.ndarray:
        direction = np.where(np.diff(c, prepend=c[0]) > 0, 1, -1)
        return np.cumsum(direction * v)

    # ──────────────────────────────────────────
    # 复合信号
    # ──────────────────────────────────────────

    @staticmethod
    def _ma_bull_arrangement(c: np.ndarray, n: int) -> np.ndarray:
        if n < 60:
            return np.zeros(n)
        ma5  = MLFeatureEngine._sma(c, 5)[-n:]
        ma10 = MLFeatureEngine._sma(c, 10)[-n:]
        ma20 = MLFeatureEngine._sma(c, 20)[-n:]
        return ((ma5 > ma10) & (ma10 > ma20)).astype(float)

    @staticmethod
    def _ma_bear_arrangement(c: np.ndarray, n: int) -> np.ndarray:
        if n < 60:
            return np.zeros(n)
        ma5  = MLFeatureEngine._sma(c, 5)[-n:]
        ma10 = MLFeatureEngine._sma(c, 10)[-n:]
        ma20 = MLFeatureEngine._sma(c, 20)[-n:]
        return ((ma5 < ma10) & (ma10 < ma20)).astype(float)

    @staticmethod
    def _golden_cross(c: np.ndarray) -> np.ndarray:
        n = len(c)
        result = np.zeros(n)
        ma5  = MLFeatureEngine._sma(c, 5)
        ma20 = MLFeatureEngine._sma(c, 20)
        for i in range(2, n):
            if ma5[i - 2] < ma20[i - 2] and ma5[i] >= ma20[i]:
                result[i] = 1.0
        return result

    @staticmethod
    def _death_cross(c: np.ndarray) -> np.ndarray:
        n = len(c)
        result = np.zeros(n)
        ma5  = MLFeatureEngine._sma(c, 5)
        ma20 = MLFeatureEngine._sma(c, 20)
        for i in range(2, n):
            if ma5[i - 2] > ma20[i - 2] and ma5[i] <= ma20[i]:
                result[i] = 1.0
        return result

    @staticmethod
    def _macd_cross(macd: np.ndarray, sig: np.ndarray) -> np.ndarray:
        n = len(macd)
        result = np.zeros(n)
        for i in range(2, n):
            if macd[i - 2] < sig[i - 2] and macd[i] >= sig[i]:
                result[i] = 1.0
            elif macd[i - 2] > sig[i - 2] and macd[i] <= sig[i]:
                result[i] = -1.0
        return result

    @staticmethod
    def _divergence(c: np.ndarray, ind: np.ndarray, window: int = 10) -> np.ndarray:
        n = len(c)
        result = np.zeros(n)
        for i in range(window, n):
            pw = c[i - window:i + 1]
            iw = ind[i - window:i + 1]
            if c[i] >= np.max(pw[:-1]) and ind[i] < np.max(iw[:-1]):
                result[i] = 1.0
            elif c[i] <= np.min(pw[:-1]) and ind[i] > np.min(iw[:-1]):
                result[i] = -1.0
        return result

    @staticmethod
    def _kdj_diverge(c: np.ndarray, k: np.ndarray, window: int = 10) -> np.ndarray:
        return MLFeatureEngine._divergence(c, k, window)

    @staticmethod
    def _price_vol_divergence(c: np.ndarray, v: np.ndarray) -> np.ndarray:
        n = len(c)
        result = np.zeros(n)
        for i in range(5, n):
            if c[i] > c[i - 1] and v[i] < v[i - 1]:
                result[i] = 1.0
            elif c[i] < c[i - 1] and v[i] > v[i - 1]:
                result[i] = -1.0
        return result

    @staticmethod
    def _vol_shrink(c: np.ndarray, v: np.ndarray, window: int = 5) -> np.ndarray:
        n = len(v)
        result = np.zeros(n)
        for i in range(window + 1, n):
            v_now  = np.mean(v[i - window + 1:i + 1])
            v_prev = np.mean(v[i - window * 2:i - window + 1])
            if v_prev > 0:
                result[i] = v_now / v_prev
        return result
