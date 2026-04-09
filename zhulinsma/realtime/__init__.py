"""
竹林司马实时数据流处理引擎
统一整合WebSocket网关、数据采集、增量计算、预警触发、优化存储
"""
import asyncio
import logging
from typing import Optional, List, Dict, Callable
from datetime import datetime

from .gateway import RealtimeGateway
from .collector import RealtimeCollector, DataSourceConfig
from .processor import IncrementalEngine, PriceData, IndicatorResult
from .trigger import AlertTrigger, AlertRule, AlertManager, AlertType
from .protocol import RealtimeData, MessageParser

# 导入优化流组件（可选，容错处理）
try:
    from zhulinsma.streaming import OptimizedRealTimeStream, StreamConfig
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    OptimizedRealTimeStream = None
    StreamConfig = None

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealtimeEngine:
    """实时数据流处理引擎 - 整合所有实时模块"""
    
    def __init__(
        self,
        ws_host: str = "0.0.0.0",
        ws_port: int = 8765,
        collect_interval: float = 3.0,
        streaming_config: Optional[Dict] = None
    ):
        # 配置参数
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.collect_interval = collect_interval
        self._streaming_config = streaming_config or {}
        
        # 核心组件
        self.gateway = RealtimeGateway(host=ws_host, port=ws_port)
        self.collector = RealtimeCollector(collect_interval=collect_interval)
        self.engine = IncrementalEngine()
        self.alert_manager = AlertManager(gateway=self.gateway)
        
        # 优化存储组件（零拷贝 + 环形缓冲区 + 内存映射）
        self._stream: Optional[OptimizedRealTimeStream] = None
        if STREAMING_AVAILABLE and self._streaming_config.get("enabled", True):
            try:
                cfg = StreamConfig(
                    ring_buffer_capacity=self._streaming_config.get("ring_capacity", 4096),
                    zero_copy_pool_size=self._streaming_config.get("zero_copy_pool", 512),
                    mmap_path=self._streaming_config.get("mmap_path"),
                    enable_stats=self._streaming_config.get("enable_stats", True),
                )
                self._stream = OptimizedRealTimeStream(config=cfg)
                logger.info("优化存储组件 (streaming) 集成成功")
            except Exception as e:
                logger.warning(f"优化存储组件初始化失败，降级运行: {e}")
        
        # 状态
        self._running = False
        self._initialized = False
        
        # 注册回调
        self.collector.add_callback(self._on_realtime_data)
        
    async def initialize(self):
        """初始化引擎"""
        if self._initialized:
            logger.warning("引擎已初始化")
            return
            
        # 设置网关回调
        self.gateway.on_subscribe = self._on_subscribe
        self.gateway.on_unsubscribe = self._on_unsubscribe
        
        self._initialized = True
        logger.info("实时数据流处理引擎初始化完成")
    
    async def start(self):
        """启动引擎"""
        if not self._initialized:
            await self.initialize()
            
        if self._running:
            logger.warning("引擎已在运行")
            return
            
        self._running = True
        
        # 启动WebSocket网关
        await self.gateway.start()
        
        # 启动数据采集
        await self.collector.start_collecting()
        
        logger.info(f"实时数据流处理引擎启动: ws://{self.ws_host}:{self.ws_port}")
    
    async def stop(self):
        """停止引擎"""
        self._running = False
        
        # 停止采集
        await self.collector.stop_collecting()
        
        # 停止网关
        await self.gateway.stop()
        
        # 关闭优化存储
        if self._stream is not None:
            try:
                self._stream.close()
                stats = self._stream.get_stats()
                logger.info(f"优化存储已关闭 | 写入:{stats.get('ring_write_count', '?')} | "
                            f"零拷贝命中:{stats.get('zero_copy_hits', '?')} | "
                            f"刷盘:{stats.get('flush_count', '?')}次")
            except Exception as e:
                logger.warning(f"关闭优化存储时出错: {e}")
        
        logger.info("实时数据流处理引擎已停止")
    
    async def _on_realtime_data(self, stock_code: str, price_data: PriceData):
        """实时数据回调"""
        # 增量计算技术指标
        indicators = self.engine.update(stock_code, price_data)
        
        # 写入优化存储（零拷贝 + 环形缓冲区 + 可选落盘）
        if self._stream is not None:
            try:
                self._stream.write_price(
                    stock_code=stock_code,
                    timestamp=price_data.timestamp,
                    open_=price_data.open,
                    high=price_data.high,
                    low=price_data.low,
                    close=price_data.close,
                    volume=price_data.volume,
                )
            except Exception as e:
                logger.warning(f"写入优化存储失败: {e}")
        
        # 推送实时数据到WebSocket客户端
        realtime_data = self._build_realtime_data(stock_code, price_data, indicators)
        await self.gateway.push_realtime_data(stock_code, realtime_data)
        
        # 检查预警
        await self.alert_manager.check_and_notify(stock_code, indicators)
    
    def _build_realtime_data(self, stock_code: str, price_data: PriceData, indicators: IndicatorResult) -> dict:
        """构建实时数据消息"""
        change = price_data.close - price_data.open
        change_pct = (change / price_data.open * 100) if price_data.open > 0 else 0
        
        return {
            "stock_code": stock_code,
            "price": price_data.close,
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": price_data.volume,
            "open": price_data.open,
            "high": price_data.high,
            "low": price_data.low,
            "amount": price_data.close * price_data.volume,
            "timestamp": price_data.timestamp,
            # 技术指标
            "sma_5": indicators.sma_5,
            "sma_10": indicators.sma_10,
            "sma_20": indicators.sma_20,
            "sma_30": indicators.sma_30,
            "ema_12": indicators.ema_12,
            "ema_26": indicators.ema_26,
            "rsi": indicators.rsi,
            "macd": indicators.macd,
            "macd_signal": indicators.macd_signal,
            "macd_hist": indicators.macd_hist,
            "boll_upper": indicators.boll_upper,
            "boll_mid": indicators.boll_mid,
            "boll_lower": indicators.boll_lower,
            # 信号
            "golden_cross": indicators.golden_cross,
            "death_cross": indicators.death_cross,
            "trend": indicators.trend,
            "deviation_5": indicators.deviation_5
        }
    
    async def _on_subscribe(self, client_id: str, stock_codes: List[str], alert_config: dict):
        """订阅回调"""
        for stock_code in stock_codes:
            # 添加到采集监控列表
            self.collector.add_to_watch_list(stock_code)
            
            # 添加预警规则
            if alert_config:
                if "deviation_5" in alert_config:
                    self.alert_manager.add_rule(
                        stock_code, AlertType.DEVIATION_ALERT, alert_config["deviation_5"]
                    )
                if "rsi_overbought" in alert_config:
                    self.alert_manager.add_rule(
                        stock_code, AlertType.RSI_OVERBOUGHT, alert_config["rsi_overbought"]
                    )
                if "rsi_oversold" in alert_config:
                    self.alert_manager.add_rule(
                        stock_code, AlertType.RSI_OVERSOLD, alert_config["rsi_oversold"]
                    )
        
        logger.info(f"客户端 {client_id} 订阅股票: {stock_codes}")
    
    async def _on_unsubscribe(self, client_id: str, stock_codes: List[str]):
        """取消订阅回调"""
        # TODO: 如果没有其他客户端订阅，可以从监控列表移除
        logger.info(f"客户端 {client_id} 取消订阅: {stock_codes}")
    
    def add_watch_stock(self, stock_code: str):
        """添加监控股票"""
        self.collector.add_to_watch_list(stock_code)
    
    def remove_watch_stock(self, stock_code: str):
        """移除监控股票"""
        self.collector.remove_from_watch_list(stock_code)
    
    def add_alert_rule(
        self,
        stock_code: str,
        alert_type: AlertType,
        threshold: float,
        **kwargs
    ):
        """添加预警规则"""
        self.alert_manager.add_rule(stock_code, alert_type, threshold, **kwargs)
    
    def get_status(self) -> dict:
        """获取引擎状态"""
        status = {
            "running": self._running,
            "websocket": self.gateway.get_status(),
            "collector": self.collector.get_status(),
            "engine": {
                "stocks_tracked": self.engine.get_stock_count(),
                "performance": self.engine.get_performance_stats()
            },
            "alerts": self.alert_manager.trigger.get_status()
        }
        # 附加优化存储状态
        if self._stream is not None:
            try:
                status["streaming"] = self._stream.get_stats()
            except Exception:
                status["streaming"] = {"error": "failed to get stats"}
        else:
            status["streaming"] = {"enabled": False}
        return status
    
    def read_history(self, stock_code: str = None, n: int = 10) -> List[dict]:
        """
        从优化存储读取历史数据
        
        Args:
            stock_code: 股票代码，None 表示所有股票
            n: 返回条数
        Returns:
            历史数据列表
        """
        if self._stream is None:
            return []
        try:
            return self._stream.read_latest(stock_code=stock_code, n=n)
        except Exception as e:
            logger.warning(f"读取历史数据失败: {e}")
            return []
    
    def get_streaming_stats(self) -> dict:
        """获取优化存储详细统计"""
        if self._stream is None:
            return {"enabled": False}
        try:
            return self._stream.get_stats()
        except Exception as e:
            return {"error": str(e)}


# 便捷函数
async def create_realtime_engine(**kwargs) -> RealtimeEngine:
    """创建实时引擎"""
    engine = RealtimeEngine(**kwargs)
    await engine.initialize()
    return engine


# 导出
__all__ = [
    'RealtimeEngine',
    'create_realtime_engine',
    'RealtimeGateway',
    'RealtimeCollector',
    'IncrementalEngine',
    'AlertManager',
    'AlertType',
    'AlertRule',
    'IndicatorResult',
    'PriceData'
]