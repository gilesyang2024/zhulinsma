#!/usr/bin/env python3
"""
竹林司马 - 大模型增强版主程序
版本: 2.0.0
日期: 2026年4月15日

对应操作指南第十一章「大模型增强模式」的命令行入口。

支持三种模式:
1. llm_enhanced  - LLM增强模式（单分析师，深度解读）
2. multi_perspective - 多角度辩论模式（四大角色辩论）
3. interactive    - 交互式分析模式（持续对话追问）

用法:
    # LLM增强模式
    python zhulinsma_with_llm.py --mode llm_enhanced --stock 600875

    # 多角度辩论模式
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875

    # 交互式分析
    python zhulinsma_with_llm.py --mode interactive --stock 600875

    # 指定供应商和模型
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 \\
        --provider deepseek --model deepseek-chat --api-key sk-xxx

    # 生成HTML报告
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 --report
"""

import sys
import os
import json
import argparse
import urllib.request
import warnings
from datetime import datetime, date

warnings.filterwarnings("ignore")

# 项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 清除代理环境变量
for k in list(os.environ.keys()):
    if k.lower().endswith("_proxy"):
        os.environ.pop(k, None)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="竹林司马 - 大模型增强版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python zhulinsma_with_llm.py --mode llm_enhanced --stock 600875
  python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 --report
  python zhulinsma_with_llm.py --mode interactive --stock 600875
        """,
    )

    parser.add_argument("--mode", "-m", type=str, default="llm_enhanced",
                        choices=["llm_enhanced", "multi_perspective", "interactive"],
                        help="分析模式: llm_enhanced / multi_perspective / interactive")
    parser.add_argument("--stock", "-s", type=str, required=True,
                        help="股票代码 (如 600875)")
    parser.add_argument("--name", "-n", type=str, default="",
                        help="股票名称 (可选，如不指定则自动获取)")
    parser.add_argument("--provider", "-p", type=str, default="",
                        help="LLM供应商: deepseek / openai / qwen / glm / ollama")
    parser.add_argument("--model", type=str, default="",
                        help="模型名称 (如 deepseek-chat, gpt-4o-mini)")
    parser.add_argument("--api-key", type=str, default="",
                        help="API密钥 (也可通过环境变量 LLM_API_KEY 设置)")
    parser.add_argument("--report", "-r", action="store_true",
                        help="生成HTML报告")
    parser.add_argument("--output", "-o", type=str, default="",
                        help="报告输出路径 (默认 reports/ 目录)")
    parser.add_argument("--temperature", "-t", type=float, default=0.3,
                        help="LLM温度 (0.0-1.0, 默认0.3)")

    return parser.parse_args()


def fetch_realtime(symbol):
    """获取实时行情"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    fields = resp.read().decode("gbk").split("~")
    if len(fields) > 46:
        return {
            "name": fields[1], "code": fields[2],
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
            "turnover": float(fields[38]) if fields[38] else 0,
        }
    return None


