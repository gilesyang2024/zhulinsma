#!/usr/bin/env python3
"""策略引擎 - 统一的策略管理和执行入口"""

from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import pandas as pd

from .base import BaseStrategy, Signal, SignalType, StockData, StrategyType
from .five_step import FiveStepStrategy
from .four_tactics import LockupKlineStrategy, WeakToStrongStrategy, BladeOutStrategy, LimitUpStrategy
from .multifactor import MultiFactorStrategy


class StrategyEngine:
    """策略引擎 - 统一的策略管理和执行入口"""
    
    _STRATEGIES = {
        StrategyType.FIVE_STEP: FiveStepStrategy,
        StrategyType.LOCKUP_KLINE: LockupKlineStrategy,
        StrategyType.WEAK_TO_STRONG: WeakToStrongStrategy,
        StrategyType.BLADE_OUT: BladeOutStrategy,
        StrategyType.LIMIT_UP: LimitUpStrategy,
        StrategyType.MULTIFACTOR: MultiFactorStrategy,
    }
    
    def __init__(self):
        self._strategies: Dict[StrategyType, BaseStrategy] = {}
        self._history: List[Dict] = []
        
    def register_strategy(self, strategy_type: StrategyType, config: Optional[Dict] = None) -> BaseStrategy:
        """注册策略"""
        if strategy_type not in self._STRATEGIES:
            raise ValueError(f"未知策略类型: {strategy_type}")
        strategy_class = self._STRATEGIES[strategy_type]
        strategy = strategy_class(config)
        self._strategies[strategy_type] = strategy
        return strategy
    
    def get_strategy(self, strategy_type: StrategyType) -> Optional[BaseStrategy]:
        """获取已注册的策略"""
        return self._strategies.get(strategy_type)
    
    def run_strategy(self, strategy_type: StrategyType, stock_data: StockData) -> Optional[Signal]:
        """执行单个策略分析"""
        if strategy_type not in self._strategies:
            self.register_strategy(strategy_type)
        strategy = self._strategies[strategy_type]
        return strategy.analyze(stock_data)
    
    def run_all_strategies(self, stock_data: StockData) -> Dict[StrategyType, Optional[Signal]]:
        """对所有策略执行分析"""
        results = {}
        for strategy_type in self._STRATEGIES.keys():
            try:
                signal = self.run_strategy(strategy_type, stock_data)
                results[strategy_type] = signal
            except Exception as e:
                print(f"策略 {strategy_type.value} 分析出错: {e}")
                results[strategy_type] = None
        return results
    
    def scan_batch(self, strategy_type: StrategyType, stock_list: List[StockData]) -> List[Signal]:
        """批量扫描股票列表"""
        if strategy_type not in self._strategies:
            self.register_strategy(strategy_type)
        strategy = self._strategies[strategy_type]
        return strategy.scan(stock_list)
    
    def combine_signals(self, stock_data: StockData) -> Dict:
        """多策略信号叠加分析"""
        results = self.run_all_strategies(stock_data)
        
        # 统计触发情况
        triggered = []
        scores = []
        signals_details = {}
        
        for st, signal in results.items():
            if signal is not None:
                triggered.append(st.value)
                scores.append(signal.score)
                signals_details[st.value] = {
                    "score": signal.score,
                    "signal_type": signal.signal_type.value,
                    "confidence": signal.confidence
                }
        
        # 计算综合得分
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # 确定综合评级
        if avg_score >= 8.0:
            rating = "★★★★★ 强烈看好"
            action = "积极买入"
        elif avg_score >= 7.0:
            rating = "★★★★ 看好"
            action = "买入"
        elif avg_score >= 6.0:
            rating = "★★★ 中性偏多"
            action = "观察/轻仓"
        elif avg_score >= 5.0:
            rating = "★★ 中性"
            action = "观望"
        else:
            rating = "★ 谨慎"
            action = "回避"
        
        return {
            "code": stock_data.code,
            "name": stock_data.name,
            "triggered_strategies": triggered,
            "triggered_count": len(triggered),
            "average_score": round(avg_score, 2),
            "rating": rating,
            "action": action,
            "details": signals_details
        }
    
    def get_strategy_list(self) -> List[Dict]:
        """获取策略列表"""
        return [
            {"type": st.value, "name": cls().get_name(), "description": cls().get_description()}
            for st, cls in self._STRATEGIES.items()
        ]
