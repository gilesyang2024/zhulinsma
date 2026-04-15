#!/usr/bin/env python3
"""
竹林司马 - 国电南瑞(600406) 全面分析报告
使用腾讯财经数据源 + 竹林司马全量分析引擎
"""

import sys
import os
import json
import urllib.request
from datetime import datetime, date

# 清除代理
for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
        os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import warnings
warnings.filterwarnings("ignore")

STOCK_CODE = "600406"
STOCK_NAME = "国电南瑞"


def fetch_tencent_data(symbol="sh600406", days=120):
    """从腾讯财经获取前复权日K数据"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    raw = json.loads(resp.read().decode("utf-8"))

    klines = raw["data"][symbol]["qfqday"]
    # 腾讯格式: [日期, 开盘, 收盘, 最高, 最低, 成交量(手)]
    records = []
    for k in klines[-days:]:
        records.append({
            "date": k[0],
            "open": float(k[1]),
            "close": float(k[2]),
            "high": float(k[3]),
            "low": float(k[4]),
            "volume": float(k[5]) * 100,  # 手 -> 股
        })
    return records


def fetch_realtime(symbol="sh600406"):
    """获取实时行情快照"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode("gbk")
    # 简易解析
    fields = text.split("~")
    if len(fields) > 45:
        return {
            "name": fields[1],
            "code": fields[2],
            "current": float(fields[3]) if fields[3] else 0,
            "yesterday_close": float(fields[4]) if fields[4] else 0,
            "today_open": float(fields[5]) if fields[5] else 0,
            "volume": int(fields[6]) if fields[6] else 0,
            "amount": float(fields[37]) if fields[37] else 0,  # 成交额(万)
            "high": float(fields[33]) if fields[33] else 0,
            "low": float(fields[34]) if fields[34] else 0,
            "change_pct": float(fields[32]) if fields[32] else 0,
            "pe": float(fields[39]) if fields[39] else 0,
            "pb": float(fields[46]) if fields[46] else 0,
            "market_cap": float(fields[45]) if fields[45] else 0,  # 总市值(亿)
        }
    return None


def sep(title="", width=70):
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'━' * pad} {title} {'━' * pad}")
    else:
        print("━" * width)


def bar_chart(value, max_val=10, length=20):
    filled = int(value / max_val * length)
    return "█" * filled + "░" * (length - filled)


# ═══════════════════════════════════════════════════════════════════
# 主分析流程
# ═══════════════════════════════════════════════════════════════════

