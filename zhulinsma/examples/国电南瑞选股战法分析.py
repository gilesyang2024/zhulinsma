#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 国电南瑞选股战法分析示例
演示四大战法 + 5步选股法对国电南瑞(600406.SH)的完整分析流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# 国电南瑞真实行情数据（使用 akshare 获取）
# ─────────────────────────────────────────────────────────────────
STOCK_CODE = "600406"
STOCK_NAME = "国电南瑞"

def load_real_data():
    """使用 akshare 获取真实日K数据"""
    try:
        import akshare as ak
        market_code = "sh"  # 沪市
        symbol = f"{market_code}{STOCK_CODE}"
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date="20250101",
            end_date="20260414",
            adjust="qfq",
        )
        # 统一列名
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
        })
        print(f"[数据] 成功获取真实行情 {len(df)} 条（{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}）")
        return df
    except Exception as e:
        print(f"[数据] akshare 获取失败（{e}），使用模拟数据")
        return None

df = load_real_data()

if df is not None:
    收盘价序列 = np.array(df["close"].values, dtype=float)
    最高价序列 = np.array(df["high"].values, dtype=float)
    最低价序列 = np.array(df["low"].values, dtype=float)
    成交量序列 = np.array(df["volume"].values, dtype=float)
    开盘价序列 = np.array(df["open"].values, dtype=float)
else:
    # 降级：模拟数据（保留原有逻辑）
    np.random.seed(20260327)
    基础价格 = 28.5
    收盘价序列 = 基础价格 + np.cumsum(np.random.randn(60) * 0.3)
    收盘价序列 = np.clip(收盘价序列, 24.0, 36.0)
    最高价序列 = 收盘价序列 + np.abs(np.random.randn(60)) * 0.3
    最低价序列 = 收盘价序列 - np.abs(np.random.randn(60)) * 0.3
    成交量序列 = np.abs(np.random.randn(60)) * 5000000 + 8000000
    开盘价序列 = 收盘价序列  # 近似



def 打印分隔线(title: str = "", width: int = 65):
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"{'─'*pad} {title} {'─'*pad}")
    else:
        print("─" * width)


def 运行五步选股法分析():
    """选股5步实战法评分"""
    from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
    ti = TechnicalIndicators(验证模式=False)

    打印分隔线("选股5步实战法分析")

    # ── Step 1: 看趋势 ──
    sma5  = ti.SMA(收盘价序列, 5)[-1]
    sma10 = ti.SMA(收盘价序列, 10)[-1]
    sma20 = ti.SMA(收盘价序列, 20)[-1]
    sma60 = ti.SMA(收盘价序列, 60)[-1]
    当前价 = float(收盘价序列[-1])

    多头排列 = sma5 > sma10 > sma20 > sma60
    站上60日 = 当前价 > sma60
    趋势得分 = 10.0 if (多头排列 and 站上60日) else (6.0 if 站上60日 else 3.0)
    print(f"\n📊 Step 1 看趋势  [{趋势得分:.1f}/10]")
    print(f"   MA5={sma5:.2f}  MA10={sma10:.2f}  MA20={sma20:.2f}  MA60={sma60:.2f}")
    print(f"   多头排列: {'✅' if 多头排列 else '❌'}  站上60日线: {'✅' if 站上60日 else '❌'}")

    # ── Step 2: 看资金 ──
    近5日均量 = float(np.mean(成交量序列[-5:]))
    20日均量  = float(np.mean(成交量序列[-20:]))
    量比 = 近5日均量 / (20日均量 + 1e-10)
    资金得分 = 8.0 if 1.2 <= 量比 <= 1.8 else (6.0 if 1.0 <= 量比 <= 2.5 else 4.0)
    print(f"\n💰 Step 2 看资金  [{资金得分:.1f}/10]")
    print(f"   近5日均量: {近5日均量:,.0f}  20日均量: {20日均量:,.0f}  量比: {量比:.2f}")

    # ── Step 3: 看基本面 ──
    # 模拟估算
    模拟PE = 18.5
    模拟ROE = 14.2
    模拟负债率 = 45.3
    基本面得分 = 8.5 if (模拟PE < 25 and 模拟ROE > 10 and 模拟负债率 < 60) else 5.0
    print(f"\n📋 Step 3 看基本面  [{基本面得分:.1f}/10]")
    print(f"   PE={模拟PE}  ROE={模拟ROE}%  资产负债率={模拟负债率}%")

    # ── Step 4: 看板块 ──
    板块得分 = 7.5  # 电力设备板块处于政策主线
    print(f"\n🔲 Step 4 看板块  [{板块得分:.1f}/10]")
    print(f"   所属板块: 电力设备/智能电网  政策利好: ✅  板块热度: 高")

    # ── Step 5: 看形态 ──
    rsi序列 = ti.RSI(收盘价序列, 14)
    最新RSI = float(rsi序列[-1])
    macd结果 = ti.MACD(收盘价序列)
    最新hist = float(macd结果["histogram"][-1])
    形态得分 = 8.0 if (40 < 最新RSI < 65 and 最新hist > 0) else 5.0
    print(f"\n🕯️  Step 5 看形态  [{形态得分:.1f}/10]")
    print(f"   RSI={最新RSI:.1f}  MACD柱={最新hist:.4f}")

    # ── 综合评分 ──
    打印分隔线("综合评分")
    权重 = {"趋势": 0.30, "资金": 0.25, "基本面": 0.20, "板块": 0.15, "形态": 0.10}
    各维度 = [趋势得分, 资金得分, 基本面得分, 板块得分, 形态得分]
    综合分 = sum(s * w for s, w in zip(各维度, 权重.values()))

    星级 = "★★★★★" if 综合分 >= 9.0 else ("★★★★" if 综合分 >= 7.5 else ("★★★" if 综合分 >= 6.0 else "★★"))
    print(f"\n   {STOCK_NAME}（{STOCK_CODE}）")
    print(f"   综合评分：{综合分:.2f} / 10.0")
    print(f"   投资评级：{星级}")
    print()
    for 维度, 得分, w in zip(["趋势强度", "资金信号", "基本面", "板块热度", "形态评估"],
                             各维度, 权重.values()):
        bar = "█" * int(得分) + "░" * (10 - int(得分))
        print(f"   {维度:<8}：{得分:.2f}  {bar}  (权重{w*100:.0f}%)")

    return 综合分


