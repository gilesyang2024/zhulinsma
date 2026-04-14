#!/usr/bin/env python3
"""
利刃出鞘策略
入选条件：
  1. 倍量阴：成交量 > 20日均量×2 + 当日K线为阴线
  2. 长上影线：上影线 / (最高-最低) > 60%
  3. 接近20日新高：收盘价 >= 近20日最高价×0.97
  4. RSI > 50（多方略占优，但非超买）
  5. 缩量确认：倍量阴后次日量能萎缩（主力洗盘后锁仓）
  6. MACD 在0轴上方或出现金叉
排除条件：
  - 倍量阴当日成交量萎缩不足（量比<1.8）→ 洗盘不充分
  - RSI > 75（超买，上影线可能是出货）
  - 接近历史新高（>50日新高）→ 获利盘压力过大
风控：止损设于倍量阴最低点-2%
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any

from .base import BaseStrategy, StrategyResult, SignalStrength


class BladeOutStrategy(BaseStrategy):
    """
    利刃出鞘策略

    核心理念：涨停/强势股回调中，主力用"倍量阴+长上影"进行日内洗盘，
    收盘守住关键价位不出货，是主力拉升前最后的震仓。
    特征：成交量放大（2倍以上）+ 阴线 + 长上影线刺出新高后回落。
    信号出现后次日若缩量不破洗盘点位，可确认为洗盘完毕。
    """

    name = "利刃出鞘策略"
    description = "倍量阴 + 长上影 = 主力洗盘完毕，次日缩量确认后买入"

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
        low = np.array(df["low"].values, dtype=float)
        volume = np.array(df["volume"].values, dtype=float)
        candle = indicators.get("形态特征", {})
        rsi = indicators.get("rsi")
        macd = indicators.get("macd", {})
        ma = indicators.get("ma", {})

        if n < 25:
            return self._build_result(
                stock_code, stock_name,
                {}, ["数据不足（<25日）"],
                {}, {"risk_score": 100, "risk_level": "未知"},
                {"reason": "数据不足", "action": "无法分析", "confidence": 0.0},
            )

        # ── 计算战法核心指标 ─────────────────────
        # 倍量阴检测（近5日内）
        vol_ma20 = float(np.mean(volume[-21:-1]))
        倍量阴_detected = False
        倍量阴_date = None
        倍量阴_low = None
        倍量阴_index = None

        for i in range(-5, 0):
            vol_ratio = float(volume[i]) / (vol_ma20 + 1e-10)
            is_bearish = close[i] < open_arr[i]
            if vol_ratio >= 2.0 and is_bearish:
                倍量阴_detected = True
                倍量阴_date = str(df["date"].values[i]) if "date" in df.columns else str(n + i)
                倍量阴_low = float(low[i])
                倍量阴_index = i
                break

        # 接近20日新高
        近期最高20 = float(np.max(close[-20:]))
        接近新高 = bool(close[-1] >= 近期最高20 * 0.97)

        # 长上影线检测（近3日内）
        长上影_detected = False
        for i in range(-3, 0):
            total_range = float(high[i] - low[i] + 1e-10)
            upper_shadow = float(high[i] - max(close[i], open_arr[i]))
            if total_range > 0:
                shadow_ratio = upper_shadow / total_range
                if shadow_ratio > 0.60:
                    长上影_detected = True
                    break

        # 缩量确认（倍量阴后次日量能萎缩）
        缩量确认 = False
        if 倍量阴_index is not None and 倍量阴_index < -1:
            vol_after = float(volume[倍量阴_index - 1])
            vol_before倍量 = float(volume[倍量阴_index])
            缩量确认 = vol_after < vol_before倍量 * 0.8

        # 20日新高检测（过于接近历史高点则排除）
        近期最高50 = float(np.max(close[-50:]))
        接近历史新高 = bool(close[-1] >= 近期最高50 * 0.98)

        # ── 入选条件 ─────────────────────────────
        entry = {}

        entry["倍量阴"] = 倍量阴_detected
        entry["长上影线"] = 长上影_detected
        entry["接近20日新高"] = 接近新高
        entry["RSI健康(45-75)"] = (rsi is not None) and (45 <= rsi <= 75)
        entry["缩量确认"] = 缩量确认

        # MACD 条件：0轴上方或金叉
        macd_diff = macd.get("diff")
        macd_dea = macd.get("dea")
        entry["MACD多头"] = (macd_diff is not None) and (macd_diff > 0)
        entry["MACD金叉"] = (macd_diff is not None) and (macd_dea is not None) and (macd_diff > macd_dea)

        # 站稳均线（MA5/MA10）
        ma5 = ma.get("ma5")
        ma10 = ma.get("ma10")
        entry["站稳MA5"] = (ma5 is not None) and (float(close[-1]) > ma5)
        entry["均线多头"] = (ma5 is not None) and (ma10 is not None) and (ma5 > ma10)

        # ── 排除条件 ─────────────────────────────
        exclusions = self._default_exclusions(df, indicators, realtime)

        if not 倍量阴_detected:
            exclusions.append("未检测到倍量阴线")
        if not 长上影_detected:
            exclusions.append("未检测到长上影线")
        if rsi and rsi > 75:
            exclusions.append(f"RSI超买（{rsi}），上影线可能是出货非洗盘")
        if rsi and rsi < 30:
            exclusions.append(f"RSI超卖（{rsi}），趋势走弱")
        if 接近历史新高:
            exclusions.append("接近历史新高，获利盘压力大")
        if 倍量阴_detected and not 缩量确认:
            exclusions.append("倍量阴后未缩量，洗盘不充分")

        # ── 综合评分 ─────────────────────────────
        # 基础分：核心三条件（倍量阴+长上影+接近新高）= 3分
        core_conditions = sum(1 for c in ["倍量阴", "长上影线", "接近20日新高"] if entry.get(c))
        entry_score = core_conditions * (3.0 / 3.0)  # 基础分

        # 附加分
        if entry.get("缩量确认"):
            entry_score += 0.5
        if entry.get("MACD多头"):
            entry_score += 0.3
        if entry.get("均线多头"):
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
            "倍量阴": {
                "已检测": 倍量阴_detected,
                "日期": 倍量阴_date,
                "最低价": round(倍量阴_low, 2) if 倍量阴_low else None,
            },
            "长上影线": 长上影_detected,
            "接近20日新高": 接近新高,
            "近期最高20": round(近期最高20, 2),
            "缩量确认": 缩量确认,
            "MACD": macd,
            "均线多头": entry.get("均线多头", False),
        }

        # ── 风控 ────────────────────────────────
        if 倍量阴_low:
            stop_loss_price = round(float(倍量阴_low) * 0.98, 2)
        else:
            stop_loss_price = round(float(close[-1]) * 0.97, 2)

        take_profit_price = round(float(近期最高20) * 1.05, 2)

        risk_result = indicators.get("风险", {})
        risk_score = risk_result.get("综合风险分数", 50)
        if len(exclusions) > 0:
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
        if signal == SignalStrength.STRONG_BUY:
            action = "倍量阴次日缩量确认后可买入，止损设倍量阴最低-2%"
            holding_period = "5-15天（目标突破20日新高）"
            position_ratio = "轻仓（15-20%）"
        elif signal == SignalStrength.BUY:
            action = "需等待次日缩量确认后再买入"
            holding_period = "5-10天"
            position_ratio = "轻仓（10%）"
        elif signal == SignalStrength.HOLD:
            action = "缺少核心条件（倍量阴/长上影），继续观察"
            holding_period = "观望"
            position_ratio = "空仓"
        else:
            action = "条件不足，不参与"
            holding_period = "-"
            position_ratio = "空仓"

        warnings = []
        if 倍量阴_detected and not 缩量确认:
            warnings.append("倍量阴后未缩量，主力可能仍在出货")
        if rsi and rsi > 65:
            warnings.append("RSI 偏高，洗盘失败概率上升")
        if 接近历史新高:
            warnings.append("接近历史新高，注意解套盘压力")

        reason_parts = []
        if 倍量阴_detected:
            reason_parts.append("倍量阴✅")
        if 长上影_detected:
            reason_parts.append("长上影✅")
        if 接近新高:
            reason_parts.append("接近20日新高✅")
        if 缩量确认:
            reason_parts.append("缩量确认✅")
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
