#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 支撑阻力分析器
通过价格密集成交区、局部极值、均线等方法识别支撑位与阻力位
"""

import numpy as np
from typing import Dict, List, Optional, Union


class SupportResistanceAnalyzer:
    """
    支撑阻力分析器

    功能：
    - 基于局部极值识别关键价格位
    - 基于成交量加权的价格密集区（Volume Profile 简化版）
    - 均线动态支撑/阻力
    - 与当前价格的距离计算
    """

    def __init__(self, 灵敏度: float = 0.02):
        """
        参数:
            灵敏度: 价格聚合容差（默认2%，相邻 ±2% 的价位合并）
        """
        self.灵敏度 = 灵敏度

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def 分析支撑阻力(
        self,
        收盘价: Union[np.ndarray, List[float]],
        最高价: Optional[Union[np.ndarray, List[float]]] = None,
        最低价: Optional[Union[np.ndarray, List[float]]] = None,
        成交量: Optional[Union[np.ndarray, List[float]]] = None,
    ) -> Dict:
        """
        执行支撑阻力完整分析

        返回:
            支撑位列表、阻力位列表、关键价位区间、与当前价距离
        """
        收盘 = np.asarray(收盘价, dtype=float)
        当前价 = float(收盘[-1])

        # 1. 局部极值法
        极值支撑, 极值阻力 = self._极值法(收盘)

        # 2. 带 OHLC 时增加影线极值
        if 最高价 is not None and 最低价 is not None:
            高 = np.asarray(最高价, dtype=float)
            低 = np.asarray(最低价, dtype=float)
            ohlc支撑, ohlc阻力 = self._ohlc极值法(高, 低)
            极值支撑 = sorted(set(极值支撑 + ohlc支撑))
            极值阻力 = sorted(set(极值阻力 + ohlc阻力))

        # 3. 均线支撑/阻力
        均线支撑, 均线阻力 = self._均线法(收盘, 当前价)

        # 4. 合并所有支撑/阻力并聚合
        所有支撑 = self._聚合价位(极值支撑 + 均线支撑)
        所有阻力 = self._聚合价位(极值阻力 + 均线阻力)

        # 5. 过滤（支撑在当前价以下，阻力在当前价以上）
        支撑位列表 = sorted([p for p in 所有支撑 if p < 当前价], reverse=True)[:5]
        阻力位列表 = sorted([p for p in 所有阻力 if p > 当前价])[:5]

        # 6. 距离计算
        最近支撑 = 支撑位列表[0] if 支撑位列表 else None
        最近阻力 = 阻力位列表[0] if 阻力位列表 else None

        def _距离百分比(目标):
            if 目标 is None:
                return None
            return round((目标 - 当前价) / 当前价 * 100, 2)

        return {
            "当前价格": round(当前价, 4),
            "支撑位": [round(p, 4) for p in 支撑位列表],
            "阻力位": [round(p, 4) for p in 阻力位列表],
            "最近支撑": round(最近支撑, 4) if 最近支撑 else None,
            "最近阻力": round(最近阻力, 4) if 最近阻力 else None,
            "距最近支撑": _距离百分比(最近支撑),
            "距最近阻力": _距离百分比(最近阻力),
            "支撑强度": self._评估强度(支撑位列表, 收盘, "支撑"),
            "阻力强度": self._评估强度(阻力位列表, 收盘, "阻力"),
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _极值法(self, 收盘: np.ndarray, 窗口: int = 5) -> tuple:
        """用局部极值识别历史支撑/阻力"""
        支撑 = []
        阻力 = []
        for i in range(窗口, len(收盘) - 窗口):
            段 = 收盘[i - 窗口: i + 窗口 + 1]
            if 收盘[i] <= np.min(段):
                支撑.append(float(收盘[i]))
            if 收盘[i] >= np.max(段):
                阻力.append(float(收盘[i]))
        return 支撑, 阻力

    def _ohlc极值法(self, 高: np.ndarray, 低: np.ndarray, 窗口: int = 3) -> tuple:
        """利用最高/最低价影线"""
        支撑 = []
        阻力 = []
        for i in range(窗口, len(高) - 窗口):
            if 低[i] <= np.min(低[i - 窗口: i + 窗口 + 1]):
                支撑.append(float(低[i]))
            if 高[i] >= np.max(高[i - 窗口: i + 窗口 + 1]):
                阻力.append(float(高[i]))
        return 支撑, 阻力

    def _均线法(self, 收盘: np.ndarray, 当前价: float) -> tuple:
        """均线作为动态支撑/阻力"""
        支撑 = []
        阻力 = []
        for p in [5, 10, 20, 30, 60]:
            if len(收盘) >= p:
                ma = float(np.mean(收盘[-p:]))
                if ma < 当前价:
                    支撑.append(ma)
                else:
                    阻力.append(ma)
        return 支撑, 阻力

    def _聚合价位(self, 价位列表: List[float]) -> List[float]:
        """将相邻 ±灵敏度% 的价位聚合为一个"""
        if not 价位列表:
            return []
        sorted_prices = sorted(价位列表)
        聚合结果 = [sorted_prices[0]]
        for p in sorted_prices[1:]:
            if abs(p - 聚合结果[-1]) / (聚合结果[-1] + 1e-10) > self.灵敏度:
                聚合结果.append(p)
            else:
                # 用均值更新
                聚合结果[-1] = (聚合结果[-1] + p) / 2
        return 聚合结果

    def _评估强度(self, 价位列表: List[float], 收盘: np.ndarray, 类型: str) -> str:
        if not 价位列表:
            return "无"
        # 检验每个价位被触及的次数
        总触及 = 0
        for 价位 in 价位列表[:3]:
            容差 = 价位 * self.灵敏度
            触及 = int(np.sum(np.abs(收盘 - 价位) <= 容差))
            总触及 += 触及
        if 总触及 >= 6:
            return "强"
        elif 总触及 >= 3:
            return "中等"
        else:
            return "弱"
