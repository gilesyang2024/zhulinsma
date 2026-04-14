#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 数据标准化模块
将不同来源的数据统一为竹林司马内部格式
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union


class DataNormalizer:
    """
    数据标准化器

    功能：
    - 将 akshare/tushare/baostock 等不同来源 DataFrame 转为统一格式
    - 字段名称映射与标准化
    - 数据类型转换
    - 日期格式统一（YYYY-MM-DD）
    """

    # 各数据源的字段映射（source → standard）
    _字段映射 = {
        "akshare": {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_chg",
        },
        "tushare": {
            "trade_date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "vol": "volume",
            "amount": "amount",
            "pct_chg": "pct_chg",
        },
        "baostock": {
            "date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
            "amount": "amount",
            "pctChg": "pct_chg",
        },
        "yfinance": {
            "Date": "date",
            "Open": "open",
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
        },
    }

    def 标准化(
        self,
        df: pd.DataFrame,
        数据源: str = "akshare",
        股票代码: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        将原始 DataFrame 标准化为统一格式

        返回列：date, open, high, low, close, volume, amount(可选), pct_chg(可选)
        """
        映射 = self._字段映射.get(数据源, {})
        标准df = df.rename(columns={v: k for k, v in 映射.items() if v in df.columns})

        # 反向映射：将源字段名改为标准字段名
        反向映射 = {v: k for k, v in 映射.items()}
        标准df = df.rename(columns=反向映射)

        # 确保 date 列存在且为字符串
        if "date" in 标准df.columns:
            标准df["date"] = pd.to_datetime(标准df["date"]).dt.strftime("%Y-%m-%d")
        elif "trade_date" in 标准df.columns:
            标准df = 标准df.rename(columns={"trade_date": "date"})
            标准df["date"] = pd.to_datetime(标准df["date"]).dt.strftime("%Y-%m-%d")

        # 数值类型转换
        数值列 = ["open", "high", "low", "close", "volume", "amount", "pct_chg"]
        for col in 数值列:
            if col in 标准df.columns:
                标准df[col] = pd.to_numeric(标准df[col], errors="coerce")

        # 排序（按日期升序）
        if "date" in 标准df.columns:
            标准df = 标准df.sort_values("date").reset_index(drop=True)

        if 股票代码:
            标准df["ts_code"] = 股票代码

        return 标准df

    def 提取价格数组(self, df: pd.DataFrame, 字段: str = "close") -> np.ndarray:
        """从标准化 DataFrame 中提取价格数组"""
        if 字段 not in df.columns:
            raise ValueError(f"字段 '{字段}' 不存在，可用: {list(df.columns)}")
        return df[字段].values.astype(float)

    def 验证标准格式(self, df: pd.DataFrame) -> Dict:
        """验证 DataFrame 是否符合竹林司马标准格式"""
        必要列 = {"date", "open", "high", "low", "close", "volume"}
        缺失列 = 必要列 - set(df.columns)
        return {
            "有效": len(缺失列) == 0,
            "缺失列": list(缺失列),
            "数据行数": len(df),
            "日期范围": (df["date"].min(), df["date"].max()) if "date" in df.columns else None,
        }
