#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 增量计算引擎
只对新增数据进行增量计算，高效更新 SMA/EMA/RSI/MACD/布林带
"""

import numpy as np
from typing import Dict, List, Optional
from collections import deque


class IncrementalProcessor:
    """
    增量计算引擎

    特点：
    - O(1) 增量更新（无需重算全量历史）
    - 内部维护滑动窗口
    - 支持 SMA / EMA / RSI / MACD / 布林带
    - 线程安全（单 symbol 实例独立）
    """

    def __init__(self, 配置: Optional[Dict] = None):
        cfg = 配置 or {}
        # SMA 周期列表
        self._sma周期 = cfg.get("sma_periods", [5, 10, 20, 60])
        # EMA 参数
        self._ema12_alpha = 2 / (12 + 1)
        self._ema26_alpha = 2 / (26 + 1)
        # RSI 周期
        self._rsi周期 = cfg.get("rsi_period", 14)
        # 布林带
        self._bb周期 = cfg.get("bb_period", 20)

        # 内部状态
        self._价格窗口 = deque(maxlen=max(self._sma周期 + [self._bb周期, 26 + 9 + 5]))
        self._ema12: Optional[float] = None
        self._ema26: Optional[float] = None
        self._signal9: Optional[float] = None
        self._rsi_avg_gain: Optional[float] = None
        self._rsi_avg_loss: Optional[float] = None
        self._prev_price: Optional[float] = None
        self._计算次数 = 0

    def 推送价格(self, 价格: float) -> Dict:
        """
        推送一个新价格，返回最新技术指标值

        返回:
            {
                "sma": {5: val, 10: val, ...},
                "ema12": val,
                "ema26": val,
                "macd": {"macd": val, "signal": val, "hist": val},
                "rsi": val,
                "bollinger": {"upper": val, "middle": val, "lower": val},
            }
        """
        self._价格窗口.append(价格)
        self._计算次数 += 1

        结果 = {
            "price": 价格,
            "count": self._计算次数,
            "sma": self._更新SMA(),
            "ema12": self._更新EMA12(价格),
            "ema26": self._更新EMA26(价格),
            "macd": self._更新MACD(),
            "rsi": self._更新RSI(价格),
            "bollinger": self._更新布林带(),
        }

        self._prev_price = 价格
        return 结果

    def 批量初始化(self, 历史价格: List[float]) -> Dict:
        """用历史数据初始化状态，返回最后一条价格的指标值"""
        last_result = {}
        for p in 历史价格:
            last_result = self.推送价格(p)
        return last_result

    def 重置(self) -> None:
        """重置所有状态"""
        self._价格窗口.clear()
        self._ema12 = self._ema26 = self._signal9 = None
        self._rsi_avg_gain = self._rsi_avg_loss = None
        self._prev_price = None
        self._计算次数 = 0

    # ──────────────────────────────────────────────
    # 私有增量计算
    # ──────────────────────────────────────────────

    def _更新SMA(self) -> Dict[int, Optional[float]]:
        prices = list(self._价格窗口)
        result = {}
        for p in self._sma周期:
            if len(prices) >= p:
                result[p] = round(float(np.mean(prices[-p:])), 4)
            else:
                result[p] = None
        return result

    def _更新EMA12(self, 价格: float) -> Optional[float]:
        if self._ema12 is None:
            if len(self._价格窗口) >= 12:
                self._ema12 = float(np.mean(list(self._价格窗口)[-12:]))
        else:
            self._ema12 = self._ema12_alpha * 价格 + (1 - self._ema12_alpha) * self._ema12
        return round(self._ema12, 4) if self._ema12 is not None else None

    def _更新EMA26(self, 价格: float) -> Optional[float]:
        if self._ema26 is None:
            if len(self._价格窗口) >= 26:
                self._ema26 = float(np.mean(list(self._价格窗口)[-26:]))
        else:
            self._ema26 = self._ema26_alpha * 价格 + (1 - self._ema26_alpha) * self._ema26
        return round(self._ema26, 4) if self._ema26 is not None else None

    def _更新MACD(self) -> Dict:
        if self._ema12 is None or self._ema26 is None:
            return {"macd": None, "signal": None, "hist": None}
        macd_val = self._ema12 - self._ema26
        alpha9 = 2 / (9 + 1)
        if self._signal9 is None:
            self._signal9 = macd_val
        else:
            self._signal9 = alpha9 * macd_val + (1 - alpha9) * self._signal9
        return {
            "macd": round(macd_val, 6),
            "signal": round(self._signal9, 6),
            "hist": round(macd_val - self._signal9, 6),
        }

    def _更新RSI(self, 价格: float) -> Optional[float]:
        if self._prev_price is None:
            return None
        变动 = 价格 - self._prev_price
        gain = max(0.0, 变动)
        loss = max(0.0, -变动)

        if self._rsi_avg_gain is None:
            # 需要足够数据点才能初始化
            if len(self._价格窗口) >= self._rsi周期 + 1:
                prices = list(self._价格窗口)[-(self._rsi周期 + 1):]
                diffs = np.diff(prices)
                self._rsi_avg_gain = float(np.mean(np.maximum(diffs, 0)))
                self._rsi_avg_loss = float(np.mean(np.maximum(-diffs, 0)))
            else:
                return None
        else:
            n = self._rsi周期
            self._rsi_avg_gain = (self._rsi_avg_gain * (n - 1) + gain) / n
            self._rsi_avg_loss = (self._rsi_avg_loss * (n - 1) + loss) / n

        rs = self._rsi_avg_gain / (self._rsi_avg_loss + 1e-10)
        return round(100 - 100 / (1 + rs), 2)

    def _更新布林带(self) -> Dict:
        prices = list(self._价格窗口)
        if len(prices) < self._bb周期:
            return {"upper": None, "middle": None, "lower": None, "width": None}
        窗口 = np.array(prices[-self._bb周期:])
        middle = float(np.mean(窗口))
        std = float(np.std(窗口))
        return {
            "upper": round(middle + 2 * std, 4),
            "middle": round(middle, 4),
            "lower": round(middle - 2 * std, 4),
            "width": round(4 * std / (middle + 1e-10), 6),
        }
