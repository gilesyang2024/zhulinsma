#!/usr/bin/env python3
"""
竹林司马 - 选股战法策略框架
版本: 1.0.0
日期: 2026年4月14日
位置: 广州

提供统一的策略基类和四大战法的可复用实现:
1. 锁仓K线策略 (LockupKlineStrategy)
2. 竞价弱转强策略 (WeakToStrongStrategy)
3. 利刃出鞘策略 (BladeOutStrategy)
4. 涨停版法策略 (LimitUpStrategy)

每个策略均支持:
- 标准化输入 (DataFrame)
- 参数可配置
- 返回结构化信号结果
- 支持批量扫描
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd


class SignalType(Enum):
    """信号类型"""
    BUY = "买入"
    SELL = "卖出"
    HOLD = "观望"


class SignalStrength(Enum):
    """信号强度"""
    STRONG = "强"
    MEDIUM = "中"
    WEAK = "弱"


@dataclass
class StrategySignal:
    """
    标准化策略信号

    所有策略返回统一格式，便于上层集成。
    """
    策略名称: str
    股票代码: str
    触发: bool
    信号类型: SignalType
    信号强度: SignalStrength
    评分: float  # 0-100
    触发条件: Dict[str, Any] = field(default_factory=dict)
    建议操作: str = ""
    详细说明: str = ""

    def to_dict(self) -> Dict:
        return {
            "策略名称": self.策略名称,
            "股票代码": self.股票代码,
            "触发": self.触发,
            "信号类型": self.信号类型.value,
            "信号强度": self.信号强度.value,
            "评分": self.评分,
            "触发条件": self.触发条件,
            "建议操作": self.建议操作,
            "详细说明": self.详细说明,
        }


class BaseStrategy(ABC):
    """
    策略基类

    所有选股战法策略继承此类，实现 analyze() 方法。
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        """
        分析股票数据，返回策略信号

        参数:
            df: 标准化 DataFrame，需包含 date/open/high/low/close/volume 列
            股票代码: 股票代码

        返回:
            StrategySignal 标准化信号
        """
        ...

    def 批量扫描(self, 股票数据字典: Dict[str, pd.DataFrame]) -> List[StrategySignal]:
        """
        批量扫描多只股票

        参数:
            股票数据字典: {股票代码: DataFrame}

        返回:
            信号列表（按评分降序）
        """
        signals = []
        for code, df in 股票数据字典.items():
            try:
                signal = self.analyze(df, code)
                signals.append(signal)
            except Exception:
                continue
        signals.sort(key=lambda s: s.评分, reverse=True)
        return signals


# ============================================================
# 战法1: 锁仓K线策略
# ============================================================