def fetch_kline(symbol, days=120):
    """获取日K线"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    raw = json.loads(resp.read().decode("utf-8"))
    klines = raw["data"][symbol]["qfqday"]
    return [
        {"date": k[0], "open": float(k[1]), "close": float(k[2]),
         "high": float(k[3]), "low": float(k[4]), "volume": float(k[5]) * 100}
        for k in klines[-days:]
    ]


def prepare_analysis_data(stock_code, stock_name, symbol):
    """准备分析所需的数据"""
    import numpy as np
    import pandas as pd

    print(f"📡 获取 {stock_name}({stock_code}) 数据...")

    # 获取数据
    records = fetch_kline(symbol, days=120)
    realtime = fetch_realtime(symbol)

    if not records:
        print("❌ 无法获取K线数据")
        return None

    df = pd.DataFrame(records)
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    volume = df["volume"].values.astype(float)

    # 计算技术指标
    from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
    ti = TechnicalIndicators(验证模式=False)

    ma5 = ti.SMA(close, 5)
    ma10 = ti.SMA(close, 10)
    ma20 = ti.SMA(close, 20)
    ma60 = ti.SMA(close, min(60, len(close)))
    rsi6, rsi14 = ti.RSI(close, 6), ti.RSI(close, 14)
    macd_data = ti.MACD(close)
    boll = ti.BollingerBands(close, 20)

    # KDJ
    K, D = 50.0, 50.0
    for i in range(len(close)):
        s = max(0, i - 8)
        hn, ln = np.max(high[s:i + 1]), np.min(low[s:i + 1])
        rsv = (close[i] - ln) / (hn - ln + 1e-10) * 100
        K, D = (2 / 3) * K + (1 / 3) * rsv, (2 / 3) * D + (1 / 3) * K
    J = 3 * K - 2 * D

    # 基础分析
    current_price = float(close[-1])
    chg = realtime["change_pct"] if realtime else 0

    vol_5d_avg = np.mean(volume[-5:])
    vol_20d_avg = np.mean(volume[-20:])
    vol_ratio = vol_5d_avg / (vol_20d_avg + 1e-10)
    recent_5d_chg = (close[-1] - close[-6]) / close[-6] * 100 if len(close) > 5 else 0
    recent_20d_chg = (close[-1] - close[-21]) / close[-21] * 100 if len(close) > 20 else 0

    bull_arrange = ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]

    # 战法信号
    vol_std_ratio = np.std(volume[-5:]) / (np.mean(volume[-5:]) + 1e-10)
    price_range_ratio = (np.max(close[-5:]) - np.min(close[-5:])) / (np.min(close[-5:]) + 1e-10)

    strategy_signals = [
        {"名称": "锁仓K线", "触发": vol_std_ratio < 0.15 and price_range_ratio < 0.04,
         "信号类型": "买入", "评分": 85 if vol_std_ratio < 0.15 and price_range_ratio < 0.04 else 0,
         "说明": f"量能波动{vol_std_ratio:.2f}+价格波动{price_range_ratio:.2f}"},
        {"名称": "竞价弱转强", "触发": False, "信号类型": "买入", "评分": 0,
         "说明": "需竞价数据（盘中分析）"},
        {"名称": "利刃出鞘",
         "触发": close[-1] >= np.max(high[-20:]) * 0.97 and rsi14[-1] > 50,
         "信号类型": "买入",
         "评分": 75 if close[-1] >= np.max(high[-20:]) * 0.97 and rsi14[-1] > 50 else 0,
         "说明": f"接近20日高点{close[-1] / np.max(high[-20:]) * 100:.1f}%"},
        {"名称": "涨停板回踩",
         "触发": abs(close[-1] - ma20[-1]) / ma20[-1] < 0.03 and price_range_ratio < 0.05,
         "信号类型": "买入",
         "评分": 80 if abs(close[-1] - ma20[-1]) / ma20[-1] < 0.03 else 0,
         "说明": f"偏离MA20 {abs(close[-1] - ma20[-1]) / ma20[-1] * 100:.2f}%"},
    ]

    # AI引擎
    from zhulinsma.core.ai import AIScoreEngine, SignalFusion, PatternRecognition, AIRiskEngine

    score_engine = AIScoreEngine()
    ai_score = score_engine.评分(df, strategy_signals)

    fusion_engine = SignalFusion()
    fusion_result = fusion_engine.融合(strategy_signals)

    pattern_engine = PatternRecognition()
    pattern_result = pattern_engine.识别(df, 最近N日=5)

    risk_engine = AIRiskEngine()
    ai_risk = risk_engine.评估(df)

    # 构造技术面数据
    technical_data = {
        "均线排列": "多头排列" if bull_arrange else "空头排列" if ma5[-1] < ma10[-1] < ma20[-1] else "交织",
        f"MA5/MA10/MA20/MA60": f"{ma5[-1]:.2f} / {ma10[-1]:.2f} / {ma20[-1]:.2f} / {ma60[-1]:.2f}",
        f"当前价 vs MA60": f"{'上方' if close[-1] > ma60[-1] else '下方'}",
        f"MACD DIF/Signal": f"{macd_data['macd'][-1]:.4f} / {macd_data['signal'][-1]:.4f}",
        "MACD柱状图": f"{macd_data['histogram'][-1]:.4f}" if len(macd_data["histogram"]) > 0 else "N/A",
        f"RSI6/RSI14": f"{rsi6[-1]:.1f} / {rsi14[-1]:.1f}",
        f"KDJ K/D/J": f"{K:.1f} / {D:.1f} / {J:.1f}",
        "布林上/中/下轨": f"{boll['upper'][-1]:.2f} / {boll['middle'][-1]:.2f} / {boll['lower'][-1]:.2f}",
        "5日/20日量比": f"{vol_ratio:.2f}",
        "量价关系": "放量上涨" if vol_ratio > 1.0 and recent_5d_chg > 0 else
                    "缩量下跌" if vol_ratio < 1.0 and recent_5d_chg < 0 else
                    "放量下跌" if vol_ratio > 1.0 and recent_5d_chg < 0 else "缩量横盘",
        "近5日涨跌幅": f"{recent_5d_chg:+.2f}%",
        "近20日涨跌幅": f"{recent_20d_chg:+.2f}%",
    }

    # 基本面数据
    pe = realtime["pe"] if realtime and realtime["pe"] > 0 else 0
    pb = realtime["pb"] if realtime else 0
    cap = realtime["market_cap"] if realtime else 0

    fundamental_data = {
        "市盈率(PE)": f"{pe:.1f}" if pe > 0 else "N/A",
        "市净率(PB)": f"{pb:.2f}" if pb > 0 else "N/A",
        "总市值(亿)": f"{cap:.0f}" if cap > 0 else "N/A",
        "换手率": f"{realtime['turnover']:.1f}%" if realtime else "N/A",
    }

    # 风险数据
    risk_detail = ai_risk.get("风险明细", {})
    risk_data = {
        "风险等级": ai_risk.get("风险等级", "N/A"),
        "综合风险分": ai_risk.get("综合风险分数", "N/A"),
        "ATR止损位": ai_risk.get("止损位", "N/A"),
        "止盈(保守/基准/乐观)": f"保守{ai_risk.get('止盈目标', {}).get('保守', 'N/A')} / 基准{ai_risk.get('止盈目标', {}).get('基准', 'N/A')} / 乐观{ai_risk.get('止盈目标', {}).get('乐观', 'N/A')}",
        "仓位上限": ai_risk.get("仓位上限", "N/A"),
        "年化波动率": risk_detail.get("年化波动率", "N/A"),
        "最大回撤(20日)": risk_detail.get("最大回撤", "N/A"),
    }

    return {
        "df": df,
        "realtime": realtime,
        "current_price": current_price,
        "technical_data": technical_data,
        "fundamental_data": fundamental_data,
        "strategy_signals": strategy_signals,
        "risk_data": risk_data,
        "ai_score": ai_score,
        "fusion_result": fusion_result,
        "pattern_result": pattern_result,
        "ai_risk": ai_risk,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "rsi6": rsi6, "rsi14": rsi14,
        "macd_data": macd_data,
        "kdj": {"k": K, "d": D, "j": J},
        "boll": boll,
        "vol_ratio": vol_ratio,
        "recent_5d_chg": recent_5d_chg,
        "recent_20d_chg": recent_20d_chg,
        "bull_arrange": bull_arrange,
    }


def run_llm_enhanced(args, data):
    """模式一: LLM增强模式（单分析师深度解读）"""
    from zhulinsma.core.llm.enhanced import EnhancedAnalysis

    print("\n" + "=" * 60)
    print("🤖 LLM 增强模式")
    print("=" * 60)

    llm_kwargs = {}
    if args.provider:
        llm_kwargs["provider"] = args.provider
    if args.model:
        llm_kwargs["model"] = args.model
    if args.api_key:
        llm_kwargs["api_key"] = args.api_key
    if args.temperature:
        llm_kwargs["temperature"] = args.temperature

    enhanced = EnhancedAnalysis(**llm_kwargs)

    if not enhanced.llm_available:
        print("❌ LLM 不可用，请检查:")
        print("   1. 是否设置了 LLM_API_KEY 环境变量")
        print("   2. 或使用 --api-key 参数")
        print("   3. 或使用 --provider ollama 启动本地模型")
        return None

    print(f"   ✅ {enhanced.mode} ({enhanced._client.info()['provider']} / {enhanced._client.info()['model']})")
    print("   📡 进行深度分析（约30-60秒）...")

    stock_code = args.stock
    stock_name = args.name or data["realtime"]["name"] if data["realtime"] else f"股票{stock_code}"

    price_info = {
        "close": data["current_price"],
        "change_pct": data["realtime"]["change_pct"] if data["realtime"] else 0,
        "recent_prices": [float(c) for c in data["df"]["close"].values[-10:]],
    }
    ma_data = {
        "arrangement": data["technical_data"]["均线排列"],
        "price_vs_ma5": data["technical_data"]["当前价 vs MA60"],
        "price_vs_ma10": data["technical_data"]["当前价 vs MA60"],
        "price_vs_ma20": data["technical_data"]["当前价 vs MA60"],
        "price_vs_ma60": data["technical_data"]["当前价 vs MA60"],
    }
    macd_data = {
        "dif": data["technical_data"]["MACD DIF/Signal"].split("/")[0].strip(),
        "signal": data["technical_data"]["MACD DIF/Signal"].split("/")[1].strip(),
        "histogram": data["technical_data"]["MACD柱状图"],
        "cross": "金叉" if len(data["macd_data"]["histogram"]) >= 2 and
                data["macd_data"]["histogram"][-2] < 0 < data["macd_data"]["histogram"][-1] else
                "死叉" if len(data["macd_data"]["histogram"]) >= 2 and
                data["macd_data"]["histogram"][-2] > 0 > data["macd_data"]["histogram"][-1] else "无",
    }
    rsi_data = {
        "rsi6": data["technical_data"]["RSI6/RSI14"].split("/")[0].strip(),
        "rsi14": data["technical_data"]["RSI6/RSI14"].split("/")[1].strip(),
        "status": "超买" if data["rsi14"][-1] > 70 else ("超卖" if data["rsi14"][-1] < 30 else "正常"),
    }
    kdj_data = {
        "k": f"{data['kdj']['k']:.1f}",
        "d": f"{data['kdj']['d']:.1f}",
        "j": f"{data['kdj']['j']:.1f}",
        "cross": "金叉" if data["kdj"]["k"] > data["kdj"]["d"] else "死叉",
    }
    volume_info = {
        "volume_ratio": data["technical_data"]["5日/20日量比"],
        "ma5_vs_ma20": data["technical_data"]["5日/20日量比"],
        "price_volume_relation": data["technical_data"]["量价关系"],
    }
    trend_info = {
        "short_term": "上涨" if data["recent_5d_chg"] > 0 else "下跌",
        "mid_term": "上涨" if data["recent_20d_chg"] > 0 else "下跌",
        "strength": f"{((data['current_price'] - (data['ma5'][-1] + data['ma10'][-1] + data['ma20'][-1] + data['ma60'][-1]) / 4) / ((data['ma5'][-1] + data['ma10'][-1] + data['ma20'][-1] + data['ma60'][-1]) / 4) * 100):+.2f}%",
    }

    result = enhanced.full_analysis(
        df=data["df"],
        stock_code=stock_code,
        stock_name=stock_name,
        strategy_signals=data["strategy_signals"],
        price_info=price_info,
        ma_data=ma_data,
        macd_data=macd_data,
        rsi_data=rsi_data,
        kdj_data=kdj_data,
        volume_info=volume_info,
        trend_info=trend_info,
    )

    return result


def run_multi_perspective(args, data):
    """模式二: 多角度辩论模式（四大角色辩论）"""
    from zhulinsma.core.llm.debate import MultiPerspectiveAgent

    print("\n" + "=" * 60)
    print("🎭 多角度辩论模式（四大角色深度分析）")
    print("=" * 60)

    llm_kwargs = {}
    if args.provider:
        llm_kwargs["provider"] = args.provider
    if args.model:
        llm_kwargs["model"] = args.model
    if args.api_key:
        llm_kwargs["api_key"] = args.api_key

    agent = MultiPerspectiveAgent(**llm_kwargs)

    # 检查LLM可用性
    if not agent.client.config.api_key and agent.client.config.provider.value != "ollama":
        print("❌ LLM 不可用，请检查:")
        print("   1. 是否设置了 LLM_API_KEY 环境变量")
        print("   2. 或使用 --api-key 参数")
        print("   3. 或使用 --provider ollama 启动本地模型")
        return None

    print(f"   ✅ 供应商: {agent.client.info()['provider']} / 模型: {agent.client.info()['model']}")
    print()

    stock_code = args.stock
    stock_name = args.name or data["realtime"]["name"] if data["realtime"] else f"股票{stock_code}"

    result = agent.analyze(
        stock_name=stock_name,
        stock_code=stock_code,
        current_price=data["current_price"],
        technical_data=data["technical_data"],
        fundamental_data=data["fundamental_data"],
        strategy_signals=data["strategy_signals"],
        risk_data=data["risk_data"],
    )

    return result


def run_interactive(args, data):
    """模式三: 交互式分析模式"""
    from zhulinsma.core.llm.client import LLMClient

    print("\n" + "=" * 60)
    print("💬 交互式分析模式")
    print("=" * 60)
    print("输入问题，AI将基于实时数据为你解答。输入 'quit' 或 '退出' 结束。")
    print()

    llm_kwargs = {}
    if args.provider:
        llm_kwargs["provider"] = args.provider
    if args.model:
        llm_kwargs["model"] = args.model
    if args.api_key:
        llm_kwargs["api_key"] = args.api_key

    client = LLMClient(**llm_kwargs)

    if not client.config.api_key and client.config.provider.value != "ollama":
        print("❌ LLM 不可用")
        return None

    print(f"   ✅ 供应商: {client.info()['provider']} / 模型: {client.info()['model']}")
    print()

    stock_code = args.stock
    stock_name = args.name or data["realtime"]["name"] if data["realtime"] else f"股票{stock_code}"

    # 构建系统提示
    system_prompt = f"""你是"竹林司马"AI首席分析师，正在分析 {stock_name}（{stock_code}）。

