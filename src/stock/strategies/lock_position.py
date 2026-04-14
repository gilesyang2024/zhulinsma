#!/usr/bin/env python3
"""
锁仓K线策略
入选条件：
  1. 近5日量能变异系数(CV) < 0.15（极度缩量）
  2. 近5日价格振幅 < 4%（横盘整理）
  3. 近5日均量 vs 10日前5日均量 < 0.7（量能持续收缩）
  4. 收盘价 > MA20（多头排列）
排除条件：
  - RSI 超买(>75) / 超卖(<30)
  - 波动率异常高
风控：止损设于横盘区间下沿-3%，目标位突破后量能放大确认
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

from .base import BaseStrategy, StrategyResult, SignalStrength


class LockPositionStrategy(BaseStrategy):
    """
    锁仓K线策略

    核心理念：主力在拉升前会锁仓控盘，表现为成交量持续萎缩+价格横盘整理。
    当出现量能极度收缩（CV<0.15）+ 价格横盘（振幅<4%）+ 对比10日前量能明显萎缩时，
    是主力锁仓的强烈信号，等待突破确认后介入。
    """

    name = "锁仓K线策略"
    description = "成交量极度萎缩 + 价格横盘 = 主力控盘锁仓，等待突破确认"

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
        volume = np.array(df["volume"].values, dtype=float)
        vol_feat = indicators.get("量能特征", {})
        ma = indicators.get("ma", {})
        rsi = indicators.get("rsi")

        # ── 入选条件 ─────────────────────────────
        entry = {}

        # 条件1：量能极度收缩（CV < 0.15）
        vol_cv = vol_feat.get("vol_cv")
        entry["量能CV<0.15"] = (vol_cv is not None) and (vol_cv < 0.15)

        # 条件2：价格横盘（近5日振幅 < 4%）
        recent_5 = close[-5:]
        price_range = (np.max(recent_5) - np.min(recent_5)) / (np.min(recent_5) + 1e-10)
        entry["价格振幅<4%"] = price_range < 0.04

        # 条件3：量能对比10日前明显萎缩（当前均量 < 10日前均量×0.7）
        vol_compare = vol_feat.get("vol_compare_10d")
        entry["量能vs10日前<0.7"] = (vol_compare is not None) and (vol_compare < 0.70)

        # 条件4：收盘 > MA20（多头排列）
        ma20 = ma.get("ma20")
        entry["收盘>MA20"] = (ma20 is not None) and (close[-1] > ma20)

        # 条件5：RSI 处于健康区间（40-70，多头趋势但未超买）
        entry["RSI健康区间40-70"] = (rsi is not None) and (40 <= rsi <= 70)

        # 附加条件6：5日内出现过放量后缩量（主力试盘后锁仓）
        if n >= 10:
            vol_ma5 = np.mean(volume[-5:])
            vol_ma5_before = np.mean(volume[-10:-5])
            entry["试盘后锁仓"] = vol_ma5 < vol_ma5_before * 0.8
        else:
            entry["试盘后锁仓"] = False

        # ── 排除条件 ─────────────────────────────
        exclusions = self._default_exclusions(df, indicators, realtime)

        # 锁仓策略特有排除
        if rsi and rsi > 75:
            exclusions.append(f"RSI超买（{rsi}），上涨空间受限")
        if rsi and rsi < 30:
            exclusions.append(f"RSI超卖（{rsi}），趋势走弱")
        if price_range > 0.10:
            exclusions.append(f"价格振幅过大（{price_range*100:.1f}%）")

        # ── 综合评分 ─────────────────────────────
        entry_score = sum(1 for v in entry.values() if v) * (3.0 / max(len(entry), 1))

        # RSI 在理想区间（50-60）额外加分
        rsi_bonus = 0.5 if (rsi and 50 <= rsi <= 60) else 0.0
        signal_score = min(entry_score + rsi_bonus, 5.0)

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
            "vol_cv": round(vol_cv, 4) if vol_cv else None,
            "price_range_5d": round(price_range * 100, 2),
            "vol_compare_10d": round(vol_compare, 4) if vol_compare else None,
            "横盘区间": {
                "上沿": round(float(np.max(recent_5)), 2),
                "下沿": round(float(np.min(recent_5)), 2),
                "中轴": round(float(np.mean(recent_5)), 2),
            },
            "ma20": round(ma20, 2) if ma20 else None,
        }

        # ── 风控 ─────────────────────────────────
        stop_loss_price = round(float(np.min(recent_5)) * 0.97, 2)
        take_profit_price = round(float(np.max(recent_5)) * 1.05, 2)  # 突破上沿5%目标

        risk_result = indicators.get("风险", {})
        risk_score = risk_result.get("综合风险分数", 50)

        if len(exclusions) > 0:
            risk_score = min(risk_score + 20, 100)

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
            action = "建议关注，突破横盘上沿后买入"
            holding_period = "3-10天（突破确认后持有）"
            position_ratio = "轻仓试探（<20%）"
        elif signal == SignalStrength.BUY:
            action = "可轻仓布局，等待量能放大确认"
            holding_period = "5-8天"
            position_ratio = "轻仓（10-20%）"
        elif signal == SignalStrength.HOLD:
            action = "继续观察，等待更明确的信号"
            holding_period = "观望"
            position_ratio = "空仓"
        else:
            action = "信号较弱，不建议参与"
            holding_period = "-"
            position_ratio = "空仓"

        warnings = []
        if vol_cv and vol_cv < 0.10:
            warnings.append("量能极度收缩，注意假突破风险")
        if price_range < 0.02:
            warnings.append("价格极度收敛，可能随时变盘")
        if vol_compare and vol_compare < 0.50:
            warnings.append("量能极度萎缩，突破可能失败")

        reason = (
            f"量能CV={vol_cv:.2%}（<15%）" if vol_cv else "无CV数据"
        ) + f"，振幅={price_range:.2%}（<4%），"

        if vol_compare:
            reason += f"量能对比10日前={vol_compare:.0%}（<70%），"
        reason += f"MA20={ma20:.2f}（{'多头' if close[-1] > (ma20 or 0) else '空头'}）"

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