class LockupKlineStrategy(BaseStrategy):
    """
    锁仓K线策略

    逻辑:
    - 量能收缩: 近N日成交量变异系数 < 阈值（主力锁仓不交易）
    - 价格横盘: 近N日价格振幅 < 阈值（窄幅整理）
    - 双条件满足 = 主力锁仓信号，等待突破方向

    适用场景: 底部横盘整理后即将变盘
    """

    def __init__(
        self,
        观察周期: int = 5,
        量能变异系数阈值: float = 0.15,
        价格振幅阈值: float = 0.04,
    ):
        super().__init__("锁仓K线策略", "量能收缩+价格横盘=主力锁仓信号")
        self.观察周期 = 观察周期
        self.量能变异系数阈值 = 量能变异系数阈值
        self.价格振幅阈值 = 价格振幅阈值

    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        close = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float)

        if len(close) < self.观察周期 + 1:
            return self._未触发(股票代码, "数据不足")

        近期收盘 = close[-self.观察周期:]
        近期量 = volume[-self.观察周期:]

        量能变异系数 = np.std(近期量) / (np.mean(近期量) + 1e-10)
        价格振幅 = (np.max(近期收盘) - np.min(近期收盘)) / (np.min(近期收盘) + 1e-10)

        量能收缩 = 量能变异系数 < self.量能变异系数阈值
        价格横盘 = 价格振幅 < self.价格振幅阈值
        触发 = 量能收缩 and 价格横盘

        评分 = min(100, int((1 - 量能变异系数) * 50 + (1 - 价格振幅) * 50)) if 触发 else 0

        return StrategySignal(
            策略名称=self.name,
            股票代码=股票代码,
            触发=触发,
            信号类型=SignalType.BUY if 触发 else SignalType.HOLD,
            信号强度=SignalStrength.STRONG if 评分 > 80 else SignalStrength.MEDIUM,
            评分=评分,
            触发条件={
                "量能变异系数": round(量能变异系数, 4),
                "量能收缩": 量能收缩,
                "价格振幅": round(价格振幅, 4),
                "价格横盘": 价格横盘,
            },
            建议操作="锁仓阶段，等待方向突破后顺势跟进" if 触发 else "未满足锁仓条件",
            详细说明=f"量能CV={量能变异系数:.4f}（阈值{self.量能变异系数阈值}），振幅={价格振幅:.4f}（阈值{self.价格振幅阈值}）",
        )

    def _未触发(self, 股票代码: str, 原因: str) -> StrategySignal:
        return StrategySignal(
            策略名称=self.name, 股票代码=股票代码, 触发=False,
            信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
            详细说明=原因,
        )


# ============================================================
# 战法2: 竞价弱转强策略
# ============================================================

class WeakToStrongStrategy(BaseStrategy):
    """
    竞价弱转强策略

    逻辑:
    - 前日大跌（跌幅 > 阈值），市场恐慌
    - 次日低开后迅速拉回，收盘价 > 前日收盘价
    - 量能放大（量比 > 阈值），资金承接有力
    - 三条件满足 = 弱转强信号

    适用场景: 恐慌性下跌后的抄底机会
    """

    def __init__(
        self,
        前日跌幅阈值: float = 2.0,
        量比阈值: float = 1.2,
        回收比例阈值: float = 0.0,
    ):
        super().__init__("竞价弱转强策略", "前日大跌+次日回收=弱转强买入信号")
        self.前日跌幅阈值 = 前日跌幅阈值
        self.量比阈值 = 量比阈值
        self.回收比例阈值 = 回收比例阈值

    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        close = df["close"].values.astype(float)
        open_ = df["open"].values.astype(float)
        volume = df["volume"].values.astype(float)

        if len(close) < 22:  # 需要20日均量
            return self._未触发(股票代码, "数据不足")

        前日收盘 = close[-2]
        前前日收盘 = close[-3]
        今日收盘 = close[-1]
        今日开盘 = open_[-1]

        前日涨幅 = (前日收盘 - 前前日收盘) / 前前日收盘 * 100
        前日大跌 = 前日涨幅 < -self.前日跌幅阈值

        回收比例 = (今日收盘 - 前日收盘) / 前日收盘 * 100
        价格回收 = 回收比例 > self.回收比例阈值

        近5日均量 = np.mean(volume[-6:-1])
        今日量 = volume[-1]
        量比 = 今日量 / (近5日均量 + 1e-10)
        放量 = 量比 > self.量比阈值

        触发 = 前日大跌 and 价格回收 and 放量
        强度 = abs(前日涨幅) + 回收比例 + (量比 - 1) * 10
        评分 = min(100, int(强度 * 3)) if 触发 else 0

        return StrategySignal(
            策略名称=self.name,
            股票代码=股票代码,
            触发=触发,
            信号类型=SignalType.BUY if 触发 else SignalType.HOLD,
            信号强度=SignalStrength.STRONG if 评分 > 80 else SignalStrength.MEDIUM,
            评分=评分,
            触发条件={
                "前日涨幅%": round(前日涨幅, 2),
                "前日大跌": 前日大跌,
                "回收比例%": round(回收比例, 2),
                "价格回收": 价格回收,
                "量比": round(量比, 2),
                "放量": 放量,
            },
            建议操作="弱转强确认，可分批建仓" if 触发 else "未满足弱转强条件",
            详细说明=f"前日跌{前日涨幅:.2f}%，今日回收{回收比例:.2f}%，量比{量比:.2f}",
        )

    def _未触发(self, 股票代码: str, 原因: str) -> StrategySignal:
        return StrategySignal(
            策略名称=self.name, 股票代码=股票代码, 触发=False,
            信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
            详细说明=原因,
        )


