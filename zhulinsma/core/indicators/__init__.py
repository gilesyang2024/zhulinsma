"""
indicators模块 - 技术指标库
包含RSI、MACD、布林带等常用技术指标
"""

__version__ = "1.0.0"

from .technical_indicators import (
    RSI,
    MACD,
    BollingerBands,
    SMA,
    EMA,
    TechnicalIndicators
)

__all__ = [
    'RSI',
    'MACD',
    'BollingerBands',
    'SMA',
    'EMA',
    'TechnicalIndicators'
]

# 注意：ATR和Stochastic函数在TechnicalIndicators类中提供
# 使用方式：ti = TechnicalIndicators(); atr = ti.ATR(...)
