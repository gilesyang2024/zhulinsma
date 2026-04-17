#!/usr/bin/env python3
"""
国电南瑞(600406) 完整分析 - 直接使用腾讯财经API
竹林司马选股分析引擎 · 集成验证
"""
import sys, os, re, json, subprocess
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from datetime import datetime
from src.core.indicators.technical_indicators import TechnicalIndicators
from src.core.analysis.risk_analyzer import RiskAnalyzer
from src.core.analysis.trend_analyzer import TrendAnalyzer
from src.core.ai.score_engine import AIScoreEngine
from src.stock.report.generator import StockReportGenerator, ReportData


# ─── 数据获取层（腾讯财经 + 新浪，无代理）──────────────────
def fetch_kline(symbol: str, count: int = 120) -> pd.DataFrame:
    """获取日K线 via 腾讯财经"""
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?_var=kline_dayqfq&param={symbol},day,,,{count},qfq")
    out = subprocess.check_output(
        ["curl", "-s", "--noproxy", "*", url]
    ).decode("utf-8", errors="replace")
    text = out.strip()
    if text.startswith("kline_dayqfq="):
        text = text[len("kline_dayqfq="):]
    data = json.loads(text)
    klines = data["data"][symbol].get("qfqday") or data["data"][symbol].get("day", [])
    rows = []
    for k in klines:
        date, open_, close, high, low, vol = k
        rows.append({
            "date": date,
            "open": float(open_), "high": float(high),
            "low": float(low), "close": float(close),
            "volume": float(vol) * 100,   # 手→股，与qt口径一致
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_realtime(symbol: str) -> dict:
    """获取实时行情 via 腾讯财经 qt

    字段映射（sh600406实测）：
    [1]=name [2]=code [3]=current [4]=prev_close [5]=open
    [6]=high [7]=low [30]=datetime [31]=chg [32]=chg_pct
    [33]=high [34]=low [36]=volume(手) [37]=amount(万)
    """
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?_var=kline_dayqfq&param={symbol},day,,,1,qfq")
    out = subprocess.check_output(
        ["curl", "-s", "--noproxy", "*", url]
    ).decode("utf-8", errors="replace")
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
    high = float(info[33]) if info[33] else 0   # [33]=today high
    low = float(info[34]) if info[34] else 0   # [34]=today low
    chg = float(info[31]) if info[31] else 0   # [31]=chg
    chg_pct = float(info[32]) if info[32] else 0  # [32]=chg_pct
    vol = float(info[36]) * 100 if info[36] else 0  # [36]=手 → 股
    amount = float(info[37]) * 10000 if info[37] else 0  # [37]=万 → 元
    amplitude = ((high - low) / prev * 100) if prev else 0

    return {
        "name": name, "open": open_, "prev_close": prev,
        "current": current, "high": high, "low": low,
        "chg": chg, "chg_pct": chg_pct,
        "volume": vol, "amount": amount,
        "amplitude": amplitude,
    }


def fetch_float_share(code: str) -> tuple:
    """获取流通股本（股）和行业 via AkShare"""
    try:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=code)
        info = {str(r["item"]).strip(): r["value"] for _, r in df.iterrows()}
        float_share = float(info.get("流通股", 0))   # 股
        industry = str(info.get("行业", ""))
        return float_share, industry
    except Exception as e:
        return 0.0, ""


# ─── 主分析流程 ───────────────────────────────────────────
print("=" * 60)
print("竹林司马 · 国电南瑞(600406) 完整分析")
print("=" * 60)

# 1. 获取数据
print("\n[1/5] 获取行情数据...")
df = fetch_kline("sh600406", count=120)
snapshot = fetch_realtime("sh600406")
price = snapshot["current"]
chg_pct = snapshot["chg_pct"]
print(f"  K线: {len(df)} 条  ({df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()})")
print(f"  实时: ¥{price}  涨跌: {chg_pct:+.2f}%  振幅: {snapshot['amplitude']:.2f}%")
print(f"  成交量: {snapshot['volume']/1e8:.2f}亿  成交额: {snapshot['amount']/1e8:.2f}亿")

# 1b. 获取流通股本（用于精确换手率计算）
float_share, industry = fetch_float_share("600406")
correct_turnover = (snapshot["volume"] / float_share * 100) if float_share > 0 else 0.0
print(f"  流通股本: {float_share/1e8:.2f}亿股  行业: {industry}")

# 2. 技术指标
print("\n[2/5] 计算技术指标...")
ti = TechnicalIndicators()
bundle = ti.compute_all(df)
bundle.turnover = correct_turnover  # 用真实流通股本覆盖错误的换手率
print(f"  MACD: {bundle.macd.macd:.4f}  Signal: {bundle.macd.signal:.4f}  Hist: {bundle.macd.histogram:.4f}")
print(f"  RSI: {bundle.rsi.rsi:.1f} ({bundle.rsi.status})")
print(f"  KDJ: K={bundle.kdj.k:.1f} D={bundle.kdj.d:.1f} J={bundle.kdj.j:.1f} [{bundle.kdj.status}]")
print(f"  布林: {bundle.bollinger.upper:.2f}/{bundle.bollinger.middle:.2f}/{bundle.bollinger.lower:.2f}")
print(f"  MA5={bundle.ma.ma5:.2f} MA10={bundle.ma.ma10:.2f} MA20={bundle.ma.ma20:.2f}")
print(f"  ATR={bundle.atr:.2f}  换手率={bundle.turnover:.2f}%")

# 3. 风险分析
print("\n[3/5] 风险分析...")
ra = RiskAnalyzer()
risk = ra.analyze(bundle)
print(f"  风险: {risk.overall_risk_level}级({risk.overall_risk_score:.0f}分)")
print(f"  止损: ¥{risk.stop_loss_price:.2f}  VaR(95%): ¥{risk.var_95:.2f}")
print(f"  最大回撤预测: {risk.max_drawdown_30d:.1f}%")

# 4. 趋势分析
print("\n[4/5] 趋势分析...")
ta = TrendAnalyzer()
trend = ta.analyze(df, bundle)
print(f"  短期: {trend.short_trend}  中期: {trend.medium_trend}  长期: {trend.long_trend}")
print(f"  趋势强度: {trend.trend_strength:.0f}/100")
print(f"  支撑: {trend.support_levels}  阻力: {trend.resistance_levels}")

# 5. AI综合评分
print("\n[5/5] AI综合评分...")
engine = AIScoreEngine()
fundamentals = {
    "pe": 28.5, "pb": 3.8, "ps": 3.1, "roe": 14.2,
    "profit_growth_yoy": 12.5, "revenue_growth_yoy": 10.8,
    "debt_ratio": 45.0, "net_margin": 13.5, "gross_margin": 27.0,
    "dividend_yield": 1.8,
    "master_scores": {
        "巴菲特": 62,   # ROE=14.2%良好，PE=28.5合理，护城河稳定
        "芒格": 65,    # 电网自动化龙头，定价权强
        "达里奥": 58,  # 电力设备高杠杆(dr=45%)，分散尚可
        "彼得·林奇": 60,  # PEG=28.5/12.5=2.3>1，成长性一般
        "格雷厄姆": 55, # PE=28.5略高，安全边际中等
        "格林布拉特": 62,  # ROE=14.2%，资本回报率良好
        "邓普顿": 58,   # 当前估值中性，非极度悲观
        "索罗斯": 50,   # 情绪中性，无明显反身性机会
    },
}
market_data = {
    "news_count_5d": 6, "news_sentiment": 0.52,
    "institutional_coverage": 25, "main_net_flow_5d": 1.8,
}
rec = engine.score(
    "600406", "国电南瑞", bundle,
    fundamentals=fundamentals,
    risk_report=risk,
    trend_report=trend,
    market_data=market_data,
)

print(f"\n  ╔════════════════════════════════════════════╗")
print(f"  ║  综合评分: {rec.overall_score:.0f}/100   [{rec.overall_grade}]          ║")
print(f"  ║  技术: {rec.tech_score.score:.0f}  基本面: {rec.fund_score.score:.0f}  情绪: {rec.emotion_score.score:.0f}    ║")
print(f"  ║  信号: {rec.overall_action}  持仓: {rec.position_advice:<8}      ║")
print(f"  ║  止损: ¥{rec.stop_loss:.2f}  目标1: ¥{rec.target_price_1:.2f}  目标2: ¥{rec.target_price_2:.2f}  ║")
print(f"  ╚════════════════════════════════════════════╝")

# 5. 生成HTML报告
print("\n[5/5] 生成HTML报告...")
gen = StockReportGenerator()
data = ReportData()
data.from_indicators_bundle("国电南瑞", "600406", bundle)

# 用qt实时行情覆盖bundle的成交量/成交额（更准确）
data.volume = snapshot["volume"]   # 股（qt已转换）
data.amount = snapshot["amount"]  # 元
data.turnover = bundle.turnover   # 已用真实流通股本修正

# 计算区间收益率（从K线价格推导）
closes = df["close"].values
cur = float(closes[-1])
data.return_5d  = (cur / float(closes[-6])  - 1) * 100 if len(closes) >= 6  else 0.0
data.return_10d = (cur / float(closes[-11]) - 1) * 100 if len(closes) >= 11 else 0.0
data.return_30d = (cur / float(closes[-31]) - 1) * 100 if len(closes) >= 31 else 0.0
data.return_60d = (cur / float(closes[-61]) - 1) * 100 if len(closes) >= 61 else 0.0
data.high_60d   = float(df["high"].values[-60:].max())
data.low_60d    = float(df["low"].values[-60:].min())
data.position_60d = (cur - data.low_60d) / (data.high_60d - data.low_60d + 1e-10) * 100

# 数据新鲜度（最后K线日期距今天数）
last_kline_date = df["date"].max().date()
data.data_days = (datetime.now().date() - last_kline_date).days

data.from_risk_report(risk)
data.from_trend_report(trend)
data.from_fundamentals(fundamentals)
data.from_market_data(market_data)
data.from_ai_recommendation(rec)
data.report_date = datetime.now().strftime("%Y-%m-%d")
data.exchange = "SH"
data.industry = industry if industry else "电网设备"

html = gen.generate(data)
report_path = "/Users/gilesyang/Downloads/gilesyang2024/guodian_nanrui_report_0416.html"
gen.save(html, report_path)
print(f"  报告已保存: {report_path}")

# 最终摘要
print("\n" + "=" * 60)
print("核心结论")
print("=" * 60)
print(f"综合评分: {rec.overall_score:.0f}/100  [{rec.overall_grade}]")
print(f"操作信号: {rec.overall_action}  建议: {rec.position_advice}")
print(f"止损: ¥{rec.stop_loss:.2f}  目标1: ¥{rec.target_price_1:.2f}  目标2: ¥{rec.target_price_2:.2f}")
if trend.support_levels:
    print(f"支撑位: ¥{trend.support_levels[0]:.2f}", end="")
    if len(trend.support_levels) > 1:
        print(f" / ¥{trend.support_levels[1]:.2f}", end="")
    print()
if trend.resistance_levels:
    print(f"阻力位: ¥{trend.resistance_levels[0]:.2f}", end="")
    if len(trend.resistance_levels) > 1:
        print(f" / ¥{trend.resistance_levels[1]:.2f}", end="")
    print()
print(f"风险: {risk.overall_risk_level}级  VaR(95%): ¥{risk.var_95:.2f}")
if rec.bull_points:
    print(f"\n✅ 做多逻辑: {'; '.join(rec.bull_points[:3])}")
if rec.bear_points:
    print(f"⚠️ 做空逻辑: {'; '.join(rec.bear_points[:3])}")
print(f"\n📋 行动计划:")
for step in rec.action_plan:
    print(f"  · {step}")
print("=" * 60)