# ============================================================
# 战法3: 利刃出鞘策略
# ============================================================

class BladeOutStrategy(BaseStrategy):
    """
    利刃出鞘策略

    逻辑:
    - 接近近期新高（距离N日新高 < 阈值）
    - RSI 处于强势区间（> 50）
    - MACD 柱状图为正（多头动能）
    - 成交量放大
    - 多条件共振 = 突破新高信号

    适用场景: 蓄势突破、创新高行情
    """

    def __init__(
        self,
        新高回溯周期: int = 20,
        新高接近阈值: float = 0.03,
        RSI阈值: float = 50,
        RSI超买阈值: float = 80,
    ):
        super().__init__("利刃出鞘策略", "接近新高+动能充足=突破信号")
        self.新高回溯周期 = 新高回溯周期
        self.新高接近阈值 = 新高接近阈值
        self.RSI阈值 = RSI阈值
        self.RSI超买阈值 = RSI超买阈值

    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        close = df["close"].values.astype(float)

        if len(close) < self.新高回溯周期 + 1:
            return self._未触发(股票代码, "数据不足")

        from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
        ti = TechnicalIndicators(验证模式=False)

        近期最高 = np.max(close[-self.新高回溯周期:])
        当前价 = close[-1]
        距新高 = (近期最高 - 当前价) / 近期最高
        接近新高 = 距新高 < self.新高接近阈值

        rsi = float(ti.RSI(close, 14)[-1])
        rsi_valid = self.RSI阈值 < rsi < self.RSI超买阈值

        macd = ti.MACD(close)
        macd_hist = float(macd["histogram"][-1])
        macd_positive = macd_hist > 0

        满足数 = sum([接近新高, rsi_valid, macd_positive])
        触发 = 满足数 >= 2
        评分 = min(100, 满足数 * 33 + int((1 - 距新高) * 10))

        return StrategySignal(
            策略名称=self.name,
            股票代码=股票代码,
            触发=触发,
            信号类型=SignalType.BUY if 触发 else SignalType.HOLD,
            信号强度=SignalStrength.STRONG if 评分 > 80 else SignalStrength.MEDIUM,
            评分=评分,
            触发条件={
                "20日新高": round(近期最高, 2),
                "当前价": round(当前价, 2),
                "距新高%": round(距新高 * 100, 2),
                "接近新高": 接近新高,
                "RSI": round(rsi, 2),
                "RSI强势": rsi_valid,
                "MACD柱": round(macd_hist, 4),
                "MACD多头": macd_positive,
            },
            建议操作="突破在即，关注放量确认后追入" if 触发 else "蓄势中，继续观察",
            详细说明=f"距新高{距新高*100:.2f}%，RSI={rsi:.1f}，MACD柱={macd_hist:.4f}",
        )

    def _未触发(self, 股票代码: str, 原因: str) -> StrategySignal:
        return StrategySignal(
            策略名称=self.name, 股票代码=股票代码, 触发=False,
            信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
            详细说明=原因,
        )


# ============================================================
# 战法4: 涨停版法策略
# ============================================================