print("\n" + "═" * 70)
print("  🎋 竹林司马 - 国电南瑞(600406.SH) 全面分析报告")
print(f"  分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("═" * 70)

# ── 1. 获取数据 ──
print("\n📡 正在获取行情数据...")
records = fetch_tencent_data("sh600406", days=120)
realtime = fetch_realtime("sh600406")

dates = [r["date"] for r in records]
close = np.array([r["close"] for r in records], dtype=float)
open_ = np.array([r["open"] for r in records], dtype=float)
high = np.array([r["high"] for r in records], dtype=float)
low = np.array([r["low"] for r in records], dtype=float)
volume = np.array([r["volume"] for r in records], dtype=float)

print(f"   ✅ 获取 {len(records)} 个交易日数据 ({dates[0]} ~ {dates[-1]})")

# ── 2. 实时行情快照 ──
sep("一、实时行情快照")
if realtime and realtime["current"] > 0:
    chg = realtime["change_pct"]
    arrow = "🔺" if chg > 0 else ("🔻" if chg < 0 else "➡️")
    print(f"""
   📊 {realtime['name']}（{realtime['code']}）
   ┌────────────────────────────────────┐
   │ 最新价: {realtime['current']:>10.2f}  {arrow} {abs(chg):.2f}%
   │ 今  开: {realtime['today_open']:>10.2f}  昨  收: {realtime['yesterday_close']:.2f}
   │ 最  高: {realtime['high']:>10.2f}  最  低: {realtime['low']:.2f}
   │ 成交量: {realtime['volume']:>12,} 手
   │ 成交额: {realtime['amount']:>10.2f} 亿
   │ 总市值: {realtime['market_cap']:>10.2f} 亿
   │ P/E:    {realtime['pe']:>10.2f}   P/B:   {realtime['pb']:.2f}
   └────────────────────────────────────┘
""")
else:
    print("   ⚠️ 非交易时段，使用最新收盘数据")
    print(f"   最新收盘价: {close[-1]:.2f}  ({dates[-1]})")

# ── 3. 技术指标计算 ──
from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators

ti = TechnicalIndicators(验证模式=False)

ma5 = ti.SMA(close, 5)
ma10 = ti.SMA(close, 10)
ma20 = ti.SMA(close, 20)
ma60 = ti.SMA(close, min(60, len(close)))
ma120 = ti.SMA(close, min(120, len(close)))
rsi14 = ti.RSI(close, 14)
rsi6 = ti.RSI(close, 6)
macd_data = ti.MACD(close)
# MACD 可能因数据长度导致signal为nan，取有效值
macd_hist_valid = macd_data["histogram"][~np.isnan(macd_data["histogram"])]
macd_signal_valid = macd_data["signal"][~np.isnan(macd_data["signal"])]
boll = ti.BollingerBands(close, 20)
# KDJ 手动计算（TI库不含KDJ）
def calc_kdj(high_arr, low_arr, close_arr, n=9, m1=3, m2=3):
    K, D = 50.0, 50.0
    K_list, D_list, J_list = [], [], []
    for i in range(len(close_arr)):
        start = max(0, i - n + 1)
        hn = np.max(high_arr[start:i+1])
        ln = np.min(low_arr[start:i+1])
        rsv = (close_arr[i] - ln) / (hn - ln + 1e-10) * 100
        K = (2/3) * K + (1/3) * rsv
        D = (2/3) * D + (1/3) * K
        J = 3 * K - 2 * D
        K_list.append(K)
        D_list.append(D)
        J_list.append(J)
    return {"k": np.array(K_list), "d": np.array(D_list), "j": np.array(J_list)}

kdj = calc_kdj(high, low, close)

sep("二、核心技术指标")
print(f"""
   ┌─ 均线系统 ─────────────────────────────────────────┐
   │  MA5:   {ma5[-1]:>8.2f}   MA10:  {ma10[-1]:>8.2f}
   │  MA20:  {ma20[-1]:>8.2f}   MA60:  {ma60[-1]:>8.2f}
   │  MA120: {ma120[-1]:>8.2f}   当前价: {close[-1]:>8.2f}
   │  多头排列(MA5>MA10>MA20>MA60): {'✅ 是' if ma5[-1]>ma10[-1]>ma20[-1]>ma60[-1] else '❌ 否'}
   └──────────────────────────────────────────────────────┘

   ┌─ MACD ──────────────────────────────────────────────┐
   │  MACD:    {macd_data['macd'][-1]:>8.4f}
   │  Signal:  {macd_signal_valid[-1] if len(macd_signal_valid)>0 else float('nan'):>8.4f}
   │  柱状图:  {macd_hist_valid[-1] if len(macd_hist_valid)>0 else float('nan'):>8.4f}  {'🔺 多头' if len(macd_hist_valid)>0 and macd_hist_valid[-1]>0 else '🔻 空头'}
   │  金叉/死叉: {'✅ 金叉(MACD上穿Signal)' if len(macd_data['macd'])>1 and macd_data['macd'][-1]>macd_data['signal'][-1] and macd_data['macd'][-2]<=macd_data['signal'][-2] else ('❌ 死叉' if len(macd_data['macd'])>1 and macd_data['macd'][-1]<macd_data['signal'][-1] and macd_data['macd'][-2]>=macd_data['signal'][-2] else '— 无交叉')}
   └──────────────────────────────────────────────────────┘

   ┌─ RSI ───────────────────────────────────────────────┐
   │  RSI6:   {rsi6[-1]:>8.2f}   {'超买>80' if rsi6[-1]>80 else ('超卖<20' if rsi6[-1]<20 else '正常区间')}
   │  RSI14:  {rsi14[-1]:>8.2f}   {'超买>70' if rsi14[-1]>70 else ('超卖<30' if rsi14[-1]<30 else '正常区间')}
   └──────────────────────────────────────────────────────┘

   ┌─ KDJ ───────────────────────────────────────────────┐
   │  K: {kdj['k'][-1]:>8.2f}   D: {kdj['d'][-1]:>8.2f}   J: {kdj['j'][-1]:>8.2f}
   │  状态: {'⚠️ 超买(J>100)' if kdj['j'][-1]>100 else ('⚠️ 超卖(J<0)' if kdj['j'][-1]<0 else '✅ 正常')}
   └──────────────────────────────────────────────────────┘

   ┌─ 布林带 ────────────────────────────────────────────┐
   │  上轨: {boll['upper'][-1]:>8.2f}   中轨: {boll['middle'][-1]:>8.2f}   下轨: {boll['lower'][-1]:>8.2f}
   │  当前价位置: {close[-1]:.2f}  {'偏上轨(强势)' if close[-1]>(boll['upper'][-1]+boll['middle'][-1])/2 else '偏下轨(弱势)'}
   └──────────────────────────────────────────────────────┘
""")

# ── 4. 趋势分析 ──
sep("三、趋势分析")

bull_arrange = ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]
above_ma60 = close[-1] > ma60[-1]
above_ma20 = close[-1] > ma20[-1]