def 运行四大战法分析():
    """四大战法信号检测"""
    打印分隔线("四大战法信号检测")

    from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
    ti = TechnicalIndicators(验证模式=False)

    最近5日收盘 = 收盘价序列[-5:]
    最近5日量   = 成交量序列[-5:]
    rsi = ti.RSI(收盘价序列, 14)[-1]
    macd = ti.MACD(收盘价序列)

    # 战法1：锁仓K线策略
    量能收缩 = np.std(最近5日量) / (np.mean(最近5日量) + 1e-10) < 0.15
    价格横盘 = (np.max(最近5日收盘) - np.min(最近5日收盘)) / (np.min(最近5日收盘) + 1e-10) < 0.04
    锁仓信号 = 量能收缩 and 价格横盘
    print(f"\n⚔️  战法1 锁仓K线策略  {'✅ 触发' if 锁仓信号 else '⭕ 未触发'}")
    print(f"   量能收缩: {'是' if 量能收缩 else '否'}  价格横盘: {'是' if 价格横盘 else '否'}")

    # 战法2：竞价弱转强（模拟判断）
    前日涨幅 = (收盘价序列[-1] - 收盘价序列[-2]) / 收盘价序列[-2] * 100
    竞价强势 = 前日涨幅 > 2.0
    print(f"\n⚔️  战法2 竞价弱转强  {'✅ 触发' if 竞价强势 else '⭕ 未触发'}")
    print(f"   前日涨幅: {前日涨幅:.2f}%")

    # 战法3：利刃出鞘（倍量阴 + 创新高后缩量）
    近期最高 = np.max(收盘价序列[-20:])
    接近新高 = 收盘价序列[-1] >= 近期最高 * 0.97
    利刃信号 = 接近新高 and rsi > 50
    print(f"\n⚔️  战法3 利刃出鞘  {'✅ 触发' if 利刃信号 else '⭕ 未触发'}")
    print(f"   接近20日新高: {'是' if 接近新高 else '否'}  RSI>{50}: {'是' if rsi>50 else '否'}")

    # 战法4：涨停版法（缩量回踩均线支撑）
    sma20 = ti.SMA(收盘价序列, 20)[-1]
    回踩支撑 = abs(收盘价序列[-1] - sma20) / sma20 < 0.03
    涨停版信号 = 回踩支撑 and 价格横盘
    print(f"\n⚔️  战法4 涨停版法  {'✅ 触发' if 涨停版信号 else '⭕ 未触发'}")
    print(f"   回踩MA20支撑: {'是' if 回踩支撑 else '否'}  缩量整理: {'是' if 价格横盘 else '否'}")

    # 信号叠加
    触发数 = sum([锁仓信号, 竞价强势, 利刃信号, 涨停版信号])
    打印分隔线("信号叠加矩阵")
    print(f"\n   触发战法数：{触发数}/4")
    if 触发数 >= 3:
        print("   综合信号：★★★★★ 高确定性信号，强力买点")
    elif 触发数 >= 2:
        print("   综合信号：★★★★  中高确定性，可考虑介入")
    elif 触发数 == 1:
        print("   综合信号：★★★   单一信号，谨慎跟踪")
    else:
        print("   综合信号：★★    暂无明显战法信号，观望")


def 运行风险评估():
    """风险与仓位评估"""
    打印分隔线("风险与仓位建议")

    from zhulinsma.core.analysis.risk_analyzer import RiskAnalyzer
    from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators

    ti = TechnicalIndicators(验证模式=False)
    rsi = float(ti.RSI(收盘价序列, 14)[-1])

    分析器 = RiskAnalyzer()
    结果 = 分析器.评估风险(收盘价序列, 成交量序列, rsi=rsi)

    print(f"\n   综合风险分数：{结果['综合风险分数']}")
    print(f"   风险等级：{结果['风险等级']}")
    print(f"   主要风险因素：{', '.join(结果['风险因素'])}")
    print(f"   操作建议：{结果['操作建议']}")

    # 仓位建议
    风险等级 = 结果['风险等级']
    仓位上限 = {"低风险": "25%", "中风险": "15%", "高风险": "5%", "极高风险": "0%"}
    止损空间 = {"低风险": "3%-5%", "中风险": "5%-8%", "高风险": "8%-12%", "极高风险": "N/A"}
    print(f"\n   仓位上限：{仓位上限.get(风险等级, 'N/A')}")
    print(f"   止损空间：{止损空间.get(风险等级, 'N/A')}")


def main():
    print("\n" + "═" * 65)
    print("  🎋 竹林司马 (Zhulinsma) - 国电南瑞选股战法分析")
    print(f"  股票：{STOCK_NAME}  代码：{STOCK_CODE}  分析日期：2026-03-27")
    print("═" * 65)

    综合分 = 运行五步选股法分析()
    运行四大战法分析()
    运行风险评估()

    打印分隔线("分析总结")
    print(f"\n  {STOCK_NAME} 综合评分 {综合分:.2f}/10.0")
    print("  数据仅供参考，投资有风险，入市需谨慎。")
    print("\n" + "═" * 65 + "\n")


if __name__ == "__main__":
    main()
