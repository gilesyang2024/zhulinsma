#!/usr/bin/env python3
"""
竹林司马 (Zhulinsma) - 实时数据采集器
从多数据源采集实时行情，聚合到统一内存队列
"""

import asyncio
import logging
import random
import time
from collections import deque
from typing import Callable, Dict, List, Optional

from ..protocol import TickData

logger = logging.getLogger(__name__)


class RealtimeCollector:
    """
    实时数据采集器

    功能：
    - 支持 akshare / tushare / 模拟数据 三种数据源
    - 异步多源并行采集
    - 内存队列缓冲（最大 10000 条）
    - 自动断线重连
    - 采集速率统计
    """

    def __init__(
        self,
        数据源: str = "simulate",
        队列大小: int = 10000,
        采集间隔: float = 0.5,   # 秒
    ):
        self.数据源 = 数据源
        self.队列 = deque(maxlen=队列大小)
        self.采集间隔 = 采集间隔
        self._运行中 = False
        self._订阅列表: List[str] = []
        self._回调列表: List[Callable] = []
        self._统计 = {"采集总数": 0, "错误次数": 0, "启动时间": None}
        self._模拟价格: Dict[str, float] = {}  # 模拟数据的当前价格状态

    # ──────────────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────────────

    def 订阅(self, ts_code_list: List[str]) -> None:
        """订阅股票实时行情"""
        for code in ts_code_list:
            if code not in self._订阅列表:
                self._订阅列表.append(code)
                self._模拟价格[code] = 100.0  # 初始价格
        logger.info(f"已订阅 {len(self._订阅列表)} 只股票")

    def 取消订阅(self, ts_code_list: List[str]) -> None:
        for code in ts_code_list:
            if code in self._订阅列表:
                self._订阅列表.remove(code)

    def 注册回调(self, callback: Callable[[TickData], None]) -> None:
        """注册 Tick 数据到达回调函数"""
        self._回调列表.append(callback)

    async def 启动(self) -> None:
        """启动采集循环"""
        self._运行中 = True
        self._统计["启动时间"] = time.time()
        logger.info(f"采集器启动，数据源={self.数据源}，订阅={self._订阅列表}")
        await self._采集循环()

    def 停止(self) -> None:
        self._运行中 = False
        logger.info("采集器已停止")

    def 获取最新Tick(self, ts_code: str) -> Optional[TickData]:
        """从队列中获取指定股票最新 Tick"""
        for tick in reversed(self.队列):
            if tick.ts_code == ts_code:
                return tick
        return None

    def 统计信息(self) -> Dict:
        运行时间 = time.time() - (self._统计["启动时间"] or time.time())
        采集速率 = self._统计["采集总数"] / max(1, 运行时间)
        return {
            **self._统计,
            "订阅数量": len(self._订阅列表),
            "队列大小": len(self.队列),
            "采集速率": round(采集速率, 2),
            "运行时间秒": round(运行时间, 1),
        }

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    async def _采集循环(self) -> None:
        while self._运行中:
            try:
                ticks = await self._获取数据()
                for tick in ticks:
                    self.队列.append(tick)
                    self._统计["采集总数"] += 1
                    for cb in self._回调列表:
                        try:
                            cb(tick)
                        except Exception as e:
                            logger.warning(f"回调执行异常: {e}")
            except Exception as e:
                self._统计["错误次数"] += 1
                logger.error(f"采集异常: {e}")

            await asyncio.sleep(self.采集间隔)

    async def _获取数据(self) -> List[TickData]:
        if self.数据源 == "simulate":
            return self._模拟数据()
        elif self.数据源 == "akshare":
            return await self._akshare采集()
        else:
            logger.warning(f"未知数据源: {self.数据源}，使用模拟数据")
            return self._模拟数据()

    def _模拟数据(self) -> List[TickData]:
        """生成模拟 Tick 数据（用于测试）"""
        ticks = []
        for code in self._订阅列表:
            prev = self._模拟价格.get(code, 100.0)
            变动 = prev * random.gauss(0, 0.003)
            新价格 = max(0.01, prev + 变动)
            self._模拟价格[code] = 新价格

            tick = TickData(
                ts_code=code,
                price=round(新价格, 3),
                volume=random.randint(100, 10000) * 100,
                amount=round(新价格 * random.randint(100, 10000) * 100, 2),
                prev_close=prev,
            )
            ticks.append(tick)
        return ticks

    async def _akshare采集(self) -> List[TickData]:
        """akshare 实时数据采集（需安装 akshare）"""
        ticks = []
        try:
            import akshare as ak
            for code in self._订阅列表:
                try:
                    symbol = code.split(".")[0]
                    df = ak.stock_bid_ask_em(symbol=symbol)
                    if df is not None and not df.empty:
                        def _get(item: str) -> float:
                            row = df[df["item"] == item]
                            return float(row["value"].values[0]) if not row.empty else 0.0

                        最新价 = _get("最新")
                        昨收 = _get("昨收")
                        tick = TickData(
                            ts_code=code,
                            price=最新价,
                            volume=int(_get("总手") * 100),  # 总手→股数
                            amount=_get("金额"),
                            prev_close=昨收,
                        )
                        ticks.append(tick)
                except Exception as e:
                    logger.debug(f"akshare {code} 采集失败: {e}")
        except ImportError:
            logger.warning("akshare 未安装，降级到模拟数据")
            ticks = self._模拟数据()
        return ticks
