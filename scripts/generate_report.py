#!/usr/bin/env python3
"""
竹林司马 - 通用股票 HTML 可视化全面分析报告
支持通过命令行参数指定股票代码
用法：python3 scripts/generate_report.py 600875 东方电气
"""

import sys, os, json, urllib.request

if len(sys.argv) >= 2:
    STOCK_CODE = sys.argv[1]
    STOCK_NAME = sys.argv[2] if len(sys.argv) >= 3 else f"股票{STOCK_CODE}"
else:
    STOCK_CODE = "600875"
    STOCK_NAME = "东方电气"

# 自动判断市场前缀
if STOCK_CODE.startswith("6"):
    SYMBOL = f"sh{STOCK_CODE}"
    MARKET = "SH"
elif STOCK_CODE.startswith(("0", "3")):
    SYMBOL = f"sz{STOCK_CODE}"
    MARKET = "SZ"
else:
    SYMBOL = f"bj{STOCK_CODE}"
    MARKET = "BJ"

from datetime import datetime, date

for k in list(os.environ.keys()):
    if k.lower().endswith('_proxy'):
        os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ═══════════════════ 数据采集 ═══════════════════

def fetch_tencent_data(symbol, days=120):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    raw = json.loads(resp.read().decode("utf-8"))
    klines = raw["data"][symbol]["qfqday"]
    return [{"date": k[0], "open": float(k[1]), "close": float(k[2]),
             "high": float(k[3]), "low": float(k[4]), "volume": float(k[5])*100} for k in klines[-days:]]

def fetch_realtime(symbol):
    url = f"https://qt.gtimg.cn/q={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    fields = resp.read().decode("gbk").split("~")
    if len(fields) > 46:
        return {"name": fields[1], "code": fields[2],
                "current": float(fields[3]) if fields[3] else 0,
                "yesterday_close": float(fields[4]) if fields[4] else 0,
                "today_open": float(fields[5]) if fields[5] else 0,
                "volume": int(fields[6]) if fields[6] else 0,
                "high": float(fields[33]) if fields[33] else 0,
                "low": float(fields[34]) if fields[34] else 0,
                "change_pct": float(fields[32]) if fields[32] else 0,
                "pe": float(fields[39]) if fields[39] else 0,
                "pb": float(fields[46]) if fields[46] else 0,
                "market_cap": float(fields[45]) if fields[45] else 0,
                "turnover": float(fields[38]) if fields[38] else 0}
    return None

def fetch_minute_data(symbol):
    """获取分时量能数据（新浪接口）"""
    try:
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={symbol}&scale=1&ma=5&datalen=250"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")
        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0:
            return data
    except:
        pass
    return []

def calc_kdj(high_arr, low_arr, close_arr, n=9):
    K, D = 50.0, 50.0
    Kl, Dl, Jl = [], [], []
    for i in range(len(close_arr)):
        s = max(0, i-n+1)
        hn, ln = np.max(high_arr[s:i+1]), np.min(low_arr[s:i+1])
        rsv = (close_arr[i]-ln)/(hn-ln+1e-10)*100
        K, D = (2/3)*K+(1/3)*rsv, (2/3)*D+(1/3)*K
        Kl.append(K); Dl.append(D); Jl.append(3*K-2*D)
    return {"k": np.array(Kl), "d": np.array(Dl), "j": np.array(Jl)}

def to_json(arr):
    if isinstance(arr, np.ndarray):
        return [None if np.isnan(x) else round(float(x),4) for x in arr]
    return arr

print(f"📡 获取{STOCK_NAME}({STOCK_CODE})行情数据...")
records = fetch_tencent_data(SYMBOL, days=120)
realtime = fetch_realtime(SYMBOL)
minute_data = fetch_minute_data(SYMBOL)
dates = [r["date"] for r in records]
close = np.array([r["close"] for r in records], dtype=float)
open_ = np.array([r["open"] for r in records], dtype=float)
high = np.array([r["high"] for r in records], dtype=float)
low = np.array([r["low"] for r in records], dtype=float)
volume = np.array([r["volume"] for r in records], dtype=float)

# 技术指标
from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
ti = TechnicalIndicators(验证模式=False)
ma5, ma10, ma20 = ti.SMA(close,5), ti.SMA(close,10), ti.SMA(close,20)
ma60 = ti.SMA(close, min(60, len(close)))
ma120 = ti.SMA(close, min(120, len(close)))
rsi6, rsi14 = ti.RSI(close,6), ti.RSI(close,14)
macd_data = ti.MACD(close)
macd_hist_valid = macd_data["histogram"][~np.isnan(macd_data["histogram"])]
boll = ti.BollingerBands(close, 20)
kdj = calc_kdj(high, low, close)

# 基本分析
bull_arrange = ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]
above_ma60, above_ma20 = close[-1] > ma60[-1], close[-1] > ma20[-1]
avg_ma = (ma5[-1]+ma10[-1]+ma20[-1]+ma60[-1])/4
trend_strength = (close[-1]-avg_ma)/avg_ma*100
recent_5d_chg = (close[-1]-close[-6])/close[-6]*100 if len(close)>5 else 0
recent_20d_chg = (close[-1]-close[-21])/close[-21]*100 if len(close)>20 else 0
vol_5d_avg, vol_20d_avg = np.mean(volume[-5:]), np.mean(volume[-20:])
vol_ratio = vol_5d_avg/(vol_20d_avg+1e-10)
vol_price_relation = "放量上涨" if (vol_ratio>1.0 and recent_5d_chg>0) else \
    ("缩量下跌" if (vol_ratio<1.0 and recent_5d_chg<0) else \
    ("放量下跌" if (vol_ratio>1.0 and recent_5d_chg<0) else "缩量横盘"))

# 分时量能分析
minute_analysis = {"available": False}
if minute_data:
    try:
        m_volumes = []
        for m in minute_data:
            if m.get("volume"):
                m_volumes.append(float(m["volume"]))
        if m_volumes:
            total_m_vol = sum(m_volumes)
            n_mins = len(m_volumes)
            # 分时段统计（假设从9:30开始）
            open_30_idx = min(30, n_mins)
            mid_am_idx = min(120, n_mins)
            mid_pm_idx = min(210, n_mins)

            open_30_vol = sum(m_volumes[:open_30_idx])
            mid_am_vol = sum(m_volumes[open_30_idx:mid_am_idx])
            mid_pm_vol = sum(m_volumes[mid_am_idx:mid_pm_idx])
            close_30_vol = sum(m_volumes[mid_pm_idx:])

            minute_analysis = {
                "available": True,
                "total_volume": total_m_vol,
                "distribution": {
                    "open_30min": {"volume": open_30_vol, "percent": round(open_30_vol/total_m_vol*100, 1)},
                    "mid_am": {"volume": mid_am_vol, "percent": round(mid_am_vol/total_m_vol*100, 1)},
                    "mid_pm": {"volume": mid_pm_vol, "percent": round(mid_pm_vol/total_m_vol*100, 1)},
                    "close_30min": {"volume": close_30_vol, "percent": round(close_30_vol/total_m_vol*100, 1)},
                },
                "signals": []
            }
            if minute_analysis["distribution"]["open_30min"]["percent"] > 30:
                minute_analysis["signals"].append("🔥 早盘主力抢筹明显")
            elif minute_analysis["distribution"]["open_30min"]["percent"] > 25:
                minute_analysis["signals"].append("📊 早盘有一定放量")
            if minute_analysis["distribution"]["close_30min"]["percent"] > 20:
                minute_analysis["signals"].append("⚠️ 尾盘放量异常，注意资金动向")
            elif minute_analysis["distribution"]["close_30min"]["percent"] > 15:
                minute_analysis["signals"].append("📊 尾盘有一定放量")
            if not minute_analysis["signals"]:
                minute_analysis["signals"].append("平 分时量能分布正常")

            # TOP 10 放量时段
            top_vols = []
            for i, m in enumerate(minute_data[:n_mins]):
                if m.get("volume"):
                    top_vols.append({
                        "time": m.get("day", f"{i:02d}:00"),
                        "price": float(m.get("close", 0)),
                        "volume": float(m["volume"]),
                        "amount": float(m.get("ma_price5", 0)) * float(m["volume"]) if m.get("ma_price5") else 0,
                    })
            top_vols.sort(key=lambda x: x["volume"], reverse=True)
            minute_analysis["top_volumes"] = top_vols[:10]
    except Exception as e:
        minute_analysis["error"] = str(e)

# ═══════════════════ AI 引擎调用 ═══════════════════

df = pd.DataFrame({
    "date": dates, "open": open_, "close": close, "high": high, "low": low, "volume": volume
})

from zhulinsma.core.ai import AIScoreEngine, SignalFusion, PatternRecognition, AIRiskEngine, AIRecommender

vol_std_ratio = np.std(volume[-5:])/(np.mean(volume[-5:])+1e-10)
price_range_ratio = (np.max(close[-5:])-np.min(close[-5:]))/(np.min(close[-5:])+1e-10)
lock_signal = vol_std_ratio < 0.15 and price_range_ratio < 0.04

