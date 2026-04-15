#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 选股策略模块
包含五步选股法、四大战法、多因子打分等策略
"""

from .base import BaseStrategy, Signal, SignalType
from .five_step import FiveStepStrategy
from .four_tactics import (
    LockupKlineStrategy,
    WeakToStrongStrategy,
    BladeOutStrategy,
    LimitUpStrategy,
)
from .multifactor import MultiFactorStrategy
from .engine import StrategyEngine

__all__ = [
    # 基类
    "BaseStrategy",
    "Signal",
    "SignalType",
    # 策略实现
    "FiveStepStrategy",
    "LockupKlineStrategy",
    "WeakToStrongStrategy",
    "BladeOutStrategy",
    "LimitUpStrategy",
    "MultiFactorStrategy",
    # 引擎
    "StrategyEngine",
]
