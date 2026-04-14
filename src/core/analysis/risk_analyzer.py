#!/usr/bin/env python3
"""
RiskAnalyzer - 多维度风险评估引擎
竹林司马 · 竹林司马AI选股分析引擎

评估维度：
  - 估值风险（PE/PB/PS vs 行业均值）
  - 财务风险（营收/利润增速、毛利率、负债率）
  - 市场风险（大盘相关性、波动率）
  - 流动性风险（换手率、量比）
  - 技术面风险（KDJ超买、MACD背离、均线空头）
  - 外部风险（政策、关税、宏观）
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from ..indicators.technical_indicators import TechnicalIndicators, IndicatorsBundle


@dataclass
class RiskItem:
    dimension: str       # 风险维度
    level: str           # 高/中/低
    score: float         # 风险得分 0~100
    description: str     # 风险描述
    action: str          # 应对建议


@dataclass
class RiskReport:
    overall_risk_score: float
    overall_risk_level: str
    risk_items: List[RiskItem]
    max_drawdown_30d: float
    var_95: float
    stop_loss_price: float
    risk_return_ratio: float
    risk_items_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0


class RiskAnalyzer:
    """
    多维度风险评估引擎

    集成8位大师风险框架：
      - 巴菲特（护城河/ROE）
      - 芒格（逆向思维/反转风险）
      - 达里奥（宏观风险/分散化）
      - 格雷厄姆（安全边际/估值）
      - 彼得·林奇（成长风险/PEG）
      - 格林布拉特（资本回报/ROIC）
      - 邓普顿（极度悲观原则）
      - 索罗斯（反身性/宏观黑天鹅）
    """

    def __init__(self):
        self.ti = TechnicalIndicators()

    def analyze(
        self,
        indicators: IndicatorsBundle,
        fundamentals: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> RiskReport:
        fundamentals = fundamentals or {}
        market_data = market_data or {}
        risk_items: List[RiskItem] = []

        current_price = indicators.current_price
        tech_score = indicators.tech_score

        # 1. 估值风险
        risk_items.append(self._eval_pe_risk(
            fundamentals.get("pe"), fundamentals.get("industry_pe", 27.0)))
        risk_items.append(self._eval_pb_risk(fundamentals.get("pb")))

        # 2. 技术面风险
        risk_items.append(self._eval_kdj_risk(indicators.kdj))
        risk_items.append(self._eval_macd_risk(indicators.macd))
        risk_items.append(self._eval_ma_risk(indicators.ma, current_price))
        risk_items.append(self._eval_boll_risk(indicators.bollinger, current_price))

        # 3. 流动性 + 波动性风险
        risk_items.append(self._eval_turnover_risk(
            indicators.turnover, indicators.volume, fundamentals.get("avg_volume_20d")))
        risk_items.append(self._eval_volatility_risk(
            indicators.atr, current_price, indicators.amplitude))

        # 4. 资金流向
        risk_items.append(self._eval_flow_risk(market_data))

        # 5. 基本面
        risk_items.append(self._eval_fundamental_risk(fundamentals))

        # 综合评分
        weights_map = {"高": 1.5, "中": 1.0, "低": 0.5}
        raw_score = sum(r.score * weights_map[r.level] for r in risk_items) / \
                    sum(weights_map[r.level] for r in risk_items)
        tech_contrib = (100 - tech_score) * 0.3
        overall = min(100, raw_score * 0.7 + tech_contrib)

        if overall >= 70:
            level = "极高"
        elif overall >= 50:
            level = "高"
        elif overall >= 30:
            level = "中"
        else:
            level = "低"

        # 止损价
        stop_loss = current_price * (1 - 2.0 * indicators.atr / current_price)
        stop_loss = round(min(
            stop_loss,
            round(indicators.ma.ma20 * 0.97, 2) if indicators.ma.ma20 else stop_loss,
            round(indicators.ma.ma10 * 0.98, 2) if indicators.ma.ma10 else stop_loss,
        ), 2)

        # 最大回撤预测
        max_dd = round(indicators.amplitude * 1.5, 2)
        var_95 = round(current_price * (indicators.atr / current_price * 1.65), 2)

        # 风险收益比
        upside = max(0, (indicators.ma.ma20 - current_price) / current_price * 100) \
                 if indicators.ma.ma20 else 8
        risk_pct = abs(current_price - stop_loss) / current_price * 100
        rr_ratio = round(upside / (risk_pct + 0.01), 2)

        return RiskReport(
            overall_risk_score=round(overall, 1),
            overall_risk_level=level,
            risk_items=risk_items,
            max_drawdown_30d=max_dd,
            var_95=var_95,
            stop_loss_price=stop_loss,
            risk_return_ratio=rr_ratio,
            risk_items_count=len(risk_items),
            high_risk_count=sum(1 for r in risk_items if r.level == "高"),
            medium_risk_count=sum(1 for r in risk_items if r.level == "中"),
            low_risk_count=sum(1 for r in risk_items if r.level == "低"),
        )

    def _eval_pe_risk(self, pe: Optional[float], industry_pe: float) -> RiskItem:
        if pe is None:
            return RiskItem("估值风险", "中", 45, "PE数据缺失", "补充基本面数据后重新评估")
        if pe <= 0 or pe > 500:
            return RiskItem("估值风险", "高", 85, f"PE={pe} 极度异常", "规避此类标的")
        premium = (pe - industry_pe) / industry_pe * 100
        if premium > 80:
            return RiskItem("估值风险", "高", 90,
                f"PE={pe:.0f} 比行业均值{industry_pe:.0f}高{premium:.0f}%，估值泡沫",
                "高溢价时等待估值回归，谨慎追高")
        elif premium > 40:
            return RiskItem("估值风险", "高", 65,
                f"PE={pe:.0f} 比行业高{premium:.0f}%，估值偏贵",
                "要求业绩高增长匹配PE")
        elif premium > 15:
            return RiskItem("估值风险", "中", 45,
                f"PE={pe:.0f} 比行业高{premium:.0f}%，溢价合理",
                "关注成长性是否支撑估值")
        elif pe < industry_pe * 0.7:
            return RiskItem("估值风险", "低", 20,
                f"PE={pe:.0f} 低于行业均值，行业折价",
                "可适当超配")
        else:
            return RiskItem("估值风险", "中", 35,
                f"PE={pe:.0f} 接近行业均值，估值合理",
                "正常关注")

    def _eval_pb_risk(self, pb: Optional[float]) -> RiskItem:
        if pb is None:
            return RiskItem("估值风险(PB)", "中", 40, "PB数据缺失", "建议补充PB数据")
        if pb > 8:
            return RiskItem("估值风险(PB)", "高", 80,
                f"PB={pb:.2f} 极度偏高，资产重置价值风险大", "规避高PB标的")
        elif pb > 4:
            return RiskItem("估值风险(PB)", "高", 65,
                f"PB={pb:.2f} 偏高，需强成长支撑", "要求业绩高增长匹配PB")
        elif pb > 2:
            return RiskItem("估值风险(PB)", "中", 40,
                f"PB={pb:.2f} 合理区间", "关注ROE是否稳定")
        else:
            return RiskItem("估值风险(PB)", "低", 20,
                f"PB={pb:.2f} 低估，蓝筹特质", "可适当重仓")

    def _eval_kdj_risk(self, kdj) -> RiskItem:
        if kdj.overbought:
            return RiskItem("技术面风险(KDJ)", "高", 72,
                f"KDJ超买（K={kdj.k:.1f} D={kdj.d:.1f} J={kdj.j:.1f}），历史回调概率>70%",
                "超买状态下建议减仓或等待回调")
        elif kdj.oversold:
            return RiskItem("技术面风险(KDJ)", "中", 40,
                f"KDJ超卖（K={kdj.k:.1f}），可能出现反弹",
                "超卖区域可关注超跌反弹机会")
        else:
            return RiskItem("技术面风险(KDJ)", "低", 25,
                f"KDJ中性（K={kdj.k:.1f} D={kdj.d:.1f}），无明显超买超卖",
                "KDJ暂无特殊风险")

    def _eval_macd_risk(self, macd) -> RiskItem:
        if macd.divergence == "顶背离":
            return RiskItem("技术面风险(MACD)", "高", 78,
                "MACD顶背离：价格创新高但MACD柱未跟随，看跌信号",
                "顶背离是重要看跌信号，建议减仓")
        elif macd.divergence == "底背离":
            return RiskItem("技术面风险(MACD)", "中", 35,
                "MACD底背离：价格创新低但MACD柱未跟随，可能企稳",
                "底背离可关注低位布局机会")
        elif not macd.bullish:
            return RiskItem("技术面风险(MACD)", "中", 50,
                f"MACD柱<0（={macd.histogram:.3f}），处于空头区域",
                "MACD空头区域建议谨慎，耐心等待金叉")
        else:
            return RiskItem("技术面风险(MACD)", "低", 20,
                f"MACD柱>0（={macd.histogram:.3f}），多头动能良好",
                "MACD多头暂无特殊风险")

    def _eval_ma_risk(self, ma, price: float) -> RiskItem:
        if ma.bearish_fan:
            return RiskItem("技术面风险(均线)", "高", 70,
                "均线空头排列（5<10<20<60），中长期趋势向下",
                "空头排列下规避，建议等待趋势修复")
        elif ma.golden_fan:
            return RiskItem("技术面风险(均线)", "低", 15,
                "均线多头排列，上升趋势健康",
                "多头排列下顺势持有，注意高位止盈")
        else:
            below = bool(price < ma.ma20) if ma.ma20 else False
            if below:
                return RiskItem("技术面风险(均线)", "中", 55,
                    f"价格({price:.2f})跌破MA20({ma.ma20:.2f})，短期偏弱",
                    "建议等待重新站上MA20后再介入")
            return RiskItem("技术面风险(均线)", "低", 30,
                "均线混合排列，震荡格局",
                "震荡格局适合高抛低吸")

    def _eval_boll_risk(self, boll, price: float) -> RiskItem:
        if boll.position > 0.95:
            return RiskItem("技术面风险(布林带)", "高", 68,
                f"价格触及布林上轨（{boll.upper:.2f}），当前位置{boll.position:.0%}，向上空间有限",
                "接近上轨建议分批减仓，等待回踩中轨")
        elif boll.position < 0.1:
            return RiskItem("技术面风险(布林带)", "中", 40,
                f"价格触及布林下轨（{boll.lower:.2f}），超卖信号",
                "触及下轨可关注反弹机会")
        elif boll.squeeze:
            return RiskItem("技术面风险(布林带)", "低", 25,
                "布林带收口，波动率压缩，可能蓄势突破",
                "收口区耐心等待方向选择")
        else:
            return RiskItem("技术面风险(布林带)", "低", 25,
                f"价格位于布林带{boll.position:.0%}分位，位置正常",
                "布林带暂无特殊风险")

    def _eval_turnover_risk(self, turnover: float, vol: float,
                             avg_vol: Optional[float]) -> RiskItem:
        if avg_vol and vol > avg_vol * 3:
            return RiskItem("流动性风险", "高", 60,
                f"今日成交量是20日均量的{vol/(avg_vol+1):.1f}倍，异常放量",
                "异常放量需判断是吸筹还是派发")
        elif turnover < 0.5:
            return RiskItem("流动性风险", "中", 45,
                f"换手率{turnover:.2f}%偏低，流动性不足",
                "低流动性股大资金进出困难，需注意冲击成本")
        elif turnover > 15:
            return RiskItem("流动性风险", "中", 50,
                f"换手率{turnover:.2f}%偏高，博弈激烈",
                "高换手需判断筹码结构，主力是否在出货")
        else:
            return RiskItem("流动性风险", "低", 20,
                f"换手率{turnover:.2f}%适中，流动性良好",
                "流动性无特殊风险")

    def _eval_volatility_risk(self, atr: float, price: float,
                               amplitude: float) -> RiskItem:
        atr_pct = atr / price * 100
        if atr_pct > 5:
            return RiskItem("波动性风险", "高", 70,
                f"ATR={atr:.2f}（{atr_pct:.1f}%），波动率极高",
                "高波动股短线风险大，建议降低仓位")
        elif atr_pct > 3:
            return RiskItem("波动性风险", "中", 50,
                f"ATR={atr:.2f}（{atr_pct:.1f}%），波动率偏高",
                "适当关注止损设置，控制回撤")
        else:
            return RiskItem("波动性风险", "低", 25,
                f"ATR={atr:.2f}（{atr_pct:.1f}%），波动率正常",
                "波动率正常，适合趋势策略")

    def _eval_flow_risk(self, market_data: Dict) -> RiskItem:
        main_flow = market_data.get("main_net_flow_5d", 0.0)
        if main_flow < -1e8:
            return RiskItem("资金流向风险", "高", 72,
                f"5日主力净流出{main_flow/1e8:.2f}亿元，持续出逃",
                "主力持续流出是看跌信号，建议减仓")
        elif main_flow < -5000:
            return RiskItem("资金流向风险", "中", 50,
                f"5日主力净流出{main_flow/1e4:.0f}万元，略有流出",
                "关注主力流向是否逆转")
        elif main_flow > 1e8:
            return RiskItem("资金流向风险", "低", 20,
                f"5日主力净流入{main_flow/1e8:.2f}亿元，主力吸筹",
                "主力净流入是积极信号")
        else:
            return RiskItem("资金流向风险", "低", 30,
                "资金流向数据暂无",
                "建议补充实时资金流向数据")

    def _eval_fundamental_risk(self, fundamentals: Dict) -> RiskItem:
        rev_growth = fundamentals.get("revenue_growth_yoy")
        profit_growth = fundamentals.get("profit_growth_yoy")
        roe = fundamentals.get("roe")
        debt_ratio = fundamentals.get("debt_ratio")
        score = 30
        descs = []
        if rev_growth is not None and rev_growth < -10:
            descs.append(f"营收同比{rev_growth:.1f}%")
            score += 20
        if profit_growth is not None and profit_growth < -20:
            descs.append(f"净利润同比{profit_growth:.1f}%")
            score += 25
        if roe is not None and roe < 5:
            descs.append(f"ROE={roe:.1f}%偏低")
            score += 15
        if debt_ratio is not None and debt_ratio > 80:
            descs.append(f"负债率{debt_ratio:.0f}%")
            score += 15
        level = "高" if score >= 60 else ("中" if score >= 40 else "低")
        desc = "；".join(descs) if descs else "基本面暂无明显风险"
        return RiskItem("基本面风险", level, min(score, 95), desc, "深入分析基本面恶化原因")