prev_chg = (close[-1]-close[-2])/close[-2]*100 if len(close)>1 else 0
prev_drop = close[-2]<close[-3] if len(close)>2 else False
today_recovery = close[-1]>close[-3] if len(close)>2 else False
auction_signal = prev_drop and today_recovery and prev_chg > 1.0

recent_20d_high = np.max(high[-20:])
blade_signal = close[-1] >= recent_20d_high * 0.97 and rsi14[-1] > 50

pullback_ma20 = abs(close[-1]-ma20[-1])/ma20[-1] < 0.03
limit_signal = pullback_ma20 and price_range_ratio < 0.05

strategy_signals = [
    {"名称": "锁仓K线", "触发": lock_signal, "信号类型": "买入", "评分": 85 if lock_signal else 0,
     "说明": f"量能波动{vol_std_ratio:.2f}+价格波动{price_range_ratio:.2f}"},
    {"名称": "竞价弱转强", "触发": auction_signal, "信号类型": "买入", "评分": 80 if auction_signal else 0,
     "说明": f"涨幅{prev_chg:+.2f}%"},
    {"名称": "利刃出鞘", "触发": blade_signal, "信号类型": "买入", "评分": 75 if blade_signal else 0,
     "说明": f"接近20日高点{close[-1]/recent_20d_high*100:.1f}%"},
    {"名称": "涨停板回踩", "触发": limit_signal, "信号类型": "买入", "评分": 80 if limit_signal else 0,
     "说明": f"偏离MA20 {abs(close[-1]-ma20[-1])/ma20[-1]*100:.2f}%"},
]

score_engine = AIScoreEngine()
ai_score = score_engine.评分(df, strategy_signals)

fusion_engine = SignalFusion()
fusion_result = fusion_engine.融合(strategy_signals)

pattern_engine = PatternRecognition()
pattern_result = pattern_engine.识别(df, 最近N日=5)

risk_engine = AIRiskEngine()
ai_risk = risk_engine.评估(df)

from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer
basic_risk = RiskAnalyzer().评估风险(close, volume, rsi=float(rsi14[-1]))

recommender = AIRecommender()
ai_recommend = recommender.分析(df, STOCK_CODE, strategy_signals)

# 趋势预测
def predict_trend(close, ma5, ma10, ma20, ma60, rsi14, macd_hist_valid, vol_ratio):
    score = 50
    reasons = []
    if ma5[-1] > ma10[-1] > ma20[-1]:
        score += 20; reasons.append("短期均线多头排列")
    elif ma5[-1] < ma10[-1] < ma20[-1]:
        score -= 20; reasons.append("短期均线空头排列")
    if close[-1] > ma60[-1]:
        score += 10; reasons.append("站上MA60中期均线")
    else:
        score -= 10; reasons.append("位于MA60下方")
    if len(macd_hist_valid) >= 2:
        if macd_hist_valid[-1] > 0 and macd_hist_valid[-1] > macd_hist_valid[-2]:
            score += 15; reasons.append("MACD柱状图放量多头")
        elif macd_hist_valid[-1] < 0 and macd_hist_valid[-1] < macd_hist_valid[-2]:
            score -= 15; reasons.append("MACD柱状图加速空头")
    if rsi14[-1] > 60:
        score += 5; reasons.append("RSI偏强势区间")
    elif rsi14[-1] < 35:
        score -= 5; reasons.append("RSI偏弱势区间")
    if vol_ratio > 1.2:
        score += 5; reasons.append("量能放大")
    elif vol_ratio < 0.7:
        score -= 5; reasons.append("量能萎缩")
    if len(close) >= 20:
        x = np.arange(20)
        slope = np.polyfit(x, close[-20:], 1)[0]
        if slope > 0:
            score += 10; reasons.append("20日价格趋势向上")
        else:
            score -= 10; reasons.append("20日价格趋势向下")
    score = max(0, min(100, score))
    if score >= 75: direction, confidence = "上升趋势", "高"
    elif score >= 55: direction, confidence = "上升趋势", "中"
    elif score >= 45: direction, confidence = "震荡整理", "中"
    elif score >= 25: direction, confidence = "下降趋势", "中"
    else: direction, confidence = "下降趋势", "高"
    if len(close) >= 20:
        slope = np.polyfit(x, close[-20:], 1)[0]
        pred_5d = [close[-1] + slope * i for i in range(1, 6)]
    else:
        pred_5d = [close[-1]] * 5
    return {"方向": direction, "置信度": confidence, "得分": score,
            "依据": reasons, "预测5日价": [round(p, 2) for p in pred_5d],
            "当前价": round(float(close[-1]), 2)}

trend_pred = predict_trend(close, ma5, ma10, ma20, ma60, rsi14, macd_hist_valid, vol_ratio)

# 五步选股综合评分
pe, pb, cap = (realtime["pe"], realtime["pb"], realtime["market_cap"]) if realtime and realtime["pe"]>0 else (26.3, 4.27, 2102)
if bull_arrange and above_ma60: trend_score = 9.0
elif above_ma60 and above_ma20: trend_score = 7.0
elif above_ma20: trend_score = 5.5
else: trend_score = 3.0
fund_score = 8.5 if vol_price_relation=="放量上涨" else (3.5 if vol_price_relation=="放量下跌" else 6.0)
if 1.0<=vol_ratio<=1.5: fund_score = max(fund_score, 7.5)
fundamental_score = 8.0 if (pe<30 and cap>500) else (6.0 if pe<50 else 4.0)
sector_score = 7.5
volatility = np.std(np.diff(close[-20:])/close[-20:][:-1])*100
pat_score = 5.0
if bull_arrange: pat_score += 2.0
if 40<rsi14[-1]<65: pat_score += 1.0
if close[-1]>boll["middle"][-1]: pat_score += 1.0
if kdj["j"][-1]>kdj["k"][-1] and kdj["k"][-1]>kdj["d"][-1]: pat_score += 1.0
pat_score = min(pat_score, 10.0)

step_weights_map = {"趋势强度": 0.30, "资金信号": 0.25, "基本面": 0.20, "板块热度": 0.15, "形态评估": 0.10}
step_scores = {"趋势强度": trend_score, "资金信号": fund_score, "基本面": fundamental_score, "板块热度": sector_score, "形态评估": pat_score}
final_score = sum(step_scores[k]*v for k,v in step_weights_map.items())
stars = "★★★★★" if final_score>=8.5 else ("★★★★" if final_score>=7.0 else ("★★★" if final_score>=5.5 else "★★"))

def gen_operation_advice(final_score, triggered, ai_risk, ai_score, trend_pred, signals):
    risk_lv = ai_risk.get("风险等级", "中风险")
    rating = ai_score.get("投资评级", "中性观望")
    stop_loss = ai_risk.get("止损位", 0)
    tp = ai_risk.get("止盈目标", {})
    position = ai_risk.get("仓位上限", "10%")
    trend_dir = trend_pred["方向"]
    if final_score >= 8.0 and triggered >= 2:
        level, color, action = "积极买入", "#22c55e", "逢回调分3批建仓"
        pos_range = "15%-25%"
    elif final_score >= 6.5:
        level, color, action = "适度参与", "#f59e0b", "轻仓试探，设好止损"
        pos_range = "5%-10%"
    else:
        level, color, action = "观望等待", "#ef4444", "空仓或极轻仓跟踪"
        pos_range = "0%-5%"
    steps = []
    if trend_dir == "上升趋势": steps.append(f"趋势偏多，可沿MA5/MA10逐步建仓")
    elif trend_dir == "下降趋势": steps.append(f"趋势偏空，严格等待企稳信号再入场")
    else: steps.append(f"趋势震荡，区间操作为主")
    if stop_loss > 0: steps.append(f"止损位：{stop_loss:.2f}（ATR止损）")
    if tp: steps.append(f"止盈目标：保守{tp.get('保守','—')} / 基准{tp.get('基准','—')} / 乐观{tp.get('乐观','—')}")
    steps.append(f"建议仓位：{pos_range}（上限{position}）")
    steps.append(f"AI评级：{rating} | 风险等级：{risk_lv}")
    triggered_names = [s["名称"] for s in signals if s["触发"]]
    if triggered_names: steps.append(f"触发战法：{'、'.join(triggered_names)}")
    return {"level": level, "color": color, "action": action, "steps": steps}

op_advice = gen_operation_advice(final_score, sum(1 for s in strategy_signals if s["触发"]), ai_risk, ai_score, trend_pred, strategy_signals)

triggered_count = sum(1 for s in strategy_signals if s["触发"])
report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
chg = realtime["change_pct"] if realtime else 0
macd_hist_show = f"{macd_hist_valid[-1]:.4f}" if len(macd_hist_valid) > 0 else "nan"
tp_conservative = ai_risk.get("止盈目标", {}).get("保守", "—")
tp_base = ai_risk.get("止盈目标", {}).get("基准", "—")
tp_optimistic = ai_risk.get("止盈目标", {}).get("乐观", "—")
risk_detail_vol = ai_risk.get("风险明细", {}).get("年化波动率", "—")
risk_detail_drawdown = ai_risk.get("风险明细", {}).get("最大回撤", "—")

