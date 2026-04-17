#!/usr/bin/env python3
"""
验证新报告模板 — 结论先行 + 预测分析
使用国电南瑞(600406)真实数据
"""
import sys, os, json, subprocess
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from datetime import datetime
from src.core.indicators.technical_indicators import TechnicalIndicators
from src.core.analysis.risk_analyzer import RiskAnalyzer
from src.core.analysis.trend_analyzer import TrendAnalyzer
from src.core.ai.score_engine import AIScoreEngine
from src.stock.report.generator import StockReportGenerator, ReportData

# ─── 数据获取（腾讯财经）──────────────────
def fetch_kline(symbol, count=120):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?_var=kline_dayqfq&param={symbol},day,,,{count},qfq")
    out = subprocess.check_output(["curl", "-s", "--noproxy", "*", url]).decode("utf-8", errors="replace")
    text = out.strip()
    if text.startswith("kline_dayqfq="):
        text = text[len("kline_dayqfq="):]
    data = json.loads(text)
    klines = data["data"][symbol].get("qfqday") or data["data"][symbol].get("day", [])
    rows = []
    for k in klines:
        date, open_, close, high, low, vol = k
        rows.append({"date": date, "open": float(open_), "high": float(high),
                     "low": float(low), "close": float(close), "volume": float(vol)})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_realtime(symbol):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?_var=kline_dayqfq&param={symbol},day,,,1,qfq")
    out = subprocess.check_output(["curl", "-s", "--noproxy", "*", url]).decode("utf-8", errors="replace")
    text = out.strip()
    if text.startswith("kline_dayqfq="):
        text = text[len("kline_dayqfq="):]
    data = json.loads(text)
    qt = data["data"][symbol].get("qt", {})
    info = qt.get(symbol, qt.get(list(qt.keys())[0], []))
    if not info:
        raise ValueError(f"无行情数据: {symbol}")
    name = info[1]
    current = float(info[3]) if info[3] else 0
    prev = float(info[4]) if info[4] else 0
    open_ = float(info[5]) if info[5] else 0
    high = float(info[6]) if info[6] else 0
    low = float(info[7]) if info[7] else 0
    vol = float(info[32]) * 100 if info[32] else 0
    amount = float(info[33]) if info[33] else 0
    chg = current - prev
    chg_pct = (chg / prev * 100) if prev else 0
    amplitude = ((high - low) / prev * 100) if prev else 0
    return {
        "name": name, "open": open_, "prev_close": prev,
        "current": current, "high": high, "low": low,
        "chg": chg, "chg_pct": chg_pct,
        "volume": vol, "amount": amount, "amplitude": amplitude,
    }


# ─── 主流程 ───────────────────────────────
print("=" * 60)
print("竹林司马 v2 · 新模板验证 — 国电南瑞(600406)")
print("=" * 60)

# 1. 获取数据
print("\n[1/5] 获取行情数据...")
df = fetch_kline("sh600406", count=120)
snapshot = fetch_realtime("sh600406")
price = snapshot["current"]
print(f"  K线: {len(df)}条  实时: ¥{price}  涨跌: {snapshot['chg_pct']:+.2f}%")

# 2. 技术指标
print("\n[2/5] 计算技术指标...")
ti = TechnicalIndicators()
bundle = ti.compute_all(df)

# 3. 风险分析
print("[3/5] 风险分析...")
ra = RiskAnalyzer()
risk = ra.analyze(bundle)

# 4. 趋势分析
print("[4/5] 趋势分析...")
ta = TrendAnalyzer()
trend = ta.analyze(df, bundle)

# 5. AI评分 + 生成报告
print("[5/5] AI综合评分 + 生成新模板报告...")
engine = AIScoreEngine()
fundamentals = {
    "pe": 28.5, "pb": 3.8, "ps": 3.1, "roe": 14.2,
    "profit_growth_yoy": 12.5, "revenue_growth_yoy": 10.8,
    "debt_ratio": 45.0, "net_margin": 13.5, "gross_margin": 27.0,
    "dividend_yield": 1.8,
}
market_data = {
    "news_count_5d": 6, "news_sentiment": 0.52,
    "institutional_coverage": 25, "main_net_flow_5d": 1.8,
}
rec = engine.score(
    "600406", "国电南瑞", bundle,
    fundamentals=fundamentals, risk_report=risk,
    trend_report=trend, market_data=market_data,
)
print(f"  综合评分: {rec.overall_score:.0f}/100  [{rec.overall_grade}]  {rec.overall_action}")

# ─── 构建报告数据 ─────────────────────────
gen = StockReportGenerator()
data = ReportData()
data.from_indicators_bundle("国电南瑞", "600406", bundle)
data.from_risk_report(risk)
data.from_trend_report(trend)
data.from_fundamentals(fundamentals)
data.from_market_data(market_data)
data.from_ai_recommendation(rec)
data.report_date = datetime.now().strftime("%Y-%m-%d")
data.exchange = "SH"
data.industry = "电力设备·电网自动化"
data.data_days = len(df)

# ══════ 预测分析数据填充（规则引擎兜底 + 模拟数据）══════
data.prediction_enabled = True
data.trend_forecast = "短期震荡偏弱，关注MA20支撑25.80。主力资金持续流出抑制反弹空间，需等缩量企稳信号。"
data.trend_confidence = "中"
data.forecast_horizon = "3-5个交易日"

# 乐观情景
data.scenario_bull = {
    "target": "¥28.50 (+7.3%)",
    "prob": "25%",
    "trigger": "主力资金回流 + 站稳MA20",
    "desc": "若北向资金加仓且板块政策利好，有望挑战前高。量能需回到日均80万手以上。",
}
# 基准情景
data.scenario_base = {
    "target": "¥26.30 (-0.9%)",
    "prob": "50%",
    "trigger": "维持当前格局",
    "desc": "继续围绕MA20震荡整理，等待方向选择。缩量横盘，等待催化剂。",
}
# 悲观情景
data.scenario_bear = {
    "target": "¥24.50 (-7.7%)",
    "prob": "25%",
    "trigger": "跌破MA60支撑26.13",
    "desc": "若大盘系统性回调或主力加速出逃，可能回踩布林下轨。止损位25.80需严守。",
}

data.predicted_support = 25.80
data.predicted_resistance = 27.80
data.breakout_up_prob = 25.0
data.breakout_down_prob = 30.0
data.best_entry_window = "回调至25.80-26.00区间缩量企稳时"
data.key_catalyst = "电网投资政策加码 / 一季报超预期 / 北向资金加仓"
data.risk_event = "大盘系统性回调风险 / 主力资金持续流出"

# ─── 生成并保存 ───────────────────────────
html = gen.generate(data)
report_path = os.path.join(_project_root, "docs", "gdnh_600406_report_v2.html")
gen.save(html, report_path)
print(f"\n  ✅ 新模板报告已保存: {report_path}")
print(f"\n{'=' * 60}")
print(f"新模板结构:")
print(f"  1. 🎯 首席投资官结论面板（结论先行）")
print(f"  2. 📊 三维度评分卡片")
print(f"  3. 🔮 预测分析（三情景 + 趋势预判 + 催化因素）")
print(f"  4-12. 详细数据（行情/技术/趋势/基本面/情绪/战法/风险/多空/交易）")
print(f"{'=' * 60}")
