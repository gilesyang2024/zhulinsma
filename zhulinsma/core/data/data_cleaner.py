#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 数据清洗模块
处理缺失值、异常值、时间序列对齐等常见数据问题
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union


class DataCleaner:
    """
    数据清洗器

    功能：
    - 缺失值检测与填充（前向填充 / 线性插值 / 均值填充）
    - 异常值检测与处理（Z-score / IQR 方法）
    - 时间序列连续性校验（检测日期跳空）
    - 价格有效性验证（负数/零值/跳价检测）
    - 清洗报告生成
    """

    def __init__(self, 异常值方法: str = "iqr", 填充方法: str = "ffill"):
        """
        参数:
            异常值方法: 'iqr'（四分位距法）或 'zscore'（Z分数法）
            填充方法: 'ffill'（前向）/ 'bfill'（后向）/ 'linear'（线性插值）/ 'mean'（均值）
        """
        self.异常值方法 = 异常值方法
        self.填充方法 = 填充方法
        self._清洗报告: List[Dict] = []

    def 清洗数据(
        self,
        收盘价: Union[np.ndarray, List[float], pd.Series],
        时间索引: Optional[pd.DatetimeIndex] = None,
    ) -> Dict:
        """
        执行完整数据清洗流水线

        返回:
            {
                "清洗后数据": np.ndarray,
                "原始长度": int,
                "清洗后长度": int,
                "缺失值数量": int,
                "异常值数量": int,
                "清洗报告": [...]
            }
        """
        if isinstance(收盘价, pd.Series):
            数据 = 收盘价.values.astype(float)
        else:
            数据 = np.asarray(收盘价, dtype=float)

        原始长度 = len(数据)
        报告: List[str] = []

        # Step 1: 负值/零值处理
        无效掩码 = 数据 <= 0
        if 无效掩码.any():
            数据[无效掩码] = np.nan
            报告.append(f"检测到{无效掩码.sum()}个无效价格（≤0），已替换为NaN")

        # Step 2: 缺失值统计
        缺失数量 = int(np.isnan(数据).sum())

        # Step 3: 异常值检测
        异常掩码 = self._检测异常值(数据)
        异常数量 = int(异常掩码.sum())
        if 异常数量 > 0:
            数据[异常掩码] = np.nan
            报告.append(f"检测到{异常数量}个异常值（{self.异常值方法}），已替换为NaN")

        # Step 4: 填充缺失值
        数据 = self._填充缺失值(数据)
        报告.append(f"已使用'{self.填充方法}'方法填充缺失值")

        # Step 5: 时间连续性检查
        日期报告 = ""
        if 时间索引 is not None:
            日期报告 = self._检查时间连续性(时间索引)
            if 日期报告:
                报告.append(日期报告)

        self._清洗报告.extend(报告)

        return {
            "清洗后数据": 数据,
            "原始长度": 原始长度,
            "清洗后长度": len(数据),
            "缺失值数量": 缺失数量,
            "异常值数量": 异常数量,
            "清洗报告": 报告,
            "数据质量": self._计算质量分(缺失数量, 异常数量, 原始长度),
        }

    def 验证价格有效性(self, 价格: Union[np.ndarray, List[float]]) -> Dict:
        """快速验证价格序列的基本有效性"""
        数据 = np.asarray(价格, dtype=float)
        问题列表 = []

        if np.any(np.isnan(数据)):
            问题列表.append(f"含{np.isnan(数据).sum()}个NaN值")
        if np.any(数据 <= 0):
            问题列表.append(f"含{(数据 <= 0).sum()}个非正数价格")

        # 跳价检测（相邻日涨跌超过20%）
        涨跌幅 = np.abs(np.diff(数据) / (数据[:-1] + 1e-10))
        大跳价 = np.sum(涨跌幅 > 0.20)
        if 大跳价 > 0:
            问题列表.append(f"含{大跳价}个超20%的单日跳价")

        return {
            "有效": len(问题列表) == 0,
            "问题列表": 问题列表,
            "数据长度": len(数据),
            "价格范围": (round(float(np.nanmin(数据)), 4), round(float(np.nanmax(数据)), 4)),
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _检测异常值(self, 数据: np.ndarray) -> np.ndarray:
        有效 = 数据[~np.isnan(数据)]
        if len(有效) < 4:
            return np.zeros(len(数据), dtype=bool)

        if self.异常值方法 == "iqr":
            Q1 = np.percentile(有效, 25)
            Q3 = np.percentile(有效, 75)
            IQR = Q3 - Q1
            下界, 上界 = Q1 - 3 * IQR, Q3 + 3 * IQR
            return ~np.isnan(数据) & ((数据 < 下界) | (数据 > 上界))
        else:  # zscore
            均值 = np.nanmean(数据)
            标准差 = np.nanstd(数据)
            z分数 = np.abs((数据 - 均值) / (标准差 + 1e-10))
            return ~np.isnan(数据) & (z分数 > 3.5)

    def _填充缺失值(self, 数据: np.ndarray) -> np.ndarray:
        series = pd.Series(数据)
        if self.填充方法 == "ffill":
            series = series.ffill().bfill()
        elif self.填充方法 == "bfill":
            series = series.bfill().ffill()
        elif self.填充方法 == "linear":
            series = series.interpolate(method="linear").ffill().bfill()
        elif self.填充方法 == "mean":
            series = series.fillna(series.mean())
        return series.values.astype(float)

    def _检查时间连续性(self, 时间索引: pd.DatetimeIndex) -> str:
        if len(时间索引) < 2:
            return ""
        间隔 = (时间索引[1:] - 时间索引[:-1]).days
        异常间隔 = np.sum(间隔 > 5)  # 允许周末+节假日，超5天视为异常跳空
        if 异常间隔 > 0:
            return f"检测到{异常间隔}处时间跳空（间隔>5天）"
        return ""

    def _计算质量分(self, 缺失: int, 异常: int, 总长: int) -> float:
        if 总长 == 0:
            return 0.0
        扣分 = (缺失 + 异常) / 总长
        return round(max(0.0, 1.0 - 扣分), 4)