# ═══════════════════ 通俗化分析文本生成 ═══════════════════

def human_ma(ma5v, ma10v, ma20v, ma60v, price, bull):
    """均线通俗解读"""
    if bull:
        pos = "站在所有均线上方，属于强势格局"
    elif price > ma20v:
        pos = f"站在MA20({ma20v:.2f})上方，但MA60({ma60v:.2f})还没突破"
    elif price > ma60v:
        pos = f"站在MA60({ma60v:.2f})上方，但跌破MA20({ma20v:.2f})，短期转弱"
    else:
        pos = f"跌破MA60({ma60v:.2f})，处于弱势区域"
    
    if bull:
        arrange = "均线呈多头排列（MA5>MA10>MA20>MA60），趋势向上，适合持股待涨"
    elif ma5v < ma10v < ma20v < ma60v:
        arrange = "均线呈空头排列（MA5<MA10<MA20<MA60），趋势向下，建议回避"
    elif ma5v > ma10v and ma10v < ma20v:
        arrange = "短期均线拐头但中期仍弱，可能是反弹信号，需观察确认"
    elif ma5v < ma10v and ma10v > ma20v:
        arrange = "短期回调但中期趋势仍在，可能是上涨中继，关注MA20支撑"
    else:
        arrange = "均线交织，方向不明，建议观望等待方向选择"
    
    return pos, arrange

def human_momentum(dif, hist, rsi6v, rsi14v, kv, dv, jv, price, boll_mid):
    """动量指标通俗解读"""
    # MACD
    if not np.isnan(hist) and hist > 0:
        macd_text = f"MACD柱状图为正值({hist:.4f})，多头力量占优"
    elif not np.isnan(hist) and hist < 0:
        macd_text = f"MACD柱状图为负值({hist:.4f})，空头力量占优"
    else:
        macd_text = "MACD柱状图数据不足，暂无判断"
    
    if not np.isnan(dif):
        if dif > 0:
            macd_text += "，DIF在零轴上方，中期趋势偏多"
        else:
            macd_text += "，DIF在零轴下方，中期趋势偏空"
    
    # RSI
    if rsi14v > 80:
        rsi_text = f"RSI14={rsi14v:.0f}，进入超买区域，注意短期回调风险"
    elif rsi14v > 70:
        rsi_text = f"RSI14={rsi14v:.0f}，接近超买，上涨动力可能减弱"
    elif rsi14v < 20:
        rsi_text = f"RSI14={rsi14v:.0f}，进入超卖区域，可能存在反弹机会"
    elif rsi14v < 30:
        rsi_text = f"RSI14={rsi14v:.0f}，接近超卖，下跌动能可能衰竭"
    elif 40 <= rsi14v <= 65:
        rsi_text = f"RSI14={rsi14v:.0f}，处于中性区间，多空相对平衡"
    else:
        rsi_text = f"RSI14={rsi14v:.0f}，{'偏强' if rsi14v > 50 else '偏弱'}"
    
    # KDJ
    if jv > 100:
        kdj_text = f"K={kv:.0f} D={dv:.0f} J={jv:.0f}，J值超过100，短期超买信号"
    elif jv < 0:
        kdj_text = f"K={kv:.0f} D={dv:.0f} J={jv:.0f}，J值低于0，短期超卖信号"
    elif kv > dv and kv < 80:
        kdj_text = f"K={kv:.0f} D={dv:.0f} J={jv:.0f}，K线在D线上方，金叉状态，偏多"
    elif kv < dv and kv > 20:
        kdj_text = f"K={kv:.0f} D={dv:.0f} J={jv:.0f}，K线在D线下方，死叉状态，偏空"
    else:
        kdj_text = f"K={kv:.0f} D={dv:.0f} J={jv:.0f}，多空分歧中"
    
    # 布林
    if price > boll_mid:
        boll_text = f"当前价在布林中轨({boll_mid:.2f})上方，走势偏强"
    else:
        boll_text = f"当前价在布林中轨({boll_mid:.2f})下方，走势偏弱"
    
    return macd_text, rsi_text, kdj_text, boll_text

def human_trend(price, ma60v, ma20v, trend_str, chg5, chg20):
    """趋势通俗解读"""
    if trend_str > 2:
        t_strength = f"趋势强度+{trend_str:.1f}%，价格明显高于均线均值，走势较强"
    elif trend_str > 0:
        t_strength = f"趋势强度+{trend_str:.1f}%，价格略高于均线均值，走势偏暖"
    elif trend_str > -2:
        t_strength = f"趋势强度{trend_str:.1f}%，价格接近均线均值，走势平淡"
    else:
        t_strength = f"趋势强度{trend_str:.1f}%，价格低于均线均值，走势偏弱"
    
    if chg20 > 5:
        t_recent = f"近20日涨{chg20:.1f}%，中期处于上涨通道"
    elif chg20 > 0:
        t_recent = f"近20日涨{chg20:.1f}%，中期小幅上涨"
    elif chg20 > -5:
        t_recent = f"近20日跌{abs(chg20):.1f}%，中期小幅回调"
    else:
        t_recent = f"近20日跌{abs(chg20):.1f}%，中期处于下跌通道"
    
    if price > ma60v and price > ma20v:
        t_status = "当前站上MA20和MA60两条关键均线，中期趋势健康"
    elif price > ma20v:
        t_status = "站上MA20但未站上MA60，中期趋势仍有压力"
    elif price > ma60v:
        t_status = "跌破MA20但仍在MA60上方，短期走弱但中期支撑尚存"
    else:
        t_status = "MA20和MA60均未站上，短期和中期趋势都偏空"
    
    return t_strength, t_recent, t_status

def human_volume(vol_ratio, vol_price, vol_5d, vol_20d, volatility):
    """量能通俗解读"""
    if vol_ratio > 1.5:
        v_ratio_text = f"近5日均量是20日的{vol_ratio:.1f}倍，成交量明显放大"
    elif vol_ratio > 1.0:
        v_ratio_text = f"近5日均量是20日的{vol_ratio:.1f}倍，成交量有所放大"
    elif vol_ratio > 0.7:
        v_ratio_text = f"近5日均量是20日的{vol_ratio:.1f}倍，成交量基本持平"
    else:
        v_ratio_text = f"近5日均量是20日的{vol_ratio:.1f}倍，成交量明显萎缩"
    
    vp_map = {
        "放量上涨": "📈 量价齐升！价格上涨伴随成交量放大，是最健康的上涨形态，说明资金在积极买入",
        "缩量下跌": "📉 缩量下跌，抛压不大但买盘也不积极，说明市场观望情绪浓厚，需等待放量企稳信号",
        "放量下跌": "⚠️ 放量下跌！价格下跌伴随成交量放大，说明有资金在出逃，需要警惕",
        "缩量横盘": "➡️ 缩量横盘，多空双方都在观望，一旦放量突破方向将确立"
    }
    vp_text = vp_map.get(vol_price, f"量价关系：{vol_price}")
    
    if volatility > 3:
        v_vol_text = f"日波动率{volatility:.1f}%，价格波动较大，短线操作风险偏高"
    elif volatility > 1.5:
        v_vol_text = f"日波动率{volatility:.1f}%，价格波动适中，适合正常操作"
    else:
        v_vol_text = f"日波动率{volatility:.1f}%，价格波动很小，走势比较平稳"
    
    return v_ratio_text, vp_text, v_vol_text

# 生成通俗文本
ma_pos, ma_arrange = human_ma(ma5[-1], ma10[-1], ma20[-1], ma60[-1], close[-1], bull_arrange)
macd_text, rsi_text, kdj_text, boll_text = human_momentum(
    macd_data['macd'][-1], macd_hist_valid[-1] if len(macd_hist_valid)>0 else float('nan'),
    rsi6[-1], rsi14[-1], kdj['k'][-1], kdj['d'][-1], kdj['j'][-1], close[-1], boll['middle'][-1])
t_strength, t_recent, t_status = human_trend(close[-1], ma60[-1], ma20[-1], trend_strength, recent_5d_chg, recent_20d_chg)
v_ratio_text, vp_text, v_vol_text = human_volume(vol_ratio, vol_price_relation, vol_5d_avg, vol_20d_avg, volatility)

print(f"📊 数据就绪，生成HTML报告...")

# ═══════════════════ LLM 大模型增强 ═══════════════════
llm_mode = False
llm_analysis = {}
llm_errors = []

try:
    from zhulinsma.core.llm.enhanced import EnhancedAnalysis
    print("🤖 初始化 LLM 增强引擎...")
    enhanced = EnhancedAnalysis()
    llm_mode = enhanced.llm_available
    if llm_mode:
        print(f"   ✅ {enhanced.mode} ({enhanced._client.info()['provider']} / {enhanced._client.info()['model']})")
    else:
        print("   ⚠️ LLM 不可用，使用规则引擎模式")
        print(f"   提示: 设置环境变量 LLM_PROVIDER + LLM_API_KEY 启用大模型增强")
