#!/usr/bin/env python3
"""
涨停板战法
入选条件：
  1. 涨停日期记录：近30日内有涨停记录
  2. 涨停后缩量回踩：涨停后3-8日内成交量萎缩（<涨停当日量×0.5）
  3. 均线支撑：回踩时收盘价踩在 MA10 或 MA20 支撑位（±3%以内）
  4. RSI 在 40-65 区间（未超买，有上涨空间）
  5. 不在"8天未能收复"状态（涨停后第8日仍未超过涨停日收盘价）
排除条件：
  - 涨停无量（<5000万成交额）→ 主力未真实参与
  - 连续涨停 > 3板 → 获利盘过大
  - 8天未收复 → 止损规则触发
  - RSI > 70（超买）
风控：8天收复规则——若涨停后第8日仍未超过涨停日最高价，强制止损
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

from .base import BaseStrategy, StrategyResult, SignalStrength


class LimitUpStrategy(BaseStrategy):
    """
    涨停板战法

    核心理念：涨停板是主力最强势的做多信号，但次日若高开低走、
    缩量回踩关键均线，是主力洗盘吸筹的机会。
    核心风控："8天收复规则"——若涨停后8个交易日内未能收复涨停日收盘价，
    说明主力实力不足，强制止损出局。
    """

    name = "涨停板战法"
    description = "涨停后缩量回踩 + 均线支撑 + 8天收复规则 = 安全低吸买点"

    # 8天收复规则天数
    RECOVERY_DAYS = 8

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
        high = np.array(df["high"].values, dtype=float)
        volume = np.array(df["volume"].values, dtype=float)
        amount = np.array(df["amount"].values, dtype=float) if "amount" in df.columns else None
        rsi = indicators.get("rsi")
        ma = indicators.get("ma", {})

        if n < 30:
            return self._build_result(
                stock_code, stock_name,
                {}, ["数据不足（<30日）"],
                {}, {"risk_score": 100, "risk_level": "未知"},
                {"reason": "数据不足", "action": "无法分析", "confidence": 0.0},
            )

        # ── 涨停检测 ─────────────────────────────
        # 涨停：日涨幅 >= 9.8%（以开盘价为基准）
        涨停记录 = []
        for i in range(n):
            if open_arr[i] > 0:
                pct = (close[i] - open_arr[i]) / open_arr[i] * 100
                if pct >= 9.8:
                    涨停记录.append({
                        "index": i,
                        "date": str(df["date"].values[i]) if "date" in df.columns else str(i),
                        "close": float(close[i]),
                        "open": float(open_arr[i]),
                        "high": float(high[i]),
                        "volume": float(volume[i]),
                        "amount": float(amount[i]) if amount is not None else None,
                        "pct": pct,
                    })

        # 取最近一次涨停
        last_zt = 涨停记录[-1] if 涨停记录 else None

        # ── 涨停后分析 ────────────────────────────
        zt_days_ago = None
        if last_zt:
            zt_days_ago = n - 1 - last_zt["index"]

        # 涨停距今不足1日：还在涨停板中，无法买入
        # 涨停距今1-15日：处于回踩确认阶段（战法适用窗口）
        zt_window = (zt_days_ago is not None) and (1 <= zt_days_ago <= 15)

        # ── 8天收复规则 ───────────────────────────
        # 计算：涨停日之后的交易日中，是否有1天收盘价 > 涨停日收盘价
        recovered = False
        recovery_days = 0
        if last_zt:
            zt_close = last_zt["close"]
            for i in range(last_zt["index"] + 1, n):
                recovery_days += 1
                if close[i] >= zt_close:
                    recovered = True
                    break

        # 8天规则触发
        rule_triggered = False
        rule_trigger_msg = ""
        if last_zt and recovery_days >= self.RECOVERY_DAYS and not recovered:
            rule_triggered = True
            rule_trigger_msg = f"8天未收复（已过{recovery_days}天）"

        # ── 回踩分析（涨停后3-8日内的缩量回踩）────────
        缩量回踩 = False
        回踩支撑均线 = None
        if last_zt and 1 <= zt_days_ago <= 10:
            zt_vol = last_zt["volume"]
            # 回踩区间：涨停后2天到8天
            for i in range(last_zt["index"] + 2, min(last_zt["index"] + 9, n)):
                vol_ratio = float(volume[i]) / (zt_vol + 1e-10)
                if vol_ratio < 0.5:  # 缩量回踩
                    缩量回踩 = True
                    # 检测均线支撑
                    close_price = float(close[i])
                    for ma_key, ma_val in ma.items():
                        if ma_val and abs(close_price - ma_val) / ma_val < 0.03:
                            回踩支撑均线 = ma_key
                            break
                    break

        # ── 均线支撑分析 ──────────────────────────
        current_close = float(close[-1])
        ma_support = None
        for ma_key, ma_val in sorted(ma.items(), key=lambda x: int(x[0].replace("ma", ""))):
            if ma_val and abs(current_close - ma_val) / ma_val < 0.03:
                ma_support = ma_key
                break

        # ── 入选条件 ─────────────────────────────
        entry = {}

        entry["近30日有涨停"] = last_zt is not None
        entry["涨停后回踩窗口"] = zt_window
        entry["缩量回踩"] = 缩量回踩
        entry["均线支撑"] = ma_support is not None
        entry["均线支撑MA10"] = ma.get("ma10") and abs(current_close - ma["ma10"]) / ma["ma10"] < 0.03
        entry["均线支撑MA20"] = ma.get("ma20") and abs(current_close - ma["ma20"]) / ma["ma20"] < 0.03
        entry["RSI健康区间40-65"] = (rsi is not None) and (40 <= rsi <= 65)
        entry["8天收复"] = recovered if last_zt else True
        entry["收盘>MA5"] = ma.get("ma5") and current_close > ma["ma5"]

        # ── 排除条件 ─────────────────────────────
        exclusions = self._default_exclusions(df, indicators, realtime)

        if not last_zt:
            exclusions.append("近30日无涨停记录")
        if last_zt and last_zt.get("amount") and last_zt["amount"] < 50000000:
            exclusions.append(f"涨停无量（{last_zt['amount']/1e8:.1f}亿），主力未参与")
        if realtime and realtime.get("pct_change", 0) > 9.5:
            exclusions.append("今日涨停，无法买入")
        if rsi and rsi > 70:
            exclusions.append(f"RSI超买（{rsi}）")
        if rsi and rsi < 35:
            exclusions.append(f"RSI超卖（{rsi}），趋势可能走弱")
        if rule_triggered:
            exclusions.append(rule_trigger_msg)
        if last_zt and last_zt.get("pct", 0) > 12:
            exclusions.append("异常涨停（>12%），风险极高")
        if zt_days_ago and zt_days_ago > 15:
            exclusions.append("涨停已过15日，窗口期结束")

        # ── 综合评分 ─────────────────────────────
        # 核心：涨停+缩量回踩+均线支撑
        core_score = sum(1 for c in ["近30日有涨停", "缩量回踩", "均线支撑", "RSI健康区间40-65"] if entry.get(c))
        entry_score = core_score * (3.0 / 4.0)

        # 8天收复成功 +0.5
        if entry["8天收复"]:
            entry_score += 0.5

        # MA20支撑比MA10更稳固
        if entry["均线支撑MA20"]:
            entry_score += 0.3

        # 涨停距今适中（3-8日）加分
        if zt_days_ago and 3 <= zt_days_ago <= 8:
            entry_score += 0.2

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
            "涨停记录": {
                "近30日涨停次数": len(涨停记录),
                "最近涨停": {
                    "日期": last_zt["date"] if last_zt else None,
                    "距今": f"{zt_days_ago}天" if zt_days_ago else None,
                    "涨幅": f"{last_zt['pct']:.1f}%" if last_zt else None,
                    "成交额": f"{last_zt['amount']/1e8:.2f}亿" if last_zt and last_zt.get("amount") else None,
                },
            },
            "8天收复": {
                "状态": "已收复" if recovered else ("触发止损" if rule_triggered else "未收复"),
                "已过天数": recovery_days,
            },
            "回踩": {
                "缩量回踩": 缩量回踩,
                "均线支撑": 回踩支撑均线,
            },
        }

        # ── 风控（8天收复规则）───────────────────
        if last_zt:
            stop_loss_price = round(float(last_zt["close"]) * 0.97, 2)  # 跌回涨停价-3%
            take_profit_price = round(float(last_zt["high"]) * 1.10, 2)  # 突破涨停高价10%
        else:
            stop_loss_price = round(current_close * 0.97, 2)
            take_profit_price = round(current_close * 1.10, 2)

        risk_result = indicators.get("风险", {})
        risk_score = risk_result.get("综合风险分数", 50)
        if rule_triggered:
            risk_score = 95
        elif len(exclusions) > 0:
            risk_score = min(risk_score + 10, 100)

        risk_level_map = {
            "低风险": risk_score < 30,
            "中低风险": 30 <= risk_score < 50,
            "中风险": 50 <= risk_score < 70,
            "中高风险": 70 <= risk_score < 85,
            "高风险": risk_score >= 85,
        }
        risk_level = next((k for k, v in risk_level_map.items() if v), "未知")

        # ── 操作建议 ─────────────────────────────
        if rule_triggered:
            action = "8天收复规则触发，强制止损"
            holding_period = "止损出局"
            position_ratio = "空仓"
        elif signal == SignalStrength.STRONG_BUY:
            action = "缩量回踩均线支撑买入，止损设涨停价-3%"
            holding_period = "5-10天（目标突破涨停高价）"
            position_ratio = "轻仓（15-20%）"
        elif signal == SignalStrength.BUY:
            action = "回踩均线附近买入，止损设MA10-2%"
            holding_period = "5-8天"
            position_ratio = "轻仓（10-15%）"
        elif signal == SignalStrength.HOLD:
            action = "等待回踩确认，跌破均线则放弃"
            holding_period = "观望"
            position_ratio = "空仓"
        else:
            action = "条件不足，不参与"
            holding_period = "-"
            position_ratio = "空仓"

        warnings = []
        if zt_days_ago and zt_days_ago <= 2:
            warnings.append("涨停距今不足2日，追高风险大")
        if not 缩量回踩:
            warnings.append("未出现缩量回踩，买点不清晰")
        if last_zt and last_zt.get("amount") and last_zt["amount"] < 1e9:
            warnings.append("涨停成交额偏小（<10亿），主力参与度存疑")

        reason_parts = []
        if last_zt:
            reason_parts.append(f"近{zt_days_ago}日前涨停（{last_zt['pct']:.1f}%）")
        if 缩量回踩:
            reason_parts.append("缩量回踩✅")
        if ma_support:
            reason_parts.append(f"{ma_support}支撑✅")
        if entry["8天收复"]:
            reason_parts.append("8天已收复✅")
        reason = "，".join(reason_parts) if reason_parts else "条件不足"

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
