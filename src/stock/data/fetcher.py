#!/usr/bin/env python3
"""
StockFetcher - A股行情数据获取器
封装 akshare，统一提供日K/分钟K/竞价数据/涨停数据接口
"""

import akshare as ak
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")


class StockFetcher:
    """
    A股数据统一获取接口

    支持：
    - 日K线历史数据
    - 实时行情快照
    - 集合竞价数据（9:15-9:25）
    - 涨停板数据
    - 分时分钟数据
    """

    # A股指数代码映射
    INDEX_MAP = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000300": "沪深300",
    }

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_ttl = 300  # 5分钟
        self._cache_time: Dict[str, datetime] = {}

    # ─────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────

    def _is_cache_valid(self, key: str) -> bool:
        if not self.use_cache:
            return False
        if key not in self._cache_time:
            return False
        elapsed = (datetime.now() - self._cache_time[key]).total_seconds()
        return elapsed < self._cache_ttl

    def _set_cache(self, key: str, df: pd.DataFrame):
        self._cache[key] = df.copy()
        self._cache_time[key] = datetime.now()

    def _normalize_code(self, stock_code: str) -> tuple[str, str]:
        """
        将股票代码转换为 akshare 格式
        返回 (market_code, stock_code)
        """
        code = stock_code.strip().upper()
        if code.startswith("60"):
            return "sh", code
        elif code.startswith(("00", "30")):
            return "sz", code
        elif code.startswith("68"):
            return "bj", code  # 北交所
        elif code.startswith("8") or code.startswith("4"):
            return "bj", code  # 北交所
        else:
            return "sh", code  # 默认上证

    # ─────────────────────────────────────────────
    # 核心接口
    # ─────────────────────────────────────────────

    def get_daily(
        self,
        stock_code: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """
        获取日K线数据

        参数:
            stock_code: 股票代码，如 "600000"（可带后缀如 SH/SZ）
            period: 时间周期，默认 "daily"
            start_date: 开始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            adjust: 复权类型，"qfq"前复权/"hfq"后复权/""不复权

        返回:
            DataFrame，列: date, open, high, low, close, volume, amount
        """
        cache_key = f"daily_{stock_code}_{start_date}_{end_date}_{adjust}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        market, code = self._normalize_code(stock_code)
        symbol = f"{market}{code}"

        # 默认取近2年数据
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            df = self._normalize_daily_columns(df)
            self._set_cache(cache_key, df)
            return df
        except Exception as e:
            raise RuntimeError(f"获取日K线失败 [{symbol}]: {e}")

    def _normalize_daily_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一列名，akshare返回列名可能有中英文混合"""
        col_map = {
            "日期": "date",
            "股票代码": "code",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "price_change",
            "换手率": "turnover",
        }
        df = df.rename(columns=col_map)
        # 只保留需要的列
        keep_cols = ["date", "open", "close", "high", "low", "volume", "amount"]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = np.nan
        return df[keep_cols].copy()

    def get_realtime(self, stock_code: str) -> Dict:
        """
        获取个股实时行情快照

        返回:
            dict，包含最新价/涨跌幅/成交量/换手率等字段
        """
        market, code = self._normalize_code(stock_code)
        symbol = f"{market}{code}"

        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty:
                raise ValueError(f"股票 {symbol} 未找到")
            r = row.iloc[0]
            return {
                "code": symbol,
                "name": r.get("名称", ""),
                "close": float(r.get("最新价", 0)),
                "open": float(r.get("今开", 0)),
                "high": float(r.get("最高", 0)),
                "low": float(r.get("最低", 0)),
                "volume": float(r.get("成交量", 0)),
                "amount": float(r.get("成交额", 0)),
                "pct_change": float(r.get("涨跌幅", 0)),
                "turnover": float(r.get("换手率", 0)),
                "market_cap": float(r.get("总市值", 0)),
                "pe": float(r.get("市盈率-动态", 0)) if r.get("市盈率-动态", "") != "-" else None,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            raise RuntimeError(f"获取实时行情失败 [{symbol}]: {e}")

    def get_auction(self, stock_code: str, date: Optional[str] = None) -> Dict:
        """
        获取集合竞价数据（A股9:15-9:25）

        参数:
            stock_code: 股票代码
            date: 日期，默认上一个交易日

        返回:
            dict，包含竞价量/竞价额/竞价涨幅/竞价价格
        """
        market, code = self._normalize_code(stock_code)
        symbol = f"{market}{code}"

        if date is None:
            # 取上一个交易日
            try:
                df_cal = ak.tool_trade_date_hist_sina()
                today = datetime.now().strftime("%Y-%m-%d")
                trading_dates = df_cal[df_cal["trade_date"] < today]["trade_date"].tolist()
                date = trading_dates[-1] if trading_dates else None
            except Exception:
                date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            # 竞价数据（需要盘中获取，盘中后才有完整数据）
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=date.replace("-", ""),
                end_date=date.replace("-", ""),
                adjust="qfq",
            )
            if df.empty:
                return self._empty_auction(symbol)

            r = df.iloc[-1]
            return {
                "code": symbol,
                "date": date,
                "open": float(r.get("开盘", 0)),
                "close_prev": float(r.get("收盘", 0)) if df.shape[0] > 1 else float(r.get("开盘", 0)),
                "volume": float(r.get("成交量", 0)),
                "pct_change": float(r.get("涨跌幅", 0)),
            }
        except Exception:
            return self._empty_auction(symbol)

    def _empty_auction(self, symbol: str) -> Dict:
        return {
            "code": symbol,
            "date": None,
            "open": None,
            "close_prev": None,
            "volume": None,
            "pct_change": None,
        }

    def get_limit_up(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        获取涨停板列表

        返回:
            DataFrame，列: code, name, close, pct_change, turnover, sector
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        cache_key = f"limit_up_{date}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        try:
            df = ak.stock_zt_pool_em(date=date)
            df = df.rename(columns={
                "代码": "code",
                "名称": "name",
                "收盘价": "close",
                "涨停价": "zt_price",
                "连板数": "consecutive_days",
                "流通市值": "float_market_cap",
                "换手率": "turnover",
                "成交额": "amount",
                "板块": "sector",
            })
            cols = ["code", "name", "close", "zt_price", "consecutive_days", "float_market_cap", "turnover", "amount"]
            for col in cols:
                if col not in df.columns:
                    df[col] = None
            result = df[cols].copy()
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            raise RuntimeError(f"获取涨停板数据失败 [{date}]: {e}")

    def get_limit_up_date(self, stock_code: str, lookback: int = 30) -> List[str]:
        """
        获取个股近N日的涨停日期列表（用于涨停板战法）
        """
        market, code = self._normalize_code(stock_code)
        symbol = f"{market}{code}"

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=lookback * 2)).strftime("%Y%m%d")

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            df = self._normalize_daily_columns(df)

            # 涨停：日涨幅 >= 9.8%（考虑ST股等特殊情况）
            zt_dates = []
            for _, row in df.iterrows():
                if pd.notna(row["close"]) and pd.notna(row["open"]) and row["open"] > 0:
                    pct = (row["close"] - row["open"]) / row["open"] * 100
                    if pct >= 9.8:
                        zt_dates.append(str(row["date"]))
            return zt_dates
        except Exception as e:
            raise RuntimeError(f"获取涨停日期失败 [{symbol}]: {e}")

    def get_intraday(self, stock_code: str, date: Optional[str] = None) -> pd.DataFrame:
        """
        获取分时数据（分钟K线）
        """
        market, code = self._normalize_code(stock_code)
        symbol = f"{market}{code}"

        try:
            df = ak.stock_zh_a_minute(
                symbol=symbol,
                period="1",
                adjust="qfq",
            )
            if "时间" in df.columns:
                df = df.rename(columns={"时间": "time", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"})
            return df.tail(240)  # 最近一天240分钟
        except Exception as e:
            raise RuntimeError(f"获取分时数据失败 [{symbol}]: {e}")

    def get_bulk_realtime(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取多个股票实时行情
        """
        results = {}
        for code in stock_codes:
            try:
                results[code] = self.get_realtime(code)
            except Exception:
                results[code] = {"code": code, "error": True}
        return results


# 单例实例
_fetcher_instance: Optional[StockFetcher] = None

def get_fetcher() -> StockFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = StockFetcher(use_cache=True)
    return _fetcher_instance
