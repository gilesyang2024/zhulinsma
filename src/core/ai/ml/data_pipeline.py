#!/usr/bin/env python3
"""
MLDataPipeline - 数据管道
从 AkShare → 特征工程 → 标注构建 → ML训练集

竹林司马 AI驱动A股技术分析引擎 · ML预测模块
"""

from __future__ import annotations

import os
import json
import subprocess
import numpy as np
import pandas as pd
import warnings
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from feature_engineering import MLFeatureEngine


class LabelBuilder:
    """
    标签构建器
    基于未来N日收益率构建涨跌标签（0=跌，1=涨）
    """

    @staticmethod
    def add_labels(
        df: pd.DataFrame,
        horizons: List[int] = [1, 5, 20],
    ) -> pd.DataFrame:
        """
        添加未来N日涨跌标签

        参数:
            df:      特征DataFrame（来自 MLFeatureEngine.build_features）
            horizons: 预测周期列表，默认 [1, 5, 20] 天

        返回:
            添加了 label_next_{N}d 列的 DataFrame
        """
        df = df.copy().reset_index(drop=True)
        close = df["close"].values.astype(float)

        for h in horizons:
            label_col  = f"label_next_{h}d"
            prob_col   = f"return_next_{h}d"
            future_ret = np.full(len(df), np.nan)
            for i in range(len(df) - h):
                future_ret[i] = (close[i + h] / (close[i] + 1e-10) - 1) * 100
            df[prob_col]  = future_ret
            df[label_col] = (future_ret > 0).astype(int)

        return df

    @staticmethod
    def add_risk_labels(df: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
        """
        添加风险标签：最大回撤、VaR

        参数:
            df:      特征DataFrame
            horizon: 回看窗口，默认20日

        返回:
            添加 max_drawdown_{N}d, var_95_{N}d 列
        """
        df = df.copy().reset_index(drop=True)
        close = df["close"].values.astype(float)

        max_dd = np.full(len(df), np.nan)
        var_95 = np.full(len(df), np.nan)

        for i in range(horizon, len(df)):
            window = close[i - horizon + 1:i + 1]
            peak = np.maximum.accumulate(window)
            dd = (window - peak) / (peak + 1e-10) * 100
            max_dd[i] = np.min(dd)
            returns = np.diff(window, prepend=window[0]) / (window[0] + 1e-10) * 100
            sorted_ret = np.sort(returns)
            cutoff = int(np.ceil(0.05 * len(sorted_ret)))
            var_95[i] = sorted_ret[cutoff] if cutoff < len(sorted_ret) else sorted_ret[-1]

        df[f"max_drawdown_{horizon}d"] = max_dd
        df[f"var_95_{horizon}d"]        = var_95

        return df


class MLDataPipeline:
    """
    ML数据管道

    端到端：AkShare原始数据 → 清洗 → 特征 → 标注 → 训练集

    使用方式：
        pipeline = MLDataPipeline(stock_codes=["600000","000001"])
        dataset  = pipeline.build_dataset(start_date="20180101", end_date="20251231")
        X_train, y_train = dataset["X_train"], dataset["y_train"]
    """

    def __init__(
        self,
        stock_codes: Optional[List[str]] = None,
        index_code: str = "sh000001",
        lookback: int = 200,
    ):
        """
        参数:
            stock_codes: 股票代码列表，None=使用沪深300成分
            index_code:  大盘指数代码
            lookback:    特征计算回看天数
        """
        self.stock_codes = stock_codes or []
        self.index_code  = index_code
        self.feature_engine = MLFeatureEngine(lookback=lookback)
        self._index_df: Optional[pd.DataFrame] = None

    def build_dataset(
        self,
        start_date: str = "20180101",
        end_date: str = "20251231",
        horizons: List[int] = [1, 5, 20],
        min_samples: int = 100,
    ) -> Dict[str, pd.DataFrame]:
        """
        构建完整ML数据集

        参数:
            start_date:  数据开始日期
            end_date:    数据结束日期
            horizons:    预测周期
            min_samples: 单只股票最少样本数

        返回:
            Dict: {"features": DataFrame, "labels": DataFrame}
        """
        import akshare as ak

        def _finance_data_daily(ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
            """通过 finance-data API 获取日线数据（支持代理网络）"""
            token = os.getenv("NEODATA_TOKEN")
            if not token:
                return None
            try:
                cmd = [
                    "curl", "-s", "-X", "POST",
                    "https://www.codebuddy.cn/v2/tool/financedata",
                    "-H", "Content-Type: application/json",
                    "-H", f"Authorization: Bearer {token}",
                    "-d", json.dumps({
                        "api_name": "daily",
                        "params": {"ts_code": ts_code, "start_date": start, "end_date": end},
                        "fields": ""
                    })
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                result = json.loads(r.stdout)
                if result.get("code") != 0:
                    return None
                data = result.get("data") or {}
                fields = data.get("fields", [])
                items = data.get("items", [])
                if not items:
                    return None
                df = pd.DataFrame(items, columns=fields)
                df = df.rename(columns={
                    "trade_date": "date", "vol": "volume",
                    "pct_chg": "pct_change",
                })
                # date 列是整数 "20200102"，必须先转字符串
                df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
                for col in ["open", "high", "low", "close", "volume", "amount",
                             "pct_chg", "change", "pre_close"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
                return df.sort_values("date").reset_index(drop=True)
            except Exception:
                return None

        all_features: List[pd.DataFrame] = []
        print(f"[MLDataPipeline] 开始构建数据集，日期范围: {start_date} ~ {end_date}")

        # 获取大盘指数（用于情绪特征）
        self._index_df = None
        try:
            idx_ts = self._index_to_tscode(self.index_code)
            self._index_df = self._finance_index_daily(idx_ts, start_date, end_date)
            if self._index_df is not None and len(self._index_df) > 10:
                print(f"[MLDataPipeline] 指数数据获取成功: {self.index_code} ({len(self._index_df)}条)")
            else:
                raise ValueError("finance-data 返回空")
        except Exception as e:
            print(f"[MLDataPipeline] 指数数据获取失败: {e}，将跳过相对强弱特征")

        # 遍历股票
        for code in self.stock_codes:
            try:
                ts_code = self._code_to_tscode(code)
                df_raw = _finance_data_daily(ts_code, start_date, end_date)
                if df_raw is None or len(df_raw) < 20:
                    # finance-data 失败，降级 AkShare
                    mkt, sym = self._normalize(code)
                    df_raw = ak.stock_zh_a_hist(
                        symbol=f"{mkt}{sym}", period="daily",
                        start_date=start_date, end_date=end_date, adjust="qfq",
                    )
                    df_raw = self._normalize_columns(df_raw)
                df_feat = self.feature_engine.build_features(
                    df_raw,
                    stock_code=code,
                    index_df=self._index_df,
                )
                if len(df_feat) >= min_samples:
                    all_features.append(df_feat)
                    print(f"  ✓ {code}: {len(df_feat)} 样本")
                else:
                    print(f"  ✗ {code}: 样本不足({len(df_feat)})")
            except Exception as e:
                print(f"  ✗ {code}: 获取失败 {e}")

        if not all_features:
            raise ValueError("所有股票数据获取失败，请检查股票代码和网络连接")

        df_all = pd.concat(all_features, ignore_index=True)

        # 添加标签
        df_all = LabelBuilder.add_labels(df_all, horizons=horizons)
        df_all = LabelBuilder.add_risk_labels(df_all, horizon=20)

        print(f"[MLDataPipeline] 数据集构建完成: {len(df_all)} 条样本，特征数: {len(df_all.columns) - 10}")

        drop_cols = [c for c in ["return_next_1d","return_next_5d","return_next_20d",
                                  "max_drawdown_20d","var_95_20d"] + [f"label_next_{h}d" for h in horizons]
                     if c in df_all.columns]
        label_cols = ["stock_code","date"] + [f"label_next_{h}d" for h in horizons] + \
                     ["return_next_1d","return_next_5d","return_next_20d",
                      "max_drawdown_20d","var_95_20d"]
        return {
            "features": df_all.drop(columns=drop_cols),
            "labels":   df_all[label_cols],
        }

    def prepare_single_stock(
        self,
        df_daily: pd.DataFrame,
        stock_code: str = "UNKNOWN",
        horizons: List[int] = [1, 5, 20],
    ) -> pd.DataFrame:
        """
        单只股票实时推理准备（无需未来标签）

        参数:
            df_daily:   日K DataFrame (date/open/high/low/close/volume)
            stock_code: 股票代码
            horizons:   预测周期

        返回:
            特征DataFrame（最后一行即为今日特征）
        """
        df_feat = self.feature_engine.build_features(
            df_daily,
            stock_code=stock_code,
            index_df=self._index_df,
        )
        df_feat = LabelBuilder.add_labels(df_feat, horizons=horizons)
        return df_feat

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
        }
        df = df.rename(columns=col_map)
        return df

    @staticmethod
    def _normalize(code: str) -> Tuple[str, str]:
        c = code.strip().upper()
        if c.startswith("60") or c.startswith("5"):
            return "sh", c
        elif c.startswith(("00", "30", "8", "4")):
            return "sz", c
        elif c.startswith("8") or c.startswith("4"):
            return "bj", c
        return "sh", c

    @staticmethod
    def _code_to_tscode(code: str) -> str:
        """股票代码 → finance-data ts_code 格式"""
        c = code.strip().upper()
        if "." in c:
            return c
        if c.startswith("60") or c.startswith("5"):
            return f"{c}.SH"
        if c.startswith("00") or c.startswith("30"):
            return f"{c}.SZ"
        if c.startswith("8") or c.startswith("4"):
            return f"{c}.BJ"
        return f"{c}.SH"

    @staticmethod
    def _index_to_tscode(index_code: str) -> str:
        """指数代码 → finance-data ts_code 格式"""
        c = index_code.strip().lower()
        mapping = {
            "sh000001": "000001.SH", "sh000300": "000300.SH",
            "sh000016": "000016.SH", "sh000688": "000688.SH",
            "sz399001": "399001.SZ", "sz399006": "399006.SZ",
            "000001": "000001.SH", "000300": "000300.SH",
            "399001": "399001.SZ", "399006": "399006.SZ",
        }
        return mapping.get(c, mapping.get(c.upper(), c.upper() + ".SH"))

    @staticmethod
    def _finance_index_daily(ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """通过 finance-data index_daily API 获取指数日线数据"""
        token = os.getenv("NEODATA_TOKEN")
        if not token:
            return None
        try:
            cmd = [
                "curl", "-s", "-X", "POST",
                "https://www.codebuddy.cn/v2/tool/financedata",
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {token}",
                "-d", json.dumps({
                    "api_name": "index_daily",
                    "params": {"ts_code": ts_code, "start_date": start, "end_date": end},
                    "fields": ""
                })
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            result = json.loads(r.stdout)
            if result.get("code") != 0:
                return None
            data = result.get("data") or {}
            fields = data.get("fields", [])
            items = data.get("items", [])
            if not items:
                return None
            df = pd.DataFrame(items, columns=fields)
            df = df.rename(columns={"trade_date": "date", "vol": "volume"})
            df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
            return df.sort_values("date").reset_index(drop=True)
        except Exception:
            return None
