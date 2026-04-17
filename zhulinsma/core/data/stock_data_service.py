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

    # ============================================================
    # 新增：七大维度数据获取（2026-04-16 增强）
    # 覆盖：资金流向 / 北向资金 / 龙虎榜 / 公告 / 财务 / 板块 / 大盘
    # ============================================================

    def _清理代理(self) -> Dict:
        """清除代理环境变量，返回旧值以便恢复"""
        import os
        keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]
        return {k: os.environ.pop(k, None) for k in keys}

    def _恢复代理(self, old_env: Dict) -> None:
        import os
        for k, v in old_env.items():
            if v is not None:
                os.environ[k] = v

    def 获取资金流向(self, 股票代码: str) -> Dict[str, Any]:
        """
        获取个股资金流向数据（东方财富）

        返回:
            {
                "主力净流入": float（元）,
                "主力净流入占比": float（%）,
                "超大单净流入": float,
                "大单净流入": float,
                "中单净流入": float,
                "小单净流入": float,
                "更新时间": str,
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用", "主力净流入": 0}

        import akshare as ak
        old_env = self._清理代理()
        try:
            symbol = 股票代码.split(".")[0]
            df = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith("6") else "sz")
            if df is None or df.empty:
                return {"错误": "无资金流向数据", "主力净流入": 0}

            latest = df.iloc[-1]
            result = {
                "更新日期": str(latest.get("日期", "")),
                "主力净流入": float(latest.get("主力净流入-净额", 0) or 0),
                "主力净流入占比": float(latest.get("主力净流入-净占比", 0) or 0),
                "超大单净流入": float(latest.get("超大单净流入-净额", 0) or 0),
                "大单净流入": float(latest.get("大单净流入-净额", 0) or 0),
                "中单净流入": float(latest.get("中单净流入-净额", 0) or 0),
                "小单净流入": float(latest.get("小单净流入-净额", 0) or 0),
            }
            # 辅助判断
            主力 = result["主力净流入"]
            result["资金流向判断"] = (
                "主力大幅净流入" if 主力 > 5e7 else
                "主力净流入" if 主力 > 1e7 else
                "主力小幅流入" if 主力 > 0 else
                "主力小幅流出" if 主力 > -1e7 else
                "主力大幅净流出"
            )
            return result
        except Exception as e:
            return {"错误": str(e), "主力净流入": 0}
        finally:
            self._恢复代理(old_env)

    def 获取北向资金(self) -> Dict[str, Any]:
        """
        获取北向资金（沪深港通）今日及近期数据

        返回:
            {
                "今日北向净买入": float（亿元）,
                "沪股通净买入": float,
                "深股通净买入": float,
                "近5日累计": float,
                "市场情绪": str,
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用", "今日北向净买入": 0}

        import akshare as ak
        old_env = self._清理代理()
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")
            if df is None or df.empty:
                return {"错误": "无北向资金数据", "今日北向净买入": 0}

            df = df.tail(5)
            today_val = float(df.iloc[-1].get("当日资金流入", 0) or 0)
            recent_5 = float(df["当日资金流入"].sum() or 0)

            return {
                "今日北向净买入(亿)": round(today_val / 1e8, 2),
                "近5日累计(亿)": round(recent_5 / 1e8, 2),
                "市场情绪": (
                    "外资大幅买入" if today_val > 50e8 else
                    "外资净买入" if today_val > 0 else
                    "外资净卖出" if today_val > -50e8 else
                    "外资大幅撤离"
                ),
                "更新日期": str(df.iloc[-1].get("日期", "")),
            }
        except Exception as e:
            return {"错误": str(e), "今日北向净买入(亿)": 0}
        finally:
            self._恢复代理(old_env)

    def 获取龙虎榜(self, 股票代码: str, 最近天数: int = 20) -> Dict[str, Any]:
        """
        获取个股近期龙虎榜记录

        返回:
            {
                "上榜次数": int,
                "机构买入次数": int,
                "净买入合计": float（元）,
                "上榜记录": [...],
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用", "上榜次数": 0}

        import akshare as ak
        from datetime import datetime, timedelta
        old_env = self._清理代理()
        try:
            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=最近天数)).strftime("%Y%m%d")
            symbol = 股票代码.split(".")[0]

            df = ak.stock_lhb_detail_em(symbol=symbol, start_date=start, end_date=end)
            if df is None or df.empty:
                return {"上榜次数": 0, "机构买入次数": 0, "净买入合计": 0, "上榜记录": []}

            上榜次数 = len(df)
            records = []
            净买入合计 = 0.0
            机构买入 = 0

            for _, row in df.iterrows():
                净额 = float(row.get("净额", 0) or 0)
                净买入合计 += 净额
                营业部 = str(row.get("营业部名称", ""))
                if "机构" in 营业部 or "基金" in 营业部:
                    机构买入 += 1
                records.append({
                    "日期": str(row.get("上榜日期", "")),
                    "上榜原因": str(row.get("上榜原因", "")),
                    "净额(万)": round(净额 / 1e4, 1),
                })

            return {
                "上榜次数": 上榜次数,
                "机构买入次数": 机构买入,
                "净买入合计(万)": round(净买入合计 / 1e4, 1),
                "上榜判断": "机构频繁介入" if 机构买入 >= 2 else ("有龙虎榜关注" if 上榜次数 > 0 else "近期未上龙虎榜"),
                "上榜记录": records[:5],  # 最近5条
            }
        except Exception as e:
            return {"错误": str(e), "上榜次数": 0}
        finally:
            self._恢复代理(old_env)

    def 获取公告(self, 股票代码: str, 最近天数: int = 30) -> Dict[str, Any]:
        """
        获取个股近期公告摘要

        返回:
            {
                "公告数量": int,
                "重大公告": [...],  # 含回购/增持/业绩/中标等
                "情绪倾向": "利好/利空/中性",
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用", "公告数量": 0}

        import akshare as ak
        old_env = self._清理代理()
        try:
            symbol = 股票代码.split(".")[0]
            df = ak.stock_notice_report(symbol=symbol)
            if df is None or df.empty:
                return {"公告数量": 0, "重大公告": [], "情绪倾向": "中性"}

            # 筛选最近天数
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=最近天数)).strftime("%Y-%m-%d")
            if "公告日期" in df.columns:
                df = df[df["公告日期"] >= cutoff]

            公告数量 = len(df)
            利好关键词 = ["回购", "增持", "中标", "获批", "分红", "业绩超预期", "合同", "收购"]
            利空关键词 = ["诉讼", "处罚", "立案", "质押", "减持", "亏损", "调查"]

            重大公告 = []
            利好数 = 0
            利空数 = 0

            for _, row in df.iterrows():
                标题 = str(row.get("公告标题", "") or row.get("标题", ""))
                is_重大 = any(kw in 标题 for kw in 利好关键词 + 利空关键词)
                if is_重大:
                    重大公告.append({
                        "日期": str(row.get("公告日期", "")),
                        "标题": 标题[:50],
                        "类型": "利好" if any(kw in 标题 for kw in 利好关键词) else "利空",
                    })
                    if any(kw in 标题 for kw in 利好关键词):
                        利好数 += 1
                    else:
                        利空数 += 1

            情绪 = "利好" if 利好数 > 利空数 else ("利空" if 利空数 > 利好数 else "中性")
            return {
                "公告数量": 公告数量,
                "利好公告数": 利好数,
                "利空公告数": 利空数,
                "情绪倾向": 情绪,
                "重大公告": 重大公告[:5],
            }
        except Exception as e:
            return {"错误": str(e), "公告数量": 0, "情绪倾向": "中性"}
        finally:
            self._恢复代理(old_env)

    def 获取财务数据(self, 股票代码: str) -> Dict[str, Any]:
        """
        获取个股关键财务指标（PE/PB/ROE/毛利率/营收增长等）

        返回:
            {
                "PE": float,
                "PB": float,
                "ROE": float,
                "毛利率": float,
                "净利润增长率": float,
                "总市值(亿)": float,
                "估值判断": str,
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用"}

        import akshare as ak
        old_env = self._清理代理()
        try:
            symbol = 股票代码.split(".")[0]

            # 尝试获取个股信息（含估值）
            result = {}
            try:
                df_info = ak.stock_individual_info_em(symbol=symbol)
                if df_info is not None and not df_info.empty:
                    info_dict = dict(zip(df_info["item"], df_info["value"]))
                    result["总市值(亿)"] = round(float(str(info_dict.get("总市值", 0)).replace(",", "") or 0) / 1e8, 2)
                    result["流通市值(亿)"] = round(float(str(info_dict.get("流通市值", 0)).replace(",", "") or 0) / 1e8, 2)
                    result["PE(动)"] = float(str(info_dict.get("市盈率(动态)", 0)).replace("--", "0") or 0)
                    result["PB"] = float(str(info_dict.get("市净率", 0)).replace("--", "0") or 0)
            except Exception:
                pass

            # 获取财务指标（ROE/毛利率等）
            try:
                df_fin = ak.stock_financial_analysis_indicator(symbol=symbol, start_year="2023")
                if df_fin is not None and not df_fin.empty:
                    latest = df_fin.iloc[-1]
                    result["ROE(%)"] = float(latest.get("净资产收益率", 0) or 0)
                    result["毛利率(%)"] = float(latest.get("销售毛利率", 0) or 0)
                    result["净利润增长率(%)"] = float(latest.get("净利润增长率", 0) or 0)
                    result["营收增长率(%)"] = float(latest.get("主营业务收入增长率", 0) or 0)
            except Exception:
                pass

            # 估值判断
            pe = result.get("PE(动)", 0)
            pb = result.get("PB", 0)
            roe = result.get("ROE(%)", 0)
            if pe > 0 and roe > 0:
                result["估值判断"] = (
                    "低估" if pe < 20 and pb < 2 else
                    "合理" if pe < 35 else
                    "偏高" if pe < 60 else
                    "高估"
                )
            else:
                result["估值判断"] = "数据不足"

            return result
        except Exception as e:
            return {"错误": str(e)}
        finally:
            self._恢复代理(old_env)

    def 获取板块信息(self, 股票代码: str) -> Dict[str, Any]:
        """
        获取个股所属板块及板块涨跌情绪

        返回:
            {
                "所属行业": str,
                "行业涨跌(%)": float,
                "行业排名": str,
                "板块热度": str,
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用"}

        import akshare as ak
        old_env = self._清理代理()
        try:
            symbol = 股票代码.split(".")[0]

            # 获取个股所属行业
            所属行业 = "未知"
            try:
                df_info = ak.stock_individual_info_em(symbol=symbol)
                if df_info is not None and not df_info.empty:
                    info_dict = dict(zip(df_info["item"], df_info["value"]))
                    所属行业 = str(info_dict.get("行业", "未知"))
            except Exception:
                pass

            # 获取行业板块行情
            行业涨跌 = 0.0
            行业排名 = "未知"
            try:
                df_sector = ak.stock_sector_spot(need_number="100")
                if df_sector is not None and not df_sector.empty and 所属行业 != "未知":
                    match = df_sector[df_sector["板块名称"].str.contains(所属行业[:4], na=False)]
                    if not match.empty:
                        行业涨跌 = float(match.iloc[0].get("涨跌幅", 0) or 0)
                        行业排名 = f"第{match.index[0]+1}名/共{len(df_sector)}个板块"
            except Exception:
                pass

            return {
                "所属行业": 所属行业,
                "行业涨跌(%)": round(行业涨跌, 2),
                "行业排名": 行业排名,
                "板块热度": (
                    "板块强势领涨" if 行业涨跌 > 2 else
                    "板块上涨" if 行业涨跌 > 0.5 else
                    "板块平稳" if 行业涨跌 > -0.5 else
                    "板块下跌"
                ),
            }
        except Exception as e:
            return {"错误": str(e), "所属行业": "未知"}
        finally:
            self._恢复代理(old_env)

    def 获取大盘环境(self) -> Dict[str, Any]:
        """
        获取沪深300/上证/创业板当日表现及大盘情绪

        返回:
            {
                "上证涨跌(%)": float,
                "深证涨跌(%)": float,
                "创业板涨跌(%)": float,
                "沪深300涨跌(%)": float,
                "大盘情绪": str,
                "市场状态": str,
            }
        """
        if not self._数据源可用["akshare"]:
            return {"错误": "akshare不可用", "大盘情绪": "未知"}

        import akshare as ak
        old_env = self._清理代理()
        try:
            result = {}
            # 获取主要指数实时行情
            try:
                df = ak.stock_zh_index_spot_em()
                if df is not None and not df.empty:
                    def _get_chg(name_kw: str) -> float:
                        row = df[df["名称"].str.contains(name_kw, na=False)]
                        return float(row.iloc[0].get("涨跌幅", 0)) if not row.empty else 0.0

                    result["上证涨跌(%)"] = round(_get_chg("上证指数"), 2)
                    result["深证涨跌(%)"] = round(_get_chg("深证成指"), 2)
                    result["创业板涨跌(%)"] = round(_get_chg("创业板指"), 2)
                    result["沪深300涨跌(%)"] = round(_get_chg("沪深300"), 2)
            except Exception:
                pass

            # 大盘综合情绪
            avg = sum([
                result.get("上证涨跌(%)", 0),
                result.get("深证涨跌(%)", 0),
                result.get("沪深300涨跌(%)", 0),
            ]) / 3

            result["大盘情绪"] = (
                "市场大幅上涨，做多氛围浓厚" if avg > 2 else
                "市场偏强，风险偏好提升" if avg > 0.5 else
                "市场震荡，谨慎操作" if avg > -0.5 else
                "市场偏弱，注意风险" if avg > -2 else
                "市场大跌，防守为主"
            )
            result["市场状态"] = "强势" if avg > 1 else ("震荡" if avg > -1 else "弱势")

            return result
        except Exception as e:
            return {"错误": str(e), "大盘情绪": "未知"}
        finally:
            self._恢复代理(old_env)

    def 获取全维度数据(
        self,
        股票代码: str,
        包含北向: bool = True,
        包含龙虎榜: bool = True,
    ) -> Dict[str, Any]:
        """
        一键获取全维度数据（技术面+资金面+消息面+大盘）

        这是 LLM 上下文注入的核心入口。

        返回完整的多维度数据字典，可直接传入 debate.py 的 analyze() 方法。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 并发获取（减少总耗时）
        tasks = {
            "资金流向": lambda: self.获取资金流向(股票代码),
            "财务数据": lambda: self.获取财务数据(股票代码),
            "板块信息": lambda: self.获取板块信息(股票代码),
            "公告": lambda: self.获取公告(股票代码),
            "大盘环境": lambda: self.获取大盘环境(),
        }
        if 包含北向:
            tasks["北向资金"] = lambda: self.获取北向资金()
        if 包含龙虎榜:
            tasks["龙虎榜"] = lambda: self.获取龙虎榜(股票代码)

        results = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    results[name] = future.result(timeout=15)
                except Exception as e:
                    results[name] = {"错误": str(e)}

        return results


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