# 趋势强度（价格在均线系统中的位置）
avg_ma = (ma5[-1] + ma10[-1] + ma20[-1] + ma60[-1]) / 4
trend_strength = (close[-1] - avg_ma) / avg_ma * 100

# 近期趋势（20日涨幅）
recent_20d_chg = (close[-1] - close[-21]) / close[-21] * 100 if len(close) > 20 else 0
recent_5d_chg = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 5 else 0

print(f"""
   📈 趋势方向判断：
   ├─ 多头排列: {'✅ 完全多头排列' if bull_arrange else '❌ 未完全多头'}
   ├─ 站上MA60: {'✅ 是 (+' + f'{(close[-1]-ma60[-1])/ma60[-1]*100:.1f}%)' if above_ma60 else '❌ 否 (-' + f'{(ma60[-1]-close[-1])/ma60[-1]*100:.1f}%)' if not above_ma60 else ''}
   ├─ 站上MA20: {'✅ 是' if above_ma20 else '❌ 否'}
   ├─ 趋势强度: {trend_strength:+.2f}% (偏离均线均值)
   ├─ 近5日涨跌: {recent_5d_chg:+.2f}%
   └─ 近20日涨跌: {recent_20d_chg:+.2f}%
""")

if bull_arrange and above_ma60:
    trend_verdict = "🟢 强上升趋势"
    trend_score = 9.0
elif above_ma60 and above_ma20:
    trend_verdict = "🟡 中期上升趋势"
    trend_score = 7.0
elif above_ma20:
    trend_verdict = "🟡 短期反弹"
    trend_score = 5.5
else:
    trend_verdict = "🔴 下降趋势"
    trend_score = 3.0

print(f"   📊 趋势判定: {trend_verdict}  [{trend_score:.1f}/10]")

# ── 5. 量能分析 ──
sep("四、量能分析")

vol_5d_avg = np.mean(volume[-5:])
vol_20d_avg = np.mean(volume[-20:])
vol_ratio = vol_5d_avg / (vol_20d_avg + 1e-10)

# 量价关系
price_chg_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 5 else 0
vol_price_relation = "放量上涨" if (vol_ratio > 1.0 and price_chg_5d > 0) else \
                     ("缩量下跌" if (vol_ratio < 1.0 and price_chg_5d < 0) else \
                     ("放量下跌" if (vol_ratio > 1.0 and price_chg_5d < 0) else "缩量横盘"))

# 连续缩量天数
shrink_days = 0
for i in range(len(volume)-1, max(len(volume)-10, 0), -1):
    if volume[i] < vol_20d_avg:
        shrink_days += 1
    else:
        break

print(f"""
   📊 量能指标：
   ├─ 近5日均量:  {vol_5d_avg:>12,.0f} 股
   ├─ 近20日均量: {vol_20d_avg:>12,.0f} 股
   ├─ 量比(5/20): {vol_ratio:.2f}  {'放大' if vol_ratio > 1.2 else ('萎缩' if vol_ratio < 0.8 else '持平')}
   ├─ 量价关系:   {vol_price_relation}
   └─ 连续缩量:   {shrink_days} 天
""")

