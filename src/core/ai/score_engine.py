#!/usr/bin/env python3
"""
AIScoreEngine - AI综合评分与信号融合引擎
竹林司马 · 竹林司马AI选股分析引擎
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from ..indicators.technical_indicators import IndicatorsBundle
from ..analysis.risk_analyzer import RiskReport
from ..analysis.trend_analyzer import TrendReport


@dataclass
class ScoreDimension:
    score: float
    weight: float
    weighted_score: float
    grade: str
    key_factors: List[str]


@dataclass
class TradingSignal:
    action: str
    confidence: float
    reason: str
    conditions: List[str]


@dataclass
class AIRecommendation:
    stock_code: str
    stock_name: str
    overall_score: float
    overall_grade: str
    overall_action: str
    tech_score: ScoreDimension
    fund_score: ScoreDimension
    emotion_score: ScoreDimension
    position_advice: str
    entry_price: float
    stop_loss: float
    target_price_1: float
    target_price_2: float
    holding_period: str
    risk_level: str
    signal: TradingSignal
    bull_points: List[str]
    bear_points: List[str]
    action_plan: List[str]
    analyst_notes: str


class AIScoreEngine:
    GRADE_THRESHOLDS = [(80, "A"), (65, "B"), (50, "C"), (35, "D")]

    def score(
        self,
        stock_code: str,
        stock_name: str,
        indicators: IndicatorsBundle,
        fundamentals: Optional[Dict[str, Any]] = None,
        risk_report: Optional[RiskReport] = None,
        trend_report: Optional[TrendReport] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> AIRecommendation:
        fundamentals = fundamentals or {}
        market_data = market_data or {}

        current_price = indicators.current_price
        tech_dim = self._score_technical(indicators)
        fund_dim = self._score_fundamental(fundamentals)
        emotion_dim = self._score_emotion(market_data, indicators)

        # 综合评分（加权）
        overall = tech_dim.score * 0.40 + fund_dim.score * 0.35 + emotion_dim.score * 0.25
        if risk_report:
            overall = overall * (1 - risk_report.overall_risk_score / 200)
        overall = max(0.0, min(100.0, overall))
        grade = self._score_to_grade(overall)

        # 信号
        signal = self._gen_signal(overall, tech_dim, indicators, market_data)
        position = self._calc_position(overall, risk_report)
        stop_loss = risk_report.stop_loss_price if risk_report else round(current_price * 0.93, 2)
        target_1 = round(current_price * 1.08, 2)
        target_2 = round(current_price * 1.15, 2)

        bull = self._extract_bull(indicators, fundamentals)
        bear = self._extract_bear(indicators, fundamentals, market_data, risk_report)
        plan = self._make_plan(signal, indicators, stop_loss, target_1, target_2)
        risk_level = risk_report.overall_risk_level if risk_report else "中"
        holding = "短线（5~15日）" if indicators.kdj.overbought \
            else ("中线（1~3月）" if indicators.ma.golden_fan and not indicators.kdj.overbought else "观望")
        notes = self._make_notes(overall, grade, risk_report)

        return AIRecommendation(
            stock_code=stock_code, stock_name=stock_name,
            overall_score=round(overall, 1), overall_grade=grade,
            overall_action=signal.action,
            tech_score=tech_dim, fund_score=fund_dim, emotion_score=emotion_dim,
            position_advice=position, entry_price=round(current_price, 2),
            stop_loss=round(stop_loss, 2), target_price_1=target_1, target_price_2=target_2,
            holding_period=holding, risk_level=risk_level,
            signal=signal, bull_points=bull, bear_points=bear,
            action_plan=plan, analyst_notes=notes,
        )

    def _score_technical(self, ind: IndicatorsBundle) -> ScoreDimension:
        factors, ma_sc, macd_sc, kdj_sc, rsi_sc, boll_sc = [], 0, 0, 0, 0, 0

        # 均线 20分
        if ind.ma.golden_fan:
            ma_sc = 20; factors.append("均线多头排列")
        elif ind.ma.trend == "震荡":
            ma_sc = 10; factors.append("均线混合")
        else:
            ma_sc = 3; factors.append("均线空头排列")
        if ind.current_price > (ind.ma.ma5 or 0) > (ind.ma.ma20 or 0):
            ma_sc = min(20, ma_sc + 3); factors.append("价格站上各均线")

        # MACD 30分
        if ind.macd.bullish and ind.macd.histogram > 0.5:
            macd_sc = 28; factors.append(f"MACD多头(柱={ind.macd.histogram:.3f})")
        elif ind.macd.bullish:
            macd_sc = 20; factors.append("MACD零轴上方")
        elif ind.macd.death_cross:
            macd_sc = 5; factors.append("MACD死叉")
        else:
            macd_sc = 10; factors.append("MACD零轴下方")
        if ind.macd.divergence == "底背离":
            macd_sc = min(30, macd_sc + 8); factors.append("MACD底背离")
        if ind.macd.divergence == "顶背离":
            macd_sc = max(0, macd_sc - 10); factors.append("MACD顶背离")

        # KDJ 20分
        if ind.kdj.golden_cross and not ind.kdj.overbought:
            kdj_sc = 18; factors.append("KDJ低位金叉")
        elif ind.kdj.status == "中性":
            kdj_sc = 12; factors.append("KDJ中性")
        elif ind.kdj.overbought:
            kdj_sc = 5; factors.append(f"KDJ超买(K={ind.kdj.k:.0f})")
        elif ind.kdj.oversold:
            kdj_sc = 15; factors.append(f"KDJ超卖低位")

        # RSI 15分
        if 40 <= ind.rsi.rsi <= 60:
            rsi_sc = 13; factors.append(f"RSI中性({ind.rsi.rsi:.1f})")
        elif ind.rsi.rsi < 40:
            rsi_sc = 10; factors.append(f"RSI偏低({ind.rsi.rsi:.1f})")
        else:
            rsi_sc = 5; factors.append(f"RSI超买({ind.rsi.rsi:.1f})")

        # 布林 15分
        pos = ind.bollinger.position
        if 0.3 <= pos <= 0.6:
            boll_sc = 13; factors.append(f"布林中段({pos:.0%})")
        elif pos < 0.2:
            boll_sc = 15; factors.append(f"布林下轨({pos:.0%})")
        else:
            boll_sc = 5; factors.append(f"布林上轨({pos:.0%})")
        if ind.bollinger.squeeze:
            boll_sc = min(15, boll_sc + 3); factors.append("布林收口蓄势")

        total = min(100, ma_sc + macd_sc + kdj_sc + rsi_sc + boll_sc)
        return ScoreDimension(total, 0.40, total, self._score_to_grade(total), factors[:5])

    def _score_fundamental(self, fund: Dict) -> ScoreDimension:
        factors, val_sc, grow_sc, prof_sc, health_sc = [], 50, 50, 50, 50
        pe = fund.get("pe"); pb = fund.get("pb")
        industry_pe = fund.get("industry_pe", 27.0)

        if pe:
            if 0 < pe <= industry_pe * 0.7:
                val_sc = 28; factors.append(f"PE={pe:.0f}显著低估")
            elif 0 < pe <= industry_pe * 1.1:
                val_sc = 22; factors.append(f"PE={pe:.0f}合理")
            else:
                val_sc = max(5, 18 - (pe - industry_pe * 1.5) / industry_pe * 8)
                factors.append(f"PE={pe:.0f}偏高")

        profit_g = fund.get("profit_growth_yoy")
        if profit_g is not None:
            if profit_g > 30: grow_sc = 28; factors.append(f"净利润+{profit_g:.0f}%")
            elif profit_g > 15: grow_sc = 22; factors.append(f"净利润+{profit_g:.0f}%")
            elif profit_g > 0: grow_sc = 15; factors.append(f"净利润+{profit_g:.0f}%")
            else: grow_sc = 5; factors.append(f"净利润{profit_g:.0f}%")

        roe = fund.get("roe")
        if roe:
            if roe > 20: prof_sc = 23; factors.append(f"ROE={roe:.1f}%优秀")
            elif roe > 15: prof_sc = 18; factors.append(f"ROE={roe:.1f}%良好")
            else: prof_sc = 10; factors.append(f"ROE={roe:.1f}%偏弱")

        debt = fund.get("debt_ratio")
        if debt:
            health_sc = 14 if debt < 50 else (10 if debt < 70 else 5)
            factors.append(f"负债率{debt:.0f}%{'健康' if debt < 50 else '可控' if debt < 70 else '偏高'}")

        total = min(100, val_sc + grow_sc + prof_sc + health_sc)
        return ScoreDimension(total, 0.35, total, self._score_to_grade(total), factors[:5])

    def _score_emotion(self, market: Dict, ind: IndicatorsBundle) -> ScoreDimension:
        factors, flow_sc, exec_sc, sector_sc, analyst_sc = [], 50, 50, 50, 50
        flow = market.get("main_net_flow_5d", 0.0)
        if flow > 5e7: flow_sc = 28; factors.append(f"5日主力净流入{flow/1e8:.2f}亿")
        elif flow > 0: flow_sc = 22; factors.append("5日主力小幅净流入")
        elif flow > -5e7: flow_sc = 12; factors.append("5日主力略有流出")
        else: flow_sc = 5; factors.append(f"5日主力净流出{abs(flow)/1e8:.2f}亿")

        exec_action = market.get("executive_action", "无")
        if exec_action == "增持": exec_sc = 18; factors.append("高管增持")
        elif exec_action == "减持": exec_sc = 5; factors.append("高管减持")
        else: exec_sc = 15; factors.append("高管无异常")

        vol_ratio = market.get("volume_ratio", 1.0)
        if ind.change_pct > 3 and vol_ratio > 1.5:
            analyst_sc = 8; factors.append("高开低走派发嫌疑")
        elif ind.change_pct > 0 and vol_ratio < 0.8:
            analyst_sc = 22; factors.append("缩量上涨控盘良好")
        else:
            analyst_sc = 15; factors.append("盘口正常")

        total = min(100, flow_sc + exec_sc + sector_sc + analyst_sc)
        return ScoreDimension(total, 0.25, total, self._score_to_grade(total), factors[:5])

    def _gen_signal(self, overall: float, tech_dim: ScoreDimension,
                    ind: IndicatorsBundle, market: Dict) -> TradingSignal:
        conditions = []
        if overall >= 70 and tech_dim.score >= 65 and ind.macd.bullish and ind.ma.golden_fan:
            action, confidence = "BUY", min(0.95, 0.7 + tech_dim.score / 200)
            conditions = [f"综合评分{overall:.0f}分≥70", "技术面与基本面共振", "MACD多头+均线多头"]
        elif overall >= 60 and ind.macd.golden_cross:
            action, confidence = "BUY", 0.75
            conditions = [f"综合评分{overall:.0f}分", "MACD形成金叉"]
        elif overall < 40:
            action, confidence = "SELL", 0.80
            conditions = [f"综合评分{overall:.0f}分<40", "风险大于机会"]
        elif overall >= 50 and ind.kdj.overbought:
            action, confidence = "WAIT", 0.60
            conditions = [f"综合评分{overall:.0f}分", f"KDJ超买(K={ind.kdj.k:.0f})", "等待回调后介入"]
        else:
            action, confidence = "HOLD", 0.55
            conditions = [f"综合评分{overall:.0f}分中性", "趋势未明，持有观察"]

        reason_map = {
            "BUY": f"综合{overall:.0f}分/{tech_dim.grade}级，{'MACD多头' if ind.macd.bullish else '偏弱'}，"
                   f"{'多头排列' if ind.ma.golden_fan else '中性'}均线",
            "SELL": f"综合{overall:.0f}分，{'KDJ超买' if ind.kdj.overbought else '技术偏弱'}，风险大于机会",
            "WAIT": f"综合{overall:.0f}分，KDJ{'超买' if ind.kdj.overbought else '中性'}，方向不明",
            "HOLD": f"综合{overall:.0f}分中性，整体中性，观望",
        }
        return TradingSignal(action, round(confidence, 2), reason_map.get(action, ""), conditions)

    def _calc_position(self, overall: float, risk_report: Optional[RiskReport]) -> str:
        risk = risk_report.overall_risk_score if risk_report else 40
        if overall >= 75 and risk < 40: return "10%~15%（积极布局）"
        elif overall >= 65 and risk < 50: return "5%~10%（谨慎布局）"
        elif overall >= 55: return "0%~5%（轻仓观望）"
        elif overall >= 40: return "0%（空仓）"
        return "0%（规避）"

    def _extract_bull(self, ind: IndicatorsBundle, fund: Dict) -> List[str]:
        p = []
        if ind.ma.golden_fan: p.append("均线多头排列，上升趋势完好")
        if ind.macd.bullish: p.append(f"MACD零轴上方（柱={ind.macd.histogram:.3f}）")
        if ind.macd.golden_cross: p.append("MACD金叉，短期看涨")
        if ind.kdj.oversold: p.append(f"KDJ低位（J={ind.kdj.j:.1f}），反弹概率大")
        if (fund.get("profit_growth_yoy") or 0) > 15: p.append(f"净利润+{fund['profit_growth_yoy']:.0f}%，成长优秀")
        if (fund.get("roe") or 0) > 15: p.append(f"ROE={fund['roe']:.1f}%，盈利突出")
        if ind.bollinger.squeeze: p.append("布林收口蓄势待发")
        return p[:6]

    def _extract_bear(self, ind: IndicatorsBundle, fund: Dict,
                      market: Dict, risk: Optional[RiskReport]) -> List[str]:
        p = []
        if ind.kdj.overbought: p.append(f"KDJ严重超买（K={ind.kdj.k:.0f}），回调概率>70%")
        if ind.macd.divergence == "顶背离": p.append("MACD顶背离，价格创新高但动能减弱")
        if ind.ma.bearish_fan: p.append("均线空头排列，趋势向下")
        if ind.bollinger.position > 0.9: p.append(f"触及布林上轨({ind.bollinger.position:.0%})，向上空间有限")
        if (fund.get("pe") or 0) > 60: p.append(f"PE={fund['pe']:.0f}极高，估值泡沫风险")
        if market.get("executive_action") == "减持": p.append("高管减持，内部人偏空")
        if risk and risk.high_risk_count >= 3: p.append(f"风险评估：{risk.high_risk_count}项高风险")
        if ind.change_pct > 5: p.append(f"今日涨幅+{ind.change_pct:.1f}%，追高风险大")
        return p[:6]

    def _make_plan(self, signal, ind, stop, t1, t2) -> List[str]:
        price = ind.current_price
        plan = [
            f"建议操作：{signal.action}",
            f"当前价：¥{price:.2f}",
            f"止损价：¥{stop:.2f}（跌破即出）",
            f"目标1：¥{t1:.2f}（+{(t1/price-1)*100:.1f}%）",
            f"目标2：¥{t2:.2f}（+{(t2/price-1)*100:.1f}%）",
        ]
        if signal.action == "BUY":
            plan.append(f"等回踩MA10(¥{ind.ma.ma10:.2f})或MA20(¥{ind.ma.ma20:.2f})再介入")
            plan.append("分批建仓：首批30%，确认后加仓至目标仓位")
        elif signal.action == "HOLD":
            plan.append("持有观察，不追加")
            plan.append(f"跌破MA20(¥{ind.ma.ma20:.2f})考虑减仓")
        elif signal.action == "WAIT":
            plan.append("等待KDJ回到中性(K<70)")
            plan.append("回调至MA20附近缩量企稳可重新关注")
        elif signal.action == "SELL":
            plan.append("建议减仓或清仓")
            plan.append("不要逆势加仓摊平")
        return plan

    def _make_notes(self, overall: float, grade: str, risk) -> str:
        notes = f"综合评分{overall:.0f}分，{grade}级。"
        if overall >= 70: notes += "技术面与基本面共振，趋势向好，可布局。"
        elif overall >= 55: notes += "整体中性偏多，注意KDJ超买，建议分批介入。"
        elif overall >= 40: notes += "多空交织，建议耐心等待更好价位。"
        else: notes += "风险大于机会，当前不建议建仓。"
        if risk and risk.overall_risk_level in ["极高", "高"]:
            notes += f" 风险等级{risk.overall_risk_level}，需高度重视。"
        notes += " 本报告仅供参考，不构成投资建议。"
        return notes

    @staticmethod
    def _score_to_grade(score: float) -> str:
        for threshold, grade in AIScoreEngine.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "D"
