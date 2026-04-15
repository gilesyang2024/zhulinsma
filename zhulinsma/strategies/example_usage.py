#!/usr/bin/env python3
"""
策略模块使用示例
"""

import numpy as np
import pandas as pd
from datetime import datetime

from zhulinsma.strategies import (
    StrategyEngine,
    FiveStepStrategy,
    LockupKlineStrategy,
    MultiFactorStrategy,
    Signal,
    StockData,
    StrategyType
)


def create_mock_stock_data(code: str, name: str, days: int = 60) -> StockData:
    """创建模拟股票数据用于测试"""
    np.random.seed(hash(code) % 2**32)
    
    # 生成价格序列
    base_price = 20.0 + np.random.rand() * 30
    returns = np.random.randn(days) * 0.02
    close = base_price * np.cumprod(1 + returns)
    
    # 生成OHLC
    high = close * (1 + np.abs(np.random.randn(days) * 0.01))
    low = close * (1 - np.abs(np.random.randn(days) * 0.01))
    open_price = low + np.random.rand(days) * (high - low)
    
    # 生成成交量
    volume = np.abs(np.random.randn(days)) * 1000000 + 5000000
    
    # 创建DataFrame
    df = pd.DataFrame({
        'date': pd.date_range(end=datetime.now(), periods=days),
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    return StockData(
        code=code,
        name=name,
        df=df,
        pe=15 + np.random.rand() * 20,
        pb=1.5 + np.random.rand() * 3,
        market_cap=100 + np.random.rand() * 900,
        metadata={'sector': '电力设备', 'policy_benefit': True}
    )


def example_five_step():
    """五步选股法示例"""
    print("\n" + "="*60)
    print("示例1: 五步选股法分析")
    print("="*60)
    
    stock = create_mock_stock_data("600406.SH", "国电南瑞")
    strategy = FiveStepStrategy()
    signal = strategy.analyze(stock)
    
    if signal:
        print(f"\n股票: {signal.name} ({signal.code})")
        print(f"策略: {signal.strategy}")
        print(f"综合评分: {signal.score}/10.0")
        print(f"投资评级: {signal.rating_stars}")
        print(f"操作建议: {signal.action_text}")
        print(f"\n各维度得分:")
        for dim, score in signal.details.get("各维度得分", {}).items():
            bar = "█" * int(score) + "░" * (10 - int(score))
            print(f"  {dim:<8}: {score:.2f}  {bar}")
    else:
        print("未生成信号")


def example_four_tactics():
    """四大战法示例"""
    print("\n" + "="*60)
    print("示例2: 四大战法分析")
    print("="*60)
    
    # 创建一个可能触发锁仓信号的股票数据
    close = np.array([100.0 + i * 0.1 + np.sin(i * 0.3) * 0.5 for i in range(60)])
    volume = np.array([1000000 * (0.5 + 0.5 * np.sin(i * 0.5)) for i in range(60)])
    
    df = pd.DataFrame({
        'date': pd.date_range(end=datetime.now(), periods=60),
        'close': close,
        'open': close * 0.99,
        'high': close * 1.01,
        'low': close * 0.98,
        'volume': volume
    })
    
    stock = StockData(
        code="600022.SH",
        name="山东钢铁",
        df=df
    )
    
    strategies = [
        LockupKlineStrategy(),
    ]
    
    for strategy in strategies:
        signal = strategy.analyze(stock)
        print(f"\n策略: {strategy.get_name()}")
        if signal:
            print(f"  评分: {signal.score}")
            print(f"  信号类型: {signal.signal_type.value}")
            print(f"  触发条件: {signal.signals}")
        else:
            print("  未触发")


def example_multifactor():
    """多因子打分示例"""
    print("\n" + "="*60)
    print("示例3: 多因子打分分析")
    print("="*60)
    
    stock = create_mock_stock_data("000001.SZ", "平安银行")
    strategy = MultiFactorStrategy()
    signal = strategy.analyze(stock)
    
    if signal:
        print(f"\n股票: {signal.name} ({signal.code})")
        print(f"综合评分: {signal.score}/10.0")
        print(f"\n各因子得分:")
        for dim, score in signal.details.get("各维度得分", {}).items():
            weight = signal.details.get("权重配置", {}).get(dim, 0)
            bar = "█" * int(score) + "░" * (10 - int(score))
            print(f"  {dim:<8}: {score:.2f}  {bar}  (权重{weight*100:.0f}%)")


def example_engine():
    """策略引擎示例"""
    print("\n" + "="*60)
    print("示例4: 策略引擎 - 多策略综合")
    print("="*60)
    
    engine = StrategyEngine()
    stock = create_mock_stock_data("600519.SH", "贵州茅台")
    
    # 运行所有策略
    results = engine.run_all_strategies(stock)
    
    print(f"\n股票: {stock.name} ({stock.code})")
    print("\n各策略评分:")
    for st, signal in results.items():
        if signal:
            print(f"  {st.value:<15}: {signal.score:.2f}  {signal.rating_stars}")
        else:
            print(f"  {st.value:<15}: 无信号")
    
    # 信号叠加分析
    combined = engine.combine_signals(stock)
    print(f"\n综合评估:")
    print(f"  平均得分: {combined['average_score']}")
    print(f"  投资评级: {combined['rating']}")
    print(f"  操作建议: {combined['action']}")
    print(f"  触发策略数: {combined['triggered_count']}/6")


def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("  竹林司马策略模块使用示例")
    print("="*60)
    
    example_five_step()
    example_four_tactics()
    example_multifactor()
    example_engine()
    
    print("\n" + "="*60)
    print("示例运行完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