except Exception as e:
    print(f"   ⚠️ LLM 模块加载失败: {e}")

if llm_mode:
    try:
        print("   📡 调用大模型分析（约30-60秒，请耐心等待）...")
        price_info_data = {
            "close": float(close[-1]),
            "change_pct": chg,
            "recent_prices": [float(c) for c in close[-10:]],
        }
        ma_data_dict = {
            "arrangement": "多头排列" if bull_arrange else ("空头排列" if ma5[-1]<ma10[-1]<ma20[-1] else "交织"),
            "price_vs_ma5": f"{'上方' if close[-1]>ma5[-1] else '下方'}",
            "price_vs_ma10": f"{'上方' if close[-1]>ma10[-1] else '下方'}",
            "price_vs_ma20": f"{'上方' if close[-1]>ma20[-1] else '下方'}",
            "price_vs_ma60": f"{'上方' if close[-1]>ma60[-1] else '下方'}",
        }
        macd_data_dict = {
            "dif": f"{macd_data['macd'][-1]:.4f}" if not np.isnan(macd_data['macd'][-1]) else "nan",
            "signal": f"{macd_data['signal'][-1]:.4f}" if not np.isnan(macd_data['signal'][-1]) else "nan",
            "histogram": f"{macd_hist_valid[-1]:.4f}" if len(macd_hist_valid)>0 else "nan",
            "cross": "金叉" if len(macd_hist_valid)>=2 and macd_hist_valid[-2]<0 and macd_hist_valid[-1]>0 else ("死叉" if len(macd_hist_valid)>=2 and macd_hist_valid[-2]>0 and macd_hist_valid[-1]<0 else "无"),
        }
        rsi_data_dict = {
            "rsi6": f"{rsi6[-1]:.1f}",
            "rsi14": f"{rsi14[-1]:.1f}",
            "status": "超买" if rsi14[-1]>70 else ("超卖" if rsi14[-1]<30 else "正常"),
        }
        kdj_data_dict = {
            "k": f"{kdj['k'][-1]:.1f}", "d": f"{kdj['d'][-1]:.1f}", "j": f"{kdj['j'][-1]:.1f}",
            "cross": "金叉" if kdj['k'][-1]>kdj['d'][-1] and kdj['j'][-1]>kdj['k'][-1] else ("死叉" if kdj['k'][-1]<kdj['d'][-1] else "无"),
        }
        volume_info_dict = {
            "volume_ratio": f"{vol_ratio:.2f}",
            "ma5_vs_ma20": f"{vol_5d_avg/vol_20d_avg:.2f}" if vol_20d_avg > 0 else "N/A",
            "price_volume_relation": vol_price_relation,
        }
        trend_info_dict = {
            "short_term": "上涨" if recent_5d_chg > 0 else "下跌",
            "mid_term": "上涨" if recent_20d_chg > 0 else "下跌",
            "strength": f"{trend_strength:+.2f}%",
        }

        llm_analysis = enhanced._run_llm_analysis(
            stock_name=STOCK_NAME,
            stock_code=STOCK_CODE,
            current_price=float(close[-1]),
            price_info=price_info_data,
            ma_data=ma_data_dict,
            macd_data=macd_data_dict,
            rsi_data=rsi_data_dict,
            kdj_data=kdj_data_dict,
            volume_info=volume_info_dict,
            trend_info=trend_info_dict,
            strategy_signals=strategy_signals,
            rule_results={
                "score": ai_score,
                "signal_fusion": fusion_result,
                "pattern": pattern_result,
                "risk": ai_risk,
            },
        )
        success = llm_analysis.get("_success_count", 0)
        errors = llm_analysis.get("_errors", [])
        print(f"   ✅ LLM 分析完成：{success}/6 模块成功")
        for err in errors:
            print(f"   ⚠️ {err}")
    except Exception as e:
        print(f"   ❌ LLM 分析失败: {e}")
        llm_mode = False

# LLM 文本转 HTML 辅助函数
def markdown_to_html(text):
    """将 Markdown 文本转为 HTML（简易版）"""
    if not text:
        return '<span style="color:var(--dim);">规则引擎模式（LLM 不可用）</span>'
    import re
    html = text
    # 转义 HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 标题
    html = re.sub(r'^### (.+)$', r'<h4 style="font-size:14px;font-weight:700;color:var(--accent);margin:12px 0 6px;">\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h3 style="font-size:15px;font-weight:700;color:var(--accent);margin:14px 0 8px;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^\*\*(.+?)\*\*', r'<strong style="color:var(--text);">\1</strong>', html, flags=re.MULTILINE)
    # 列表
    html = re.sub(r'^- (.+)$', r'<div style="padding:3px 0 3px 16px;font-size:13px;position:relative;">• \1</div>', html, flags=re.MULTILINE)
    # 引用
    html = re.sub(r'^&gt; (.+)$', r'<div style="padding:6px 12px;background:rgba(255,255,255,.03);border-left:3px solid var(--accent);font-size:12px;color:var(--dim);margin:6px 0;">\1</div>', html, flags=re.MULTILINE)
    # 换行
    html = html.replace("\n\n", "<br><br>")
    html = html.replace("\n", "<br>")
    return html

# 准备 LLM 增强文本
llm_dimensions_html = markdown_to_html(llm_analysis.get("dimensions", "")) if llm_mode else ""
llm_strategies_html = markdown_to_html(llm_analysis.get("strategies", "")) if llm_mode else ""
llm_execution_html = markdown_to_html(llm_analysis.get("execution_plan", "")) if llm_mode else ""
llm_risk_html = markdown_to_html(llm_analysis.get("risk_analysis", "")) if llm_mode else ""
llm_advice_html = markdown_to_html(llm_analysis.get("investment_advice", "")) if llm_mode else ""
llm_trend_html = markdown_to_html(llm_analysis.get("trend_prediction", "")) if llm_mode else ""
llm_provider_name = enhanced._client.info()["provider"] if llm_mode and enhanced._client else "规则引擎"

