#!/usr/bin/env python3
"""
选股战法 API 路由（完整版）
竹林司马 · 竹林司马AI选股分析引擎

提供：战法分析、实时行情、技术指标、AI评分、趋势分析、风险评估、HTML报告生成
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import sys, os, logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.stock.data.fetcher import StockFetcher, get_fetcher
from src.stock.indicators.wrapper import IndicatorWrapper
from src.stock.strategies.base import StrategyEngine
from src.stock.strategies.lock_position import LockPositionStrategy
from src.stock.strategies.auction_reversal import AuctionReversalStrategy
from src.stock.strategies.blade_out import BladeOutStrategy
from src.stock.strategies.limit_up import LimitUpStrategy

# 核心分析模块
from src.core.indicators.technical_indicators import TechnicalIndicators
from src.core.analysis.risk_analyzer import RiskAnalyzer
from src.core.analysis.trend_analyzer import TrendAnalyzer
from src.core.ai.score_engine import AIScoreEngine

# 报告生成器
from src.stock.report.generator import StockReportGenerator, ReportData

logger = logging.getLogger(__name__)
router = APIRouter(tags=["选股战法"])

# 模块级单例
_engine = _fetcher = _indicator = _ti = _trend = _risk = _ai = None


def get_engine(): global _engine
def get_fetcher_s(): global _fetcher
def get_indicator_w(): global _indicator
def get_ti_s(): global _ti
def get_trend_s(): global _trend
def get_risk_s(): global _risk
def get_ai_s(): global _ai


# ─────────────────────────────────────────────
# 请求/响应模型
# ─────────────────────────────────────────────

class StockAnalyzeRequest(BaseModel):
    stock_code: str
    stock_name: str = ""
    fundamentals: Optional[Dict[str, Any]] = None
    market_data: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────
# 端点1：全链路分析（核心）
# POST /api/v1/stock/analyze
# ─────────────────────────────────────────────

@router.post("/analyze", summary="全链路股票分析")
async def analyze_stock(req: StockAnalyzeRequest):
    """全链路分析：技术指标 → 风险 → 趋势 → AI评分 → HTML报告"""
    global _engine, _fetcher, _indicator, _ti, _trend, _risk, _ai
    try:
        code = req.stock_code.strip()
        name = req.stock_name.strip() or code

        # 1. 数据获取
        if _fetcher is None: _fetcher = get_fetcher()
        df = _fetcher.get_daily(code, adjust="qfq")
        if len(df) < 60:
            raise HTTPException(400, f"数据不足，需要60日，当前{len(df)}日")
        realtime = {}
        try: realtime = _fetcher.get_realtime(code)
        except: pass

        # 2. 技术指标
        if _ti is None: _ti = TechnicalIndicators()
        bundle = _ti.compute_all(df)

        # 3. 趋势
        if _trend is None: _trend = TrendAnalyzer()
        trend_report = _trend.analyze(df, bundle)

        # 4. 风险
        if _risk is None: _risk = RiskAnalyzer()
        risk_report = _risk.analyze(bundle, req.fundamentals, req.market_data)

        # 5. AI评分
        if _ai is None: _ai = AIScoreEngine()
        ai_rec = _ai.score(code, name, bundle, req.fundamentals,
                            risk_report, trend_report, req.market_data)

        # 6. 填充 ReportData
        data = ReportData()
        data.from_indicators_bundle(name, code, bundle)
        data.from_risk_report(risk_report)
        data.from_trend_report(trend_report)
        data.from_ai_recommendation(ai_rec)
        if req.fundamentals: data.from_fundamentals(req.fundamentals)
        if req.market_data: data.from_market_data(req.market_data)
        data.data_days = len(df)
        data.calc_overall()

        # 7. 生成HTML报告
        gen = StockReportGenerator()
        html = gen.generate(data)
        reports_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        fname = f"{code}_{name}.html"
        report_path = gen.save(html, os.path.join(reports_dir, fname))

        return {
            "code": 200, "message": "success",
            "stock_code": code, "stock_name": name,
            "overall_score": ai_rec.overall_score,
            "overall_grade": ai_rec.overall_grade,
            "overall_action": ai_rec.overall_action,
            "tech_score": bundle.tech_score,
            "tech_grade": bundle.tech_grade,
            "fund_score": ai_rec.fund_score.score,
            "emotion_score": ai_rec.emotion_score.score,
            "signal": {
                "action": ai_rec.signal.action,
                "confidence": ai_rec.signal.confidence,
                "reason": ai_rec.signal.reason,
            },
            "entry_price": ai_rec.entry_price,
            "stop_loss": ai_rec.stop_loss,
            "target_1": ai_rec.target_price_1,
            "target_2": ai_rec.target_price_2,
            "position_advice": ai_rec.position_advice,
            "risk_level": risk_report.overall_risk_level,
            "risk_score": risk_report.overall_risk_score,
            "stop_loss_risk": risk_report.stop_loss_price,
            "bull_points": ai_rec.bull_points,
            "bear_points": ai_rec.bear_points,
            "action_plan": ai_rec.action_plan,
            "analyst_notes": ai_rec.analyst_notes,
            "trend": {
                "long_trend": trend_report.long_trend,
                "medium_trend": trend_report.medium_trend,
                "short_trend": trend_report.short_trend,
                "trend_strength": trend_report.trend_strength,
                "momentum": trend_report.momentum,
                "support_levels": trend_report.support_levels,
                "resistance_levels": trend_report.resistance_levels,
            },
            "tech_indicators": {
                "ma5": bundle.ma.ma5, "ma10": bundle.ma.ma10,
                "ma20": bundle.ma.ma20, "ma60": bundle.ma.ma60,
                "ma_trend": bundle.ma.trend,
                "macd": bundle.macd.macd,
                "macd_signal": bundle.macd.signal,
                "macd_histogram": bundle.macd.histogram,
                "macd_bullish": bundle.macd.bullish,
                "macd_divergence": bundle.macd.divergence,
                "kdj_k": bundle.kdj.k,
                "kdj_d": bundle.kdj.d,
                "kdj_j": bundle.kdj.j,
                "kdj_status": bundle.kdj.status,
                "rsi": bundle.rsi.rsi,
                "boll_upper": bundle.bollinger.upper,
                "boll_middle": bundle.bollinger.middle,
                "boll_lower": bundle.bollinger.lower,
                "boll_position": bundle.bollinger.position,
                "atr": bundle.atr,
            },
            "report_path": report_path,
            "report_url": f"/reports/{fname}",
            "data_days": len(df),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"全链路分析失败: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────
# 端点2：轻量指标接口
# GET /api/v1/stock/indicators/{code}
# ─────────────────────────────────────────────

@router.get("/indicators/{stock_code}", summary="技术指标")
async def get_indicators(stock_code: str):
    """仅返回技术指标，不生成报告"""
    global _fetcher, _ti
    try:
        if _fetcher is None: _fetcher = get_fetcher()
        df = _fetcher.get_daily(stock_code, adjust="qfq")
        if len(df) < 60:
            raise HTTPException(400, f"数据不足，当前{len(df)}日")
        if _ti is None: _ti = TechnicalIndicators()
        b = _ti.compute_all(df)
        return {
            "code": 200, "stock_code": stock_code,
            "current_price": b.current_price, "change_pct": b.change_pct,
            "tech_score": b.tech_score, "tech_grade": b.tech_grade,
            "ma": {"ma5": b.ma.ma5, "ma10": b.ma.ma10, "ma20": b.ma.ma20,
                   "ma60": b.ma.ma60, "trend": b.ma.trend, "golden_fan": b.ma.golden_fan},
            "macd": {"macd": b.macd.macd, "signal": b.macd.signal,
                      "histogram": b.macd.histogram, "bullish": b.macd.bullish,
                      "golden_cross": b.macd.golden_cross,
                      "death_cross": b.macd.death_cross,
                      "divergence": b.macd.divergence},
            "kdj": {"k": b.kdj.k, "d": b.kdj.d, "j": b.kdj.j,
                     "status": b.kdj.status, "overbought": b.kdj.overbought,
                     "oversold": b.kdj.oversold},
            "rsi": {"value": b.rsi.rsi, "status": b.rsi.status},
            "bollinger": {"upper": b.bollinger.upper, "middle": b.bollinger.middle,
                           "lower": b.bollinger.lower, "position": b.bollinger.position,
                           "squeeze": b.bollinger.squeeze},
            "atr": b.atr, "data_days": len(df),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"技术指标失败: {e}")
        raise HTTPException(500, str(e))


# ─────────────────────────────────────────────
# 端点3：健康检查
# GET /api/v1/stock/health
# ─────────────────────────────────────────────

@router.get("/health", summary="模块健康检查")
async def stock_health():
    global _fetcher, _ti, _trend, _risk, _ai
    components = {}
    try:
        if _fetcher is None: _fetcher = get_fetcher()
        components["data_fetcher"] = {"status": "ok", "source": "akshare"}
    except Exception as e:
        components["data_fetcher"] = {"status": "error", "detail": str(e)}
    try:
        if _ti is None: _ti = TechnicalIndicators()
        components["technical_indicators"] = {"status": "ok"}
    except Exception as e:
        components["technical_indicators"] = {"status": "error", "detail": str(e)}
    try:
        if _risk is None: _risk = RiskAnalyzer()
        components["risk_analyzer"] = {"status": "ok"}
    except Exception as e:
        components["risk_analyzer"] = {"status": "error", "detail": str(e)}
    try:
        if _trend is None: _trend = TrendAnalyzer()
        components["trend_analyzer"] = {"status": "ok"}
    except Exception as e:
        components["trend_analyzer"] = {"status": "error", "detail": str(e)}
    try:
        if _ai is None: _ai = AIScoreEngine()
        components["ai_score_engine"] = {"status": "ok"}
    except Exception as e:
        components["ai_score_engine"] = {"status": "error", "detail": str(e)}
    try:
        StockReportGenerator()
        components["report_generator"] = {"status": "ok"}
    except Exception as e:
        components["report_generator"] = {"status": "error", "detail": str(e)}

    all_ok = all(c["status"] == "ok" for c in components.values())
    return {"code": 200 if all_ok else 503,
            "message": "healthy" if all_ok else "degraded",
            "components": components}