class LimitUpStrategy(BaseStrategy):
    """
    涨停版法策略

    逻辑:
    - 价格回踩关键均线支撑（MA20/MA60）
    - 回踩幅度在阈值内（假跌破 vs 真跌破）
    - 缩量整理（量能 < 均量）
    - 均线多头排列（MA5 > MA10 > MA20）
    - 多条件满足 = 均线支撑买入信号

    适用场景: 趋势股回调到均线支撑位
    """

    def __init__(
        self,
        回踩均线周期: int = 20,
        回踩幅度阈值: float = 0.03,
        量比阈值: float = 0.8,
    ):
        super().__init__("涨停版法策略", "回踩均线+缩量+多头排列=支撑买入信号")
        self.回踩均线周期 = 回踩均线周期
        self.回踩幅度阈值 = 回踩幅度阈值
        self.量比阈值 = 量比阈值

    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        close = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float)

        if len(close) < max(60, self.回踩均线周期 + 5):
            return self._未触发(股票代码, "数据不足")

        from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
        ti = TechnicalIndicators(验证模式=False)

        sma5 = float(ti.SMA(close, 5)[-1])
        sma10 = float(ti.SMA(close, 10)[-1])
        sma20 = float(ti.SMA(close, self.回踩均线周期)[-1])
        sma60 = float(ti.SMA(close, 60)[-1])
        当前价 = float(close[-1])

        回踩均线 = sma20
        回踩幅度 = abs(当前价 - 回踩均线) / 回踩均线
        回踩支撑 = 回踩幅度 < self.回踩幅度阈值

        多头排列 = sma5 > sma10 > sma20 > sma60
        站上均线 = 当前价 > 回踩均线

        近5日均量 = np.mean(volume[-6:-1])
        今日量 = volume[-1]
        量比 = 今日量 / (近5日均量 + 1e-10)
        缩量 = 量比 < self.量比阈值

        满足数 = sum([回踩支撑, 多头排列, 站上均线, 缩量])
        触发 = 满足数 >= 3
        评分 = min(100, 满足数 * 25 + int((1 - 回踩幅度) * 15))

        return StrategySignal(
            策略名称=self.name,
            股票代码=股票代码,
            触发=触发,
            信号类型=SignalType.BUY if 触发 else SignalType.HOLD,
            信号强度=SignalStrength.STRONG if 评分 > 80 else SignalStrength.MEDIUM,
            评分=评分,
            触发条件={
                "MA5": round(sma5, 2),
                "MA10": round(sma10, 2),
                "MA20": round(sma20, 2),
                "MA60": round(sma60, 2),
                "当前价": round(当前价, 2),
                "回踩幅度%": round(回踩幅度 * 100, 2),
                "回踩支撑": 回踩支撑,
                "多头排列": 多头排列,
                "量比": round(量比, 2),
                "缩量": 缩量,
            },
            建议操作="均线支撑有效，可轻仓介入" if 触发 else "未满足买入条件",
            详细说明=f"MA20={sma20:.2f}，回踩{回踩幅度*100:.2f}%，量比{量比:.2f}",
        )

    def _未触发(self, 股票代码: str, 原因: str) -> StrategySignal:
        return StrategySignal(
            策略名称=self.name, 股票代码=股票代码, 触发=False,
            信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
            详细说明=原因,
        )


# ============================================================
# 五步选股法
# ============================================================

