#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 趋势分析器
基于均线排列、线性回归、ADX等多维度综合判断趋势
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union


class TrendAnalyzer:
    """
    趋势分析器
    
    功能：
    - 均线排列评分（多头/空头/混乱）
    - 线性回归趋势强度计算
    - ADX 趋势强度指标
    - 多周期趋势综合判断
    - 趋势持续性与转折点识别
    """

    def __init__(self):
        self.分析历史: List[Dict] = []

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def 分析趋势(
        self,
        收盘价: Union[np.ndarray, List[float]],
        最高价: Optional[Union[np.ndarray, List[float]]] = None,
        最低价: Optional[Union[np.ndarray, List[float]]] = None,
    ) -> Dict:
        """
        执行完整趋势分析

        参数:
            收盘价: 收盘价序列（至少60个数据点）
            最高价: 最高价序列（可选，用于计算ADX）
            最低价: 最低价序列（可选，用于计算ADX）

        返回:
            趋势分析结果字典
        """
        收盘 = np.asarray(收盘价, dtype=float)

        均线结果 = self._计算均线排列(收盘)
        线性趋势 = self._线性回归趋势(收盘)
        短期趋势 = self._短期趋势判断(收盘)

        adx结果: Optional[Dict] = None
        if 最高价 is not None and 最低价 is not None:
            高 = np.asarray(最高价, dtype=float)
            低 = np.asarray(最低价, dtype=float)
            adx结果 = self._计算ADX(高, 低, 收盘)

        综合趋势, 趋势强度评分 = self._综合判断(均线结果, 线性趋势, adx结果)

        结果 = {
            "综合趋势": 综合趋势,
            "趋势强度评分": round(趋势强度评分, 2),
            "均线排列": 均线结果,
            "线性回归趋势": 线性趋势,
            "短期趋势": 短期趋势,
            "ADX": adx结果,
            "最新价格": float(收盘[-1]),
            "数据长度": len(收盘),
        }

        self.分析历史.append(结果)
        if len(self.分析历史) > 200:
            self.分析历史 = self.分析历史[-200:]

        return 结果

    def 识别趋势转折点(
        self, 收盘价: Union[np.ndarray, List[float]], 窗口: int = 5
    ) -> Dict:
        """
        识别近期趋势转折点（局部极值）

        返回:
            {"极大值索引": [...], "极小值索引": [...], "最近转折": str}
        """
        收盘 = np.asarray(收盘价, dtype=float)
        极大值 = []
        极小值 = []
        for i in range(窗口, len(收盘) - 窗口):
            窗口段 = 收盘[i - 窗口: i + 窗口 + 1]
            if 收盘[i] == np.max(窗口段):
                极大值.append(i)
            if 收盘[i] == np.min(窗口段):
                极小值.append(i)

        最近转折 = "无"
        if 极大值 and 极小值:
            最后极大 = 极大值[-1]
            最后极小 = 极小值[-1]
            if 最后极大 > 最后极小:
                最近转折 = f"顶部转折（索引{最后极大}）"
            else:
                最近转折 = f"底部转折（索引{最后极小}）"

        return {
            "极大值索引": 极大值,
            "极小值索引": 极小值,
            "极大值数量": len(极大值),
            "极小值数量": len(极小值),
            "最近转折": 最近转折,
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _计算均线排列(self, 收盘: np.ndarray) -> Dict:
        """计算 SMA5/10/20/30/60 排列并评分"""
        周期列表 = [5, 10, 20, 30, 60]
        均线值: Dict[int, float] = {}
        for p in 周期列表:
            if len(收盘) >= p:
                均线值[p] = float(np.mean(收盘[-p:]))

        if len(均线值) < 2:
            return {"排列状态": "数据不足", "多头程度": 0.0, "均线值": 均线值}

        有序周期 = sorted(均线值.keys())
        多头计数 = 0
        总比较 = 0
        for i in range(len(有序周期) - 1):
            短 = 有序周期[i]
            长 = 有序周期[i + 1]
            总比较 += 1
            if 均线值[短] > 均线值[长]:
                多头计数 += 1

        多头程度 = 多头计数 / 总比较

        if 多头程度 >= 0.8:
            排列状态 = "完全多头排列"
        elif 多头程度 >= 0.6:
            排列状态 = "多头排列为主"
        elif 多头程度 <= 0.2:
            排列状态 = "空头排列"
        elif 多头程度 <= 0.4:
            排列状态 = "空头排列为主"
        else:
            排列状态 = "均线交叉混乱"

        # 当前价格相对 MA20 的位置
        价格位置 = "MA20以上" if len(收盘) > 0 and 20 in 均线值 and 收盘[-1] > 均线值[20] else "MA20以下"

        return {
            "排列状态": 排列状态,
            "多头程度": round(多头程度, 4),
            "均线值": {k: round(v, 4) for k, v in 均线值.items()},
            "价格位置": 价格位置,
        }

    def _线性回归趋势(self, 收盘: np.ndarray, 周期: int = 20) -> Dict:
        """对最近 N 个交易日做线性回归，返回斜率与趋势强度"""
        if len(收盘) < 周期:
            return {"趋势方向": "未知", "斜率": 0.0, "R2": 0.0, "强度": "弱"}

        数据段 = 收盘[-周期:]
        x = np.arange(周期, dtype=float)
        y = 数据段

        # 最小二乘法
        x_mean = x.mean()
        y_mean = y.mean()
        斜率 = float(np.sum((x - x_mean) * (y - y_mean)) / (np.sum((x - x_mean) ** 2) + 1e-10))

        # R²
        y_pred = 斜率 * (x - x_mean) + y_mean
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y_mean) ** 2))
        R2 = 1.0 - ss_res / (ss_tot + 1e-10)

        # 标准化斜率（相对于均值）
        标准化斜率 = 斜率 / (y_mean + 1e-10) * 100  # 每日涨跌幅 %

        趋势方向 = "上升" if 斜率 > 0 else ("下降" if 斜率 < 0 else "横盘")
        强度 = "强" if abs(标准化斜率) > 0.3 else ("中等" if abs(标准化斜率) > 0.1 else "弱")

        return {
            "趋势方向": 趋势方向,
            "斜率": round(斜率, 6),
            "标准化斜率": round(标准化斜率, 4),
            "R2": round(R2, 4),
            "强度": 强度,
            "分析周期": 周期,
        }

    def _短期趋势判断(self, 收盘: np.ndarray, 短窗口: int = 5) -> Dict:
        """5日内价格方向判断"""
        if len(收盘) < 短窗口 + 1:
            return {"短期方向": "未知", "5日涨幅": 0.0}

        五日前 = float(收盘[-(短窗口 + 1)])
        最新 = float(收盘[-1])
        涨幅 = (最新 - 五日前) / (五日前 + 1e-10) * 100

        return {
            "短期方向": "上涨" if 涨幅 > 0.5 else ("下跌" if 涨幅 < -0.5 else "横盘"),
            "5日涨幅": round(涨幅, 2),
        }

    def _计算ADX(
        self, 最高: np.ndarray, 最低: np.ndarray, 收盘: np.ndarray, 周期: int = 14
    ) -> Dict:
        """
        计算 ADX（趋势强度）、+DI、-DI
        ADX > 25 视为有趋势，> 50 视为强趋势
        """
        n = len(收盘)
        if n < 周期 + 1:
            return {"ADX": None, "DI+": None, "DI-": None, "趋势强度": "数据不足"}

        # True Range
        tr = np.zeros(n)
        for i in range(1, n):
            hl = 最高[i] - 最低[i]
            hpc = abs(最高[i] - 收盘[i - 1])
            lpc = abs(最低[i] - 收盘[i - 1])
            tr[i] = max(hl, hpc, lpc)

        # Directional Movement
        dm_plus = np.zeros(n)
        dm_minus = np.zeros(n)
        for i in range(1, n):
            up = 最高[i] - 最高[i - 1]
            down = 最低[i - 1] - 最低[i]
            dm_plus[i] = up if up > down and up > 0 else 0.0
            dm_minus[i] = down if down > up and down > 0 else 0.0

        # Smooth
        def _smooth(arr: np.ndarray, p: int) -> np.ndarray:
            s = np.zeros(len(arr))
            s[p] = arr[1: p + 1].sum()
            for i in range(p + 1, len(arr)):
                s[i] = s[i - 1] - s[i - 1] / p + arr[i]
            return s

        atr14 = _smooth(tr, 周期)
        dm_p14 = _smooth(dm_plus, 周期)
        dm_m14 = _smooth(dm_minus, 周期)

        DI_plus = 100 * dm_p14 / (atr14 + 1e-10)
        DI_minus = 100 * dm_m14 / (atr14 + 1e-10)
        DX = 100 * np.abs(DI_plus - DI_minus) / (DI_plus + DI_minus + 1e-10)

        adx_arr = np.zeros(n)
        adx_arr[2 * 周期] = DX[周期 + 1: 2 * 周期 + 1].mean() if 2 * 周期 < n else 0.0
        for i in range(2 * 周期 + 1, n):
            adx_arr[i] = (adx_arr[i - 1] * (周期 - 1) + DX[i]) / 周期

        adx_val = float(adx_arr[-1])
        di_p_val = float(DI_plus[-1])
        di_m_val = float(DI_minus[-1])

        if adx_val > 50:
            趋势强度 = "极强趋势"
        elif adx_val > 25:
            趋势强度 = "有趋势"
        elif adx_val > 15:
            趋势强度 = "弱趋势"
        else:
            趋势强度 = "无趋势/震荡"

        return {
            "ADX": round(adx_val, 2),
            "DI+": round(di_p_val, 2),
            "DI-": round(di_m_val, 2),
            "趋势强度": 趋势强度,
            "方向": "多头" if di_p_val > di_m_val else "空头",
        }

    def _综合判断(
        self,
        均线结果: Dict,
        线性趋势: Dict,
        adx结果: Optional[Dict],
    ) -> Tuple[str, float]:
        """综合均线、线性回归、ADX，输出趋势标签和评分(0~10)"""
        评分 = 5.0  # 基础分

        # 均线贡献（±2分）
        多头程度 = 均线结果.get("多头程度", 0.5)
        评分 += (多头程度 - 0.5) * 4  # 满多头→+2，满空头→-2

        # 线性回归贡献（±2分）
        标准化斜率 = 线性趋势.get("标准化斜率", 0.0)
        评分 += min(2.0, max(-2.0, 标准化斜率* 3))

        # ADX 贡献（方向±1分，强度修正）
        if adx结果 and adx结果.get("ADX") is not None:
            adx = adx结果["ADX"]
            方向 = adx结果.get("方向", "")
            adx调整 = (adx - 25) / 50  # 0~1
            if 方向 == "多头":
                评分 += adx调整
            else:
                评分 -= adx调整

        评分 = min(10.0, max(0.0, 评分))

        if 评分 >= 7:
            标签 = "上升趋势"
        elif 评分 >= 5.5:
            标签 = "偏多震荡"
        elif 评分 >= 4.5:
            标签 = "横盘震荡"
        elif 评分 >= 3:
            标签 = "偏空震荡"
        else:
            标签 = "下降趋势"

        return 标签, 评分