fund_score = 7.5 if 1.0 <= vol_ratio <= 1.5 else (5.0 if vol_ratio > 2.0 else 6.0)
if vol_price_relation == "放量上涨":
    fund_score = 8.5
elif vol_price_relation == "放量下跌":
    fund_score = 3.5
print(f"   📊 资金面评分: {fund_score:.1f}/10")

# ── 6. 四大战法信号检测 ──
sep("五、四大战法信号检测")

signals = {}

# 战法1：锁仓K线
vol_std_ratio = np.std(volume[-5:]) / (np.mean(volume[-5:]) + 1e-10)
price_range_ratio = (np.max(close[-5:]) - np.min(close[-5:])) / (np.min(close[-5:]) + 1e-10)
lock_signal = vol_std_ratio < 0.15 and price_range_ratio < 0.04
signals["锁仓K线"] = lock_signal
print(f"""
   ⚔️ 战法1: 锁仓K线策略 {'✅ 触发' if lock_signal else '⭕ 未触发'}
   ├─ 量能波动率: {vol_std_ratio:.2f}  (阈值<0.15)
   ├─ 价格波动率: {price_range_ratio:.2f}  (阈值<0.04)
   └─ 判定: {'量能极度收缩+价格横盘=锁仓信号' if lock_signal else '不满足锁仓条件'}
""")

# 战法2：竞价弱转强
prev_chg = (close[-1] - close[-2]) / close[-2] * 100
gap_up = open_[-1] > close[-2]  # 当日跳空高开
auction_signal = (close[-2] < close[-3]) and (close[-1] > close[-2]) and prev_chg > 1.5
# 简化：前一日下跌，今日反包
if len(close) > 2:
    prev_drop = close[-2] < close[-3]
    today_recovery = close[-1] > close[-3]
    auction_signal = prev_drop and today_recovery and prev_chg > 1.0
signals["竞价弱转强"] = auction_signal
print(f"""
   ⚔️ 战法2: 竞价弱转强 {'✅ 触发' if auction_signal else '⭕ 未触发'}
   ├─ 前日下跌: {'是' if len(close)>2 and close[-2]<close[-3] else '否'}
   ├─ 今日反包: {'是' if len(close)>2 and close[-1]>close[-3] else '否'}
   ├─ 今日涨幅: {prev_chg:+.2f}%
   └─ 判定: {'弱转强确认' if auction_signal else '未形成弱转强'}
""")

# 战法3：利刃出鞘
recent_20d_high = np.max(high[-20:])
near_high = close[-1] >= recent_20d_high * 0.97
blade_signal = near_high and rsi14[-1] > 50
signals["利刃出鞘"] = blade_signal
print(f"""
   ⚔️ 战法3: 利刃出鞘 {'✅ 触发' if blade_signal else '⭕ 未触发'}
   ├─ 20日最高: {recent_20d_high:.2f}
   ├─ 当前价格: {close[-1]:.2f}  ({close[-1]/recent_20d_high*100:.1f}%)
   ├─ RSI14:    {rsi14[-1]:.1f}
   └─ 判定: {'接近新高+RSI>50=出鞘信号' if blade_signal else '不满足出鞘条件'}
""")

# 战法4：涨停板战法
pullback_ma20 = abs(close[-1] - ma20[-1]) / ma20[-1] < 0.03
limit_signal = pullback_ma20 and price_range_ratio < 0.05
signals["涨停板回踩"] = limit_signal
print(f"""
   ⚠️ 战法4: 涨停板战法 {'✅ 触发' if limit_signal else '⭕ 未触发'}
   ├─ MA20:     {ma20[-1]:.2f}
   ├─ 偏离MA20: {abs(close[-1]-ma20[-1])/ma20[-1]*100:.2f}%  (阈值<3%)
   ├─ 5日波幅:  {price_range_ratio:.2f}
   └─ 判定: {'回踩均线支撑+缩量整理=买入信号' if limit_signal else '不满足回踩条件'}
""")