class FiveStepSelectionStrategy(BaseStrategy):
    """
    五步选股法策略

    五维度加权评分:
    1. 看趋势 (30%): 均线多头排列 + 站上60日线
    2. 看资金 (25%): 量比合理性
    3. 看基本面 (20%): PE/ROE/负债率（需外部数据）
    4. 看板块 (15%): 板块热度（需外部数据）
    5. 看形态 (10%): RSI + MACD 状态
    """

    def __init__(
        self,
        权重: Optional[Dict[str, float]] = None,
        基本面数据: Optional[Dict] = None,
        板块得分: float = 7.0,
    ):
        super().__init__("五步选股法", "五维度加权评分选股策略")
        self.权重 = 权重 or {"趋势": 0.30, "资金": 0.25, "基本面": 0.20, "板块": 0.15, "形态": 0.10}
        self.基本面数据 = 基本面数据 or {}
        self.板块得分 = 板块得分

    def analyze(self, df: pd.DataFrame, 股票代码: str = "") -> StrategySignal:
        close = df["close"].values.astype(float)
        volume = df["volume"].values.astype(float)

        if len(close) < 60:
            return self._未触发(股票代码, "数据不足60日")

        from zhulinsma.core.indicators.technical_indicators import TechnicalIndicators
        ti = TechnicalIndicators(验证模式=False)

        # Step 1: 趋势
        sma5 = float(ti.SMA(close, 5)[-1])
        sma10 = float(ti.SMA(close, 10)[-1])
        sma20 = float(ti.SMA(close, 20)[-1])
        sma60 = float(ti.SMA(close, 60)[-1])
        当前价 = float(close[-1])
        多头排列 = sma5 > sma10 > sma20 > sma60
        站上60日 = 当前价 > sma60
        趋势得分 = 10.0 if (多头排列 and 站上60日) else (6.0 if 站上60日 else 3.0)

        # Step 2: 资金
        近5日均量 = np.mean(volume[-5:])
        近20日均量 = np.mean(volume[-20:])
        量比 = 近5日均量 / (近20日均量 + 1e-10)
        资金得分 = 8.0 if 1.2 <= 量比 <= 1.8 else (6.0 if 1.0 <= 量比 <= 2.5 else 4.0)

        # Step 3: 基本面
        pe = self.基本面数据.get("PE", 20)
        roe = self.基本面数据.get("ROE", 10)
        负债率 = self.基本面数据.get("负债率", 55)
        基本面得分 = 8.5 if (pe < 25 and roe > 10 and 负债率 < 60) else 5.0

        # Step 4: 板块
        板块得分 = self.板块得分

        # Step 5: 形态
        rsi = float(ti.RSI(close, 14)[-1])
        macd = ti.MACD(close)
        hist = float(macd["histogram"][-1])
        形态得分 = 8.0 if (40 < rsi < 65 and hist > 0) else 5.0

        各维度得分 = {"趋势": 趋势得分, "资金": 资金得分, "基本面": 基本面得分, "板块": 板块得分, "形态": 形态得分}
        综合分 = sum(各维度得分[k] * self.权重[k] for k in self.权重)

        星级 = ("★★★★★" if 综合分 >= 9.0 else "★★★★" if 综合分 >= 7.5 else "★★★" if 综合分 >= 6.0 else "★★")

        return StrategySignal(
            策略名称=self.name,
            股票代码=股票代码,
            触发=综合分 >= 6.0,
            信号类型=SignalType.BUY if 综合分 >= 7.5 else SignalType.HOLD,
            信号强度=SignalStrength.STRONG if 综合分 >= 9.0 else SignalStrength.MEDIUM,
            评分=round(综合分 * 10),
            触发条件={
                "各维度得分": {k: round(v, 1) for k, v in 各维度得分.items()},
                "权重": self.权重,
                "综合分": round(综合分, 2),
                "投资评级": 星级,
            },
            建议操作=f"{'积极关注' if 综合分 >= 9 else '可适当参与' if 综合分 >= 7.5 else '继续观察'}",
            详细说明=f"综合评分{综合分:.2f}/10，评级{星级}",
        )

    def _未触发(self, 股票代码: str, 原因: str) -> StrategySignal:
        return StrategySignal(
            策略名称=self.name, 股票代码=股票代码, 触发=False,
            信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
            详细说明=原因,
        )


# ============================================================
# 策略引擎：统一调度
# ============================================================