# ═══════════════════ HTML 生成 ═══════════════════
# 分时量能HTML片段
minute_html = ""
if minute_analysis.get("available"):
    dist = minute_analysis["distribution"]
    signals_html = ""
    for sig in minute_analysis.get("signals", []):
        signals_html += f'<div style="padding:4px 0;">{sig}</div>'

    top_vols_html = ""
    for i, tv in enumerate(minute_analysis.get("top_volumes", [])[:10], 1):
        top_vols_html += f"""<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.03);font-size:12px;">
        <span style="color:var(--dim);">#{i} {tv['time']}</span>
        <span style="color:var(--text);">{tv['price']:.2f}元</span>
        <span style="color:var(--cyan);font-weight:700;">{tv['volume']:.0f}手</span>
      </div>"""

    # 分时分布数据用于ECharts
    minute_dist_json = json.dumps([
        {"name": "早盘30分", "value": dist["open_30min"]["volume"]},
        {"name": "上午中段", "value": dist["mid_am"]["volume"]},
        {"name": "下午中段", "value": dist["mid_pm"]["volume"]},
        {"name": "尾盘30分", "value": dist["close_30min"]["volume"]},
    ])

    minute_html = f"""
<!-- 分时量能分析 -->
<div class="card" style="border-color:rgba(6,182,212,.3);">
  <div class="card-header">
    <h2><span style="color:var(--cyan);">⏱</span> 分时量能分析</h2>
    <span class="badge tag-cyan">当日分时</span>
  </div>
  <div class="grid2">
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">成交分布（{minute_analysis['total_volume']:.0f}手）</h3>
      <div class="chart-c chart-sm" id="minutePieChart"></div>
      <div style="margin-top:8px;">
        <div class="row"><span>早盘30分(9:30-10:00)</span><span class="val" style="color:var(--cyan);">{dist['open_30min']['volume']:.0f}手 ({dist['open_30min']['percent']}%)</span></div>
        <div class="row"><span>上午中段(10:00-11:30)</span><span class="val">{dist['mid_am']['volume']:.0f}手 ({dist['mid_am']['percent']}%)</span></div>
        <div class="row"><span>下午中段(13:00-14:30)</span><span class="val">{dist['mid_pm']['volume']:.0f}手 ({dist['mid_pm']['percent']}%)</span></div>
        <div class="row"><span>尾盘30分(14:30-15:00)</span><span class="val" style="color:var(--orange);">{dist['close_30min']['volume']:.0f}手 ({dist['close_30min']['percent']}%)</span></div>
      </div>
      <div style="margin-top:10px;padding:10px;background:rgba(6,182,212,.06);border:1px solid rgba(6,182,212,.15);border-radius:8px;font-size:12px;">
        <strong style="color:var(--cyan);">⚡ 主力动向判断</strong><br>{signals_html}
      </div>
    </div>
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">放量时段 TOP 10</h3>
      {top_vols_html}
    </div>
  </div>
</div>
"""
else:
    minute_html = """
<div class="card" style="border-color:rgba(107,112,128,.3);">
  <div class="card-header">
    <h2><span style="color:var(--dim);">⏱</span> 分时量能分析</h2>
    <span class="badge tag-dim">非交易时段</span>
  </div>
  <div style="text-align:center;padding:20px;color:var(--dim);font-size:13px;">
    当前为非交易时段，分时量能数据不可用。显示收盘日数据。
  </div>
</div>
"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{STOCK_NAME}({STOCK_CODE}) - 竹林司马 AI 分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root {{
  --bg: #0a0c10; --card: #141720; --card2: #1a1e2c; --border: #252a3a;
  --text: #e8eaf0; --dim: #6b7080; --accent: #6366f1; --accent2: #818cf8;
  --red: #ef4444; --green: #22c55e; --yellow: #f59e0b; --blue: #3b82f6;
  --purple: #a855f7; --cyan: #06b6d4; --orange: #f97316;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",sans-serif; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px 16px; }}
.header {{ text-align:center; padding:36px 20px 32px; background:linear-gradient(180deg,#141720 0%,#0a0c10 100%); border-bottom:1px solid var(--border); margin:-20px -16px 28px; position:relative; }}
.header::before {{ content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%;
  background:radial-gradient(circle at 30% 40%,rgba(99,102,241,0.06) 0%,transparent 50%),radial-gradient(circle at 70% 60%,rgba(168,85,247,0.04) 0%,transparent 50%); }}
.header .logo {{ font-size:12px; color:var(--dim); letter-spacing:5px; text-transform:uppercase; margin-bottom:8px; position:relative; }}
.header h1 {{ font-size:30px; font-weight:800; margin-bottom:6px; position:relative; }}
.header .sub {{ font-size:14px; color:var(--dim); position:relative; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px; margin-bottom:20px; }}
.card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border); }}
.card-header h2 {{ font-size:16px; font-weight:700; display:flex; align-items:center; gap:8px; }}
.card-header .badge {{ font-size:11px; padding:3px 10px; border-radius:20px; font-weight:600; }}
.snapshot {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-bottom:24px; }}
.snap {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px; transition:all .2s; }}
.snap:hover {{ border-color:var(--accent); background:var(--card2); }}
.snap .l {{ font-size:11px; color:var(--dim); margin-bottom:2px; }}
.snap .v {{ font-size:20px; font-weight:800; }}
.snap .s {{ font-size:11px; color:var(--dim); margin-top:2px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
@media(max-width:768px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
.row {{ display:flex; justify-content:space-between; padding:5px 0; font-size:13px; }}
.row .val {{ font-weight:700; font-variant-numeric:tabular-nums; }}
.tag {{ display:inline-block; padding:2px 10px; border-radius:20px; font-size:11px; font-weight:700; }}
.tag-red {{ background:rgba(239,68,68,.12); color:var(--red); }}
.tag-green {{ background:rgba(34,197,94,.12); color:var(--green); }}
.tag-yellow {{ background:rgba(245,158,11,.12); color:var(--yellow); }}
.tag-blue {{ background:rgba(59,130,246,.12); color:var(--blue); }}
.tag-purple {{ background:rgba(168,85,247,.12); color:var(--purple); }}
.tag-cyan {{ background:rgba(6,182,212,.12); color:var(--cyan); }}
.tag-orange {{ background:rgba(249,115,22,.12); color:var(--orange); }}
.tag-dim {{ background:rgba(107,112,128,.12); color:var(--dim); }}
.signal-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }}
@media(max-width:768px) {{ .signal-grid {{ grid-template-columns:1fr; }} }}
.sig {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; position:relative; overflow:hidden; }}
.sig.on {{ border-color:var(--red); }}
.sig.on::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; background:linear-gradient(90deg,var(--red),var(--yellow)); }}
.sig .sn {{ font-size:15px; font-weight:700; margin-bottom:6px; }}
.sig .sd {{ font-size:12px; color:var(--dim); margin-bottom:8px; }}
.sig .sb {{ display:inline-block; padding:3px 12px; border-radius:20px; font-size:11px; font-weight:700; }}
.bar-row {{ display:flex; align-items:center; margin-bottom:10px; }}
.bar-row .bn {{ width:72px; font-size:12px; color:var(--dim); flex-shrink:0; }}
.bar-row .bw {{ flex:1; height:7px; background:rgba(255,255,255,.04); border-radius:4px; margin:0 10px; overflow:hidden; }}
.bar-row .bf {{ height:100%; border-radius:4px; transition:width .8s ease; }}
.bar-row .bs {{ width:55px; text-align:right; font-size:13px; font-weight:700; flex-shrink:0; }}
.big-num {{ text-align:center; padding:20px 0; }}
.big-num .num {{ font-size:52px; font-weight:900; background:linear-gradient(135deg,var(--accent),var(--purple)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.big-num .lbl {{ font-size:13px; color:var(--dim); margin-top:2px; }}
.chart-box {{ background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; margin-bottom:20px; }}
.chart-box .ch {{ padding:14px 18px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }}
.chart-box .ch h3 {{ font-size:14px; font-weight:600; }}
.chart-c {{ width:100%; height:380px; padding:6px; }}
.chart-sm {{ height:240px; }}
.risk-bar {{ height:10px; background:linear-gradient(90deg,var(--green),var(--yellow),var(--red)); border-radius:5px; position:relative; margin:14px 0 6px; }}
.risk-bar .ptr {{ position:absolute; top:-5px; width:18px; height:18px; background:#fff; border-radius:50%; border:3px solid var(--bg); box-shadow:0 2px 8px rgba(0,0,0,.3); transform:translateX(-50%); }}
.risk-labels {{ display:flex; justify-content:space-between; font-size:10px; color:var(--dim); }}
.steps {{ list-style:none; counter-reset:step; }}
.steps li {{ counter-increment:step; padding:10px 0 10px 36px; position:relative; font-size:13px; line-height:1.7; border-bottom:1px solid rgba(255,255,255,.03); }}
.steps li:last-child {{ border:none; }}
.steps li::before {{ content:counter(step); position:absolute; left:0; top:10px; width:24px; height:24px; border-radius:50%; background:var(--accent); color:#fff; font-size:12px; font-weight:700; display:flex; align-items:center; justify-content:center; }}
.stitle {{ font-size:18px; font-weight:800; margin-bottom:14px; display:flex; align-items:center; gap:10px; }}
.stitle .icon {{ width:32px; height:32px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:16px; }}
.final-card {{ background:linear-gradient(135deg,var(--card) 0%,rgba(99,102,241,.08) 100%); border:2px solid var(--accent); border-radius:18px; padding:28px; text-align:center; margin-bottom:20px; }}
.final-card .fn {{ font-size:64px; font-weight:900; }}
.final-card .stars {{ font-size:22px; color:var(--yellow); margin-top:4px; }}
.final-card .tag-big {{ display:inline-block; margin-top:14px; padding:8px 28px; border-radius:10px; font-size:15px; font-weight:700; }}
.footer {{ text-align:center; padding:28px 0; color:var(--dim); font-size:11px; border-top:1px solid var(--border); margin-top:20px; }}
.price-up {{ color:var(--red); }} .price-down {{ color:var(--green); }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <div class="logo">🎋 竹林司马 AI 分析系统</div>
  <h1>{STOCK_NAME}（{STOCK_CODE}.{MARKET}）</h1>
  <div class="sub">七大维度 AI 深度分析 + 分时量能 · {report_time}</div>
</div>

<div class="stitle"><div class="icon" style="background:rgba(99,102,241,.15);color:var(--accent);">📊</div>实时行情</div>
<div class="snapshot">
  <div class="snap">
    <div class="l">最新价</div>
    <div class="v {'price-up' if chg>0 else 'price-down'}">{realtime['current'] if realtime else close[-1]:.2f}</div>
    <div class="s">{'🔺' if chg>0 else '🔻'} {abs(chg):.2f}% · 成交{(realtime['volume'] if realtime else 0):,}手</div>
  </div>
  <div class="snap">
    <div class="l">今开 / 昨收</div>
    <div class="v" style="font-size:17px;">{(realtime['today_open'] if realtime else open_[-1]):.2f} <span style="color:var(--dim);font-size:12px;">/ {(realtime['yesterday_close'] if realtime else close[-2]):.2f}</span></div>
    <div class="s">高 {(realtime['high'] if realtime else high[-1]):.2f} · 低 {(realtime['low'] if realtime else low[-1]):.2f}</div>
  </div>
  <div class="snap">
    <div class="l">总市值</div>
    <div class="v">{cap:.0f}<span style="font-size:12px;color:var(--dim);"> 亿</span></div>
    <div class="s">PE {pe:.1f} · PB {pb:.2f}</div>
  </div>
  <div class="snap">
    <div class="l">AI 趋势预测</div>
    <div class="v" style="font-size:17px;color:{'var(--red)' if trend_pred['方向']=='上升趋势' else 'var(--green)' if trend_pred['方向']=='下降趋势' else 'var(--yellow)'};">{trend_pred['方向']}</div>
    <div class="s">置信度 {trend_pred['置信度']} · 得分 {trend_pred['得分']}/100</div>
  </div>
</div>

<!-- ══════════ 模块一：选股分析维度 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--accent);">①</span> 选股分析维度</h2>
    <span class="badge {'tag-purple' if llm_mode else 'tag-blue'}">{'🤖 AI 深度解读' if llm_mode else '通俗解读'}</span>
  </div>
  {"<div style='padding:0 0 16px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_dimensions_html+"</div>" if llm_mode and llm_dimensions_html else ""}
  <div class="grid2">
    <div class="card" style="margin:0;background:var(--card2);border-color:var(--border);">
      <h3 style="font-size:13px;color:var(--accent);margin-bottom:10px;">📍 当前在什么位置？（均线系统）</h3>
      <div style="font-size:13px;line-height:1.8;color:var(--text);">
        <div style="margin-bottom:8px;">{ma_pos}</div>
        <div style="margin-bottom:8px;">{ma_arrange}</div>
        <div style="padding:6px 10px;background:rgba(99,102,241,.08);border-radius:6px;font-size:12px;color:var(--dim);">
          MA5={ma5[-1]:.2f} · MA10={ma10[-1]:.2f} · MA20={ma20[-1]:.2f} · MA60={ma60[-1]:.2f}
        </div>
      </div>
    </div>
    <div class="card" style="margin:0;background:var(--card2);border-color:var(--border);">
      <h3 style="font-size:13px;color:var(--blue);margin-bottom:10px;">💨 动量怎么样？（MACD/RSI/KDJ）</h3>
      <div style="font-size:13px;line-height:1.8;color:var(--text);">
        <div style="margin-bottom:6px;">{macd_text}</div>
        <div style="margin-bottom:6px;">{rsi_text}</div>
        <div style="margin-bottom:6px;">{kdj_text}</div>
        <div>{boll_text}</div>
      </div>
    </div>
    <div class="card" style="margin:0;background:var(--card2);border-color:var(--border);">
      <h3 style="font-size:13px;color:var(--red);margin-bottom:10px;">📈 是什么趋势？（趋势判断）</h3>
      <div style="font-size:13px;line-height:1.8;color:var(--text);">
        <div style="margin-bottom:8px;">{t_status}</div>
        <div style="margin-bottom:8px;">{t_strength}</div>
        <div>{t_recent}</div>
        <div style="margin-top:6px;padding:6px 10px;background:rgba(239,68,68,.06);border-radius:6px;font-size:12px;color:var(--dim);">
          近5日 <span class="{'price-up' if recent_5d_chg>0 else 'price-down'}">{recent_5d_chg:+.1f}%</span> · 近20日 <span class="{'price-up' if recent_20d_chg>0 else 'price-down'}">{recent_20d_chg:+.1f}%</span>
        </div>
      </div>
    </div>
    <div class="card" style="margin:0;background:var(--card2);border-color:var(--border);">
      <h3 style="font-size:13px;color:var(--cyan);margin-bottom:10px;">💹 买卖活跃吗？（量能分析）</h3>
      <div style="font-size:13px;line-height:1.8;color:var(--text);">
        <div style="margin-bottom:8px;">{vp_text}</div>
        <div style="margin-bottom:8px;">{v_ratio_text}</div>
        <div>{v_vol_text}</div>
      </div>
    </div>
  </div>
</div>

<div class="chart-box">
  <div class="ch"><h3>K线走势 + 均线系统</h3><span class="badge tag-purple">{len(records)} 交易日</span></div>
  <div class="chart-c" id="klineChart"></div>
</div>

<div class="chart-box">
  <div class="ch"><h3>动量指标（MACD / RSI / KDJ）</h3><span class="badge tag-cyan">多维分析</span></div>
  <div class="chart-c" id="momentumChart"></div>
</div>

<!-- ══════════ 分时量能分析 ══════════ -->
{minute_html}

<!-- ══════════ 模块二：四大选股策略战法 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--orange);">②</span> 四大选股策略战法</h2>
    <span class="badge tag-orange">触发 {triggered_count}/4</span>
  </div>
  {"<div style='padding:0 0 12px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_strategies_html+"</div>" if llm_mode and llm_strategies_html else ""}
  <div class="signal-grid">"""