# 信号汇总
triggered = sum(signals.values())
sep("战法信号汇总")
print(f"""
   ┌──────────────────────────────────────────┐
   │  锁仓K线:     {'✅' if signals['锁仓K线'] else '⭕'}    竞价弱转强: {'✅' if signals['竞价弱转强'] else '⭕'}
   │  利刃出鞘:     {'✅' if signals['利刃出鞘'] else '⭕'}    涨停板回踩: {'✅' if signals['涨停板回踩'] else '⭕'}
   │                                          │
   │  触发战法: {triggered}/4                         │
   │  {'⭐⭐⭐⭐⭐ 高确定性·强力买点' if triggered>=3 else '⭐⭐⭐⭐ 中高确定性·可考虑介入' if triggered>=2 else '⭐⭐⭐ 单一信号·谨慎跟踪' if triggered==1 else '⭐⭐ 暂无信号·建议观望'}
   └──────────────────────────────────────────┘
""")

signal_score = 3.0 + triggered * 2.0  # 3, 5, 7, 9, 11→10

# ── 7. AI智能评分（6维度） ──
sep("六、AI智能评分（6维度）")

# 维度1: 趋势评分
v_trend = trend_score

# 维度2: 动量评分
if len(macd_hist_valid) > 0:
    macd_hist = macd_hist_valid[-1]
    macd_hist_prev = macd_hist_valid[-2] if len(macd_hist_valid) > 1 else 0
else:
    macd_hist, macd_hist_prev = 0, 0
momentum_score = 7.0
if macd_hist > 0 and macd_hist > macd_hist_prev:
    momentum_score = 8.5
elif macd_hist > 0:
    momentum_score = 7.0
elif macd_hist < 0 and macd_hist < macd_hist_prev:
    momentum_score = 3.5
else:
    momentum_score = 5.0
v_momentum = momentum_score

# 维度3: 量能评分
v_volume = fund_score

# 维度4: 波动率评分
volatility = np.std(np.diff(close[-20:]) / close[-20:][:-1]) * 100
vol_score = 8.0 if volatility < 2.0 else (6.0 if volatility < 3.5 else 4.0)
v_volatility = vol_score

# 维度5: 技术形态评分
pattern_score = 5.0
if bull_arrange:
    pattern_score += 2.0
if 40 < rsi14[-1] < 65:
    pattern_score += 1.0
if close[-1] > boll["middle"][-1]:
    pattern_score += 1.0
if kdj["j"][-1] > kdj["k"][-1] and kdj["k"][-1] > kdj["d"][-1]:
    pattern_score += 1.0
v_pattern = min(pattern_score, 10.0)

# 维度6: 风险调整评分
risk_score = 10.0 - vol_score  # 低波动=低风险=高分
v_risk = risk_score

dimensions = {
    "趋势强度": v_trend,
    "动量指标": v_momentum,
    "量能分析": v_volume,
    "波动率": v_volatility,
    "技术形态": v_pattern,
    "风险评级": v_risk,
}
weights = [0.25, 0.20, 0.15, 0.10, 0.20, 0.10]

print("\n   维度              评分      权重      加权分     可视化")
print("   " + "─" * 62)
ai_total = 0
for (name, score), w in zip(dimensions.items(), weights):
    weighted = score * w
    ai_total += weighted
    print(f"   {name:<10}   {score:>5.1f}/10  {w*100:>4.0f}%    {weighted:>5.2f}    {bar_chart(score)}")
print("   " + "─" * 62)
print(f"   {'AI综合评分':<10}   {sum(dimensions.values())/len(dimensions):>5.2f}/10  100%    {ai_total:.2f}")

# ── 8. 风险评估 ──
sep("七、风险评估")

from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer

analyzer = RiskAnalyzer()
risk_result = analyzer.评估风险(close, volume, rsi=float(rsi14[-1]))

print(f"""
   🛡️ 风险评估结果：
   ├─ 综合风险分数: {risk_result['综合风险分数']}
   ├─ 风险等级:     {risk_result['风险等级']}
   ├─ 风险因素:     {', '.join(risk_result['风险因素'])}
   ├─ 操作建议:     {risk_result['操作建议']}
   │
   ├─ 建议仓位上限: {risk_result['仓位上限'] if '仓位上限' in risk_result else {'低风险':'25%','中风险':'15%','高风险':'5%','极高风险':'0%'}.get(risk_result['风险等级'], 'N/A')}
   └─ 止损空间:     {risk_result['止损空间'] if '止损空间' in risk_result else {'低风险':'3%-5%','中风险':'5%-8%','高风险':'8%-12%','极高风险':'N/A'}.get(risk_result['风险等级'], 'N/A')}
""")