class StrategyEngine:
    """
    策略引擎

    统一管理和调度所有选股战法策略，提供:
    - 单股多策略分析
    - 多股批量扫描
    - 信号叠加和综合评分
    """

    def __init__(self, 启用策略: Optional[List[str]] = None):
        self.策略注册表 = {
            "锁仓K线": LockupKlineStrategy(),
            "竞价弱转强": WeakToStrongStrategy(),
            "利刃出鞘": BladeOutStrategy(),
            "涨停版法": LimitUpStrategy(),
            "五步选股法": FiveStepSelectionStrategy(),
        }

        if 启用策略:
            self.策略注册表 = {k: v for k, v in self.策略注册表.items() if k in 启用策略}

    def 分析(self, df: pd.DataFrame, 股票代码: str = "") -> Dict[str, Any]:
        """
        对单只股票运行所有策略

        返回:
            {
                "股票代码": str,
                "信号列表": [StrategySignal, ...],
                "触发数": int,
                "总策略数": int,
                "综合评分": float,
                "投资建议": str,
            }
        """
        signals = []
        for name, strategy in self.策略注册表.items():
            try:
                signal = strategy.analyze(df, 股票代码)
                signals.append(signal)
            except Exception as e:
                signals.append(StrategySignal(
                    策略名称=name, 股票代码=股票代码, 触发=False,
                    信号类型=SignalType.HOLD, 信号强度=SignalStrength.WEAK, 评分=0,
                    详细说明=f"执行失败: {e}",
                ))

        触发数 = sum(1 for s in signals if s.触发)
        总策略数 = len(signals)
        触发率 = 触发数 / 总策略数 if 总策略数 > 0 else 0
        平均评分 = np.mean([s.评分 for s in signals]) if signals else 0

        if 触发数 >= 3:
            建议 = "★★★★★ 高确定性信号，强力买点"
        elif 触发数 >= 2:
            建议 = "★★★★ 中高确定性，可考虑介入"
        elif 触发数 == 1:
            建议 = "★★★ 单一信号，谨慎跟踪"
        else:
            建议 = "★★ 暂无明显战法信号，观望"

        return {
            "股票代码": 股票代码,
            "信号列表": [s.to_dict() for s in signals],
            "触发数": 触发数,
            "总策略数": 总策略数,
            "触发率": round(触发率, 2),
            "综合评分": round(平均评分, 1),
            "投资建议": 建议,
        }

    def 批量扫描(self, 股票数据字典: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """批量扫描多只股票"""
        results = []
        for code, df in 股票数据字典.items():
            try:
                result = self.分析(df, code)
                results.append(result)
            except Exception:
                continue
        results.sort(key=lambda r: r["综合评分"], reverse=True)
        return results


# ========== 测试 ==========

if __name__ == "__main__":
    import json

    # 生成模拟数据
    np.random.seed(42)
    n = 80
    base_price = 28.5
    close = base_price + np.cumsum(np.random.randn(n) * 0.3)
    close = np.clip(close, 24.0, 36.0)
    high = close + np.abs(np.random.randn(n)) * 0.3
    low = close - np.abs(np.random.randn(n)) * 0.3
    volume = np.abs(np.random.randn(n)) * 5000000 + 8000000
    open_ = close + np.random.randn(n) * 0.2

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n),
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    })

    engine = StrategyEngine()
    result = engine.分析(df, "600406")

    print("=" * 60)
    print("  竹林司马 - 选股战法策略引擎测试")
    print("=" * 60)
    print(f"\n股票: {result['股票代码']}")
    print(f"触发战法: {result['触发数']}/{result['总策略数']}")
    print(f"综合评分: {result['综合评分']}")
    print(f"投资建议: {result['投资建议']}")
    print()

    for signal in result["信号列表"]:
        icon = "✅" if signal["触发"] else "⭕"
        print(f"  {icon} {signal['策略名称']}: 评分{signal['评分']}  {signal['信号类型']}")
        if signal["触发"]:
            print(f"     条件: {signal['触发条件']}")
            print(f"     建议: {signal['建议操作']}")
