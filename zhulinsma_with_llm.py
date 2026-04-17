#!/usr/bin/env python3
"""
竹林司马 - 大模型增强版主程序
版本: 2.0.0
日期: 2026年4月15日

对应操作指南第十一章「大模型增强模式」的命令行入口。

支持三种模式:
1. llm_enhanced  - LLM增强模式（单分析师，深度解读）
2. multi_perspective - 多角度辩论模式（四大角色辩论 + 结论先行报告）
3. interactive    - 交互式分析模式（持续对话追问）

用法:
    # LLM增强模式
    python zhulinsma_with_llm.py --mode llm_enhanced --stock 600875

    # 多角度辩论模式（自动生成结论先行报告）
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875

    # 交互式分析
    python zhulinsma_with_llm.py --mode interactive --stock 600875

    # 指定供应商和模型
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 \\
        --provider deepseek --model deepseek-chat --api-key sk-xxx

    # 使用旧版辩论报告模板
    python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 --report-old
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

# 加载 .env 配置（含 LLM_API_KEY / LLM_BASE_URL 等）
from dotenv import load_dotenv
load_dotenv()

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
  python zhulinsma_with_llm.py --mode multi_perspective --stock 600875
  python zhulinsma_with_llm.py --mode multi_perspective --stock 600875 --report-old
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
    parser.add_argument("--report", "-r", action="store_true", default=False,
                        help="[旧版] 生成旧辩论HTML报告（已弃用，默认自动生成新格式报告）")
    parser.add_argument("--report-old", action="store_true",
                        help="使用旧版辩论报告模板（默认使用结论先行新模板）")
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
    # 尝试获取全维度数据用于10维评分（轻量级，不影响主流程）
    _extra_for_score = {}
    try:
        from zhulinsma.core.data.stock_data_service import StockDataService
        _sds = StockDataService()
        _extra_for_score = _sds.获取全维度数据(
            股票代码=stock_code,
            包含北向=True,
            包含龙虎榜=False,   # 轻量模式：跳过龙虎榜节省时间
        )
    except Exception:
        pass
    ai_score = score_engine.评分(df, strategy_signals, extra_data=_extra_for_score)

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
        "price_vs_ma5":  "上方" if data["current_price"] > data["ma5"][-1]  else "下方",
        "price_vs_ma10": "上方" if data["current_price"] > data["ma10"][-1] else "下方",
        "price_vs_ma20": "上方" if data["current_price"] > data["ma20"][-1] else "下方",
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

    # ====== 新增：获取全维度数据（资金/北向/龙虎榜/公告/财务/板块/大盘）======
    full_data = {}
    print("📡 获取全维度扩展数据（资金流向/北向/板块/公告等）...")
    try:
        from zhulinsma.core.data.stock_data_service import StockDataService
        sds = StockDataService()
        full_data = sds.获取全维度数据(
            股票代码=stock_code,
            包含北向=True,
            包含龙虎榜=True,
        )
        # 打印获取概况
        for dim_name, dim_val in full_data.items():
            if isinstance(dim_val, dict) and "错误" not in dim_val:
                print(f"   ✅ {dim_name}: 获取成功")
            else:
                err = dim_val.get("错误", "未知错误") if isinstance(dim_val, dict) else str(dim_val)
                print(f"   ⚠️  {dim_name}: {err[:60]}")

        # 注入到 data 字典供报告生成使用
        fund_raw = full_data.get("财务数据", {}) or {}
        if isinstance(fund_raw, dict) and "错误" not in fund_raw:
            data["finance_data"] = {
                "ps": None,
                "peg": None,
                "eps": None,
                "roe": fund_raw.get("ROE(%)"),
                "profit_growth_yoy": fund_raw.get("净利润增长率(%)"),
                "revenue_growth_yoy": fund_raw.get("营收增长率(%)"),
                "debt_ratio": None,
                "dividend_yield": None,
                "net_profit": None,
            }

        flow_raw = full_data.get("资金流向", {}) or {}
        if isinstance(flow_raw, dict) and "错误" not in flow_raw:
            main_flow = flow_raw.get("主力净流入", 0)
            data["market_data"] = {
                "main_net_flow_5d": main_flow,   # 单日作为近似
                "main_net_flow_10d": 0,          # 多日数据暂无
                "main_net_flow_30d": 0,
                "executive_action": "无",
                "is_limit_up": False,
            }
    except Exception as e:
        print(f"   ⚠️  全维度数据获取异常: {e}（将使用基础数据继续分析）")

    print()

    result = agent.analyze(
        stock_name=stock_name,
        stock_code=stock_code,
        current_price=data["current_price"],
        technical_data=data["technical_data"],
        fundamental_data=data["fundamental_data"],
        strategy_signals=data["strategy_signals"],
        risk_data=data["risk_data"],
        full_data=full_data,   # ← 注入全维度数据
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
    from zhulinsma.core.llm.debate import ANALYST_ROLES

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


def generate_unified_report(result, data, args):
    """
    生成统一格式报告（结论先行 + 预测分析）

    将辩论分析结果 + 市场数据 + 技术指标合并为 ReportData，
    使用 StockReportGenerator 输出标准化 HTML 报告。

    报告结构：
      1. 🎯 首席投资官结论面板（结论先行）
      2. 📊 三维度评分卡片（技术/基本面/情绪）
      3. 🔮 预测分析（三情景 + 趋势预判 + 催化因素）
      4-12. 详细数据（行情/技术/趋势/基本面/情绪/战法/风险/多空/交易）
    """
    from src.stock.report.generator import StockReportGenerator, ReportData
    from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
    import numpy as np

    if not result:
        return None

    stock_code = args.stock
    stock_name = args.name or data["realtime"]["name"] if data["realtime"] else f"股票{stock_code}"
    current_price = data["current_price"]

    # ─── 1. 从技术指标计算 bundle（用于填充 ReportData）───
    df = data["df"]
    close_arr = df["close"].values.astype(float)
    high_arr = df["high"].values.astype(float)
    low_arr = df["low"].values.astype(float)
    vol_arr = df["volume"].values.astype(float)

    ti = TechnicalIndicators(验证模式=False)
    ma5 = ti.SMA(close_arr, 5)
    ma10 = ti.SMA(close_arr, 10)
    ma20 = ti.SMA(close_arr, 20)
    ma60 = ti.SMA(close_arr, min(60, len(close_arr)))
    rsi6, rsi14 = ti.RSI(close_arr, 6), ti.RSI(close_arr, 14)
    macd_data = ti.MACD(close_arr)
    boll = ti.BollingerBands(close_arr, 20)

    # KDJ
    K, D = 50.0, 50.0
    for i in range(len(close_arr)):
        s = max(0, i - 8)
        hn, ln = np.max(high_arr[s:i + 1]), np.min(low_arr[s:i + 1])
        rsv = (close_arr[i] - ln) / (hn - ln + 1e-10) * 100
        K, D = (2 / 3) * K + (1 / 3) * rsv, (2 / 3) * D + (1 / 3) * K
    J = 3 * K - 2 * D

    # 计算 compute_all bundle（完整版）
    try:
        bundle = ti.compute_all(df)
    except Exception:
        bundle = None

    # ─── 2. 计算 ReportData 所需的衍生指标 ───
    prev_close = data["realtime"]["yesterday_close"] if data["realtime"] else (close_arr[-2] if len(close_arr) > 1 else current_price)
    open_price = data["realtime"]["today_open"] if data["realtime"] else float(df["open"].iloc[-1])
    high_price = data["realtime"]["high"] if data["realtime"] else float(df["high"].iloc[-1])
    low_price = data["realtime"]["low"] if data["realtime"] else float(df["low"].iloc[-1])
    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
    amplitude = ((high_price - low_price) / prev_close * 100) if prev_close else 0
    vol_5d_avg = np.mean(vol_arr[-5:]) if len(vol_arr) >= 5 else np.mean(vol_arr)
    vol_ratio = vol_5d_avg / (np.mean(vol_arr[-20:]) + 1e-10) if len(vol_arr) >= 20 else 1.0

    # 区间收益
    def _ret(n):
        if len(close_arr) > n:
            return (close_arr[-1] - close_arr[-(n + 1)]) / close_arr[-(n + 1)] * 100
        return 0.0

    return_5d = _ret(5)
    return_10d = _ret(10)
    return_30d = _ret(30)
    return_60d = _ret(60)
    high_60d = float(np.max(high_arr[-60:])) if len(high_arr) >= 60 else float(np.max(high_arr))
    low_60d = float(np.min(low_arr[-60:])) if len(low_arr) >= 60 else float(np.min(low_arr))
    position_60d = (current_price - low_60d) / (high_60d - low_60d + 1e-10) * 100

    # 趋势
    long_trend = "上升" if ma20[-1] > ma60[-1] else "下降" if ma20[-1] < ma60[-1] else "震荡"
    medium_trend = "上升" if ma5[-1] > ma20[-1] else "下降" if ma5[-1] < ma20[-1] else "震荡"
    short_trend = "上升" if return_5d > 0 else "下降" if return_5d < -2 else "震荡"
    bull_arrange = ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]

    # OBV 简化
    obv_val = 0.0
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i - 1]:
            obv_val += vol_arr[i]
        elif close_arr[i] < close_arr[i - 1]:
            obv_val -= vol_arr[i]
    obv_trend = "上升" if obv_val > 0 else "下降"

    # 支撑/阻力
    recent_20_high = float(np.max(high_arr[-20:])) if len(high_arr) >= 20 else float(np.max(high_arr))
    recent_20_low = float(np.min(low_arr[-20:])) if len(low_arr) >= 20 else float(np.min(low_arr))
    support_levels = [round(ma20[-1], 2), round(ma60[-1], 2), round(recent_20_low, 2)]
    resistance_levels = [round(recent_20_high, 2), round(ma5[-1] * 1.02, 2)]

    # MACD 判断（使用 nan_to_num 防止 NaN 输出）
    def _safe_last(arr, default=0.0):
        if arr is None or len(arr) == 0:
            return default
        v = float(arr[-1])
        return v if np.isfinite(v) else default

    macd_val = _safe_last(macd_data["macd"])
    macd_sig = _safe_last(macd_data["signal"])
    macd_hist = _safe_last(macd_data["histogram"])
    macd_bullish = macd_val > 0
    macd_golden = (len(macd_data.get("histogram", [])) >= 2 and
                   _safe_last(macd_data["histogram"], -1) < 0 < macd_hist)

    # KDJ 判断
    kdj_golden = K > D and (K < 30 or D < 30)
    kdj_overbought = K > 80
    kdj_oversold = J < 0

    # 均线趋势
    ma_trend = "多头" if bull_arrange else "空头" if ma5[-1] < ma10[-1] < ma20[-1] else "交织"

    # ─── 3. 构建报告数据 ───
    gen = StockReportGenerator()
    rd = ReportData()

    # 基础信息
    rd.stock_name = stock_name
    rd.stock_code = stock_code
    rd.exchange = "SH" if stock_code.startswith("6") else "SZ" if stock_code.startswith(("0", "3")) else "BJ"
    rd.report_date = datetime.now().strftime("%Y-%m-%d")
    rd.data_days = len(df)

    # 行情
    rd.current_price = current_price
    rd.open_price = open_price
    rd.high_price = high_price
    rd.low_price = low_price
    rd.prev_close = prev_close
    rd.change_pct = change_pct
    rd.volume = float(vol_arr[-1])
    rd.amount = data["realtime"].get("amount", 0) if data["realtime"] else 0
    rd.turnover = data["realtime"].get("turnover", 0) if data["realtime"] else 0
    rd.volume_ratio = vol_ratio
    rd.amplitude = amplitude

    # 区间表现
    rd.return_5d = return_5d
    rd.return_10d = return_10d
    rd.return_30d = return_30d
    rd.return_60d = return_60d
    rd.high_60d = high_60d
    rd.low_60d = low_60d
    rd.position_60d = position_60d
    # YTD 计算
    start_of_year_prices = df[df["date"].astype(str).str.startswith(str(date.today().year))] if "date" in df.columns else df.tail(60)
    if len(start_of_year_prices) > 1:
        rd.ytd_return = (current_price - float(start_of_year_prices["close"].iloc[0])) / float(start_of_year_prices["close"].iloc[0]) * 100
    else:
        rd.ytd_return = return_30d

    # 均线
    rd.ma5 = float(ma5[-1])
    rd.ma10 = float(ma10[-1])
    rd.ma20 = float(ma20[-1])
    rd.ma60 = float(ma60[-1]) if len(ma60) > 0 else None
    rd.ma120 = None  # 120日数据不足时跳过
    rd.ma_trend = ma_trend

    # MACD
    rd.macd_value = float(macd_val)
    rd.macd_signal = float(macd_sig)
    rd.macd_histogram = float(macd_hist)
    rd.macd_bullish = macd_bullish
    rd.macd_golden = macd_golden
    rd.macd_divergence = None

    # KDJ
    rd.kdj_k = float(K)
    rd.kdj_d = float(D)
    rd.kdj_j = float(J)
    rd.kdj_golden = kdj_golden
    rd.kdj_overbought = kdj_overbought
    rd.kdj_oversold = kdj_oversold
    rd.kdj_status = "超买" if kdj_overbought else ("超卖" if kdj_oversold else "中性")

    # RSI
    rd.rsi_value = float(rsi14[-1])
    rd.rsi_status = "超买" if rsi14[-1] > 70 else ("超卖" if rsi14[-1] < 30 else "中性")

    # 布林带
    rd.boll_upper = float(boll["upper"][-1])
    rd.boll_middle = float(boll["middle"][-1])
    rd.boll_lower = float(boll["lower"][-1])
    boll_bw = (rd.boll_upper - rd.boll_lower) / (rd.boll_middle + 1e-10)
    rd.boll_bw = boll_bw
    rd.boll_position = (current_price - rd.boll_lower) / (rd.boll_upper - rd.boll_lower + 1e-10)
    rd.boll_squeeze = boll_bw < 0.05

    # ATR / OBV
    rd.atr_value = float(np.mean(np.abs(high_arr[-14:] - low_arr[-14:]))) if len(high_arr) >= 14 else 0
    rd.obv_trend = obv_trend

    # 趋势
    rd.long_trend = long_trend
    rd.medium_trend = medium_trend
    rd.short_trend = short_trend
    rd.trend_strength = 50 + (return_5d * 2) + (10 if bull_arrange else -10)
    rd.trend_strength = max(0, min(100, rd.trend_strength))
    rd.momentum = "加速" if return_5d > 3 else ("减速" if return_5d < -3 else "平稳")
    rd.support_levels = sorted(support_levels, reverse=True)
    rd.resistance_levels = sorted(resistance_levels)

    # ─── 4. 从辩论结果注入评分和结论 ───
    views = result.get("individual_views", {})
    consensus = result.get("consensus", {})
    signals = result.get("signal_summary", {})
    prediction = result.get("prediction", {})

    # 从各角色提取评分（基于置信度映射）
    confidence_to_score = {"高": 75, "中": 55, "低": 35}
    tech_score = confidence_to_score.get(views.get("技术分析师", {}).get("confidence", "中"), 55)
    fund_score = confidence_to_score.get(views.get("基本面分析师", {}).get("confidence", "中"), 55)
    emotion_score = confidence_to_score.get(views.get("情绪分析师", {}).get("confidence", "中"), 55)
    risk_score = confidence_to_score.get(views.get("风险管理员", {}).get("confidence", "中"), 55)

    # 如果 AI 评分可用，用 AI 评分覆盖
    ai_score = data.get("ai_score", {})
    if ai_score and isinstance(ai_score, dict):
        tech_s = ai_score.get("技术面评分")
        fund_s = ai_score.get("基本面评分")
        emo_s = ai_score.get("情绪面评分")
        overall_s = ai_score.get("综合评分")
        if tech_s and isinstance(tech_s, (int, float)):
            tech_score = tech_s
        if fund_s and isinstance(fund_s, (int, float)):
            fund_score = fund_s
        if emo_s and isinstance(emo_s, (int, float)):
            emotion_score = emo_s
        if overall_s and isinstance(overall_s, (int, float)):
            rd.overall_score = overall_s

    def _grade(s):
        if s >= 75: return "A"
        if s >= 60: return "B"
        if s >= 45: return "C"
        return "D"

    rd.tech_score = tech_score
    rd.tech_grade = _grade(tech_score)
    rd.fund_score = fund_score
    rd.fund_grade = _grade(fund_score)
    rd.emotion_score = emotion_score
    rd.emotion_grade = _grade(emotion_score)
    rd.risk_score = risk_score
    rd.risk_level = "低" if risk_score < 40 else ("中" if risk_score < 65 else "高")

    # 综合评分
    if rd.overall_score == 0:
        rd.overall_score = round(tech_score * 0.40 + fund_score * 0.35 + emotion_score * 0.25, 1)
    rd.overall_grade = _grade(rd.overall_score)

    # 操作方向映射（结合 synthesis 语义二次校准）
    consensus_action = consensus.get("action", "观望")
    action_map = {"买入": "BUY", "卖出": "SELL", "回避": "SELL", "观望": "HOLD", "积极": "BUY"}
    rd.overall_action = action_map.get(consensus_action, "HOLD")
    
    # 如果 synthesis 明确提到"回避/不建仓/0%"，强制改为 HOLD
    raw_synthesis_check = (result.get("synthesis", "") or "").lower()
    force_hold_keywords = ["回避", "不建", "不建仓", "不建议", "0%", "不买", "暂不"]
    if any(kw in raw_synthesis_check for kw in force_hold_keywords):
        rd.overall_action = "HOLD"
    
    rd.position_advice = {
        "BUY": "建议建仓30%，分批加仓",
        "SELL": "建议减仓至10%或清仓",
        "HOLD": "空仓观望，等待信号",
    }.get(rd.overall_action, "空仓观望")

    # 风险数据（兼容百分比字符串和纯数字两种格式）
    def _to_float(val, default=0):
        if val is None or val == 0:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace("%", "").strip()
        try:
            return float(s)
        except (ValueError, TypeError):
            return default

    ai_risk = data.get("ai_risk", {})
    if ai_risk:
        risk_detail = ai_risk.get("风险明细", {})
        rd.stop_loss = _to_float(ai_risk.get("止损位"), current_price * 0.95)
        rd.var_95 = _to_float(risk_detail.get("VaR_95"), current_price * 0.02)
        rd.max_drawdown = _to_float(risk_detail.get("最大回撤"))
        rd.risk_return_ratio = _to_float(ai_risk.get("风险收益比"), 1.5)
    else:
        rd.stop_loss = current_price * 0.95
        rd.var_95 = current_price * 0.02
        rd.max_drawdown = 0
        rd.risk_return_ratio = 1.5

    # 止盈目标（优先使用预测分析的价格）
    rd.entry_price = current_price
    # 默认按比例，后面会被预测价格覆盖
    rd.target_price_1 = round(current_price * 1.08, 2)
    rd.target_price_2 = round(current_price * 1.15, 2)
    rd.holding_period = "5-10个交易日"
    rd.signal_confidence = rd.overall_score / 100

    # 基本面（从实时数据 + AI评分补充）
    if data["realtime"]:
        rd.pe = data["realtime"].get("pe")
        rd.pb = data["realtime"].get("pb")
        rd.pe_ttm = data["realtime"].get("pe_ttm")
        rd.turnover = data["realtime"].get("turnover", 0) or 0
        rd.amount = data["realtime"].get("amount", 0) or 0

    # 基本面补充（从 finance_data / AI 评分中获取）
    fund_extra = data.get("finance_data", {}) or {}
    if fund_extra:
        rd.ps = fund_extra.get("ps")
        rd.peg = fund_extra.get("peg")
        rd.eps = fund_extra.get("eps")
        rd.roe = fund_extra.get("roe")
        rd.profit_growth_yoy = fund_extra.get("profit_growth_yoy")
        rd.revenue_growth_yoy = fund_extra.get("revenue_growth_yoy")
        rd.debt_ratio = fund_extra.get("debt_ratio")
        rd.dividend_yield = fund_extra.get("dividend_yield")
        rd.net_profit = fund_extra.get("net_profit")
        rd.industry_pe = fund_extra.get("industry_pe", 27.0)

    # 大师评分（从 AI 评分中获取）
    ai_score = data.get("ai_score", {})
    if ai_score and isinstance(ai_score, dict):
        master_data = ai_score.get("大师评分", {})
        if master_data and isinstance(master_data, dict):
            rd.master_scores = master_data
        master_notes_data = ai_score.get("大师备注", {})
        if master_notes_data and isinstance(master_notes_data, dict):
            rd.master_notes = master_notes_data

    # 情绪（资金流向）
    market_data = data.get("market_data", {}) or {}
    if market_data:
        rd.main_net_flow_5d = market_data.get("main_net_flow_5d", 0)
        rd.main_net_flow_10d = market_data.get("main_net_flow_10d", 0)
        rd.main_net_flow_30d = market_data.get("main_net_flow_30d", 0)
        rd.executive_action = market_data.get("executive_action", "无")
        rd.executive_date = market_data.get("executive_date")
        rd.is_limit_up = market_data.get("is_limit_up", False)
        # 情绪评分从 market_data 覆盖（如有）
        emo_from_market = market_data.get("_emotion_score")
        if emo_from_market and isinstance(emo_from_market, (int, float)):
            rd.emotion_score = emo_from_market
            rd.emotion_grade = _grade(emo_from_market)

    # 风险明细（从 ai_risk 注入 risk_items）
    if ai_risk:
        risk_detail = ai_risk.get("风险明细", {})
        risk_items_raw = risk_detail.get("items", [])
        if risk_items_raw and isinstance(risk_items_raw, list):
            rd.risk_items = [
                {"level": r.get("level", "中"), "dimension": r.get("dimension", ""), "description": r.get("description", "")}
                for r in risk_items_raw
            ]

    # 多空逻辑
    rd.bull_points = signals.get("opportunity", [])[:5]
    rd.bear_points = signals.get("risk", [])[:5]

    # 战法
    strategy_signals = data.get("strategy_signals", [])
    if strategy_signals:
        rd.strategy_scores = {}
        for sig in strategy_signals:
            rd.strategy_scores[sig.get("名称", "未知")] = {
                "score": sig.get("评分", 0),
                "status": "✅ 已触发" if sig.get("触发") else "⭕ 未触发",
                "reason": sig.get("说明", ""),
            }

    # 分析师备注（首席投资官结论）— 清理 Markdown + PREDICTION_JSON
    raw_synthesis = result.get("synthesis", "") or ""
    # 清除 PREDICTION_JSON 代码块（不应出现在报告正文）
    import re as _re
    clean_notes = _re.sub(r'```PREDICTION_JSON.*?```', '', raw_synthesis, flags=_re.DOTALL).strip()
    # Markdown → HTML 简易转换（支持行首和非行首的 **bold**）
    clean_notes = _re.sub(r'^### (.+)$', r'<h4>\1</h4>', clean_notes, flags=_re.MULTILINE)
    clean_notes = _re.sub(r'^## (.+)$', r'<h3>\1</h3>', clean_notes, flags=_re.MULTILINE)
    clean_notes = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', clean_notes)  # 不限定行首
    clean_notes = _re.sub(r'^- (.+)$', r'<br>• \1', clean_notes, flags=_re.MULTILINE)
    clean_notes = clean_notes.replace("\n\n", "<br><br>").replace("\n", "<br>")
    rd.analyst_notes = clean_notes

    # signal_reason 截取前 200 字的纯文本版本（用于结论面板，不含 HTML）
    signal_reason_text = _re.sub(r'<[^>]+>', '', clean_notes)[:200]
    rd.signal_reason = signal_reason_text

    # 多空逻辑也需要清理 Markdown
    def _clean_md(text):
        if not text:
            return text
        t = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        return t
    rd.bull_points = [_clean_md(p) for p in rd.bull_points]
    rd.bear_points = [_clean_md(p) for p in rd.bear_points]
    rd.action_plan = [
        f"操作方向: {consensus_action}",
        f"仓位建议: {rd.position_advice}",
        f"止损位: ¥{rd.stop_loss:.2f}",
        f"目标1: ¥{rd.target_price_1:.2f}",
        f"目标2: ¥{rd.target_price_2:.2f}",
    ]

    # ─── 5. 注入预测分析 ───
    rd.prediction_enabled = bool(prediction and prediction.get("trend_forecast"))
    if prediction:
        rd.trend_forecast = prediction.get("trend_forecast", "")
        rd.trend_confidence = prediction.get("trend_confidence", "中")
        rd.forecast_horizon = prediction.get("forecast_horizon", "3-5个交易日")
        rd.scenario_bull = prediction.get("scenario_bull", {})
        rd.scenario_base = prediction.get("scenario_base", {})
        rd.scenario_bear = prediction.get("scenario_bear", {})

        # 解析价格数值（支持字符串格式如 "¥28.50" 或 float）
        pred_sup = prediction.get("predicted_support", 0)
        pred_res = prediction.get("predicted_resistance", 0)
        rd.predicted_support = float(pred_sup) if isinstance(pred_sup, (int, float)) else 0
        rd.predicted_resistance = float(pred_res) if isinstance(pred_res, (int, float)) else 0

        brk_up = prediction.get("breakout_up_prob", "25%")
        brk_dn = prediction.get("breakout_down_prob", "25%")
        if isinstance(brk_up, (int, float)):
            rd.breakout_up_prob = brk_up
        elif isinstance(brk_up, str):
            rd.breakout_up_prob = float(brk_up.replace("%", ""))
        if isinstance(brk_dn, (int, float)):
            rd.breakout_down_prob = brk_dn
        elif isinstance(brk_dn, str):
            rd.breakout_down_prob = float(brk_dn.replace("%", ""))

        rd.best_entry_window = prediction.get("best_entry_window", "")
        rd.key_catalyst = prediction.get("key_catalyst", "")
        rd.risk_event = prediction.get("risk_event", "")

        # 如果预测有价格，更新止盈目标
        # 基准情景价格 → 目标1，乐观情景价格 → 目标2
        base_target = rd.scenario_base.get("target", "")
        if base_target and isinstance(base_target, str):
            _pm = _re.search(r'([\d.]+)', base_target)
            if _pm:
                rd.target_price_1 = float(_pm.group(1))
        bull_target = rd.scenario_bull.get("target", "")
        if bull_target and isinstance(bull_target, str):
            _pm = _re.search(r'([\d.]+)', bull_target)
            if _pm:
                rd.target_price_2 = float(_pm.group(1))

        # 同步更新操作计划中的目标价格
        rd.action_plan = [
            f"操作方向: {consensus_action}",
            f"仓位建议: {rd.position_advice}",
            f"止损位: ¥{rd.stop_loss:.2f}",
            f"目标1: ¥{rd.target_price_1:.2f}",
            f"目标2: ¥{rd.target_price_2:.2f}",
        ]

    # ─── 6. 生成并保存报告 ───
    print("\n📊 生成统一格式报告...")
    html = gen.generate(rd)

    output_dir = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{stock_name}_{stock_code}_{date.today()}.html")
    gen.save(html, output_path)

    print(f"   ✅ 报告已生成: {output_path}")
    print(f"   文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"   报告结构: 🎯 首席结论 → 📊 三维评分 → 🔮 预测分析 → 详细数据")
    return output_path


def generate_debate_html(result, data, args):
    """[旧版] 生成多角色辩论HTML报告 — 已被 generate_unified_report 替代"""
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
            # 默认使用新模板生成报告（结论先行 + 预测分析）
            use_old = args.report_old or args.report  # --report 保留兼容
            if use_old:
                generate_debate_html(result, data, args)
            else:
                report_path = generate_unified_report(result, data, args)
    elif args.mode == "interactive":
        run_interactive(args, data)


if __name__ == "__main__":
    main()
