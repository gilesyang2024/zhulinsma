#!/usr/bin/env python3
"""
BaseStrategy - 选股战法基类
定义所有战法的统一接口，包括：入选条件、排除条件、综合评分、风控建议
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import numpy as np
import pandas as pd


class SignalStrength(Enum):
    """信号强度枚举"""
    STRONG_BUY = "强烈买入"    # 综合分 ≥ 4.0
    BUY = "买入"              # 综合分 3.0-4.0
    HOLD = "观望"             # 综合分 2.0-3.0
    SELL = "谨慎"             # 综合分 < 2.0


@dataclass
class StrategyResult:
    """
    战法分析结果
    标准化输出格式，供所有战法统一使用
    """
    # ── 基础信息 ──
    stock_code: str
    stock_name: str
    strategy_name: str

    # ── 信号 ──
    signal: SignalStrength
    signal_score: float          # 0-5 分制综合评分
    signal_reason: str            # 信号理由（一句话）

    # ── 入选条件详情 ──
    entry_conditions: Dict[str, bool]  # 各入选条件的满足状态
    entry_score: float             # 入选条件得分 (0-3)

    # ── 排除条件 ──
    exclusion_flags: List[str]    # 触发排除条件的列表
    is_excluded: bool             # 是否被排除

    # ── 战法特有指标 ──
    indicators: Dict[str, Any] = field(default_factory=dict)

    # ── 风控 ──
    stop_loss: Optional[float] = None    # 止损价
    take_profit: Optional[float] = None  # 止盈价
    risk_score: float = 0.0              # 风险分 0-100
    risk_level: str = "未知"              # 风险等级

    # ── 操作建议 ──
    action: str = "观望"           # 操作建议
    holding_period: str = ""       # 建议持仓周期
    position_ratio: str = "轻仓"   # 建议仓位

    # ── 辅助信息 ──
    confidence: float = 0.5        # 置信度 0-1
    warning: List[str] = field(default_factory=list)  # 注意事项

    def to_dict(self) -> Dict:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "strategy": self.strategy_name,
            "signal": self.signal.value,
            "score": round(self.signal_score, 2),
            "reason": self.signal_reason,
            "entry_conditions": self.entry_conditions,
            "entry_score": round(self.entry_score, 2),
            "exclusion_flags": self.exclusion_flags,
            "is_excluded": self.is_excluded,
            "indicators": self.indicators,
            "stop_loss": round(self.stop_loss, 2) if self.stop_loss else None,
            "take_profit": round(self.take_profit, 2) if self.take_profit else None,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "action": self.action,
            "holding_period": self.holding_period,
            "position_ratio": self.position_ratio,
            "confidence": round(self.confidence, 2),
            "warning": self.warning,
        }


class BaseStrategy(ABC):
    """
    选股战法抽象基类

    所有战法必须实现：
    1. name        - 战法名称
    2. description - 战法描述
    3. _check_entry()  - 入选条件
    4. _check_exclusion()  - 排除条件
    5. _score()        - 综合评分
    6. _risk_control() - 风控建议
    """

    name: str = "BaseStrategy"
    description: str = ""

    def __init__(self, strict: bool = False):
        """
        参数:
            strict: 是否严格模式（排除条件更严格）
        """
        self.strict = strict

    @abstractmethod
    def analyze(
        self,
        stock_code: str,
        stock_name: str,
        df: pd.DataFrame,
        indicators: Dict[str, Any],
        realtime: Optional[Dict] = None,
        auction: Optional[Dict] = None,
    ) -> StrategyResult:
        """
        执行战法分析（统一入口）

        参数:
            stock_code: 股票代码
            stock_name: 股票名称
            df: 日K DataFrame（至少60日）
            indicators: IndicatorWrapper.compute_all() 返回的指标字典
            realtime: 实时行情字典（可选）
            auction: 竞价数据字典（可选）

        返回:
            StrategyResult
        """
        pass

    def _build_result(
        self,
        stock_code: str,
        stock_name: str,
        entry: Dict[str, bool],
        exclusions: List[str],
        indicators: Dict[str, Any],
        risk: Dict,
        extra: Dict,
    ) -> StrategyResult:
        """
        辅助方法：构建 StrategyResult
        """
        entry_score = sum(1 for v in entry.values() if v) * (3.0 / max(len(entry), 1))

        # 综合评分 = 入选分 + 风控调整
        risk_adj = (100 - risk.get("risk_score", 50)) / 100 * 0.5
        signal_score = min(entry_score * (1 + risk_adj), 5.0)

        if signal_score >= 4.0:
            signal = SignalStrength.STRONG_BUY
        elif signal_score >= 3.0:
            signal = SignalStrength.BUY
        elif signal_score >= 2.0:
            signal = SignalStrength.HOLD
        else:
            signal = SignalStrength.SELL

        return StrategyResult(
            stock_code=stock_code,
            stock_name=stock_name,
            strategy_name=self.name,
            signal=signal,
            signal_score=signal_score,
            signal_reason=extra.get("reason", ""),
            entry_conditions=entry,
            entry_score=entry_score,
            exclusion_flags=exclusions,
            is_excluded=len(exclusions) > 0,
            indicators=indicators,
            stop_loss=risk.get("stop_loss"),
            take_profit=risk.get("take_profit"),
            risk_score=risk.get("risk_score", 0),
            risk_level=risk.get("risk_level", "未知"),
            action=extra.get("action", "观望"),
            holding_period=extra.get("holding_period", ""),
            position_ratio=extra.get("position_ratio", "轻仓"),
            confidence=extra.get("confidence", 0.5),
            warning=extra.get("warning", []),
        )

    def _default_exclusions(
        self,
        df: pd.DataFrame,
        indicators: Dict,
        realtime: Optional[Dict] = None,
    ) -> List[str]:
        """
        默认排除条件（所有战法通用）
        """
        flags = []
        n = len(df)

        # 1. 数据不足
        if n < 20:
            flags.append("数据不足（<20日）")

        # 2. 涨停后第2天（过高开）
        if realtime and realtime.get("pct_change", 0) > 9.5:
            flags.append("已涨停，无法买入")

        # 3. 风险过高
        risk = indicators.get("风险", {})
        if risk.get("综合风险分数", 0) > 80:
            flags.append("风险评分过高（>80）")

        # 4. RSI 极度超买
        rsi = indicators.get("rsi")
        if rsi and rsi > 85:
            flags.append(f"RSI极度超买（{rsi}）")

        # 5. RSI 极度超卖（非底部信号）
        if rsi and rsi < 15:
            flags.append(f"RSI极度超卖（{rsi}），趋势异常")

        # 6. 停牌/无成交
        vol = df["volume"].values[-1] if n > 0 else 0
        if vol == 0 or np.isnan(vol):
            flags.append("停牌或无成交")

        return flags


class StrategyEngine:
    """
    战法引擎 Facade
    统一管理所有战法，提供一键扫描接口
    """

    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._registered: List[BaseStrategy] = []

    def register(self, strategy: BaseStrategy):
        """注册战法"""
        self._strategies[strategy.name] = strategy
        self._registered.append(strategy)

    def analyze_stock(
        self,
        stock_code: str,
        stock_name: str,
        df: pd.DataFrame,
        indicators: Dict[str, Any],
        strategy_names: Optional[List[str]] = None,
        realtime: Optional[Dict] = None,
        auction: Optional[Dict] = None,
    ) -> List[StrategyResult]:
        """
        对个股执行所有战法分析

        参数:
            strategy_names: 指定战法列表，默认执行全部
        """
        results = []
        for s in self._registered:
            if strategy_names and s.name not in strategy_names:
                continue
            try:
                result = s.analyze(stock_code, stock_name, df, indicators, realtime, auction)
                results.append(result)
            except Exception as e:
                results.append(StrategyResult(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    strategy_name=s.name,
                    signal=SignalStrength.HOLD,
                    signal_score=0.0,
                    signal_reason=f"分析异常: {e}",
                    entry_conditions={},
                    exclusion_flags=["分析异常"],
                    is_excluded=True,
                    indicators={},
                    action="分析失败",
                    warning=[str(e)],
                ))
        return results

    def list_strategies(self) -> List[Dict]:
        return [
            {"name": s.name, "description": s.description}
            for s in self._registered
        ]
