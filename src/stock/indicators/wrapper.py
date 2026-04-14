#!/usr/bin/env python3
"""
IndicatorWrapper - 行情数据 → 技术指标引擎适配器
将 akshare 格式数据转换为 TechnicalIndicators/RiskAnalyzer 的输入格式
"""

import sys
import os
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer
from zhulinsma.core.analysis.trend_analyzer import TrendAnalyzer


class IndicatorWrapper:
    """
    指标计算统一接口

    接收 DataFrame（日K数据）→ 调用现有 TechnicalIndicators 计算所有指标
    → 返回结构化指标字典，供战法直接使用
    """

    def __init__(self):
        self.ti = TechnicalIndicators(验证模式=False, 严格模式=False)
        self.risk = RiskAnalyzer()
        self.trend = TrendAnalyzer()

    def compute_all(
        self,
        df: pd.DataFrame,
        periods: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        计算全部指标（给定日K DataFrame）

        参数:
            df: 包含 date/open/high/low/close/volume 列的 DataFrame
            periods: 自定义周期，如 {"rsi": 14, "ma": [5, 10, 20, 60]}

        返回:
            包含所有指标的结构化字典
        """
        if periods is None:
            periods = {"rsi": 14, "ma": [5, 10, 20, 60], "macd": (12, 26, 9)}

        close = np.array(df["close"].values, dtype=float)
        high = np.array(df["high"].values, dtype=float)
        low = np.array(df["low"].values, dtype=float)
        volume = np.array(df["volume"].values, dtype=float)

        n = len(close)

        # ── 均线系列 ──────────────────────────────
        ma_periods = periods.get("ma", [5, 10, 20, 60])
        ma_values = {}
        for p in ma_periods:
            if n >= p:
                ma_values[f"ma{p}"] = self.ti.SMA(close, p)[-1]
            else:
                ma_values[f"ma{p}"] = None

        # ── RSI ──────────────────────────────────
        rsi_period = periods.get("rsi", 14)
        if n >= rsi_period + 1:
            rsi = self.ti.RSI(close, rsi_period)
            rsi_latest = float(rsi[-1])
        else:
            rsi_latest = None

        # ── MACD ─────────────────────────────────
        macd_fast, macd_slow, macd_signal = periods.get("macd", (12, 26, 9))
        if n >= macd_slow + macd_signal:
            macd_result = self.ti.MACD(close, macd_fast, macd_slow, macd_signal)
            # 现有 TechnicalIndicators MACD 返回: macd, signal, histogram
            def _last(arr):
                if arr is None or (hasattr(arr, '__len__') and len(arr) == 0):
                    return None
                return float(arr[-1])

            macd_line = macd_result.get("macd")
            signal_line = macd_result.get("signal")
            histogram = macd_result.get("histogram")
            macd_diff = _last(macd_line)
            macd_dea = _last(signal_line)
            macd_bar = _last(histogram)
        else:
            macd_diff, macd_dea, macd_bar = None, None, None

        # ── KDJ ──────────────────────────────────
        if n >= 9:
            try:
                kdj = self.ti.Stochastic(high, low, close, n=9)
                k = float(kdj["k"][-1])
                d = float(kdj["d"][-1])
                j = float(3 * k - 2 * d)  # J 线 = 3K - 2D
            except Exception:
                k, d, j = None, None, None
        else:
            k, d, j = None, None, None

        # ── 布林带 ───────────────────────────────
        bb_period = periods.get("bollinger", 20)
        bb_std = periods.get("bollinger_std", 2)
        if n >= bb_period:
            bb = self.ti.BollingerBands(close, bb_period, bb_std)
            bb_upper = float(bb["upper"][-1])
            bb_mid = float(bb["middle"][-1])
            bb_lower = float(bb["lower"][-1])
            bb_position = float((close[-1] - bb_lower) / (bb_upper - bb_lower + 1e-10))
        else:
            bb_upper, bb_mid, bb_lower, bb_position = None, None, None, None

        # ── ATR ──────────────────────────────────
        if n >= 14:
            atr = self.ti.ATR(high, low, close, 14)
            atr_latest = float(atr[-1])
        else:
            atr_latest = None

        # ── OBV ──────────────────────────────────
        if n >= 2:
            obv = self._compute_obv(close, volume)
            obv_trend = "up" if obv[-1] > obv[-2] else "down"
        else:
            obv_trend = "neutral"

        # ── 量价特征（战法专用） ─────────────────
        量能特征 = self._compute_volume_features(close, volume, n)

        # ── K线形态（战法专用） ──────────────────
        形态特征 = self._compute_candle_features(df, volume, n)

        # ── 风险评分 ─────────────────────────────
        risk_result = self.risk.评估风险(close, volume, rsi_latest, None)

        return {
            # ── 基础行情 ──
            "close": float(close[-1]),
            "open": float(df["open"].values[-1]),
            "high": float(high[-1]),
            "low": float(low[-1]),
            "volume": float(volume[-1]),
            "pct_change": float((close[-1] - close[-2]) / close[-2] * 100) if n >= 2 and close[-2] != 0 else 0.0,
            # ── 均线 ──
            "ma": ma_values,
            # ── RSI/MACD/KDJ ──
            "rsi": round(rsi_latest, 2) if rsi_latest else None,
            "macd": {
                "diff": round(macd_diff, 4) if macd_diff else None,
                "dea": round(macd_dea, 4) if macd_dea else None,
                "bar": round(macd_bar, 4) if macd_bar else None,
                "signal": "金叉" if (macd_diff and macd_dea and macd_diff > macd_dea) else "死叉" if (macd_diff and macd_dea) else "中性",
            },
            "kdj": {"k": round(k, 2) if k else None, "d": round(d, 2) if d else None, "j": round(j, 2) if j else None},
            # ── 布林带 ──
            "bollinger": {
                "upper": round(bb_upper, 2) if bb_upper else None,
                "mid": round(bb_mid, 2) if bb_mid else None,
                "lower": round(bb_lower, 2) if bb_lower else None,
                "position": round(bb_position, 4) if bb_position else None,
            },
            # ── ATR/OBV ──
            "atr": round(atr_latest, 4) if atr_latest else None,
            "obv_trend": obv_trend,
            # ── 量价特征（战法用） ──
            "量能特征": 量能特征,
            # ── K线形态（战法用） ──
            "形态特征": 形态特征,
            # ── 风险评估 ──
            "风险": risk_result,
        }

    def _compute_volume_features(self, close: np.ndarray, volume: np.ndarray, n: int) -> Dict:
        """计算量价特征（战法专用）"""
        if n < 5:
            return {}

        vol = volume[-5:]
        cl = close[-5:]

        # 近5日量能变异系数（CV = std/mean）
        vol_cv = float(np.std(vol) / (np.mean(vol) + 1e-10))

        # 今日量能相对5日均量
        vol_ratio = float(volume[-1] / (np.mean(vol[:-1]) + 1e-10))

        # 近5日量能萎缩判断（今日<均量80%）
        vol_shrink = bool(volume[-1] < np.mean(vol[:-1]) * 0.8)

        # 对比10日前量能（锁仓战法用）
        if n >= 15:
            vol_now = float(np.mean(volume[-5:]))
            vol_10d_before = float(np.mean(volume[-15:-10]))
            vol_compare = float(vol_now / (vol_10d_before + 1e-10))
        else:
            vol_compare = None

        # 量价背离
        price_up = close[-1] > close[-2]
        vol_up = volume[-1] > volume[-2]
        量价背离 = bool(price_up and not vol_up)

        return {
            "vol_cv": round(vol_cv, 4),
            "vol_ratio": round(vol_ratio, 4),
            "vol_shrink": vol_shrink,
            "vol_compare_10d": round(vol_compare, 4) if vol_compare is not None else None,
            "量价背离": 量价背离,
        }

    def _compute_candle_features(self, df: pd.DataFrame, volume: np.ndarray, n: int) -> Dict:
        """计算K线形态特征（战法专用）"""
        if n < 2:
            return {}

        close = np.array(df["close"].values, dtype=float)
        open_arr = np.array(df["open"].values, dtype=float)
        high = np.array(df["high"].values, dtype=float)
        low = np.array(df["low"].values, dtype=float)

        # 今日K线
        body = abs(close[-1] - open_arr[-1])
        upper_shadow = high[-1] - max(close[-1], open_arr[-1])
        lower_shadow = min(close[-1], open_arr[-1]) - low[-1]
        total_range = high[-1] - low[-1] + 1e-10

        is_bearish = close[-1] < open_arr[-1]  # 阴线
        is_bullish = close[-1] > open_arr[-1]  # 阳线

        # 上影线比例
        upper_shadow_ratio = float(upper_shadow / total_range)
        # 下影线比例
        lower_shadow_ratio = float(lower_shadow / total_range)
        # 实体比例
        body_ratio = float(body / total_range)

        # 长上影判断（上影线>60%总幅度）
        long_upper_shadow = bool(upper_shadow_ratio > 0.6)

        # 倍量阴判断（成交量放大+阴线）
        if n >= 21:
            vol = np.array(df["volume"].values, dtype=float)
            vol_ma20 = np.mean(vol[-21:-1])
            倍量阴 = bool(is_bearish and volume[-1] > vol_ma20 * 2) if n >= 21 else False
            # 接近20日新高
            近期最高20 = float(np.max(close[-20:]))
            接近新高 = bool(close[-1] >= 近期最高20 * 0.97)
        else:
            倍量阴 = False
            接近新高 = False

        return {
            "is_bearish": is_bearish,
            "is_bullish": is_bullish,
            "upper_shadow_ratio": round(upper_shadow_ratio, 4),
            "lower_shadow_ratio": round(lower_shadow_ratio, 4),
            "body_ratio": round(body_ratio, 4),
            "long_upper_shadow": long_upper_shadow,
            "倍量阴": 倍量阴,
            "接近20日新高": 接近新高,
        }

    def _compute_obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """简化 OBV 计算"""
        direction = np.where(np.diff(close, prepend=close[0]) > 0, 1, -1)
        return np.cumsum(direction * volume)