for s in strategy_signals:
    cls = "on" if s["触发"] else ""
    html += f"""    <div class="sig {cls}">
      <div class="sn">{'🔒' if s['名称']=='锁仓K线' else '⚡' if s['名称']=='竞价弱转强' else '🗡️' if s['名称']=='利刃出鞘' else '🎯'} {s['名称']}</div>
      <div class="sd">{s['说明']}</div>
      {'<span class="sb tag-red">✅ 信号触发</span>' if s["触发"] else '<span class="sb tag-dim">⭕ 未触发</span>'}
    </div>
"""

html += f"""  </div>
  <div style="text-align:center;margin-top:14px;color:var(--dim);font-size:13px;">
    {'⭐⭐⭐⭐⭐ 高确定性·强力买点' if triggered_count>=3 else '⭐⭐⭐⭐ 中高确定性·可考虑介入' if triggered_count>=2 else '⭐⭐⭐ 单一信号·谨慎跟踪' if triggered_count==1 else '⭐⭐ 暂无信号·建议观望'}
  </div>
</div>

<!-- ══════════ 模块三：选股后操作执行建议 ══════════ -->
<div class="card" style="border-color:{op_advice['color']};">
  <div class="card-header">
    <h2><span style="color:{op_advice['color']};">③</span> 选股后操作执行建议</h2>
    <span class="badge" style="background:{op_advice['color']};color:#fff;">{op_advice['level']}</span>
  </div>
  {"<div style='padding:0 0 12px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_execution_html+"</div>" if llm_mode and llm_execution_html else ""}
  <div style="margin-bottom:12px;">
    <span style="font-size:15px;font-weight:700;">操作策略：</span>
    <span style="font-size:14px;color:var(--dim);">{op_advice['action']}</span>
  </div>
  <ul class="steps">
    <li><strong>趋势判断</strong>：{op_advice['steps'][0]}</li>"""

for i, step in enumerate(op_advice['steps'][1:], 1):
    label = ["止损止盈", "止盈目标", "仓位控制", "AI 综合判定", "信号来源"][i-1] if i <= 5 else f"步骤{i}"
    html += f"    <li><strong>{label}</strong>：{step}</li>\n"

html += f"""  </ul>
</div>

<!-- ══════════ 模块四：综合选股评分 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--cyan);">④</span> 综合选股评分</h2>
    <span class="badge tag-cyan">五步选股法</span>
  </div>
  <div class="grid2">
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">五步评分明细</h3>"""

step_colors = {"趋势强度":"var(--red)","资金信号":"var(--cyan)","基本面":"var(--accent)","板块热度":"var(--yellow)","形态评估":"var(--purple)"}
for name, score in step_scores.items():
    pct = score/10*100
    w = step_weights_map[name]
    color = step_colors.get(name,"var(--accent)")
    html += f"""      <div class="bar-row">
        <div class="bn">{name}</div>
        <div class="bw"><div class="bf" style="width:{pct}%;background:{color};"></div></div>
        <div class="bs">{score:.1f}<span style="font-size:10px;color:var(--dim);">({w*100:.0f}%)</span></div>
      </div>"""