## 当前数据
- 当前价: {data['current_price']}元
- 涨跌幅: {data['realtime']['change_pct'] if data['realtime'] else 'N/A'}%
- 均线排列: {data['technical_data']['均线排列']}
- MACD: {data['technical_data']['MACD DIF/Signal']}
- RSI: {data['technical_data']['RSI6/RSI14']}
- KDJ: {data['technical_data']['KDJ K/D/J']}
- 量价关系: {data['technical_data']['量价关系']}
- 5日/20日涨跌: {data['technical_data']['近5日涨跌幅']} / {data['technical_data']['近20日涨跌幅']}
- 风险等级: {data['risk_data']['风险等级']}
- AI综合评分: {data['ai_score'].get('综合评分', 'N/A')}/100
- 战法信号: {', '.join(s['名称'] + ('✅' if s['触发'] else '⭕') for s in data['strategy_signals'])}

## 回答要求
- 数据驱动，每个观点有数据支撑
- 通俗易懂，避免堆砌术语
- 操作导向，给出可执行建议
- 风险优先，永远提醒风险"""

    # 预设问题
    print("💡 你可以这样问:")
    print("   - 现在能买入吗？")
    print("   - 均线怎么看？")
    print("   - 风险大不大？")
    print("   - 下一步怎么操作？")
    print("   - 止损设在哪？")
    print()

    while True:
        try:
            question = input("🙋 你的问题 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 分析结束")
            break

        if not question:
            continue
        if question.lower() in ("quit", "退出", "q", "exit"):
            print("👋 分析结束")
            break

        print("🤔 思考中...", flush=True)
        try:
            answer = client.chat(message=question, system_prompt=system_prompt)
            print(f"\n{answer}\n")
        except Exception as e:
            print(f"❌ 分析失败: {e}\n")

    return None


def print_llm_enhanced_result(result):
    """打印LLM增强模式结果"""
    if not result:
        return

    meta = result["meta"]
    llm = result.get("llm_enhanced", {})
    rule = result.get("rule_engine", {})

    print("\n" + "=" * 60)
    print(f"📊 {meta['stock_name']}（{meta['stock_code']}）LLM增强分析结果")
    print(f"   分析时间: {meta['analysis_time']}")
    print(f"   分析模式: {meta['mode']}")
    if meta.get("llm_provider"):
        print(f"   LLM供应商: {meta['llm_provider']}")
    print("=" * 60)

    # 各模块LLM解读
    modules = [
        ("📊 维度解读", "dimensions"),
        ("🎯 战法解读", "strategies"),
        ("📋 操作方案", "execution_plan"),
        ("🔴 风险深度分析", "risk_analysis"),
        ("💡 投资建议", "investment_advice"),
        ("🔮 趋势预测", "trend_prediction"),
    ]

    for title, key in modules:
        content = llm.get(key, "")
        if content:
            print(f"\n{'─' * 40}")
            print(f"{title}")
            print(f"{'─' * 40}")
            print(content)

    errors = llm.get("_errors", [])
    if errors:
        print(f"\n⚠️ 部分模块失败: {errors}")


def print_debate_result(result):
    """打印辩论模式结果"""
    if not result:
        return

    meta = result["meta"]
    print(f"\n耗时: {meta['total_time']}秒 | 成功: {meta['roles_completed']}/{meta['roles_total']}个角色")

    if meta.get("errors"):
        print(f"⚠️ 错误: {meta['errors']}")

    # 打印各角色观点
    print("\n" + "=" * 60)
    views = result["individual_views"]
    for role_name, view_data in views.items():
        emoji = ANALYST_ROLES.get(role_name, {}).get("emoji", "👤")
        print(f"\n{emoji} {role_name} (置信度: {view_data.get('confidence', 'N/A')} | 操作: {view_data.get('action', 'N/A')})")
        print("─" * 40)
        print(view_data.get("viewpoint", "分析失败"))

    # 打印综合结论
    print("\n" + "=" * 60)
    print("🧠 首席投资官综合结论")
    print("=" * 60)
    print(result.get("synthesis", "综合评判失败"))

    # 打印信号汇总
    signals = result.get("signal_summary", {})
    if signals.get("risk"):
        print("\n⚠️ 风险信号:")
        for s in signals["risk"]:
            print(f"   {s}")
    if signals.get("opportunity"):
        print("\n✅ 机会信号:")
        for s in signals["opportunity"]:
            print(f"   {s}")
    if signals.get("optimize"):
        print("\n💡 优化建议:")
        for s in signals["optimize"]:
            print(f"   {s}")

    # 打印共识
    consensus = result.get("consensus", {})
    print(f"\n📊 角色共识: {consensus.get('action', 'N/A')} (一致度: {consensus.get('strength', 'N/A')})")
    print(f"   操作分布: {consensus.get('action_distribution', {})}")


def generate_debate_html(result, data, args):
    """生成多角色辩论HTML报告"""
    from zhulinsma.core.llm.debate import ANALYST_ROLES

    if not result:
        return None

    stock_code = args.stock
    stock_name = args.name or data["realtime"]["name"] if data["realtime"] else f"股票{stock_code}"
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Markdown转HTML简易函数
    def md_to_html(text):
        if not text:
            return '<span style="color:var(--dim);">暂无数据</span>'
        import re
        html = text
        html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = re.sub(r'^### (.+)$', r'<h4 style="font-size:14px;font-weight:700;color:var(--accent);margin:12px 0 6px;">\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3 style="font-size:15px;font-weight:700;color:var(--accent);margin:14px 0 8px;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^\*\*(.+?)\*\*', r'<strong style="color:var(--text);">\1</strong>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<div style="padding:3px 0 3px 16px;font-size:13px;position:relative;">• \1</div>', html, flags=re.MULTILINE)
        html = html.replace("\n\n", "<br><br>").replace("\n", "<br>")
        return html

    meta = result["meta"]
    views = result["individual_views"]
    synthesis = result.get("synthesis", "")
    signals = result.get("signal_summary", {})

    # 各角色卡片HTML
    role_cards = ""
    for role_name, view_data in views.items():
        config = ANALYST_ROLES.get(role_name, {})
        emoji = config.get("emoji", "👤")
        color = config.get("color", "var(--accent)")
        confidence = view_data.get("confidence", "N/A")
        action = view_data.get("action", "N/A")
        viewpoint = md_to_html(view_data.get("viewpoint", "分析失败"))

        action_color = "var(--red)" if action == "买入" else ("var(--green)" if action == "卖出" else "var(--yellow)")

        role_cards += f"""
    <div class="role-card" style="border-color:{color};">
      <div class="role-header">
        <div class="role-title">
          <span class="role-emoji">{emoji}</span>
          <span class="role-name">{role_name}</span>
        </div>
        <div class="role-badges">
          <span class="badge" style="background:rgba(255,255,255,.06);color:var(--dim);">置信度: {confidence}</span>
          <span class="badge" style="background:{action_color};color:#fff;">{action}</span>
        </div>
      </div>
      <div class="role-question" style="color:{color};">核心验证: {view_data.get('key_question', 'N/A')}</div>
      <div class="role-content">{viewpoint}</div>
    </div>
