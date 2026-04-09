"""
实时数据采集器 - 从多源获取实时行情数据
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
import random
import time

from ..processor import PriceData

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """数据源配置"""
    name: str
    enabled: bool = True
    priority: int = 1  # 优先级，数字越大越优先
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class RealtimeCollector:
    """实时数据采集器"""
    
    def __init__(self, collect_interval: float = 3.0):
        self.collect_interval = collect_interval
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._watch_list: List[str] = []
        self._callbacks: List[Callable] = []
        
        # 数据源配置
        self._data_sources: Dict[str, DataSourceConfig] = {
            "tushare": DataSourceConfig(name="tushare", priority=3),
            "akshare": DataSourceConfig(name="akshare", priority=2),
            "simulation": DataSourceConfig(name="simulation", priority=1)
        }
        
        # 缓存最新价格
        self._latest_prices: Dict[str, float] = {}
        
    def add_callback(self, callback: Callable):
        """添加数据回调"""
        self._callbacks.append(callback)
    
    def add_to_watch_list(self, stock_code: str):
        """添加到监控列表"""
        if stock_code not in self._watch_list:
            self._watch_list.append(stock_code)
            logger.info(f"添加股票到监控列表: {stock_code}")
    
    def remove_from_watch_list(self, stock_code: str):
        """从监控列表移除"""
        if stock_code in self._watch_list:
            self._watch_list.remove(stock_code)
            
            # 取消采集任务
            if stock_code in self._tasks:
                self._tasks[stock_code].cancel()
                del self._tasks[stock_code]
                
            logger.info(f"从监控列表移除: {stock_code}")
    
    async def start_collecting(self):
        """启动采集（对所有监控股票）"""
        if self._running:
            logger.warning("采集器已在运行")
            return
            
        self._running = True
        
        # 为每个股票创建采集任务
        for stock_code in self._watch_list:
            task = asyncio.create_task(self._collect_loop(stock_code))
            self._tasks[stock_code] = task
            
        logger.info(f"启动实时数据采集，监控 {len(self._watch_list)} 只股票")
    
    async def stop_collecting(self):
        """停止采集"""
        self._running = False
        
        # 取消所有任务
        for task in self._tasks.values():
            task.cancel()
        
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        
        logger.info("停止实时数据采集")
    
    async def _collect_loop(self, stock_code: str):
        """采集循环"""
        while self._running:
            try:
                # 获取实时数据
                price_data = await self._fetch_realtime_data(stock_code)
                
                if price_data:
                    # 更新缓存
                    self._latest_prices[stock_code] = price_data.close
                    
                    # 触发回调
                    for callback in self._callbacks:
                        try:
                            await callback(stock_code, price_data)
                        except Exception as e:
                            logger.error(f"执行回调失败: {e}")
                
                # 等待下一个采集周期
                await asyncio.sleep(self.collect_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"采集 {stock_code} 数据失败: {e}")
                await asyncio.sleep(self.collect_interval)
    
    async def _fetch_realtime_data(self, stock_code: str) -> Optional[PriceData]:
        """获取实时数据（自动选择数据源）"""
        # 按优先级尝试各数据源
        sorted_sources = sorted(
            self._data_sources.values(),
            key=lambda x: x.priority,
            reverse=True
        )
        
        for source in sorted_sources:
            if not source.enabled:
                continue
                
            try:
                if source.name == "tushare":
                    return await self._fetch_from_tushare(stock_code)
                elif source.name == "akshare":
                    return await self._fetch_from_akshare(stock_code)
                elif source.name == "simulation":
                    return await self._fetch_simulation(stock_code)
            except Exception as e:
                logger.warning(f"数据源 {source.name} 获取 {stock_code} 失败: {e}")
                continue
        
        logger.error(f"所有数据源均失败: {stock_code}")
        return None
    
    async def _fetch_from_tushare(self, stock_code: str) -> Optional[PriceData]:
        """从Tushare获取实时数据"""
        # TODO: 实现真实的Tushare接口调用
        # 这里使用模拟数据
        return await self._fetch_simulation(stock_code)
    
    async def _fetch_from_akshare(self, stock_code: str) -> Optional[PriceData]:
        """从AkShare获取实时数据"""
        # TODO: 实现真实的AkShare接口调用
        return await self._fetch_simulation(stock_code)
    
    async def _fetch_simulation(self, stock_code: str) -> Optional[PriceData]:
        """模拟实时数据（用于测试）"""
        # 获取上一手价格
        last_price = self._latest_prices.get(stock_code, 10.0)
        
        # 模拟价格波动（±1%）
        change_pct = random.uniform(-0.01, 0.01)
        current_price = last_price * (1 + change_pct)
        
        # 模拟OHLC
        open_price = last_price
        high_price = max(last_price, current_price) * random.uniform(1.0, 1.02)
        low_price = min(last_price, current_price) * random.uniform(0.98, 1.0)
        
        # 模拟成交量
        volume = random.randint(10000, 1000000)
        
        # 模拟成交额
        amount = current_price * volume
        
        return PriceData(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(current_price, 2),
            volume=volume
        )
    
    async def fetch_once(self, stock_code: str) -> Optional[PriceData]:
        """单次获取实时数据"""
        return await self._fetch_realtime_data(stock_code)
    
    def get_latest_price(self, stock_code: str) -> Optional[float]:
        """获取最新价格"""
        return self._latest_prices.get(stock_code)
    
    def get_status(self) -> dict:
        """获取采集器状态"""
        return {
            "running": self._running,
            "watch_count": len(self._watch_list),
            "active_tasks": len(self._tasks),
            "data_sources": {
                name: {"enabled": cfg.enabled, "priority": cfg.priority}
                for name, cfg in self._data_sources.items()
            }
        }


class DataCollectorFactory:
    """数据采集器工厂"""
    
    @staticmethod
    def create_collector(collector_type: str = "realtime", **kwargs) -> RealtimeCollector:
        """创建采集器"""
        if collector_type == "realtime":
            return RealtimeCollector(**kwargs)
        else:
            raise ValueError(f"未知的采集器类型: {collector_type}")


# 导出
__all__ = ['RealtimeCollector', 'DataCollectorFactory', 'DataSourceConfig', 'PriceData']