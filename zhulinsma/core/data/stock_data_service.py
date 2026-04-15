#!/usr/bin/env python3
"""
竹林司马 - 统一数据获取服务
版本: 1.0.0
日期: 2026年4月14日
位置: 广州

提供统一的股票数据获取接口，支持:
- 历史日线数据 (akshare)
- 实时行情数据 (akshare)
- 数据标准化和缓存
- 技术指标计算集成
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from zhulinsma.core.data.data_normalizer import DataNormalizer
from zhulinsma.core.data.data_cache import DataCache
from zhulinsma.core.data.data_cleaner import DataCleaner


class StockDataService:
    """
    统一股票数据服务

    打通 数据获取 → 标准化 → 清洗 → 缓存 → 指标计算 的完整链路
    """

    def __init__(self, 缓存目录: str = ".cache/stock_data"):
        self._normalizer = DataNormalizer()
        self._cleaner = DataCleaner()
        self._cache = DataCache(磁盘缓存目录=缓存目录)
        self._数据源可用 = {"akshare": False}
        self._检测数据源()

    def _检测数据源(self) -> Dict[str, bool]:
        """检测可用数据源"""
        try:
            import akshare as ak
            self._数据源可用["akshare"] = True
        except ImportError:
            self._数据源可用["akshare"] = False
        return self._数据源可用

    # ============ 历史数据获取 ============

    def 获取历史数据(
        self,
        股票代码: str,
        开始日期: Optional[str] = None,
        结束日期: Optional[str] = None,
        周期: str = "daily",
        复权: str = "qfq",
        使用缓存: bool = True,
    ) -> pd.DataFrame:
        """
        获取标准化的历史日线数据

        参数:
            股票代码: 6位代码 (如 "600406")
            开始日期: YYYYMMDD 格式 (默认: 120天前)
            结束日期: YYYYMMDD 格式 (默认: 今天)
            周期: daily/weekly/monthly
            复权: qfq(前复权)/hfq(后复权)/""(不复权)
            使用缓存: 是否使用缓存

        返回:
            标准化 DataFrame: date, open, high, low, close, volume, amount, pct_chg
        """
        if 开始日期 is None:
            开始日期 = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        if 结束日期 is None:
            结束日期 = datetime.now().strftime("%Y%m%d")

        cache_key = f"hist_{股票代码}_{开始日期}_{结束日期}_{周期}_{复权}"

        # 检查缓存
        if 使用缓存:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return pd.DataFrame(cached)

        # 获取数据
        if self._数据源可用["akshare"]:
            df = self._akshare历史数据(股票代码, 开始日期, 结束日期, 周期, 复权)
        else:
            raise RuntimeError("无可用数据源，请安装 akshare: pip install akshare")

        if df is None or df.empty:
            raise ValueError(f"无法获取 {股票代码} 的历史数据")

        # 标准化
        df = self._normalizer.标准化(df, 数据源="akshare", 股票代码=股票代码)

        # 清洗
        df = self._cleaner.清洗数据(df)

        # 缓存
        if 使用缓存:
            self._cache.set(cache_key, df.to_dict("records"))

        return df

    def _akshare历史数据(
        self, 股票代码: str, 开始日期: str, 结束日期: str, 周期: str, 复权: str
    ) -> pd.DataFrame:
        """通过 akshare 获取历史数据"""
        import akshare as ak

        # 清除可能的代理设置（akshare 请求国内 API 不需要代理）
        import os
        old_http_proxy = os.environ.pop("http_proxy", None)
        old_https_proxy = os.environ.pop("https_proxy", None)
        old_HTTP_PROXY = os.environ.pop("HTTP_PROXY", None)
        old_HTTPS_PROXY = os.environ.pop("HTTPS_PROXY", None)
        old_all_proxy = os.environ.pop("all_proxy", None)
        old_ALL_PROXY = os.environ.pop("ALL_PROXY", None)

        try:
            df = ak.stock_zh_a_hist(
                symbol=股票代码,
                period=周期,
                start_date=开始日期,
                end_date=结束日期,
                adjust=复权,
            )
            return df
        finally:
            # 恢复代理设置
            for k, v in [("http_proxy", old_http_proxy), ("https_proxy", old_https_proxy),
                        ("HTTP_PROXY", old_HTTP_PROXY), ("HTTPS_PROXY", old_HTTPS_PROXY),
                        ("all_proxy", old_all_proxy), ("ALL_PROXY", old_ALL_PROXY)]:
                if v is not None:
                    os.environ[k] = v

    # ============ 实时数据获取 ============

    def 获取实时行情(self, 股票代码列表: List[str]) -> List[Dict]:
        """
        获取实时行情快照

        参数:
            股票代码列表: ["600406", "000001"]

        返回:
            行情字典列表
        """
        if not self._数据源可用["akshare"]:
            raise RuntimeError("无可用数据源")

        import akshare as ak
        import os

        # 清除代理
        old_env = {k: os.environ.pop(k, None) for k in
                  ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]}

        try:
            results = []
            for code in 股票代码列表:
                try:
                    symbol = code.split(".")[0]
                    df = ak.stock_bid_ask_em(symbol=symbol)
                    if df is not None and not df.empty:
                        def _get(item: str) -> float:
                            row = df[df["item"] == item]
                            return float(row["value"].values[0]) if not row.empty else 0.0

                        results.append({
                            "股票代码": code,
                            "最新价": _get("最新"),
                            "昨收": _get("昨收"),
                            "今开": _get("今开"),
                            "最高": _get("最高"),
                            "最低": _get("最低"),
                            "成交量": int(_get("总手") * 100),
                            "成交额": _get("金额"),
                            "涨幅": _get("涨幅"),
                            "换手率": _get("换手"),
                            "量比": _get("量比"),
                            "涨停": _get("涨停"),
                            "跌停": _get("跌停"),
                            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                except Exception as e:
                    results.append({"股票代码": code, "错误": str(e)})
            return results
        finally:
            for k, v in old_env.items():
                if v is not None:
                    os.environ[k] = v

    # ============ 技术指标集成 ============

    def 计算技术指标(
        self,
        股票代码: str,
        指标列表: Optional[List[str]] = None,
        使用缓存: bool = True,
    ) -> Dict[str, Any]:
        """
        一站式获取数据+计算技术指标

        参数:
            股票代码: 6位代码
            指标列表: 默认全部 (SMA_5, SMA_10, SMA_20, EMA_12, EMA_26, RSI_14, MACD, 布林带)

        返回:
            {
                "股票代码": str,
                "数据范围": (开始日期, 结束日期),
                "数据长度": int,
                "最新价": float,
                "指标": {指标名: {值}},
                "原始数据": DataFrame
            }
        """
        if 指标列表 is None:
            指标列表 = ["SMA_5", "SMA_10", "SMA_20", "EMA_12", "EMA_26", "RSI_14", "MACD", "布林带"]

        # 获取历史数据
        df = self.获取历史数据(股票代码, 使用缓存=使用缓存)

        # 延迟导入指标引擎
        from zhulinsma.core.indicators.optimized_indicators import OptimizedTechnicalIndicators

        engine = OptimizedTechnicalIndicators(验证模式=False, 优化模式="auto")
        close = df["close"].values

        # 计算各项指标
        指标结果 = {}

        for 指标 in 指标列表:
            if 指标.startswith("SMA_"):
                周期 = int(指标.split("_")[1])
                vals = engine.SMA(close, 周期=周期)
                指标结果[指标] = {"最新值": float(vals[-1]) if not np.isnan(vals[-1]) else None}
            elif 指标.startswith("EMA_"):
                周期 = int(指标.split("_")[1])
                vals = engine.EMA(close, 周期=周期)
                指标结果[指标] = {"最新值": float(vals[-1]) if not np.isnan(vals[-1]) else None}
            elif 指标 == "RSI_14":
                vals = engine.RSI(close, 周期=14)
                最新RSI = float(vals[-1]) if not np.isnan(vals[-1]) else None
                指标结果["RSI_14"] = {
                    "最新值": 最新RSI,
                    "状态": "超买" if 最新RSI and 最新RSI >= 70 else ("超卖" if 最新RSI and 最新RSI <= 30 else "中性"),
                }
            elif 指标 == "MACD":
                result = engine.MACD(close)
                macd_val = float(result["macd"][-1]) if not np.isnan(result["macd"][-1]) else None
                signal_val = float(result["signal"][-1]) if not np.isnan(result["signal"][-1]) else None
                hist_val = float(result["histogram"][-1]) if not np.isnan(result["histogram"][-1]) else None
                指标结果["MACD"] = {
                    "MACD线": macd_val,
                    "信号线": signal_val,
                    "柱状图": hist_val,
                    "信号": "金叉" if macd_val and signal_val and macd_val > signal_val and hist_val > 0 else
                            ("死叉" if macd_val and signal_val and macd_val < signal_val and hist_val < 0 else "盘整"),
                }
            elif 指标 == "布林带":
                from zhulinsma.core.indicators.optimized_indicators import vectorized_BollingerBands
                result = vectorized_BollingerBands(close)
                指标结果["布林带"] = {
                    "上轨": float(result["upper"][-1]) if not np.isnan(result["upper"][-1]) else None,
                    "中轨": float(result["middle"][-1]) if not np.isnan(result["middle"][-1]) else None,
                    "下轨": float(result["lower"][-1]) if not np.isnan(result["lower"][-1]) else None,
                    "带宽": float(result["bandwidth"][-1]) if not np.isnan(result["bandwidth"][-1]) else None,
                }

        return {
            "股票代码": 股票代码,
            "数据范围": (df["date"].iloc[0], df["date"].iloc[-1]),
            "数据长度": len(df),
            "最新价": float(close[-1]),
            "指标": 指标结果,
            "原始数据": df,
        }

    # ============ 综合分析 ============

    def 综合分析(self, 股票代码: str) -> Dict[str, Any]:
        """
        综合技术分析报告

        整合趋势分析、技术指标、风险评估
        """
        from zhulinsma.core.analysis.trend_analyzer import TrendAnalyzer
        from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer

        # 获取数据
        df = self.获取历史数据(股票代码)
        close = df["close"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)

        # 技术指标
        指标结果 = self.计算技术指标(股票代码, 使用缓存=False)

        # 趋势分析
        趋势分析器 = TrendAnalyzer()
        趋势结果 = 趋势分析器.分析趋势(close, high, low)

        # 风险分析
        风险分析器 = RiskAnalyzer()
        volume = df["volume"].values.astype(float) if "volume" in df.columns else None
        rsi_vals = None
        指标 = 指标结果.get("指标", {})
        if "RSI_14" in 指标 and 指标["RSI_14"]["最新值"] is not None:
            rsi_vals = np.full(len(close), 指标["RSI_14"]["最新值"])
        风险结果 = 风险分析器.评估风险(close, volume, rsi_vals)

        return {
            "股票代码": 股票代码,
            "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "最新价": float(close[-1]),
            "技术指标": 指标结果["指标"],
            "趋势分析": 趋势结果,
            "风险评估": 风险结果,
            "数据范围": 指标结果["数据范围"],
            "免责声明": "本分析基于历史数据，仅供参考，不构成投资建议。投资有风险，入市需谨慎。",
        }

    def 数据源状态(self) -> Dict[str, Any]:
        """获取数据源可用状态"""
        return {
            "数据源": self._数据源可用,
            "缓存统计": self._cache.统计信息(),
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ========== 测试 ==========

if __name__ == "__main__":
    import json

    service = StockDataService()

    print("=== 数据源状态 ===")
    print(json.dumps(service.数据源状态(), indent=2, ensure_ascii=False, default=str))

    print("\n=== 获取 600406 历史数据 ===")
    df = service.获取历史数据("600406", 开始日期="20260301")
    print(f"数据行数: {len(df)}")
    print(df.tail(3).to_string())

    print("\n=== 计算技术指标 ===")
    result = service.计算技术指标("600406")
    print(f"最新价: {result['最新价']}")
    for name, data in result["指标"].items():
        print(f"  {name}: {data}")

    print("\n=== 综合分析 ===")
    report = service.综合分析("600406")
    print(f"趋势: {report['趋势分析']}")
    print(f"风险: {report['风险评估']}")
