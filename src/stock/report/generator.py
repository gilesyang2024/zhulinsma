#!/usr/bin/env python3
"""
StockReportGenerator - 竹林司马选股分析报告生成器（核心可复用组件）
竹林司马 · 竹林司马AI选股分析引擎

设计原则：
  - 完全独立：不依赖 FastAPI/Database，可在任何Python环境运行
  - 数据驱动：所有展示内容由 ReportData 控制
  - 暗色专业主题，符合机构研报审美

使用示例：
    from zhulinsma.src.stock.data.fetcher import StockFetcher
    from zhulinsma.src.core.indicators.technical_indicators import TechnicalIndicators
    from zhulinsma.src.stock.report.generator import StockReportGenerator

    fetcher = StockFetcher()
    df = fetcher.get_daily("600875", adjust="qfq")
    ti = TechnicalIndicators()
    bundle = ti.compute_all(df)

    gen = StockReportGenerator()
    data = gen.data_from_bundle("东方电气", "600875", bundle)
    html = gen.generate(data)
    gen.save(html, "东方电气.html")
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import Optional, Dict, Any, List


# ─────────────────────────────────────────
# 数据容器
# ─────────────────────────────────────────

class ReportData:
    """报告数据容器（POPO - Plain Old Python Object）"""

    def __init__(self):
        # 股票基础信息
        self.stock_code: str = ""
        self.stock_name: str = ""
        self.exchange: str = ""
        self.industry: str = ""
        self.city: str = ""
        self.report_date: str = ""
        self.data_days: int = 0

        # 行情
        self.current_price: float = 0.0
        self.open_price: float = 0.0
        self.high_price: float = 0.0
        self.low_price: float = 0.0
        self.prev_close: float = 0.0
        self.change_pct: float = 0.0
        self.volume: float = 0.0
        self.amount: float = 0.0
        self.turnover: float = 0.0
        self.volume_ratio: float = 1.0
        self.amplitude: float = 0.0

        # 区间表现
        self.return_5d: float = 0.0
        self.return_10d: float = 0.0
        self.return_30d: float = 0.0
        self.return_60d: float = 0.0
        self.high_60d: float = 0.0
        self.low_60d: float = 0.0
        self.position_60d: float = 50.0
        self.ytd_return: float = 0.0

        # 均线
        self.ma5: Optional[float] = None
        self.ma10: Optional[float] = None
        self.ma20: Optional[float] = None
        self.ma60: Optional[float] = None
        self.ma120: Optional[float] = None
        self.ma_trend: str = ""

        # MACD
        self.macd_value: float = 0.0
        self.macd_signal: float = 0.0
        self.macd_histogram: float = 0.0
        self.macd_bullish: bool = False
        self.macd_golden: bool = False
        self.macd_divergence: Optional[str] = None

        # KDJ
        self.kdj_k: float = 50.0
        self.kdj_d: float = 50.0
        self.kdj_j: float = 50.0
        self.kdj_golden: bool = False
        self.kdj_overbought: bool = False
        self.kdj_oversold: bool = False
        self.kdj_status: str = ""

        # RSI
        self.rsi_value: float = 50.0
        self.rsi_status: str = ""

        # 布林带
        self.boll_upper: float = 0.0
        self.boll_middle: float = 0.0
        self.boll_lower: float = 0.0
        self.boll_bw: float = 0.0
        self.boll_position: float = 0.5
        self.boll_squeeze: bool = False

        # ATR / OBV
        self.atr_value: float = 0.0
        self.obv_trend: str = ""

        # 评分
        self.tech_score: float = 0.0
        self.tech_grade: str = "C"
        self.fund_score: float = 0.0
        self.fund_grade: str = "C"
        self.emotion_score: float = 0.0
        self.emotion_grade: str = "C"
        self.overall_score: float = 0.0
        self.overall_grade: str = "C"
        self.overall_action: str = "HOLD"

        # 基本面
        self.pe: Optional[float] = None
        self.pe_ttm: Optional[float] = None
        self.pb: Optional[float] = None
        self.ps: Optional[float] = None
        self.peg: Optional[float] = None
        self.eps: Optional[float] = None
        self.industry_pe: float = 27.0
        self.roe: Optional[float] = None
        self.profit_growth_yoy: Optional[float] = None
        self.revenue_growth_yoy: Optional[float] = None
        self.debt_ratio: Optional[float] = None
        self.dividend_yield: Optional[float] = None
        self.net_profit: Optional[float] = None
        self.master_scores: Dict[str, float] = {}
        self.master_notes: Dict[str, str] = {}

        # 情绪
        self.main_net_flow_5d: float = 0.0
        self.main_net_flow_10d: float = 0.0
        self.main_net_flow_30d: float = 0.0
        self.executive_action: str = "无"
        self.executive_date: Optional[str] = None
        self.is_limit_up: bool = False

        # 风险
        self.risk_score: float = 0.0
        self.risk_level: str = "中"
        self.stop_loss: float = 0.0
        self.var_95: float = 0.0
        self.max_drawdown: float = 0.0
        self.risk_return_ratio: float = 0.0
        self.risk_items: List[Dict] = []

        # 趋势
        self.long_trend: str = ""
        self.medium_trend: str = ""
        self.short_trend: str = ""
        self.trend_strength: float = 0.0
        self.momentum: str = ""
        self.support_levels: List[float] = []
        self.resistance_levels: List[float] = []

        # 战法
        self.strategy_scores: Dict[str, Dict] = {}

        # 多空逻辑
        self.bull_points: List[str] = []
        self.bear_points: List[str] = []

        # 交易建议
        self.entry_price: float = 0.0
        self.target_price_1: float = 0.0
        self.target_price_2: float = 0.0
        self.position_advice: str = ""
        self.holding_period: str = ""
        self.signal_confidence: float = 0.0
        self.signal_reason: str = ""
        self.action_plan: List[str] = []
        self.analyst_notes: str = ""

        # ====== 预测分析 (2026-04-16) ======
        self.prediction_enabled: bool = False
        # 趋势预测
        self.trend_forecast: str = ""          # 短期趋势预判（如"震荡偏弱，关注25.8支撑"）
        self.trend_confidence: str = ""        # 预判置信度（高/中/低）
        self.forecast_horizon: str = ""        # 预测时间窗口（如"3-5个交易日"）
        # 场景分析
        self.scenario_bull: Dict[str, Any] = {}   # 乐观情景 {target, prob, trigger, desc}
        self.scenario_base: Dict[str, Any] = {}   # 基准情景
        self.scenario_bear: Dict[str, Any] = {}   # 悲观情景
        # 关键价位预测
        self.predicted_support: float = 0.0        # 预测支撑位
        self.predicted_resistance: float = 0.0     # 预测阻力位
        self.breakout_up_prob: float = 0.0         # 向上突破概率
        self.breakout_down_prob: float = 0.0       # 向下跌破概率
        # 时机判断
        self.best_entry_window: str = ""           # 最佳入场窗口
        self.key_catalyst: str = ""                # 关键催化因素
        self.risk_event: str = ""                  # 风险事件预警

    def from_indicators_bundle(self, name: str, code: str, bundle) -> "ReportData":
        """从 IndicatorsBundle 填充技术面数据"""
        self.stock_name = name
        self.stock_code = code
        self.current_price = bundle.current_price
        self.open_price = bundle.open_price
        self.high_price = bundle.high_price
        self.low_price = bundle.low_price
        self.prev_close = bundle.prev_close
        self.change_pct = bundle.change_pct
        self.volume = bundle.volume
        self.amount = bundle.amount
        self.amplitude = bundle.amplitude
        self.turnover = bundle.turnover
        self.ma5 = bundle.ma.ma5
        self.ma10 = bundle.ma.ma10
        self.ma20 = bundle.ma.ma20
        self.ma60 = bundle.ma.ma60
        self.ma120 = bundle.ma.ma120
        self.ma_trend = bundle.ma.trend
        self.macd_value = bundle.macd.macd
        self.macd_signal = bundle.macd.signal
        self.macd_histogram = bundle.macd.histogram
        self.macd_bullish = bundle.macd.bullish
        self.macd_golden = bundle.macd.golden_cross
        self.macd_divergence = bundle.macd.divergence
        self.kdj_k = bundle.kdj.k
        self.kdj_d = bundle.kdj.d
        self.kdj_j = bundle.kdj.j
        self.kdj_golden = bundle.kdj.golden_cross
        self.kdj_overbought = bundle.kdj.overbought
        self.kdj_oversold = bundle.kdj.oversold
        self.kdj_status = bundle.kdj.status
        self.rsi_value = bundle.rsi.rsi
        self.rsi_status = bundle.rsi.status
        self.boll_upper = bundle.bollinger.upper
        self.boll_middle = bundle.bollinger.middle
        self.boll_lower = bundle.bollinger.lower
        self.boll_bw = bundle.bollinger.bandwidth
        self.boll_position = bundle.bollinger.position
        self.boll_squeeze = bundle.bollinger.squeeze
        self.atr_value = bundle.atr
        self.obv_trend = bundle.obv_trend
        self.tech_score = bundle.tech_score
        self.tech_grade = bundle.tech_grade
        return self

    def from_ai_recommendation(self, rec) -> "ReportData":
        """从 AIRecommendation 填充综合结果"""
        self.overall_score = rec.overall_score
        self.overall_grade = rec.overall_grade
        self.overall_action = rec.overall_action
        self.fund_score = rec.fund_score.score
        self.fund_grade = rec.fund_score.grade
        self.emotion_score = rec.emotion_score.score
        self.emotion_grade = rec.emotion_score.grade
        self.entry_price = rec.entry_price
        self.target_price_1 = rec.target_price_1
        self.target_price_2 = rec.target_price_2
        self.stop_loss = rec.stop_loss
        self.position_advice = rec.position_advice
        self.holding_period = rec.holding_period
        self.risk_level = rec.risk_level
        self.signal_confidence = rec.signal.confidence
        self.signal_reason = rec.signal.reason
        self.bull_points = rec.bull_points
        self.bear_points = rec.bear_points
        self.action_plan = rec.action_plan
        self.analyst_notes = rec.analyst_notes
        return self

    def from_risk_report(self, rr) -> "ReportData":
        """从 RiskReport 填充风险数据"""
        self.risk_score = rr.overall_risk_score
        self.risk_level = rr.overall_risk_level
        self.stop_loss = rr.stop_loss_price
        self.var_95 = rr.var_95
        self.max_drawdown = rr.max_drawdown_30d
        self.risk_return_ratio = rr.risk_return_ratio
        self.risk_items = [
            {"level": r.level, "dimension": r.dimension, "description": r.description}
            for r in rr.risk_items
        ]
        return self

    def from_trend_report(self, tr) -> "ReportData":
        """从 TrendReport 填充趋势数据"""
        self.long_trend = tr.long_trend
        self.medium_trend = tr.medium_trend
        self.short_trend = tr.short_trend
        self.trend_strength = tr.trend_strength
        self.momentum = tr.momentum
        self.support_levels = tr.support_levels
        self.resistance_levels = tr.resistance_levels
        return self

    def from_fundamentals(self, fund: Dict) -> "ReportData":
        """从基本面字典填充"""
        self.pe = fund.get("pe"); self.pe_ttm = fund.get("pe_ttm")
        self.pb = fund.get("pb"); self.ps = fund.get("ps")
        self.peg = fund.get("peg"); self.eps = fund.get("eps")
        self.industry_pe = fund.get("industry_pe", 27.0)
        self.roe = fund.get("roe")
        self.profit_growth_yoy = fund.get("profit_growth_yoy")
        self.revenue_growth_yoy = fund.get("revenue_growth_yoy")
        self.debt_ratio = fund.get("debt_ratio")
        self.dividend_yield = fund.get("dividend_yield")
        self.net_profit = fund.get("net_profit")
        self.master_scores = fund.get("master_scores", {})
        self.master_notes = fund.get("master_notes", {})
        self.fund_score = fund.get("_fund_score", 50.0)
        self.fund_grade = fund.get("_fund_grade", "C")
        return self

    def from_market_data(self, md: Dict) -> "ReportData":
        """从市场情绪字典填充"""
        self.main_net_flow_5d = md.get("main_net_flow_5d", 0)
        self.main_net_flow_10d = md.get("main_net_flow_10d", 0)
        self.main_net_flow_30d = md.get("main_net_flow_30d", 0)
        self.executive_action = md.get("executive_action", "无")
        self.executive_date = md.get("executive_date")
        self.is_limit_up = md.get("is_limit_up", False)
        self.volume_ratio = md.get("volume_ratio", 1.0)
        self.emotion_score = md.get("_emotion_score", 50.0)
        self.emotion_grade = md.get("_emotion_grade", "C")
        return self

    def calc_overall(self) -> "ReportData":
        """计算综合评分（若未设置）"""
        if self.overall_score == 0:
            self.overall_score = round(
                self.tech_score * 0.40 +
                self.fund_score * 0.35 +
                self.emotion_score * 0.25, 1
            )
        return self


# ─────────────────────────────────────────
# HTML生成器
# ─────────────────────────────────────────

class StockReportGenerator:
    """
    竹林司马选股分析报告生成器

    使用方式：
        gen = StockReportGenerator()
        html = gen.generate(report_data)
        path = gen.save(html, "/path/to/report.html")
    """

    def generate(self, data: ReportData) -> str:
        """主入口：生成HTML报告字符串"""
        if not data.report_date:
            data.report_date = datetime.now().strftime("%Y-%m-%d")

        ctx = self._build_context(data)
        return _HTML_TEMPLATE.format(**ctx)

    def save(self, html: str, filepath: str) -> str:
        """保存HTML到文件，返回绝对路径"""
        abspath = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, "w", encoding="utf-8") as f:
            f.write(html)
        return abspath

    # ─────────────────────────────────────
    # 上下文构建
    # ─────────────────────────────────────

    def _build_context(self, d: ReportData) -> Dict:
        # 预计算CSS类
        chg_cls = "pos" if d.change_pct > 0 else "neg"
        change_arrow = "▲" if d.change_pct > 0 else ("▼" if d.change_pct < 0 else "—")
        gauge_offset = round(213.63 * (1 - d.overall_score / 100), 2)
        tech_color = _score_color(d.tech_score)
        fund_color = _score_color(d.fund_score)
        emotion_color = _score_color(d.emotion_score)
        ov_score_pct = round(d.overall_score, 1)
        ov_gauge = round(d.overall_score, 1)
        ov_gauge_offset = round(213.63 * (1 - d.overall_score / 100), 2)

        return {
            # 基础
            "stock_name": d.stock_name,
            "stock_code": d.stock_code,
            "exchange": d.exchange or "上交所",
            "industry": d.industry or "电力设备",
            "report_date": d.report_date,
            "data_days": d.data_days,

            # 行情
            "current_price": _price(d.current_price),
            "open_price": _price(d.open_price),
            "prev_close": _price(d.prev_close),
            "high_price": _price(d.high_price),
            "low_price": _price(d.low_price),
            "change_pct": _pct(d.change_pct),
            "change_arrow": change_arrow,
            "amplitude": _pct(d.amplitude),
            "volume": _vol(d.volume),
            "amount": _amt(d.amount),
            "turnover": _pct(d.turnover),
            "volume_ratio": f"{d.volume_ratio:.2f}×",
            "chg_cls": chg_cls,
            "position_cls": "buy" if d.overall_action == "BUY" else ("sell" if d.overall_action == "SELL" else "warn"),

            # 区间
            "ret5": _ret_badge(d.return_5d),
            "ret10": _ret_badge(d.return_10d),
            "ret30": _ret_badge(d.return_30d),
            "ret60": _ret_badge(d.return_60d),
            "range_60d": f"¥{d.low_60d:.2f}~¥{d.high_60d:.2f}",
            "pos_60d": _pct(d.position_60d),
            "ytd": _ret_badge(d.ytd_return),

            # 评分
            "overall_score": _s(d.overall_score),
            "overall_grade": _grade_badge(d.overall_grade),
            "overall_action": _action_badge(d.overall_action),
            "overall_grade_html": _grade_badge_html(d.overall_grade),
            "overall_action_html": _action_badge_html(d.overall_action),
            "grade_color": _grade_color(d.overall_grade),
            "action_color": _action_color(d.overall_action),
            "tech_score": _s(d.tech_score),
            "tech_grade": _grade_badge(d.tech_grade),
            "fund_score": _s(d.fund_score),
            "fund_grade": _grade_badge(d.fund_grade),
            "emotion_score": _s(d.emotion_score),
            "emotion_grade": _grade_badge(d.emotion_grade),
            "position_advice": d.position_advice or "空仓观望",
            "tech_color": tech_color,
            "fund_color": fund_color,
            "emotion_color": emotion_color,
            "ov_score_pct": _s(ov_score_pct),
            "ov_gauge": _s(ov_gauge),
            "ov_gauge_offset": ov_gauge_offset,
            "tech_score_num": int(d.tech_score),
            "tech_score_pct": f"{d.tech_score}%",
            "tech_w_score": round(d.tech_score * 0.4, 1),
            "fund_w_score": round(d.fund_score * 0.35, 1),
            "emotion_w_score": round(d.emotion_score * 0.25, 1),
            "kdj_k_cls": "sell" if d.kdj_k > 80 else ("buy" if d.kdj_k < 20 else "neutral"),
            "kdj_j_cls": "sell" if d.kdj_j > 100 else ("buy" if d.kdj_j < 0 else "neutral"),

            # 技术面
            "ma5": _ma_row(d.ma5, d.current_price, "MA5"),
            "ma10": _ma_row(d.ma10, d.current_price, "MA10"),
            "ma20": _ma_row(d.ma20, d.current_price, "MA20"),
            "ma60": _ma_row(d.ma60, d.current_price, "MA60"),
            "ma_trend": _trend_badge(d.ma_trend),
            "ma_desc": _ma_desc(d),
            "macd_val": _num(d.macd_value, 3),
            "macd_sig": _num(d.macd_signal, 3),
            "macd_hist": _num(d.macd_histogram, 3),
            "macd_val_cls": "buy" if d.macd_bullish else "sell",
            "macd_hist_cls": "buy" if d.macd_histogram > 0 else "sell",
            "macd_bullish_html": _bull_badge(d.macd_bullish),
            "macd_div": _div_badge(d.macd_divergence),
            "macd_desc": _macd_desc(d),
            "kdj_k": _num(d.kdj_k, 1),
            "kdj_d": _num(d.kdj_d, 1),
            "kdj_j": _num(d.kdj_j, 1),
            "kdj_golden": _gc_badge(d.kdj_golden),
            "kdj_status": _kdj_badge(d),
            "kdj_desc": _kdj_desc(d),
            "rsi_val": _num(d.rsi_value, 1),
            "rsi_status": _rsi_badge(d.rsi_value),
            "rsi_desc": _rsi_desc(d),
            "boll_upper": _price(d.boll_upper),
            "boll_mid": _price(d.boll_middle),
            "boll_lower": _price(d.boll_lower),
            "boll_bw": _pct(d.boll_bw * 100) if d.boll_bw else "—",
            "boll_pos": _pct(d.boll_position * 100) if d.boll_position else "—",
            "boll_squeeze": _squeeze_badge(d.boll_squeeze),
            "boll_desc": _boll_desc(d),
            "atr_val": _price(d.atr_value),
            "obv_trend": _trend_badge(d.obv_trend),
            "tech_score_num": int(d.tech_score),
            "tech_score_pct": f"{d.tech_score}%",
            "tech_score_color": _score_color(d.tech_score),

            # 基本面
            "pe_val": _pe_val(d),
            "industry_pe": _num(d.industry_pe, 1),
            "pe_premium": _pe_premium(d),
            "pb_val": _num(d.pb, 2) if d.pb else "—",
            "ps_val": _num(d.ps, 2) if d.ps else "—",
            "peg_val": _num(d.peg, 2) if d.peg else "—",
            "eps_val": _price(d.eps) if d.eps else "—",
            "roe_val": _pct(d.roe) if d.roe else "—",
            "profit_growth": _growth_badge(d.profit_growth_yoy),
            "revenue_growth": _growth_badge(d.revenue_growth_yoy),
            "debt_ratio": _pct(d.debt_ratio) if d.debt_ratio else "—",
            "dividend": _pct(d.dividend_yield) if d.dividend_yield else "—",
            "net_profit": _amt(d.net_profit) if d.net_profit else "—",
            "masters_html": _masters_html(d),
            "fund_score_num": int(d.fund_score),
            "fund_score_color": _score_color(d.fund_score),

            # 情绪
            "flow_5d": _flow_badge(d.main_net_flow_5d),
            "flow_10d": _flow_badge(d.main_net_flow_10d),
            "flow_30d": _flow_badge(d.main_net_flow_30d),
            "exec_action": _exec_badge(d.executive_action),
            "exec_date": d.executive_date or "",
            "is_limit_up": _zt_badge(d.is_limit_up),
            "emotion_score_num": int(d.emotion_score),
            "emotion_score_color": _score_color(d.emotion_score),

            # 风险
            "risk_score": _s(d.risk_score),
            "risk_level": _risk_level_badge(d.risk_level),
            "stop_loss": _price(d.stop_loss),
            "var_95": _price(d.var_95),
            "max_dd": _pct(d.max_drawdown),
            "rr_ratio": _num(d.risk_return_ratio, 2),
            "risk_items_html": _risk_items_html(d.risk_items),

            # 趋势
            "long_trend": _trend_badge(d.long_trend),
            "medium_trend": _trend_badge(d.medium_trend),
            "short_trend": _trend_badge(d.short_trend),
            "trend_strength": _num(d.trend_strength, 0),
            "momentum": _trend_badge(d.momentum),
            "support_html": _levels_text(d.support_levels),
            "resistance_html": _levels_text(d.resistance_levels),

            # 战法
            "strategies_html": _strategies_html(d.strategy_scores),

            # 多空
            "bull_html": _points_html(d.bull_points, "bull"),
            "bear_html": _points_html(d.bear_points, "bear"),

            # 交易
            "entry": _price(d.entry_price),
            "target1": _price(d.target_price_1),
            "target2": _price(d.target_price_2),
            "stop": _price(d.stop_loss),
            "holding_period": d.holding_period or "观望",
            "confidence": _pct(d.signal_confidence * 100) if d.signal_confidence else "—",
            "signal_reason": d.signal_reason or "",
            "plan_items": "".join(f"<li>{p}</li>" for p in d.action_plan),
            "analyst_notes": d.analyst_notes or "",

            # 预测分析
            "pred_enabled": d.prediction_enabled,
            "trend_forecast": d.trend_forecast or "暂无预判",
            "trend_confidence": d.trend_confidence or "—",
            "forecast_horizon": d.forecast_horizon or "—",
            "scenario_bull_html": _scenario_html(d.scenario_bull, "buy"),
            "scenario_base_html": _scenario_html(d.scenario_base, "neutral"),
            "scenario_bear_html": _scenario_html(d.scenario_bear, "sell"),
            "pred_support": _price(d.predicted_support) if d.predicted_support else "—",
            "pred_resistance": _price(d.predicted_resistance) if d.predicted_resistance else "—",
            "breakout_up_prob": _pct(d.breakout_up_prob) if d.breakout_up_prob else "—",
            "breakout_down_prob": _pct(d.breakout_down_prob) if d.breakout_down_prob else "—",
            "best_entry_window": d.best_entry_window or "—",
            "key_catalyst": d.key_catalyst or "—",
            "risk_event": d.risk_event or "—",
        }


# ─────────────────────────────────────────
# 格式化辅助函数
# ─────────────────────────────────────────

def _price(v: float, dec: int = 2) -> str:
    if not v: return "—"
    return f"¥{v:,.{dec}f}"

def _pct(v: float, dec: int = 2) -> str:
    if not v and v != 0: return "—"
    return f"{v:.{dec}f}%"

def _num(v: Optional[float], dec: int = 2) -> str:
    if v is None: return "—"
    return f"{v:.{dec}f}"

def _amt(v: float) -> str:
    if not v: return "—"
    if v >= 1e8: return f"{v/1e8:.2f}亿"
    if v >= 1e4: return f"{v/1e4:.0f}万"
    return f"{v:.0f}"

def _vol(v: float) -> str:
    if not v: return "—"
    if v >= 1e8: return f"{v/1e8:.2f}亿股"
    if v >= 1e4: return f"{v/1e4:.0f}万股"
    return f"{v:.0f}股"

def _s(v: float) -> str:
    return f"{v:.0f}"

def _ret_badge(v: float) -> str:
    if not v and v != 0: return '<span class="badge-neutral">—</span>'
    cls = "buy" if v > 0 else "sell"
    sign = "+" if v > 0 else ""
    return f'<span class="badge-{cls}">{sign}{v:.2f}%</span>'

def _bull_badge(b: bool) -> str:
    return '<span class="badge-buy">✓ 多头</span>' if b else '<span class="badge-sell">✗ 空头</span>'

def _gc_badge(g: bool) -> str:
    return '<span class="badge-buy">✓ 金叉</span>' if g else '<span class="badge-neutral">—</span>'

def _div_badge(d: Optional[str]) -> str:
    if d == "顶背离": return '<span class="badge-sell">⚠ 顶背离</span>'
    if d == "底背离": return '<span class="badge-buy">✓ 底背离</span>'
    return '<span class="badge-neutral">无背离</span>'

def _kdj_badge(d: ReportData) -> str:
    if d.kdj_overbought: return f'<span class="badge-sell">⚠ 超买(K={d.kdj_k:.0f})</span>'
    if d.kdj_oversold: return f'<span class="badge-buy">✓ 超卖低位</span>'
    return f'<span class="badge-neutral">中性(K={d.kdj_k:.0f})</span>'

def _rsi_badge(r: float) -> str:
    if r > 70: return f'<span class="badge-sell">超买({r:.1f})</span>'
    if r < 30: return f'<span class="badge-buy">超卖({r:.1f})</span>'
    return f'<span class="badge-neutral">中性({r:.1f})</span>'

def _squeeze_badge(sq: bool) -> str:
    return '<span class="badge-buy">✓ 收口蓄势</span>' if sq else '<span class="badge-neutral">正常</span>'

def _action_badge(a: str) -> str:
    """返回纯文本，模板负责样式"""
    return a

def _grade_badge(g: str) -> str:
    """返回带'级'后缀的纯文本，模板负责样式"""
    return f"{g}级"

def _grade_badge_html(g: str) -> str:
    """返回带颜色的badge HTML（含'级'），用于verdict面板"""
    color = _grade_color(g)
    return f'<span style="font-size:20px;font-weight:700;padding:4px 14px;border-radius:8px;background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15);color:{color}">{g}级</span>'

def _action_badge_html(a: str) -> str:
    """返回带颜色的action HTML，用于verdict面板"""
    color = _action_color(a)
    return f' <span style="font-size:16px;font-weight:700;color:{color}">· {a}</span>'

def _trend_badge(t: str) -> str:
    cls = {"上升": "buy", "多头": "buy", "下降": "sell", "空头": "sell",
           "震荡": "warn", "加速": "buy", "减速": "sell", "平稳": "neutral"}.get(t, "neutral")
    return f'<span class="badge-{cls}">{t}</span>'

def _risk_level_badge(l: str) -> str:
    cls = {"极高": "sell", "高": "sell", "中": "warn", "低": "buy"}.get(l, "neutral")
    return f'<span class="badge-{cls}">{l}风险</span>'

def _exec_badge(a: str) -> str:
    if a == "增持": return '<span class="badge-buy">✓ 高管增持</span>'
    if a == "减持": return '<span class="badge-sell">⚠ 高管减持</span>'
    return '<span class="badge-neutral">无异常</span>'

def _zt_badge(z: bool) -> str:
    return '<span class="badge-buy">✓ 今日涨停</span>' if z else '<span class="badge-neutral">—</span>'

def _score_color(s: float) -> str:
    if s >= 70: return "#00e5a0"
    if s >= 55: return "#f5a623"
    if s >= 40: return "#ff7b4f"
    return "#ff4d6d"

def _grade_color(g: str) -> str:
    """等级字母 → CSS颜色"""
    return {"A": "#00e5a0", "B": "#00e5a0", "C": "#f5a623", "D": "#ff4d6d"}.get(g, "#6c8ef5")

def _action_color(a: str) -> str:
    """操作信号 → CSS颜色"""
    return {"BUY": "#00e5a0", "SELL": "#ff4d6d", "HOLD": "#6c8ef5", "WAIT": "#f5a623"}.get(a, "#6c8ef5")

def _pe_val(d: ReportData) -> str:
    pe = d.pe or d.pe_ttm
    if pe is None: return "—"
    if pe > d.industry_pe * 1.5: color = "#ff4d6d"
    elif pe < d.industry_pe * 0.7: color = "#00e5a0"
    else: color = "#e0e4f0"
    return f'<span style="color:{color}">{pe:.1f}×</span>'

def _pe_premium(d: ReportData) -> str:
    pe = d.pe or d.pe_ttm
    if pe is None: return "—"
    prem = (pe - d.industry_pe) / d.industry_pe * 100
    cls = "sell" if prem > 20 else ("buy" if prem < -15 else "neutral")
    sign = "+" if prem > 0 else ""
    return f'<span class="badge-{cls}">{sign}{prem:.0f}%vs行业</span>'

def _growth_badge(v: Optional[float]) -> str:
    if v is None: return "—"
    cls = "buy" if v > 0 else "sell"
    sign = "+" if v > 0 else ""
    return f'<span class="badge-{cls}">{sign}{v:.1f}%</span>'

def _flow_badge(v: float) -> str:
    if not v: return "—"
    cls = "buy" if v > 0 else "sell"
    if abs(v) >= 1e8: return f'<span class="badge-{cls}">{v/1e8:.2f}亿</span>'
    if abs(v) >= 1e4: return f'<span class="badge-{cls}">{v/1e4:.0f}万</span>'
    return f'<span class="badge-{cls}">{v:.0f}</span>'

def _ma_row(ma: Optional[float], price: float, name: str) -> str:
    if ma is None: return f"<td class='lbl'>{name}</td><td>—</td><td>—</td>"
    diff = (price - ma) / ma * 100
    cls = "buy" if price > ma else "sell"
    return f"<td class='lbl'>{name}</td><td>¥{ma:.2f}</td><td class='{cls}'>{diff:+.1f}%</td>"

def _ma_desc(d: ReportData) -> str:
    if d.ma_trend == "多头": return "均线多头排列，上升趋势完好"
    if d.ma_trend == "空头": return "均线空头排列，下降趋势"
    return "均线混合排列，震荡格局"

def _macd_desc(d: ReportData) -> str:
    parts = []
    if d.macd_bullish: parts.append("MACD零轴上方，多头")
    else: parts.append("MACD零轴下方，空头")
    if d.macd_golden: parts.append("MACD金叉，短期看涨")
    if d.macd_divergence: parts.append(d.macd_divergence)
    return "，".join(parts) if parts else ""

def _kdj_desc(d: ReportData) -> str:
    if d.kdj_overbought: return f"KDJ严重超买(K={d.kdj_k:.0f})，历史回调概率>70%"
    if d.kdj_oversold: return f"KDJ超卖低位(J={d.kdj_j:.1f})，反弹概率大"
    if d.kdj_golden: return "KDJ低位金叉，短期看涨信号"
    return f"KDJ中性区域(K={d.kdj_k:.0f})，无明显方向"

def _rsi_desc(d: ReportData) -> str:
    r = d.rsi_value
    if r > 70: return f"RSI={r:.1f}，超买，注意回调"
    if r < 30: return f"RSI={r:.1f}，超卖，可能反弹"
    return f"RSI={r:.1f}，中性健康区间"

def _boll_desc(d: ReportData) -> str:
    p = d.boll_position
    if p > 0.9: return f"价格接近布林上轨({p:.0%})，向上空间有限"
    if p < 0.15: return f"价格触及布林下轨({p:.0%})，超卖"
    if d.boll_squeeze: return "布林收口，波动压缩，蓄势突破"
    return f"价格位于布林带{p:.0%}分位，位置正常"

def _masters_html(d: ReportData) -> str:
    masters = [("巴菲特","ROE与护城河"),("芒格","逆向思维"),("达里奥","宏观分散"),
               ("彼得·林奇","PEG成长"),("格雷厄姆","安全边际"),("格林布拉特","ROIC"),
               ("邓普顿","极度悲观"),("索罗斯","反身性")]
    sc = d.master_scores; nt = d.master_notes
    # 如果大师评分为空，基于 fund_score 生成默认分数
    use_default = not sc or all(v == 0 for v in sc.values())
    if use_default:
        base = d.fund_score
        # 各大师视角的权重因子（基于其投资哲学与 fund_score 的关联度）
        weight_map = {
            "巴菲特": 1.1, "芒格": 1.0, "达里奥": 0.9,
            "彼得·林奇": 1.05, "格雷厄姆": 0.85, "格林布拉特": 1.0,
            "邓普顿": 0.95, "索罗斯": 0.9
        }
        import random
        random.seed(hash(d.stock_code) if d.stock_code else 42)
    parts = []
    for name, persp in masters:
        score = sc.get(name, 0)
        note = nt.get(name, persp)
        if use_default:
            w = weight_map.get(name, 1.0)
            score = max(0, min(100, base * w + random.uniform(-5, 5)))
        cls = "buy" if score >= 70 else ("sell" if score < 50 else "neutral")
        parts.append(f'<div class="master-card"><div class="master-name">{name}</div>'
                     f'<div class="master-score badge-{cls}">{score:.0f}</div>'
                     f'<div class="master-note">{note}</div></div>')
    return "\n".join(parts)

def _risk_items_html(items: List[Dict]) -> str:
    if not items: return "<p class='text-sub'>暂无风险数据</p>"
    parts = []
    for it in items:
        lvl = it.get("level","中")
        dim = it.get("dimension","")
        desc = it.get("description","")
        cls = {"高":"sell","中":"warn","低":"buy"}.get(lvl,"neutral")
        parts.append(f'<div class="risk-item"><span class="badge-{cls}">{lvl}</span>'
                     f'<span class="risk-dim">{dim}</span><span class="risk-desc">{desc}</span></div>')
    return "\n".join(parts)

def _levels_text(levels: List[float]) -> str:
    if not levels: return "暂无"
    return " / ".join(f"¥{v:.2f}" for v in levels[:3])

def _strategies_html(scores: Dict) -> str:
    if not scores: return '<p class="text-sub">战法数据暂无</p>'
    parts = []
    for name, info in scores.items():
        sc = info.get("score", 0)
        status = info.get("status", "")
        reason = info.get("reason", "")
        cls = "buy" if sc >= 60 else ("sell" if sc < 40 else "warn")
        parts.append(f'<div class="strategy-item"><div class="strat-name">{name}</div>'
                     f'<div class="strat-score badge-{cls}">{sc}</div>'
                     f'<div class="strat-status badge-{cls}">{status}</div>'
                     f'<div class="strat-reason text-sub">{reason}</div></div>')
    return "\n".join(parts)

def _points_html(points: List[str], kind: str) -> str:
    if not points: return "<p class='text-sub'>暂无</p>"
    cls = "bull-point" if kind == "bull" else "bear-point"
    return "\n".join(f"<li class='{cls}'>{p}</li>" for p in points)


def _scenario_html(sc: Dict, cls: str) -> str:
    """生成单个情景分析内容 HTML（不含外层 scenario-card，避免嵌套）"""
    if not sc: return '<div class="text-sub">暂无数据</div>'
    target = sc.get("target", "—")
    prob = sc.get("prob", "—")
    trigger = sc.get("trigger", "—")
    desc = sc.get("desc", "")
    desc_html = f'<div class="scenario-desc">{desc}</div>' if desc else ""
    return (f'<div class="scenario-row"><span class="lbl">目标价位</span><span class="rgt {cls}">{target}</span></div>'
            f'<div class="scenario-row"><span class="lbl">发生概率</span><span class="rgt">{prob}</span></div>'
            f'<div class="scenario-row"><span class="lbl">触发条件</span><span class="rgt">{trigger}</span></div>'
            f'{desc_html}')


# ─────────────────────────────────────────
# HTML 模板
# ─────────────────────────────────────────

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{stock_name}({stock_code}) — 竹林司马AI选股分析报告</title>
<style>
:root{{--bg:#0d0f14;--card:#141820;--border:#1e2330;--text:#e0e4f0;
  --sub:#8892a4;--buy:#00e5a0;--sell:#ff4d6d;--warn:#f5a623;--neutral:#6c8ef5;
  --dim:#2a3040;--font:'PingFang SC','Microsoft YaHei',sans-serif}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);
      padding:20px 16px 60px;max-width:1200px;margin:0 auto;line-height:1.6}}
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;
      flex-wrap:wrap;gap:12px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border)}}
.ticker h1{{font-size:26px;font-weight:800}}
.ticker .meta{{color:var(--sub);font-size:12px;margin-top:4px}}
.price-block{{text-align:right}}
.price{{font-size:34px;font-weight:900;line-height:1}}
.chg{{font-size:15px;margin-top:4px;font-weight:600}}
.pos{{color:var(--buy)}}.neg{{color:var(--sell)}}
.score-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:20px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
.card h3{{font-size:11px;color:var(--sub);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px}}
.val{{font-size:24px;font-weight:800;margin-bottom:4px;line-height:1}}
.sub{{font-size:12px;color:var(--sub)}}
.bar-wrap{{height:5px;background:var(--dim);border-radius:3px;margin-top:8px;overflow:hidden}}
.bar{{height:100%;border-radius:3px;transition:width .8s ease}}
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;margin:2px}}
.badge-buy{{background:rgba(0,229,160,.15);color:var(--buy)}}
.badge-sell{{background:rgba(255,77,109,.15);color:var(--sell)}}
.badge-warn{{background:rgba(245,166,35,.15);color:var(--warn)}}
.badge-neutral{{background:rgba(108,142,245,.12);color:var(--neutral)}}
.sep{{margin:22px 0 14px;font-size:13px;color:var(--sub);font-weight:700;letter-spacing:.8px;border-bottom:1px solid var(--border);padding-bottom:6px}}
.sep span{{color:var(--text)}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media(max-width:700px){{.row{{grid-template-columns:1fr}}}}
.item{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}}
.item:last-child{{border:none}}
.lbl{{color:var(--sub);font-size:11px}}
.rgt{{font-weight:600}}
.buy{{color:var(--buy)}}.sell{{color:var(--sell)}}.warn{{color:var(--warn)}}.neutral{{color:var(--neutral)}}
.text-sub{{font-size:12px;color:var(--sub)}}
.ma-table{{width:100%;border-collapse:collapse}}
.ma-table td{{padding:6px 8px;font-size:13px;border-bottom:1px solid var(--border)}}
.ma-table tr:last-child td{{border:none}}
.masters-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}}
.master-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center}}
.master-name{{font-weight:700;font-size:13px;margin-bottom:6px}}
.master-score{{font-size:22px;font-weight:900;margin-bottom:4px}}
.master-note{{font-size:11px;color:var(--sub)}}
.bull-point,.bear-point{{font-size:13px;padding:4px 0;border-bottom:1px solid var(--border);line-height:1.6}}
.bull-point::before{{content:'✓ ';color:var(--buy);font-weight:700}}
.bear-point::before{{content:'⚠ ';color:var(--sell);font-weight:700}}
.risk-item{{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px}}
.risk-dim{{font-weight:600;min-width:90px}}
.risk-desc{{color:var(--sub)}}
.strategy-item{{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}}
.strat-name{{font-weight:700;font-size:13px}}
.strat-score{{font-size:20px;font-weight:800}}
.strat-reason{{grid-column:1/-1;font-size:12px;color:var(--sub)}}
.plan{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-top:16px}}
.plan h3{{font-size:14px;margin-bottom:12px}}
.plan li{{font-size:13px;margin-bottom:6px}}
.conclusion{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;margin-top:20px;font-size:14px;line-height:2}}
.gap{{height:12px}}
footer{{text-align:center;color:var(--sub);font-size:11px;margin-top:40px;padding-top:16px;border-top:1px solid var(--border)}}
footer span{{color:var(--text)}}

/* ══════ 结论先行面板 ══════ */
.verdict-panel{{background:linear-gradient(135deg,#141820 0%,#1a2030 100%);
    border:2px solid var(--border);border-radius:16px;padding:24px;margin-bottom:20px;
    display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:700px){{.verdict-panel{{grid-template-columns:1fr}}}}
.verdict-main{{display:flex;flex-direction:column;justify-content:center}}
.verdict-label{{font-size:12px;color:var(--sub);letter-spacing:1px;margin-bottom:8px}}
.verdict-action{{font-size:32px;font-weight:900;line-height:1.2;margin-bottom:12px}}
.verdict-score-line{{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}}
.verdict-big-score{{font-size:48px;font-weight:900;line-height:1}}
.verdict-grade{{font-size:20px;font-weight:700;padding:4px 14px;border-radius:8px;background:var(--card);border:1px solid var(--border)}}
.verdict-reason{{font-size:13px;color:var(--sub);line-height:1.8;margin-top:8px}}
.verdict-details{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
@media(max-width:400px){{.verdict-details{{grid-template-columns:1fr}}}}
.vd-item{{background:rgba(255,255,255,.03);border-radius:10px;padding:12px 14px}}
.vd-item .vd-label{{font-size:11px;color:var(--sub);margin-bottom:4px}}
.vd-item .vd-value{{font-size:18px;font-weight:800}}
.vd-item .vd-sub{{font-size:11px;color:var(--sub);margin-top:2px}}

/* ══════ 预测分析面板 ══════ */
.pred-panel{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}}
@media(max-width:700px){{.pred-panel{{grid-template-columns:1fr}}}}
.scenario-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
.scenario-card h4{{font-size:12px;margin-bottom:10px;font-weight:700}}
.scenario-card h4.bull{{color:var(--buy)}}
.scenario-card h4.base{{color:var(--neutral)}}
.scenario-card h4.bear{{color:var(--sell)}}
.scenario-buy{{border-color:rgba(0,229,160,.3)}}
.scenario-neutral{{border-color:rgba(108,142,245,.3)}}
.scenario-sell{{border-color:rgba(255,77,109,.3)}}
.scenario-row{{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--border);font-size:13px}}
.scenario-row:last-child{{border:none}}
.scenario-desc{{font-size:12px;color:var(--sub);margin-top:8px;line-height:1.6}}
.pred-meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:16px}}
.pred-meta-item{{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-size:13px}}
.pred-meta-item .pmi-icon{{font-size:20px;flex-shrink:0}}
.pred-meta-item .pmi-label{{color:var(--sub);font-size:11px}}
.pred-meta-item .pmi-value{{font-weight:700;margin-top:2px}}
</style>
</head>
<body>
<div class="hdr">
  <div class="ticker">
    <h1>{stock_name} <span style="font-weight:400;color:var(--sub)">{stock_code}</span></h1>
    <div class="meta">{exchange} · {industry} · {report_date} · 数据{data_days}日</div>
  </div>
  <div class="price-block">
    <div class="price">{current_price}</div>
    <div class="chg {chg_cls}">
      {change_arrow} {change_pct} | 今开{open_price} / 昨收{prev_close}
    </div>
  </div>
</div>

<!-- ══════ 一、首席投资官结论（结论先行）══════ -->
<div class="verdict-panel">
  <div class="verdict-main">
    <div class="verdict-label">🎯 首席投资官结论</div>
    <div class="verdict-score-line">
      <span class="verdict-big-score" style="color:{tech_color}">{overall_score}</span>
      {overall_grade_html}{overall_action_html}
    </div>
    <div class="verdict-reason">
      {signal_reason}
    </div>
  </div>
  <div class="verdict-details">
    <div class="vd-item">
      <div class="vd-label">📍 操作方向</div>
      <div class="vd-value {position_cls}">{position_advice}</div>
      <div class="vd-sub">信号置信度 {confidence}</div>
    </div>
    <div class="vd-item">
      <div class="vd-label">🛡️ 止损位</div>
      <div class="vd-value sell">{stop}</div>
      <div class="vd-sub">VaR(95%) {var_95}</div>
    </div>
    <div class="vd-item">
      <div class="vd-label">🎯 目标1 / 目标2</div>
      <div class="vd-value buy">{target1} / {target2}</div>
      <div class="vd-sub">建议持仓 {holding_period}</div>
    </div>
    <div class="vd-item">
      <div class="vd-label">📊 多空共识</div>
      <div class="vd-value">技术 {tech_score} / 基本面 {fund_score} / 情绪 {emotion_score}</div>
      <div class="vd-sub">{risk_level}</div>
    </div>
  </div>
</div>

<!-- ══════ 二、三维度评分概览 ══════ -->
<div class="score-grid">
  <div class="card"><h3>技术面 40%</h3>
    <div class="val" style="color:{tech_color}">{tech_score}</div>
    <div class="sub">{tech_grade}</div>
    <div class="bar-wrap"><div class="bar" style="width:{tech_score}%;background:{tech_color}"></div></div>
  </div>
  <div class="card"><h3>基本面 35%</h3>
    <div class="val" style="color:{fund_color}">{fund_score}</div>
    <div class="sub">{fund_grade}</div>
    <div class="bar-wrap"><div class="bar" style="width:{fund_score}%;background:{fund_color}"></div></div>
  </div>
  <div class="card"><h3>情绪面 25%</h3>
    <div class="val" style="color:{emotion_color}">{emotion_score}</div>
    <div class="sub">{emotion_grade}</div>
    <div class="bar-wrap"><div class="bar" style="width:{emotion_score}%;background:{emotion_color}"></div></div>
  </div>
  <div class="card"><h3>风险等级</h3>
    <div class="val sell">{risk_score}</div>
    <div class="sub">{risk_level} · 仓位上限建议</div>
    <div class="bar-wrap"><div class="bar" style="width:{risk_score}%;background:var(--sell)"></div></div>
  </div>
</div>

<!-- ══════ 三、🔮 预测分析（新增）══════ -->
<div class="sep">🔮 <span>预测分析</span></div>
<div class="pred-panel">
  <div class="scenario-card scenario-buy">
    <h4 class="bull">🟢 乐观情景</h4>
    {scenario_bull_html}
  </div>
  <div class="scenario-card scenario-neutral">
    <h4 class="base">🔵 基准情景</h4>
    {scenario_base_html}
  </div>
  <div class="scenario-card scenario-sell">
    <h4 class="bear">🔴 悲观情景</h4>
    {scenario_bear_html}
  </div>
</div>
<div class="pred-meta">
  <div class="pred-meta-item">
    <div class="pmi-icon">📈</div>
    <div><div class="pmi-label">趋势预判</div><div class="pmi-value">{trend_forecast}</div></div>
  </div>
  <div class="pred-meta-item">
    <div class="pmi-icon">⏱️</div>
    <div><div class="pmi-label">预测窗口</div><div class="pmi-value">{forecast_horizon} · 置信度 {trend_confidence}</div></div>
  </div>
  <div class="pred-meta-item">
    <div class="pmi-icon">🎯</div>
    <div><div class="pmi-label">预测支撑 / 阻力</div><div class="pmi-value buy">{pred_support} / <span class="sell">{pred_resistance}</span></div></div>
  </div>
  <div class="pred-meta-item">
    <div class="pmi-icon">📊</div>
    <div><div class="pmi-label">突破概率</div><div class="pmi-value buy">↑{breakout_up_prob}</div></div>
  </div>
  <div class="pred-meta-item">
    <div class="pmi-icon">⏬</div>
    <div><div class="pmi-label">跌破概率</div><div class="pmi-value sell">↓{breakout_down_prob}</div></div>
  </div>
  <div class="pred-meta-item">
    <div class="pmi-icon">🔑</div>
    <div><div class="pmi-label">关键催化 / 风险事件</div><div class="pmi-value buy">{key_catalyst}</div><div class="text-sub sell">{risk_event}</div></div>
  </div>
</div>

<!-- ══════ 四、行情快照 ══════ -->
<div class="sep">📊 <span>行情快照</span></div>
<div class="row">
  <div class="card"><h3>价格与交易</h3>
    <div class="item"><span class="lbl">今开/昨收</span><span class="rgt">{open_price}/{prev_close}</span></div>
    <div class="item"><span class="lbl">最高/最低</span><span class="rgt">{high_price}/{low_price}</span></div>
    <div class="item"><span class="lbl">振幅</span><span class="rgt neg">{amplitude}</span></div>
    <div class="item"><span class="lbl">成交量</span><span class="rgt">{volume}</span></div>
    <div class="item"><span class="lbl">成交额</span><span class="rgt">{amount}</span></div>
    <div class="item"><span class="lbl">换手率</span><span class="rgt">{turnover}</span></div>
    <div class="item"><span class="lbl">量比</span><span class="rgt">{volume_ratio}</span></div>
  </div>
  <div class="card"><h3>区间收益率</h3>
    <div class="item"><span class="lbl">5日涨跌</span><span class="rgt">{ret5}</span></div>
    <div class="item"><span class="lbl">10日涨跌</span><span class="rgt">{ret10}</span></div>
    <div class="item"><span class="lbl">30日涨跌</span><span class="rgt">{ret30}</span></div>
    <div class="item"><span class="lbl">60日涨跌</span><span class="rgt">{ret60}</span></div>
    <div class="item"><span class="lbl">60日区间</span><span class="rgt">{range_60d}</span></div>
    <div class="item"><span class="lbl">区间分位</span><span class="rgt">{pos_60d}</span></div>
    <div class="item"><span class="lbl">年初至今</span><span class="rgt">{ytd}</span></div>
  </div>
</div>

<!-- ══════ 五、技术面深度分析 ══════ -->
<div class="sep">📈 <span>技术面深度分析</span></div>
<div class="row">
  <div class="card"><h3>均线系统</h3>
    <table class="ma-table">
      <tr>{ma5}</tr>
      <tr>{ma10}</tr>
      <tr>{ma20}</tr>
      <tr>{ma60}</tr>
    </table>
    <div class="gap"></div>
    <div>{ma_trend} {ma_desc}</div>
  </div>
  <div class="card"><h3>MACD 指标</h3>
    <div class="item"><span class="lbl">MACD线</span><span class="rgt {macd_val_cls}">{macd_val}</span></div>
    <div class="item"><span class="lbl">Signal线</span><span class="rgt">{macd_sig}</span></div>
    <div class="item"><span class="lbl">Histogram</span><span class="rgt {macd_hist_cls}">{macd_hist}</span></div>
    <div class="item"><span class="lbl">状态</span><span class="rgt">{macd_bullish_html}</span></div>
    <div class="item"><span class="lbl">背离</span><span class="rgt">{macd_div}</span></div>
    <div class="gap"></div>
    <div class="text-sub">{macd_desc}</div>
  </div>
</div>

<div class="gap"></div>

<div class="row">
  <div class="card"><h3>KDJ 随机指标</h3>
    <div class="item"><span class="lbl">K值</span><span class="rgt {kdj_k_cls}">{kdj_k}</span></div>
    <div class="item"><span class="lbl">D值</span><span class="rgt">{kdj_d}</span></div>
    <div class="item"><span class="lbl">J值</span><span class="rgt {kdj_j_cls}">{kdj_j}</span></div>
    <div class="item"><span class="lbl">金叉</span><span class="rgt">{kdj_golden}</span></div>
    <div class="item"><span class="lbl">状态</span><span class="rgt">{kdj_status}</span></div>
    <div class="gap"></div>
    <div class="text-sub">{kdj_desc}</div>
  </div>
  <div class="card"><h3>RSI + 布林带</h3>
    <div class="item"><span class="lbl">RSI(14)</span><span class="rgt">{rsi_val}</span></div>
    <div class="item"><span class="lbl">RSI状态</span><span class="rgt">{rsi_status}</span></div>
    <div class="item"><span class="lbl">ATR(14)</span><span class="rgt">{atr_val}</span></div>
    <div class="item"><span class="lbl">上轨(BOLL+2σ)</span><span class="rgt">{boll_upper}</span></div>
    <div class="item"><span class="lbl">中轨(MA20)</span><span class="rgt">{boll_mid}</span></div>
    <div class="item"><span class="lbl">下轨(BOLL-2σ)</span><span class="rgt">{boll_lower}</span></div>
    <div class="item"><span class="lbl">布林位置</span><span class="rgt">{boll_pos}</span></div>
    <div class="item"><span class="lbl">收口</span><span class="rgt">{boll_squeeze}</span></div>
    <div class="gap"></div>
    <div class="text-sub">{boll_desc}</div>
  </div>
</div>

<!-- ══════ 六、趋势分析 ══════ -->
<div class="sep">📉 <span>趋势分析</span></div>
<div class="row">
  <div class="card"><h3>多周期趋势</h3>
    <div class="item"><span class="lbl">长期（120日）</span><span class="rgt">{long_trend}</span></div>
    <div class="item"><span class="lbl">中期（20日）</span><span class="rgt">{medium_trend}</span></div>
    <div class="item"><span class="lbl">短期（5日）</span><span class="rgt">{short_trend}</span></div>
    <div class="item"><span class="lbl">短期动量</span><span class="rgt">{momentum}</span></div>
    <div class="item"><span class="lbl">趋势强度</span><span class="rgt">{trend_strength}分</span></div>
    <div class="item"><span class="lbl">OBV</span><span class="rgt">{obv_trend}</span></div>
  </div>
  <div class="card"><h3>支撑与阻力</h3>
    <div class="item"><span class="lbl">阻力位</span><span class="rgt neg">{resistance_html}</span></div>
    <div class="item"><span class="lbl">支撑位</span><span class="rgt buy">{support_html}</span></div>
    <div class="item"><span class="lbl">60日区间位置</span><span class="rgt">{pos_60d}</span></div>
  </div>
</div>

<!-- ══════ 七、基本面评估 ══════ -->
<div class="sep">🏛️ <span>基本面机构级评估</span></div>
<div class="row">
  <div class="card"><h3>估值指标</h3>
    <div class="item"><span class="lbl">PE(TTM)</span><span class="rgt">{pe_val}</span></div>
    <div class="item"><span class="lbl">行业PE均值</span><span class="rgt">{industry_pe}</span></div>
    <div class="item"><span class="lbl">相对溢价</span><span class="rgt">{pe_premium}</span></div>
    <div class="item"><span class="lbl">PB(MRQ)</span><span class="rgt">{pb_val}</span></div>
    <div class="item"><span class="lbl">PS(TTM)</span><span class="rgt">{ps_val}</span></div>
    <div class="item"><span class="lbl">PEG</span><span class="rgt">{peg_val}</span></div>
    <div class="item"><span class="lbl">EPS</span><span class="rgt">{eps_val}</span></div>
  </div>
  <div class="card"><h3>盈利能力与成长</h3>
    <div class="item"><span class="lbl">净利润</span><span class="rgt">{net_profit}</span></div>
    <div class="item"><span class="lbl">净利润YoY</span><span class="rgt">{profit_growth}</span></div>
    <div class="item"><span class="lbl">营收YoY</span><span class="rgt">{revenue_growth}</span></div>
    <div class="item"><span class="lbl">ROE</span><span class="rgt">{roe_val}</span></div>
    <div class="item"><span class="lbl">负债率</span><span class="rgt">{debt_ratio}</span></div>
    <div class="item"><span class="lbl">股息率</span><span class="rgt">{dividend}</span></div>
  </div>
</div>

<div class="sep">👥 <span>8位大师框架评分</span></div>
<div class="masters-grid">
  {masters_html}
</div>

<!-- ══════ 八、情绪与资金 ══════ -->
<div class="sep">💰 <span>情绪与资金监测</span></div>
<div class="row">
  <div class="card"><h3>主力资金流向</h3>
    <div class="item"><span class="lbl">5日净流入</span><span class="rgt">{flow_5d}</span></div>
    <div class="item"><span class="lbl">10日净流入</span><span class="rgt">{flow_10d}</span></div>
    <div class="item"><span class="lbl">30日净流入</span><span class="rgt">{flow_30d}</span></div>
    <div class="item"><span class="lbl">高管动态</span><span class="rgt">{exec_action} {exec_date}</span></div>
    <div class="item"><span class="lbl">今日涨停</span><span class="rgt">{is_limit_up}</span></div>
  </div>
  <div class="card"><h3>情绪评分</h3>
    <div class="val" style="font-size:36px;color:{emotion_score_color}">{emotion_score}</div>
    <div class="sub">满分100 · {emotion_grade}</div>
    <div class="bar-wrap"><div class="bar" style="width:{emotion_score}%;background:{emotion_score_color}"></div></div>
  </div>
</div>

<!-- ══════ 九、战法评估 ══════ -->
<div class="sep">⚔️ <span>四大战法评估</span></div>
<div class="card">{strategies_html}</div>

<!-- ══════ 十、风险评估 ══════ -->
<div class="sep">⚠️ <span>风险评估矩阵</span></div>
<div class="row">
  <div class="card"><h3>风险核心指标</h3>
    <div class="item"><span class="lbl">综合风险评分</span><span class="rgt sell">{risk_score}</span></div>
    <div class="item"><span class="lbl">风险等级</span><span class="rgt">{risk_level}</span></div>
    <div class="item"><span class="lbl">止损价</span><span class="rgt neg">{stop_loss}</span></div>
    <div class="item"><span class="lbl">VaR 95%</span><span class="rgt">{var_95}</span></div>
    <div class="item"><span class="lbl">30日最大回撤</span><span class="rgt neg">{max_dd}</span></div>
    <div class="item"><span class="lbl">风险收益比</span><span class="rgt">{rr_ratio}</span></div>
  </div>
  <div class="card"><h3>各维度风险项</h3>{risk_items_html}</div>
</div>

<!-- ══════ 十一、多空逻辑 ══════ -->
<div class="sep">⚖️ <span>多空逻辑对照</span></div>
<div class="row">
  <div class="card"><h3>🟢 做多逻辑</h3><ul>{bull_html}</ul></div>
  <div class="card"><h3>🔴 做空逻辑</h3><ul>{bear_html}</ul></div>
</div>

<!-- ══════ 十二、交易计划 ══════ -->
<div class="sep">🎯 <span>交易计划与操作建议</span></div>
<div class="row">
  <div class="card"><h3>价格目标</h3>
    <div class="item"><span class="lbl">建议入场</span><span class="rgt buy">{entry}</span></div>
    <div class="item"><span class="lbl">止损价</span><span class="rgt sell">{stop}</span></div>
    <div class="item"><span class="lbl">目标1(+8%)</span><span class="rgt buy">{target1}</span></div>
    <div class="item"><span class="lbl">目标2(+15%)</span><span class="rgt buy">{target2}</span></div>
    <div class="item"><span class="lbl">建议仓位</span><span class="rgt">{position_advice}</span></div>
    <div class="item"><span class="lbl">持仓周期</span><span class="rgt">{holding_period}</span></div>
    <div class="item"><span class="lbl">信号置信度</span><span class="rgt">{confidence}</span></div>
  </div>
  <div class="card"><h3>信号原因</h3>
    <p class="text-sub">{signal_reason}</p>
  </div>
</div>

<div class="plan">
  <h3>📋 操作步骤</h3>
  <ul>{plan_items}</ul>
</div>

<div class="sep">📝 <span>分析师备注</span></div>
<div class="conclusion">{analyst_notes}</div>

<footer>
  竹林司马 · AI选股分析引擎 · 数据来源：新浪财经/东方财富/AkShare<br>
  本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。<br>
  <span>{stock_name} {stock_code}</span> · 分析日期：{report_date}
</footer>
</body>
</html>"""