html += f"""    </div>
    <div>
      <div class="big-num">
        <div class="num">{final_score:.2f}</div>
        <div class="lbl">综合评分 / 10.0</div>
        <div style="font-size:22px;color:var(--yellow);margin-top:6px;">{stars}</div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════ 模块五：AI 风险评估模型 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--red);">⑤</span> AI 风险评估模型</h2>
    <span class="badge tag-red">{ai_risk.get('风险等级','未知')}</span>
  </div>
  {"<div style='padding:0 0 12px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_risk_html+"</div>" if llm_mode and llm_risk_html else ""}
  <div class="grid2">
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">AI 风险引擎（ATR/回撤/波动）</h3>
      <div class="row"><span>综合风险分</span><span class="val">{ai_risk.get('综合风险分','—')}</span></div>
      <div class="row"><span>当前价</span><span class="val">{ai_risk.get('当前价','—')}</span></div>
      <div class="row"><span>ATR 止损位</span><span class="val price-down">{ai_risk.get('止损位','—')}</span></div>
      <div class="row"><span>止盈·保守</span><span class="val price-up">{tp_conservative}</span></div>
      <div class="row"><span>止盈·基准</span><span class="val price-up">{tp_base}</span></div>
      <div class="row"><span>止盈·乐观</span><span class="val price-up">{tp_optimistic}</span></div>
      <div class="row"><span>仓位上限</span><span class="val">{ai_risk.get('仓位上限','—')}</span></div>
      <div class="row"><span>年化波动率</span><span class="val">{risk_detail_vol}</span></div>
      <div class="row"><span>最大回撤(20日)</span><span class="val">{risk_detail_drawdown}</span></div>
      <div style="margin-top:10px;">
        <div class="risk-bar">
          <div class="ptr" style="left:{min(ai_risk.get('综合风险分',50),100)}%;"></div>
        </div>
        <div class="risk-labels"><span>低风险 0</span><span>中 50</span><span>高 100</span></div>
      </div>
    </div>
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">基础风险分析器（多维细粒度）</h3>
      <div class="row"><span>综合风险分数</span><span class="val">{basic_risk['综合风险分数']}</span></div>
      <div class="row"><span>风险等级</span><span class="tag tag-yellow">{basic_risk['风险等级']}</span></div>
      <div class="row"><span>波动风险</span><span class="tag {'tag-red' if basic_risk['波动风险']['等级']=='高' else 'tag-yellow' if basic_risk['波动风险']['等级']=='中' else 'tag-green'}">{basic_risk['波动风险']['等级']}({basic_risk['波动风险']['分数']})</span></div>
      <div class="row"><span>超买卖风险</span><span class="tag {'tag-red' if basic_risk['超买卖风险']['等级']=='高' else 'tag-yellow' if basic_risk['超买卖风险']['等级']=='中' else 'tag-green'}">{basic_risk['超买卖风险']['等级']}({basic_risk['超买卖风险']['分数']})</span></div>
      <div class="row"><span>量价风险</span><span class="tag {'tag-red' if basic_risk['量价风险']['等级']=='高' else 'tag-yellow' if basic_risk['量价风险']['等级']=='中' else 'tag-green'}">{basic_risk['量价风险']['等级']}({basic_risk['量价风险']['分数']})</span></div>
      <div class="row"><span>趋势风险</span><span class="tag {'tag-red' if basic_risk['趋势风险']['等级']=='高' else 'tag-yellow' if basic_risk['趋势风险']['等级']=='中' else 'tag-green'}">{basic_risk['趋势风险']['等级']}({basic_risk['趋势风险']['分数']})</span></div>
      <div class="row"><span>风险因素</span><span class="val" style="font-size:11px;">{', '.join(basic_risk['风险因素'])}</span></div>
      <div style="margin-top:10px;padding:10px;background:rgba(255,255,255,.02);border-radius:8px;font-size:12px;color:var(--dim);">
        💡 {basic_risk['风险说明']}
      </div>
    </div>
  </div>
</div>

<!-- ══════════ 模块六：AI 投资建议 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--green);">⑥</span> AI 投资建议</h2>
    <span class="badge tag-green">{ai_score.get('投资评级','中性观望')}</span>
  </div>
  {"<div style='padding:0 0 12px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_advice_html+"</div>" if llm_mode and llm_advice_html else ""}
  <div class="grid2">
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">AI 六维度评分</h3>"""

dim_colors = {"趋势强度":"var(--red)","动量指标":"var(--blue)","波动风险":"var(--yellow)","量价关系":"var(--cyan)","策略信号":"var(--orange)","资金面":"var(--green)"}
ai_dims = ai_score.get("各维度评分", {})
ai_weights = ai_score.get("权重", {})
for name, score in ai_dims.items():
    pct = score/100*100
    color = dim_colors.get(name, "var(--accent)")
    w = ai_weights.get(name, 0)
    html += f"""      <div class="bar-row">
        <div class="bn">{name}</div>
        <div class="bw"><div class="bf" style="width:{pct}%;background:{color};"></div></div>
        <div class="bs">{score:.0f}<span style="font-size:10px;color:var(--dim);">({w*100:.0f}%)</span></div>
      </div>"""

html += f"""    </div>
    <div>
      <div class="big-num">
        <div class="num">{ai_score.get('综合评分','—')}</div>
        <div class="lbl">AI 综合评分 / 100</div>
      </div>
      <div style="margin-top:12px;padding:10px;background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.15);border-radius:8px;font-size:12px;">
        <strong style="color:var(--green);">📊 评级说明：</strong>{ai_score.get('评级说明','—')}
      </div>
      <div style="margin-top:8px;padding:10px;background:rgba(255,255,255,.02);border-radius:8px;font-size:12px;color:var(--dim);">
        <strong>🔗 信号融合：</strong>{fusion_result.get('建议','—')}
      </div>
      <div style="margin-top:8px;padding:10px;background:rgba(255,255,255,.02);border-radius:8px;font-size:12px;color:var(--dim);">
        <strong>📐 K线形态：</strong>{pattern_result.get('综合信号','中性')}（看多{pattern_result.get('看多形态数',0)} / 看空{pattern_result.get('看空形态数',0)}）
      </div>
    </div>
  </div>
</div>

<div class="chart-box">
  <div class="ch"><h3>AI 评分雷达图</h3><span class="badge tag-purple">六维度</span></div>
  <div class="chart-c chart-sm" id="radarChart"></div>
</div>

<!-- ══════════ 模块七：AI 趋势预测 ══════════ -->
<div class="card">
  <div class="card-header">
    <h2><span style="color:var(--yellow);">⑦</span> AI 趋势预测</h2>
    <span class="badge tag-yellow">{trend_pred['方向']} · {trend_pred['置信度']}置信</span>
  </div>
  {"<div style='padding:0 0 12px 0;font-size:13px;line-height:1.8;color:var(--text);'>"+llm_trend_html+"</div>" if llm_mode and llm_trend_html else ""}
  <div class="grid2">
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">预测依据</h3>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">"""

for reason in trend_pred["依据"]:
    html += f'        <span class="tag tag-blue">{reason}</span>\n'