"""

    # 信号汇总HTML
    signals_html = ""
    if signals.get("risk"):
        signals_html += '<div class="signal-section"><h4 style="color:var(--red);margin-bottom:8px;">⚠️ 风险信号（需立即行动）</h4>'
        for s in signals["risk"]:
            signals_html += f'<div class="signal-item risk">⚠️ {md_to_html(s)}</div>'
        signals_html += '</div>'
    if signals.get("opportunity"):
        signals_html += '<div class="signal-section"><h4 style="color:var(--green);margin-bottom:8px;">✅ 机会信号（可执行操作）</h4>'
        for s in signals["opportunity"]:
            signals_html += f'<div class="signal-item opportunity">✅ {md_to_html(s)}</div>'
        signals_html += '</div>'
    if signals.get("optimize"):
        signals_html += '<div class="signal-section"><h4 style="color:var(--blue);margin-bottom:8px;">💡 优化建议（提升收益机会）</h4>'
        for s in signals["optimize"]:
            signals_html += f'<div class="signal-item optimize">💡 {md_to_html(s)}</div>'
        signals_html += '</div>'

    # 共识
    consensus = result.get("consensus", {})
    consensus_action = consensus.get("action", "N/A")
    consensus_strength = consensus.get("strength", "N/A")
    action_dist = consensus.get("action_distribution", {})
    dist_text = " | ".join(f"{k}: {v}票" for k, v in action_dist.items()) if action_dist else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_name}({stock_code}) - 竹林司马多角色辩论分析</title>
<style>
:root {{
  --bg: #0a0c10; --card: #141720; --card2: #1a1e2c; --border: #252a3a;
  --text: #e8eaf0; --dim: #6b7080; --accent: #6366f1;
  --red: #ef4444; --green: #22c55e; --yellow: #f59e0b; --blue: #3b82f6;
  --purple: #a855f7; --cyan: #06b6d4; --orange: #f97316;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",sans-serif; line-height:1.6; }}
.container {{ max-width:1200px; margin:0 auto; padding:20px 16px; }}
.header {{ text-align:center; padding:36px 20px 32px; background:linear-gradient(180deg,#141720 0%,#0a0c10 100%); border-bottom:1px solid var(--border); margin:-20px -16px 28px; position:relative; }}
.header::before {{ content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%;
  background:radial-gradient(circle at 30% 40%,rgba(99,102,241,0.06) 0%,transparent 50%),radial-gradient(circle at 70% 60%,rgba(168,85,247,0.04) 0%,transparent 50%); }}
.header .logo {{ font-size:12px; color:var(--dim); letter-spacing:5px; margin-bottom:8px; position:relative; }}
.header h1 {{ font-size:30px; font-weight:800; margin-bottom:6px; position:relative; }}
.header .sub {{ font-size:14px; color:var(--dim); position:relative; }}
.badge {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }}
.role-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px; margin-bottom:16px; border-left:4px solid var(--accent); }}
.role-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }}
.role-title {{ display:flex; align-items:center; gap:8px; }}
.role-emoji {{ font-size:24px; }}
.role-name {{ font-size:16px; font-weight:700; }}
.role-badges {{ display:flex; gap:6px; }}
.role-question {{ font-size:12px; font-weight:600; margin-bottom:10px; padding:6px 10px; background:rgba(255,255,255,.03); border-radius:6px; }}
.role-content {{ font-size:13px; line-height:1.8; color:var(--text); }}
.synthesis-card {{ background:linear-gradient(135deg,var(--card) 0%,rgba(99,102,241,.08) 100%); border:2px solid var(--accent); border-radius:18px; padding:28px; margin-bottom:20px; }}
.synthesis-title {{ font-size:20px; font-weight:800; text-align:center; margin-bottom:16px; }}
.synthesis-content {{ font-size:14px; line-height:1.9; }}
.signal-section {{ margin-bottom:12px; }}
.signal-item {{ padding:8px 12px; margin-bottom:6px; border-radius:8px; font-size:13px; line-height:1.6; }}
.signal-item.risk {{ background:rgba(239,68,68,.08); border-left:3px solid var(--red); }}
.signal-item.opportunity {{ background:rgba(34,197,94,.08); border-left:3px solid var(--green); }}
.signal-item.optimize {{ background:rgba(59,130,246,.08); border-left:3px solid var(--blue); }}
.consensus-bar {{ display:flex; justify-content:center; gap:20px; padding:16px; background:var(--card); border-radius:14px; border:1px solid var(--border); margin-bottom:20px; font-size:14px; }}
.consensus-item {{ text-align:center; }}
.consensus-item .label {{ font-size:11px; color:var(--dim); margin-bottom:4px; }}
.consensus-item .value {{ font-size:18px; font-weight:800; }}
.footer {{ text-align:center; padding:28px 0; color:var(--dim); font-size:11px; border-top:1px solid var(--border); margin-top:20px; }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <div class="logo">🎭 竹林司马 · 多角色辩论分析</div>
  <h1>{stock_name}（{stock_code}）</h1>
  <div class="sub">四大角色深度辩论 · {report_time} · 耗时{meta.get('total_time', 0)}s</div>
</div>

<div class="consensus-bar">
  <div class="consensus-item">
    <div class="label">角色共识</div>
    <div class="value" style="color:{'var(--red)' if consensus_action=='买入' else 'var(--green)' if consensus_action=='卖出' else 'var(--yellow)'};">{consensus_action}</div>
  </div>
  <div class="consensus-item">
    <div class="label">一致度</div>
    <div class="value">{consensus_strength}</div>
  </div>
  <div class="consensus-item">
    <div class="label">角色投票</div>
    <div class="value" style="font-size:14px;">{dist_text}</div>
  </div>
  <div class="consensus-item">
    <div class="label">当前价</div>
    <div class="value">{data['current_price']:.2f}元</div>
  </div>
</div>

<h2 style="font-size:18px;font-weight:800;margin-bottom:16px;">🎭 四大角色独立分析</h2>
{role_cards}

<h2 style="font-size:18px;font-weight:800;margin-bottom:16px;">🧠 首席投资官综合结论</h2>
<div class="synthesis-card">
  <div class="synthesis-title">🎯 最终投资决策</div>
  <div class="synthesis-content">{md_to_html(synthesis)}</div>
</div>

<h2 style="font-size:18px;font-weight:800;margin-bottom:16px;">📡 信号汇总</h2>
<div style="background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;">
{signals_html}
</div>

<div class="footer">
  <p>🎭 竹林司马多角色辩论分析系统 v2.0</p>
  <p>分析引擎：{meta.get('mode', 'N/A')} · 角色：技术分析师 + 基本面分析师 + 情绪分析师 + 风险管理员</p>
  <p>⚠️ 以上分析基于大模型生成，仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</p>
</div>

</div>
</body>
</html>
"""

    # 保存报告
    output_dir = args.output or os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{stock_code}_debate_{date.today()}.html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 辩论报告已生成: {output_path}")
    print(f"   文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")
    return output_path


def main():
    args = parse_args()

    # 自动判断市场前缀
    stock_code = args.stock
    if stock_code.startswith("6"):
        symbol = f"sh{stock_code}"
    elif stock_code.startswith(("0", "3")):
        symbol = f"sz{stock_code}"
    else:
        symbol = f"bj{stock_code}"

    # 准备数据
    import numpy as np
    import pandas as pd
    data = prepare_analysis_data(stock_code, args.name, symbol)

    if not data:
        print("❌ 数据准备失败")
        sys.exit(1)

    # 根据模式执行
    result = None
    if args.mode == "llm_enhanced":
        result = run_llm_enhanced(args, data)
        if result:
            print_llm_enhanced_result(result)
    elif args.mode == "multi_perspective":
        result = run_multi_perspective(args, data)
        if result:
            print_debate_result(result)
            if args.report:
                report_path = generate_debate_html(result, data, args)
    elif args.mode == "interactive":
        run_interactive(args, data)


if __name__ == "__main__":
    main()
