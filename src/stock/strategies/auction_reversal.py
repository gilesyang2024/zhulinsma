#!/usr/bin/env python3
"""
竞价弱转强策略
入选条件：
  1. 前日收盘涨幅 < 0%（前日弱势/阴线）
  2. 竞价高开幅度 > 1.5%（9:15-9:25竞价价格 > 昨日收盘×1.015）
  3. 竞价成交量 > 前日均量（主力竞价抢筹）
  4. 开盘30分钟内价格站稳在竞价价格上方（强势确认）
  5. RSI(14) > 45（多方占优）
排除条件：
  - 竞价高开 > 7%（高开太多，获利盘压力大）
  - 涨停开盘（无法买入）
  - RSI < 30（空方主导）
风控：止损设于竞价价格-2%，止盈目标 +5% ~ +8%
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

from .base import BaseStrategy, StrategyResult, SignalStrength


class AuctionReversalStrategy(BaseStrategy):
    """
    竞价弱转强策略

    核心理念：前日弱势（收阴/小涨）给了主力低位吸筹机会，次日竞价出现
    超预期高开（>1.5%）且量能放大，说明主力真实做多意愿强。
    适用于连板断板后的情绪回流、缩量回调后的二次启动。
    """

    name = "竞价弱转强策略"
    description = "前日弱势 + 竞价巨量高开 = 主力真实做多，快速拉升"

    def analyze(
        self,
        stock_code: str,
        stock_name: str,
        df: pd.DataFrame,
        indicators: Dict[str, Any],
        realtime: Optional[Dict] = None,
        auction: Optional[Dict] = None,
    ) -> StrategyResult:
        n = len(df)
        close = np.array(df["close"].values, dtype=float)
        open_arr = np.array(df["open"].values, dtype=float)
        volume = np.array(df["volume"].values, dtype=float)
        rsi = indicators.get("rsi")
        ma = indicators.get("ma", {})

        if n < 3:
            return self._build_result(
                stock_code, stock_name,
                {}, ["数据不足"],
                {}, {"risk_score": 100, "risk_level": "未知"},
                {"reason": "数据不足", "action": "无法分析", "confidence": 0.0},
            )

        # ── 竞价数据处理 ──────────────────────────
        # auction 数据来源: StockFetcher.get_auction()
        auction_open = auction.get("open") if auction else None
        auction_prev_close = auction.get("close_prev") if auction else None
        auction_pct = auction.get("pct_change") if auction else None

        # 若无竞价数据，从日K估算（竞价 ≈ 开盘价 近似处理）
        # 注意：akshare 日K数据开盘价 = 9:30实际开盘，与竞价有差异
        # 理想情况需要实时竞价数据，此处做降级处理
        if auction_open is None and n >= 2:
            # 降级：用今日开盘价 vs 昨日收盘价作为"竞价强度"的近似
            today_open = float(open_arr[-1])
            prev_close = float(close[-2])
            auction_open = today_open
            auction_prev_close = prev_close
            auction_pct = (today_open - prev_close) / prev_close * 100

        # ── 入选条件 ─────────────────────────────
        entry = {}

        if auction_prev_close and auction_prev_close > 0:
            # 条件1：竞价高开幅度 > 1.5%
            auction_open_val = auction_open or float(open_arr[-1])
            open_pct = (auction_open_val - auction_prev_close) / auction_prev_close * 100
            entry["竞价高开>1.5%"] = open_pct > 1.5
            entry["竞价高开>3%"] = open_pct > 3.0

            # 条件2：竞价高开 < 7%（非过度高开）
            entry["高开<7%"] = open_pct < 7.0
        else:
            open_pct = None
            entry["竞价高开>1.5%"] = False
            entry["竞价高开>3%"] = False
            entry["高开<7%"] = False

        # 条件3：前日弱势（收盘涨幅 < 0.5%）
        if n >= 2:
            prev_change = (float(close[-1]) - float(close[-2])) / float(close[-2]) * 100
            entry["前日弱势(<0.5%)"] = prev_change < 0.5
            entry["前日收阴"] = float(close[-1]) < float(close[-2])
        else:
            prev_change = None
            entry["前日弱势(<0.5%)"] = False
            entry["前日收阴"] = False

        # 条件4：竞价量放大（用今日成交量 vs 昨日估算，简化处理）
        if n >= 6:
            vol_now = float(volume[-1])
            vol_ma5_prev = float(np.mean(volume[-6:-1]))
            entry["竞价量放大(量比>1.2)"] = vol_now > vol_ma5_prev * 1.2
        else:
            entry["竞价量放大(量比>1.2)"] = False

        # 条件5：RSI > 45（多方占优）
        entry["RSI>45"] = (rsi is not None) and (rsi > 45)
        entry["RSI<70"] = (rsi is not None) and (rsi < 70)

        # 条件6：收盘站稳 MA5 均线
        ma5 = ma.get("ma5")
        entry["站稳MA5"] = (ma5 is not None) and (float(close[-1]) > ma5)

        # ── 排除条件 ─────────────────────────────
        exclusions = self._default_exclusions(df, indicators, realtime)

        # 竞价策略特有排除
        if open_pct and open_pct > 7.0:
            exclusions.append(f"高开幅度过大（{open_pct:.1f}%），获利盘压力大")
        if realtime and realtime.get("pct_change", 0) > 9.5:
            exclusions.append("已涨停，无法买入")
        if rsi and rsi < 30:
            exclusions.append(f"RSI超卖（{rsi}），空方主导")
        if open_pct and open_pct < 0:
            exclusions.append(f"竞价低开（{open_pct:.1f}%），不符合弱转强")

        # ── 综合评分 ─────────────────────────────
        entry_score = sum(1 for v in entry.values() if v) * (3.0 / max(len(entry), 1))
        signal_score = min(entry_score, 5.0)

        if signal_score >= 4.0:
            signal = SignalStrength.STRONG_BUY
        elif signal_score >= 3.0:
            signal = SignalStrength.BUY
        elif signal_score >= 2.0:
            signal = SignalStrength.HOLD
        else:
            signal = SignalStrength.SELL

        # ── 战法特有指标 ──────────────────────────
        strategy_indicators = {
            "竞价高开幅度": round(open_pct, 2) if open_pct is not None else None,
            "前日涨幅": round(prev_change, 2) if prev_change is not None else None,
            "量比": round(float(volume[-1]) / (float(np.mean(volume[-6:-1])) + 1e-10), 2) if n >= 6 else None,
            "当日开盘": auction_open,
            "昨日收盘": auction_prev_close,
        }

        # ── 风控 ────────────────────────────────
        if auction_prev_close and auction_open:
            stop_loss_price = round(float(auction_open) * 0.98, 2)
            take_profit_price = round(float(auction_open) * 1.08, 2)
        else:
            stop_loss_price = round(float(close[-1]) * 0.97, 2)
            take_profit_price = round(float(close[-1]) * 1.08, 2)

        risk_result = indicators.get("风险", {})
        risk_score = risk_result.get("综合风险分数", 50)

        if len(exclusions) > 0:
            risk_score = min(risk_score + 15, 100)

        risk_level_map = {
            "低风险": risk_score < 30,
            "中低风险": 30 <= risk_score < 50,
            "中风险": 50 <= risk_score < 70,
            "中高风险": 70 <= risk_score < 85,
            "高风险": risk_score >= 85,
        }
        risk_level = next((k for k, v in risk_level_map.items() if v), "未知")

        # ── 操作建议 ─────────────────────────────
        if signal == SignalStrength.STRONG_BUY:
            action = "9:30开盘确认后买入，止损设竞价价格-2%"
            holding_period = "3-5天（快进快出）"
            position_ratio = "轻仓（10-15%）"
        elif signal == SignalStrength.BUY:
            action = "开盘回调不破竞价价时可买入"
            holding_period = "3-7天"
            position_ratio = "轻仓（10%以内）"
        elif signal == SignalStrength.HOLD:
            action = "等待开盘确认，若站稳竞价价可买入"
            holding_period = "观望"
            position_ratio = "空仓"
        else:
            action = "信号较弱，不符合弱转强条件"
            holding_period = "-"
            position_ratio = "空仓"

        warnings = []
        if open_pct and 5.0 < open_pct < 7.0:
            warnings.append("高开幅度适中，但需注意获利回吐")
        if prev_change and prev_change < -3:
            warnings.append("前日大跌（<-3%），可能是下跌中继而非弱转强")

        reason_parts = []
        if open_pct is not None:
            reason_parts.append(f"竞价高开{open_pct:.2f}%")
        if prev_change is not None:
            reason_parts.append(f"前日{'收阴' if prev_change < 0 else '涨幅小'}")
        if rsi is not None:
            reason_parts.append(f"RSI={rsi:.1f}（多方）")
        reason = "，".join(reason_parts) if reason_parts else "数据不足"

        return self._build_result(
            stock_code, stock_name,
            entry, exclusions,
            strategy_indicators,
            {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "stop_loss": stop_loss_price,
                "take_profit": take_profit_price,
            },
            {
                "reason": reason,
                "action": action,
                "holding_period": holding_period,
                "position_ratio": position_ratio,
                "confidence": min(signal_score / 5.0, 1.0),
                "warning": warnings,
            },
        )