html += f"""      </div>
      <div style="margin-top:14px;padding:12px;background:rgba(255,255,255,.02);border-radius:8px;">
        <div class="row"><span>趋势得分</span><span class="val">{trend_pred['得分']}/100</span></div>
        <div class="row"><span>方向判定</span><span class="val" style="font-size:15px;">{trend_pred['方向']}</span></div>
        <div class="row"><span>置信度</span><span class="val">{trend_pred['置信度']}</span></div>
        <div class="row"><span>当前价</span><span class="val">{trend_pred['当前价']}</span></div>
      </div>
    </div>
    <div>
      <h3 style="font-size:13px;color:var(--dim);margin-bottom:12px;">未来5日价格预测</h3>
      <div class="chart-c chart-sm" id="predChart"></div>
    </div>
  </div>
</div>

<div class="final-card">
  <h2 style="font-size:12px;color:var(--dim);letter-spacing:3px;margin-bottom:8px;">综合结论</h2>
  <div class="fn" style="color:{op_advice['color']};">{final_score:.2f}</div>
  <div class="stars">{stars}</div>
  <div style="font-size:13px;color:var(--dim);margin-top:6px;">AI评分 {ai_score.get('综合评分','—')}/100 · {ai_score.get('投资评级','—')} · 风险{ai_risk.get('风险等级','—')}</div>
  <div class="tag-big" style="background:{op_advice['color']};color:#fff;">{op_advice['action']}</div>
</div>

<div class="footer">
  <p>🎋 竹林司马 AI 技术分析系统 v2.0</p>
  <p>分析引擎：{'🤖 '+llm_provider_name+' 大模型增强' if llm_mode else '📊 规则引擎（AIScoreEngine + SignalFusion + PatternRecognition + AIRiskEngine + AIRecommender）'} · 数据来源：腾讯财经 + 新浪分时</p>
  <p>大模型增强模式：LLM增强(llm_enhanced) / 多角色辩论(multi_perspective) / 交互式(interactive)</p>
  <p>⚠️ 以上分析基于技术指标和量化模型，仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</p>
</div>

</div>

<script>
// K线图
(function(){{
  const c = echarts.init(document.getElementById('klineChart'),'dark');
  const d={json.dumps(dates)};
  const o={json.dumps([[round(a,2),round(b,2),round(cc,2),round(dd,2)] for a,b,cc,dd in zip(open_,close,low,high)])};
  c.setOption({{backgroundColor:'#141720',tooltip:{{trigger:'axis',axisPointer:{{type:'cross'}}}},
    legend:{{data:['MA5','MA10','MA20','MA60'],top:0,textStyle:{{color:'#6b7080',fontSize:11}}}},
    grid:{{left:'7%',right:'3%',top:'12%',bottom:'14%'}},
    xAxis:{{type:'category',data:d,axisLabel:{{color:'#6b7080',fontSize:10}},axisLine:{{lineStyle:{{color:'#252a3a'}}}}}},
    yAxis:{{type:'value',scale:true,axisLabel:{{color:'#6b7080'}},splitLine:{{lineStyle:{{color:'#252a3a',type:'dashed'}}}}}},
    dataZoom:[{{type:'inside',start:60,end:100}},{{type:'slider',start:60,end:100,height:18,bottom:4}}],
    series:[
      {{name:'K线',type:'candlestick',data:o,itemStyle:{{color:'#ef4444',color0:'#22c55e',borderColor:'#ef4444',borderColor0:'#22c55e'}}}},
      {{name:'MA5',type:'line',data:{json.dumps(to_json(ma5))},smooth:true,showSymbol:false,lineStyle:{{color:'#ef4444',width:1}}}},
      {{name:'MA10',type:'line',data:{json.dumps(to_json(ma10))},smooth:true,showSymbol:false,lineStyle:{{color:'#f59e0b',width:1}}}},
      {{name:'MA20',type:'line',data:{json.dumps(to_json(ma20))},smooth:true,showSymbol:false,lineStyle:{{color:'#3b82f6',width:1.3}}}},
      {{name:'MA60',type:'line',data:{json.dumps(to_json(ma60))},smooth:true,showSymbol:false,lineStyle:{{color:'#a855f7',width:1.3}}}}
    ]}});
  window.addEventListener('resize',()=>c.resize());
}})();

// MACD+RSI+KDJ
(function(){{
  const c=echarts.init(document.getElementById('momentumChart'),'dark');
  const d={json.dumps(dates)};
  c.setOption({{backgroundColor:'#141720',tooltip:{{trigger:'axis'}},
    legend:{{data:['DIF','Signal','MACD柱','RSI6','RSI14','K','D','J'],top:0,textStyle:{{color:'#6b7080',fontSize:10}}}},
    grid:[{{left:'7%',right:'3%',top:'9%',height:'22%'}},{{left:'7%',right:'3%',top:'39%',height:'22%'}},{{left:'7%',right:'3%',top:'69%',height:'22%'}}],
    xAxis:[{{type:'category',data:d,gridIndex:0,show:false}},{{type:'category',data:d,gridIndex:1,show:false}},{{type:'category',data:d,gridIndex:2,axisLabel:{{color:'#6b7080',fontSize:10}},axisLine:{{lineStyle:{{color:'#252a3a'}}}}}}],
    yAxis:[{{type:'value',gridIndex:0,axisLabel:{{color:'#6b7080',fontSize:10}},splitLine:{{lineStyle:{{color:'#252a3a',type:'dashed'}}}}}},
           {{type:'value',gridIndex:1,min:0,max:100,axisLabel:{{color:'#6b7080',fontSize:10}},splitLine:{{lineStyle:{{color:'#252a3a',type:'dashed'}}}}}},
           {{type:'value',gridIndex:2,min:0,max:120,axisLabel:{{color:'#6b7080',fontSize:10}},splitLine:{{lineStyle:{{color:'#252a3a',type:'dashed'}}}}}}],
    series:[
      {{name:'DIF',type:'line',xAxisIndex:0,yAxisIndex:0,data:{json.dumps(to_json(macd_data['macd']))},showSymbol:false,lineStyle:{{color:'#3b82f6'}}}},
      {{name:'Signal',type:'line',xAxisIndex:0,yAxisIndex:0,data:{json.dumps(to_json(macd_data['signal']))},showSymbol:false,lineStyle:{{color:'#f59e0b'}}}},
      {{name:'MACD柱',type:'bar',xAxisIndex:0,yAxisIndex:0,data:{json.dumps(to_json(macd_data['histogram']))},itemStyle:{{color:function(p){{return p.value>=0?'#ef4444':'#22c55e';}}}}}},
      {{name:'RSI6',type:'line',xAxisIndex:1,yAxisIndex:1,data:{json.dumps(to_json(rsi6))},showSymbol:false,lineStyle:{{color:'#06b6d4'}}}},
      {{name:'RSI14',type:'line',xAxisIndex:1,yAxisIndex:1,data:{json.dumps(to_json(rsi14))},showSymbol:false,lineStyle:{{color:'#a855f7'}}}},
      {{name:'K',type:'line',xAxisIndex:2,yAxisIndex:2,data:{json.dumps(to_json(kdj['k']))},showSymbol:false,lineStyle:{{color:'#3b82f6'}}}},
      {{name:'D',type:'line',xAxisIndex:2,yAxisIndex:2,data:{json.dumps(to_json(kdj['d']))},showSymbol:false,lineStyle:{{color:'#f59e0b'}}}},
      {{name:'J',type:'line',xAxisIndex:2,yAxisIndex:2,data:{json.dumps(to_json(kdj['j']))},showSymbol:false,lineStyle:{{color:'#ef4444'}}}}
    ]}});
  window.addEventListener('resize',()=>c.resize());
}})();

// 分时量能饼图
(function(){{
  const el = document.getElementById('minutePieChart');
  if (!el) return;
  const c = echarts.init(el,'dark');
  const pieData = {minute_dist_json if minute_analysis.get('available') else '[]'};
  if (pieData.length > 0) {{
    c.setOption({{backgroundColor:'#141720',
      tooltip:{{trigger:'item',formatter:'{{b}}: {{c}}手 ({{d}}%)'}},
      series:[{{type:'pie',radius:['42%','72%'],center:['50%','50%'],
        data:pieData,
        label:{{color:'#6b7080',fontSize:11,formatter:'{{b}}\\n{{d}}%'}},
        itemStyle:{{borderColor:'#141720',borderWidth:2}},
        color:['#06b6d4','#6366f1','#f59e0b','#ef4444']
      }}]}});
  }}
  window.addEventListener('resize',()=>c.resize());
}})();

// 雷达图
(function(){{
  const c=echarts.init(document.getElementById('radarChart'),'dark');
  const dims={json.dumps(list(ai_dims.keys()))};
  const scores={json.dumps(list(ai_dims.values()))};
  c.setOption({{backgroundColor:'#141720',
    radar:{{indicator:dims.map(n=>({{name:n,max:100}})),shape:'polygon',splitNumber:5,
      axisName:{{color:'#6b7080',fontSize:11}},splitLine:{{lineStyle:{{color:'#252a3a'}}}},
      splitArea:{{areaStyle:{{color:['rgba(99,102,241,.01)','rgba(99,102,241,.03)','rgba(99,102,241,.05)','rgba(99,102,241,.07)','rgba(99,102,241,.09)']}}}},
      axisLine:{{lineStyle:{{color:'#252a3a'}}}}}},
    series:[{{type:'radar',data:[{{value:scores,name:'AI评分',areaStyle:{{color:'rgba(99,102,241,.18)'}},lineStyle:{{color:'#6366f1',width:2}},itemStyle:{{color:'#6366f1'}}}}]}}]}});
  window.addEventListener('resize',()=>c.resize());
}})();

// 趋势预测图
(function(){{
  const c=echarts.init(document.getElementById('predChart'),'dark');
  const predDates=[];const predVals={json.dumps(trend_pred['预测5日价'])};
  const curDate='{dates[-1]}';
  for(let i=1;i<=5;i++){{
    const d=new Date(curDate);
    d.setDate(d.getDate()+i);
    predDates.push((d.getMonth()+1)+'/'+d.getDate());
  }}
  c.setOption({{backgroundColor:'#141720',
    tooltip:{{trigger:'axis'}},
    grid:{{left:'12%',right:'5%',top:'10%',bottom:'18%'}},
    xAxis:{{type:'category',data:['今日(D0)',...predDates],axisLabel:{{color:'#6b7080',fontSize:11}},axisLine:{{lineStyle:{{color:'#252a3a'}}}}}},
    yAxis:{{type:'value',min:Math.min({trend_pred['当前价']},...predVals)*0.99,max:Math.max({trend_pred['当前价']},...predVals)*1.01,
      axisLabel:{{color:'#6b7080',formatter:'{{value}}'}},splitLine:{{lineStyle:{{color:'#252a3a',type:'dashed'}}}}}},
    series:[
      {{name:'预测价格',type:'line',data:[{trend_pred['当前价']},...predVals],
        lineStyle:{{color:'#f59e0b',width:2,type:'dashed'}},
        itemStyle:{{color:'#f59e0b'}},symbol:'circle',symbolSize:8,
        markLine:{{data:[{{yAxis:{trend_pred['当前价']},name:'当前价',lineStyle:{{color:'#6366f1',type:'solid',width:1}}}}],label:{{color:'#6366f1',fontSize:11}}}}}},
      {{name:'置信区间上',type:'line',data:[{trend_pred['当前价']},...predVals.map(v=>(v*1.005).toFixed(2))],
        lineStyle:{{color:'rgba(249,115,22,.2)',width:1}},symbol:'none',
        areaStyle:{{color:'rgba(249,115,22,.06)'}}}},
      {{name:'置信区间下',type:'line',data:[{trend_pred['当前价']},...predVals.map(v=>(v*0.995).toFixed(2))],
        lineStyle:{{color:'rgba(249,115,22,.2)',width:1}},symbol:'none'}}
    ]}});
  window.addEventListener('resize',()=>c.resize());
}})();
</script>
</body>
</html>
"""

output_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, f'{STOCK_CODE}_analysis_{date.today()}.html')

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ 报告已生成: {output_path}")
print(f"   文件大小: {os.path.getsize(output_path)/1024:.1f} KB")
