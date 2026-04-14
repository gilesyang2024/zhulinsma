#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 预警触发器
实时监控技术指标，触发 RSI超买超卖、金叉死叉、均线偏离等预警
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..protocol import AlertMessage, AlertType

logger = logging.getLogger(__name__)


@dataclass
class 预警规则:
    """单条预警规则配置"""
    规则ID: str
    类型: str                          # AlertType 枚举值
    描述: str
    启用: bool = True
    冷却秒数: int = 300                # 同一规则最少间隔触发时间（防止频繁报警）
    _上次触发时间: float = field(default=0.0, repr=False)

    def 可触发(self) -> bool:
        return self.启用 and (time.time() - self._上次触发时间) >= self.冷却秒数

    def 标记已触发(self) -> None:
        self._上次触发时间 = time.time()


class AlertTrigger:
    """
    预警触发器

    功能：
    - RSI 超买/超卖预警（RSI > 70 或 < 30）
    - MACD 金叉/死叉预警
    - 均线偏离度预警（价格偏离 MA20 超过阈值）
    - 成交量异动预警（量比超过阈值）
    - 支持自定义规则扩展
    - 预警回调注册
    """

    def __init__(self):
        self._规则列表: List[预警规则] = self._默认规则()
        self._回调列表: List[Callable[[AlertMessage], None]] = []
        self._历史记录: List[AlertMessage] = []
        # 记录上一次的指标值，用于交叉检测
        self._前一状态: Dict[str, Dict] = {}

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def 注册回调(self, callback: Callable[[AlertMessage], None]) -> None:
        """注册预警消息回调"""
        self._回调列表.append(callback)

    def 检查指标(self, ts_code: str, 指标数据: Dict) -> List[AlertMessage]:
        """
        检查一组指标数据，返回触发的预警列表

        参数:
            ts_code: 股票代码
            指标数据: IncrementalProcessor.推送价格() 的返回值
        """
        触发预警: List[AlertMessage] = []

        # RSI 检查
        rsi = 指标数据.get("rsi")
        if rsi is not None:
            触发预警 += self._检查RSI(ts_code, rsi)

        # MACD 金叉/死叉
        macd = 指标数据.get("macd", {})
        if macd.get("hist") is not None:
            触发预警 += self._检查MACD(ts_code, macd, 指标数据)

        # 均线偏离
        price = 指标数据.get("price")
        sma = 指标数据.get("sma", {})
        if price and sma.get(20):
            触发预警 += self._检查均线偏离(ts_code, price, sma[20])

        # 更新前一状态
        self._前一状态[ts_code] = 指标数据

        # 触发回调
        for alert in 触发预警:
            self._历史记录.append(alert)
            for cb in self._回调列表:
                try:
                    cb(alert)
                except Exception as e:
                    logger.warning(f"预警回调异常: {e}")

        if len(self._历史记录) > 1000:
            self._历史记录 = self._历史记录[-1000:]

        return 触发预警

    def 获取历史预警(self, ts_code: Optional[str] = None, 数量: int = 50) -> List[Dict]:
        records = self._历史记录
        if ts_code:
            records = [r for r in records if r.ts_code == ts_code]
        return [r.to_dict() for r in records[-数量:]]

    def 统计信息(self) -> Dict:
        return {
            "规则总数": len(self._规则列表),
            "启用规则": sum(1 for r in self._规则列表 if r.启用),
            "历史预警数": len(self._历史记录),
            "回调数量": len(self._回调列表),
        }

    # ──────────────────────────────────────────────
    # 检查逻辑
    # ──────────────────────────────────────────────

    def _检查RSI(self, ts_code: str, rsi: float) -> List[AlertMessage]:
        结果 = []
        if rsi > 70:
            规则 = self._找规则(AlertType.RSI_OVERBOUGHT)
            if 规则 and 规则.可触发():
                规则.标记已触发()
                结果.append(AlertMessage(
                    alert_type=AlertType.RSI_OVERBOUGHT,
                    ts_code=ts_code,
                    title="RSI 超买预警",
                    description=f"RSI={rsi:.1f}，已进入超买区间(>70)，注意回调风险",
                    value=rsi, threshold=70.0, severity="WARN",
                ))
        elif rsi < 30:
            规则 = self._找规则(AlertType.RSI_OVERSOLD)
            if 规则 and 规则.可触发():
                规则.标记已触发()
                结果.append(AlertMessage(
                    alert_type=AlertType.RSI_OVERSOLD,
                    ts_code=ts_code,
                    title="RSI 超卖预警",
                    description=f"RSI={rsi:.1f}，已进入超卖区间(<30)，关注反弹机会",
                    value=rsi, threshold=30.0, severity="INFO",
                ))
        return 结果

    def _检查MACD(self, ts_code: str, macd: Dict, 当前: Dict) -> List[AlertMessage]:
        结果 = []
        前一 = self._前一状态.get(ts_code, {})
        前一macd = 前一.get("macd", {})

        前hist = 前一macd.get("hist")
        当hist = macd.get("hist")

        if 前hist is None or 当hist is None:
            return []

        if 前hist < 0 and 当hist >= 0:
            规则 = self._找规则(AlertType.MACD_GOLDEN_CROSS)
            if 规则 and 规则.可触发():
                规则.标记已触发()
                结果.append(AlertMessage(
                    alert_type=AlertType.MACD_GOLDEN_CROSS,
                    ts_code=ts_code,
                    title="MACD 金叉信号",
                    description=f"MACD柱由负转正，金叉信号出现，多头占优",
                    value=当hist, threshold=0.0, severity="ALERT",
                ))
        elif 前hist > 0 and 当hist <= 0:
            规则 = self._找规则(AlertType.MACD_DEATH_CROSS)
            if 规则 and 规则.可触发():
                规则.标记已触发()
                结果.append(AlertMessage(
                    alert_type=AlertType.MACD_DEATH_CROSS,
                    ts_code=ts_code,
                    title="MACD 死叉信号",
                    description=f"MACD柱由正转负，死叉信号出现，空头占优",
                    value=当hist, threshold=0.0, severity="WARN",
                ))
        return 结果

    def _检查均线偏离(self, ts_code: str, price: float, ma20: float, 阈值: float = 0.08) -> List[AlertMessage]:
        if ma20 <= 0:
            return []
        偏离度 = (price - ma20) / ma20
        if abs(偏离度) > 阈值:
            规则 = self._找规则(AlertType.MA_DEVIATION)
            if 规则 and 规则.可触发():
                规则.标记已触发()
                方向 = "上方" if 偏离度 > 0 else "下方"
                return [AlertMessage(
                    alert_type=AlertType.MA_DEVIATION,
                    ts_code=ts_code,
                    title=f"均线偏离预警",
                    description=f"价格偏离MA20达 {偏离度*100:.1f}%（{方向}），均值回归风险",
                    value=round(偏离度 * 100, 2), threshold=阈值 * 100, severity="WARN",
                )]
        return []

    # ──────────────────────────────────────────────
    # 规则管理
    # ──────────────────────────────────────────────

    def _默认规则(self) -> List[预警规则]:
        return [
            预警规则(规则ID="rsi_ob", 类型=AlertType.RSI_OVERBOUGHT, 描述="RSI超买", 冷却秒数=300),
            预警规则(规则ID="rsi_os", 类型=AlertType.RSI_OVERSOLD, 描述="RSI超卖", 冷却秒数=300),
            预警规则(规则ID="macd_g", 类型=AlertType.MACD_GOLDEN_CROSS, 描述="MACD金叉", 冷却秒数=60),
            预警规则(规则ID="macd_d", 类型=AlertType.MACD_DEATH_CROSS, 描述="MACD死叉", 冷却秒数=60),
            预警规则(规则ID="ma_dev", 类型=AlertType.MA_DEVIATION, 描述="均线偏离", 冷却秒数=600),
        ]

    def _找规则(self, 类型: str) -> Optional[预警规则]:
        for r in self._规则列表:
            if r.类型 == 类型:
                return r
        return None