# ── 9. 五步选股综合评分 ──
sep("八、五步选股法综合评分")

# Step1 趋势
s1 = trend_score
# Step2 资金
s2 = fund_score
# Step3 基本面（从腾讯实时数据获取PE/PB）
if realtime and realtime["pe"] > 0:
    pe = realtime["pe"]
    pb = realtime["pb"]
    cap = realtime["market_cap"]
    fundamental_score = 8.0 if (pe < 30 and cap > 500) else (6.0 if pe < 50 else 4.0)
    print(f"\n   📋 Step3 基本面: PE={pe:.1f}  P/B={pb:.2f}  市值={cap:.0f}亿")
else:
    fundamental_score = 7.0  # 国电南瑞龙头基本面较好
    print(f"\n   📋 Step3 基本面: 使用估算值 (PE≈28 P/B≈3.8 市值≈2300亿)")
s3 = fundamental_score

# Step4 板块
s4 = 7.5  # 智能电网/电力设备 政策主线
print(f"   🔲 Step4 板块: 电力设备/智能电网  政策利好  热度:高")

# Step5 形态
s5 = v_pattern
print(f"   🕯️  Step5 形态: 综合技术形态评分")

step_weights = {"趋势": 0.30, "资金": 0.25, "基本面": 0.20, "板块": 0.15, "形态": 0.10}
step_scores = [s1, s2, s3, s4, s5]
final_score = sum(s * w for s, w in zip(step_scores, step_weights.values()))

stars = "★★★★★" if final_score >= 8.5 else ("★★★★" if final_score >= 7.0 else ("★★★" if final_score >= 5.5 else "★★"))

print(f"\n   {'='*55}")
print(f"   📊 {STOCK_NAME}（{STOCK_CODE}）综合评分")
print(f"   {'='*55}")
print()
for (dim, score), w in zip(
    [("趋势强度", s1), ("资金信号", s2), ("基本面", s3), ("板块热度", s4), ("形态评估", s5)],
    step_weights.values()
):
    print(f"   {dim:<8} {score:>5.1f}/10  {bar_chart(score)}  (权重{w*100:.0f}%)")

print(f"\n   {'━'*55}")
print(f"   ⭐ 综合评分: {final_score:.2f} / 10.0    评级: {stars}")
print(f"   {'━'*55}")

# ── 10. 操作建议 ──
sep("九、操作建议")

if final_score >= 8.0 and triggered >= 2:
    advice = """
   🟢 建议操作：积极关注，逢回调分批建仓
   ├─ 综合评分较高，多个战法信号共振
   ├─ 建议仓位：15%-25%（分3批建仓）
   ├─ 止损位：建议设在MA20下方3%处（{:.2f}）
   └─ 目标位：前期高点/布林带上轨附近""".format(ma20[-1] * 0.97)
elif final_score >= 6.5:
    advice = f"""
   🟡 建议操作：适度关注，等待更明确信号
   ├─ 综合评分中等，技术面部分向好
   ├─ 建议仓位：5%-10%（轻仓试探）
   ├─ 止损位：MA60下方（{ma60[-1]*0.97:.2f}）
   └─ 关注点：放量突破MA20可加仓"""
else:
    advice = """
   🔴 建议操作：观望为主，等待趋势明朗
   ├─ 综合评分偏低，趋势不明朗
   ├─ 建议仓位：0%-5%（或不操作）
   └─ 关注点：站上MA60且量能放大"""

print(advice)

# ── 免责声明 ──
sep("免责声明")
print("""
   ⚠️ 以上分析基于技术指标和量化模型，仅供参考。
   不构成任何投资建议。投资有风险，入市需谨慎。
   数据来源：腾讯财经 | 分析引擎：竹林司马 v1.0
""")

print("═" * 70)
print(f"  报告生成完毕 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("═" * 70)
