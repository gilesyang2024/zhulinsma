#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyFactor 选股战法分析
山东钢铁(600022.SH) + 国电南瑞(600406.SH)
"""

import sys
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 添加路径
sys.path.insert(0, '/Users/gilesyang/WorkBuddy/20260324203553/EasyXT/easy_xt')
sys.path.insert(0, '/Users/gilesyang/WorkBuddy/20260324203553/EasyXT/easyxt_backtest')
sys.path.insert(0, '/Users/gilesyang/WorkBuddy/20260324203553')

import akshare as ak
import numpy as np
import pandas as pd

# ==============================
# 核心技术指标计算
# ==============================

def calc_ma(series, window):
    return series.rolling(window=window, min_periods=1).mean()

def calc_ema(series, window):
    return series.ewm(span=window, adjust=False).mean()

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(close, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd_hist = (dif - dea) * 2
    return dif, dea, macd_hist

def calc_boll(close, window=20, num_std=2):
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower

def calc_kdj(high, low, close, n=9, m1=3, m2=3):
    low_min = low.rolling(window=n, min_periods=1).min()
    high_max = high.rolling(window=n, min_periods=1).max()
    rsv = (close - low_min) / (high_max - low_min + 1e-9) * 100
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j

def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_obv(close, volume):
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (volume * direction).cumsum()

# ==============================
# 多维度打分系统
# ==============================

def score_trend(df):
    """趋势得分（0-10）"""
    c = df['收盘']
    scores = []
    
    # MA多头排列
    ma5 = calc_ma(c, 5).iloc[-1]
    ma10 = calc_ma(c, 10).iloc[-1]
    ma20 = calc_ma(c, 20).iloc[-1]
    ma60 = calc_ma(c, 60).iloc[-1]
    cur = c.iloc[-1]
    
    ma_score = 0
    if cur > ma5: ma_score += 1
    if cur > ma10: ma_score += 1
    if cur > ma20: ma_score += 1.5
    if cur > ma60: ma_score += 1.5
    if ma5 > ma10 > ma20: ma_score += 2
    if ma10 > ma60: ma_score += 2
    
    # 20日涨跌幅
    change_20 = (cur - c.iloc[-20]) / c.iloc[-20] * 100
    trend_score = min(max(change_20 / 10, -2), 2) + 5
    
    final = min((ma_score / 9 * 6) + (trend_score / 10 * 4), 10)
    return round(final, 2), {
        'MA多头得分': round(ma_score, 2),
        '20日涨幅': round(change_20, 2),
        'MA5': round(ma5, 3),
        'MA10': round(ma10, 3),
        'MA20': round(ma20, 3),
        'MA60': round(ma60, 3),
    }

def score_momentum(df):
    """动量得分（0-10）"""
    c = df['收盘']
    h = df['最高']
    l = df['最低']
    
    rsi = calc_rsi(c).iloc[-1]
    dif, dea, hist = calc_macd(c)
    k, d, j = calc_kdj(h, l, c)
    
    # RSI得分：50-70最佳
    if 45 <= rsi <= 70:
        rsi_score = 8 + (rsi - 45) / 25 * 2
    elif rsi < 30:
        rsi_score = 6  # 超卖反弹机会
    elif rsi > 80:
        rsi_score = 3  # 超买风险
    else:
        rsi_score = 5
    
    # MACD得分
    macd_score = 7 if hist.iloc[-1] > 0 else 4
    if dif.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]:
        macd_score += 2
    
    # KDJ得分
    kv, dv, jv = k.iloc[-1], d.iloc[-1], j.iloc[-1]
    if 20 <= kv <= 80 and kv > dv:
        kdj_score = 7
    elif kv < 20:
        kdj_score = 6  # 超卖
    else:
        kdj_score = 4
    
    final = (rsi_score * 0.35 + macd_score * 0.40 + kdj_score * 0.25)
    return round(final, 2), {
        'RSI14': round(rsi, 2),
        'MACD_DIF': round(dif.iloc[-1], 4),
        'MACD_DEA': round(dea.iloc[-1], 4),
        'MACD_柱': round(hist.iloc[-1], 4),
        'KDJ_K': round(kv, 2),
        'KDJ_D': round(dv, 2),
        'KDJ_J': round(jv, 2),
    }

def score_volatility(df):
    """波动/风险得分（0-10），分越高风险越低"""
    c = df['收盘']
    h = df['最高']
    l = df['最低']
    
    atr = calc_atr(h, l, c).iloc[-1]
    atr_pct = atr / c.iloc[-1] * 100
    
    # 20日波动率
    returns = c.pct_change().dropna()
    vol_20 = returns.tail(20).std() * np.sqrt(252) * 100
    
    # 布林带位置
    upper, mid, lower = calc_boll(c)
    boll_pct = (c.iloc[-1] - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1] + 1e-9)
    
    # 波动越低得分越高
    if vol_20 < 20:
        vol_score = 8
    elif vol_20 < 35:
        vol_score = 6
    elif vol_20 < 50:
        vol_score = 4
    else:
        vol_score = 2
    
    # 布林带中间位置最理想
    if 0.3 <= boll_pct <= 0.7:
        boll_score = 8
    elif boll_pct > 0.9:
        boll_score = 3
    elif boll_pct < 0.1:
        boll_score = 5
    else:
        boll_score = 6
    
    final = vol_score * 0.5 + boll_score * 0.5
    return round(final, 2), {
        'ATR': round(atr, 3),
        'ATR%': round(atr_pct, 2),
        '年化波动率%': round(vol_20, 2),
        '布林带位置': round(boll_pct, 3),
        '布林上轨': round(upper.iloc[-1], 3),
        '布林中轨': round(mid.iloc[-1], 3),
        '布林下轨': round(lower.iloc[-1], 3),
    }

def score_volume_price(df):
    """量价关系得分（0-10）"""
    c = df['收盘']
    v = df['成交量']
    
    # OBV趋势
    obv = calc_obv(c, v)
    obv_5ma = calc_ma(obv, 5)
    obv_up = obv.iloc[-1] > obv_5ma.iloc[-1]
    
    # 量比（近3日均量 vs 近20日均量）
    vol_3 = v.tail(3).mean()
    vol_20 = v.tail(20).mean()
    vol_ratio = vol_3 / (vol_20 + 1e-9)
    
    # 近期价量配合
    price_up = c.iloc[-1] > c.iloc[-5]
    vol_up = v.iloc[-1] > v.iloc[-5]
    
    pv_score = 7
    if price_up and vol_up:
        pv_score = 9  # 量价齐升
    elif not price_up and not vol_up:
        pv_score = 5  # 量价齐跌
    elif price_up and not vol_up:
        pv_score = 6  # 价涨量缩（需谨慎）
    
    # 量比得分
    if 1.2 <= vol_ratio <= 2.5:
        vr_score = 8
    elif vol_ratio > 3:
        vr_score = 7  # 放量
    elif vol_ratio < 0.5:
        vr_score = 4  # 缩量
    else:
        vr_score = 6
    
    obv_score = 8 if obv_up else 4
    
    final = pv_score * 0.4 + vr_score * 0.35 + obv_score * 0.25
    return round(final, 2), {
        'OBV方向': '上升' if obv_up else '下降',
        '量比(3d/20d)': round(vol_ratio, 2),
        '价量配合': '量价齐升' if (price_up and vol_up) else ('价涨量缩' if (price_up and not vol_up) else ('放量下跌' if (not price_up and vol_up) else '量价齐跌')),
        '当日成交量': f'{v.iloc[-1]/10000:.1f}万手',
        '20日均量': f'{vol_20/10000:.1f}万手',
    }

def score_fundamental(symbol, name):
    """基本面得分（使用市场数据简估）"""
    try:
        # 获取最新股票基本信息
        info = ak.stock_individual_info_em(symbol=symbol)
        info_dict = dict(zip(info['item'], info['value']))
        
        score = 5.0  # 基础分
        details = {}
        
        # 市盈率
        pe_raw = info_dict.get('市盈率(动)', info_dict.get('市盈率', None))
        if pe_raw and pe_raw not in ['-', '--', 'None', None]:
            try:
                pe = float(str(pe_raw).replace(',', ''))
                details['市盈率(动)'] = round(pe, 2)
                if 0 < pe < 15:
                    score += 2
                elif 15 <= pe < 30:
                    score += 1
                elif pe > 60:
                    score -= 1
            except:
                pass
        
        # 市净率
        pb_raw = info_dict.get('市净率', None)
        if pb_raw and pb_raw not in ['-', '--', 'None', None]:
            try:
                pb = float(str(pb_raw).replace(',', ''))
                details['市净率'] = round(pb, 2)
                if 0 < pb < 1.5:
                    score += 1.5
                elif pb < 3:
                    score += 0.5
                elif pb > 8:
                    score -= 0.5
            except:
                pass
        
        # 总市值
        mc_raw = info_dict.get('总市值', None)
        if mc_raw and mc_raw not in ['-', '--', 'None', None]:
            details['总市值'] = str(mc_raw)
        
        # 流通市值
        fmc_raw = info_dict.get('流通市值', None)
        if fmc_raw:
            details['流通市值'] = str(fmc_raw)
        
        return round(min(score, 10), 2), details
        
    except Exception as e:
        return 6.0, {'备注': f'基本面数据获取中({e})'}

# ==============================
# 主分析函数
# ==============================

def analyze_stock(symbol, name, days=120):
    print(f"\n{'='*60}")
    print(f"📊 开始分析: {name} ({symbol}.SH)")
    print(f"{'='*60}")
    
    # 获取历史数据
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
    
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol, period='daily',
            start_date=start_date, end_date=end_date,
            adjust='qfq'
        )
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        return None
    
    if df.empty or len(df) < 30:
        print(f"❌ 数据不足: 仅 {len(df)} 条")
        return None
    
    df = df.tail(days).copy().reset_index(drop=True)
    print(f"✅ 获取数据 {len(df)} 条，最新: {df['日期'].iloc[-1]}")
    
    cur_price = df['收盘'].iloc[-1]
    prev_close = df['收盘'].iloc[-2]
    daily_change = (cur_price - prev_close) / prev_close * 100
    
    print(f"\n当前价格: {cur_price:.3f}  今日涨跌: {daily_change:+.2f}%")
    
    # 各维度评分
    trend_score, trend_detail = score_trend(df)
    momentum_score, momentum_detail = score_momentum(df)
    volatility_score, vol_detail = score_volatility(df)
    vp_score, vp_detail = score_volume_price(df)
    fundamental_score, fund_detail = score_fundamental(symbol, name)
    
    # 综合加权评分
    weights = {
        '趋势强度': 0.25,
        '动量信号': 0.25,
        '波动特征': 0.15,
        '量价关系': 0.20,
        '基本面': 0.15
    }
    
    scores = {
        '趋势强度': trend_score,
        '动量信号': momentum_score,
        '波动特征': volatility_score,
        '量价关系': vp_score,
        '基本面': fundamental_score
    }
    
    total = sum(scores[k] * weights[k] for k in scores)
    
    # 投资评级
    if total >= 8.0:
        rating = '★★★★★ 强烈看好'
        action = '积极买入'
        color = '🟢🟢'
    elif total >= 7.0:
        rating = '★★★★ 看好'
        action = '买入'
        color = '🟢'
    elif total >= 6.0:
        rating = '★★★ 中性偏多'
        action = '观察/轻仓'
        color = '🟡'
    elif total >= 5.0:
        rating = '★★ 中性'
        action = '观望'
        color = '⚪'
    else:
        rating = '★ 谨慎'
        action = '回避'
        color = '🔴'
    
    print(f"\n{'─'*50}")
    print(f"📈 各维度评分:")
    for dim, score in scores.items():
        bar = '█' * int(score) + '░' * (10 - int(score))
        print(f"  {dim:6s}: [{bar}] {score:4.1f}/10")
    print(f"{'─'*50}")
    print(f"  综合评分: {total:.2f}/10   {color}")
    print(f"  投资评级: {rating}")
    print(f"  操作建议: {action}")
    
    # 输出详细指标
    print(f"\n📌 趋势指标: {trend_detail}")
    print(f"📌 动量指标: {momentum_detail}")
    print(f"📌 波动指标: {vol_detail}")
    print(f"📌 量价指标: {vp_detail}")
    print(f"📌 基本面:   {fund_detail}")
    
    result = {
        'name': name,
        'symbol': symbol,
        'cur_price': cur_price,
        'daily_change': daily_change,
        'scores': scores,
        'total_score': round(total, 2),
        'rating': rating,
        'action': action,
        'details': {
            '趋势': trend_detail,
            '动量': momentum_detail,
            '波动': vol_detail,
            '量价': vp_detail,
            '基本面': fund_detail
        },
        'data_date': df['日期'].iloc[-1]
    }
    
    return result

# ==============================
# 主程序
# ==============================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  EasyFactor 选股战法分析系统  v2.0")
    print("  基于多因子打分模型")
    print("="*60)
    print(f"  分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    stocks = [
        ('600022', '山东钢铁'),
        ('600406', '国电南瑞'),
    ]
    
    results = []
    for sym, name in stocks:
        res = analyze_stock(sym, name, days=120)
        if res:
            results.append(res)
    
    # 对比总结
    if len(results) >= 2:
        print(f"\n\n{'='*60}")
        print("  📊 两股对比总结")
        print(f"{'='*60}")
        print(f"\n{'股票名称':<10} {'当前价':<8} {'今日涨跌':<10} {'综合评分':<10} {'操作建议'}")
        print('─'*60)
        for r in results:
            chg_str = f"{r['daily_change']:+.2f}%"
            print(f"{r['name']:<10} {r['cur_price']:<8.3f} {chg_str:<10} {r['total_score']:<10.2f} {r['action']}")
        
        # 推荐
        best = max(results, key=lambda x: x['total_score'])
        print(f"\n🏆 综合评分更高: {best['name']} ({best['total_score']:.2f}分)")
        
        # 保存JSON
        out_path = '/Users/gilesyang/WorkBuddy/20260324203553/easyfactor_results.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 分析结果已保存: {out_path}")
    
    print("\n分析完成！")
