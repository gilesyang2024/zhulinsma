import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator
from datetime import datetime
import numpy as np

from zhulinsma.core.indicators import TechnicalIndicators
from zhulinsma.core.quality import DataQualityManager

logger = logging.getLogger(__name__)


class RealTimeDataPipeline:
    """竹林司马实时数据处理流水线
    
    构建高性能实时数据处理架构，支持：
    - 异步数据流接入
    - 智能缓冲与批处理
    - 增量指标计算
    - 实时质量监控
    """
    
    def __init__(self, buffer_size: int = 100, batch_interval: float = 0.5):
        """初始化实时数据流水线
        
        参数:
            buffer_size: 缓冲区大小（数据点数量）
            batch_interval: 批处理间隔（秒）
        """
        self.buffer = asyncio.Queue(maxsize=buffer_size)
        self.buffer_size = buffer_size
        self.batch_interval = batch_interval
        
        # 核心组件
        self.技术指标工具 = TechnicalIndicators()
        self.数据质量监控器 = DataQualityManager()
        
        # 状态跟踪
        self.开始时间 = datetime.now()
        self.处理计数 = 0
        self.错误计数 = 0
        self.延迟监控 = []
        
        logger.info(f"🚀 实时数据流水线初始化完成 | 缓冲区: {buffer_size} | 间隔: {batch_interval}s")

    async def 数据源接入(self, 数据源: AsyncGenerator):
        """从数据源接收实时数据流
        
        参数:
            数据源: 异步生成器，提供实时数据点
                {
                    "股票代码": "000001.SZ",
                    "时间戳": "2026-04-02T09:05:23",
                    "价格": 15.85,
                    "成交量": 125000
                }
        """
        async for 数据点 in 数据源:
            try:
                start_time = datetime.now()
                
                # 数据质量验证
                质量结果 = self.数据质量监控器.验证单点数据(数据点)
                if not 质量结果["通过"]:
                    logger.warning(f"⚠️ 数据质量异常: {数据点['股票代码']} | 问题: {质量结果['问题']}")
                    continue
                
                # 添加到缓冲区
                await self.buffer.put(数据点)
                
                # 计算延迟
                latency = (datetime.now() - start_time).total_seconds()
                self.延迟监控.append(latency)
                
                if len(self.延迟监控) > 100:
                    self.延迟监控.pop(0)
                    
            except Exception as e:
                self.错误计数 += 1
                logger.error(f"❌ 数据源接入错误: {str(e)}")

    async def 处理流水线(self):
        """核心处理流水线 - 持续处理缓冲区数据"""
        while True:
            try:
                # 等待缓冲区有数据或超时
                if self.buffer.empty():
                    await asyncio.sleep(self.batch_interval)
                    continue
                
                # 获取一批数据
                批数据 = []
                while not self.buffer.empty() and len(批数据) < self.buffer_size:
                    批数据.append(await self.buffer.get())
                    
                if not 批数据:
                    continue
                
                # 按股票代码分组
                股票数据 = {}
                for 数据点 in 批数据:
                    股票代码 = 数据点["股票代码"]
                    if 股票代码 not in 股票数据:
                        股票数据[股票代码] = {
                            "时间戳": [],
                            "价格": [],
                            "成交量": []
                        }
                    股票数据[股票代码]["时间戳"].append(数据点["时间戳"])
                    股票数据[股票代码]["价格"].append(数据点["价格"])
                    股票数据[股票代码]["成交量"].append(数据点["成交量"])
                
                # 并行处理各股票数据
                处理任务 = []
                for 股票代码, 数据 in 股票数据.items():
                    处理任务.append(
                        self._处理单只股票(股票代码, 数据["价格"], 数据["时间戳"])
                    )
                
                await asyncio.gather(*处理任务)
                
            except Exception as e:
                self.错误计数 += 1
                logger.error(f"❌ 流水线处理错误: {str(e)}")

    async def _处理单只股票(self, 股票代码: str, 价格序列: List[float], 时间戳: List[str]):
        """处理单只股票的实时数据"""
        try:
            # 增量计算技术指标
            指标结果 = {}
            
            # SMA (20周期) - 增量计算
            if len(价格序列) >= 20:
                sma20 = self.技术指标工具.计算SMA(价格序列[-20:], 周期=20)
                指标结果["SMA_20"] = sma20
            
            # RSI (14周期) - 增量计算
            if len(价格序列) >= 14:
                rsi14 = self.技术指标工具.计算RSI(价格序列[-14:], 周期=14)
                指标结果["RSI_14"] = rsi14

            # MACD - 增量计算
            if len(价格序列) >= 26:
                macd = self.技术指标工具.计算MACD(价格序列[-26:])
                指标结果["MACD"] = macd

            # 实时趋势分析
            趋势分析 = self._实时趋势分析(价格序列)

            # 发布分析结果 (可替换为实际发布逻辑)
            self._发布结果(股票代码, {
                "指标": 指标结果,
                "趋势": 趋势分析,
                "时间戳": datetime.now().isoformat()
            })
            
            self.处理计数 += 1
            
        except Exception as e:
            self.错误计数 += 1
            logger.error(f"❌ 股票 {股票代码} 处理失败: {str(e)}")

    def _实时趋势分析(self, 价格序列: List[float]) -> Dict:
        """基于最新价格的实时趋势分析"""
        if len(价格序列) < 5:
            return {"状态": "数据不足", "趋势": "未知"}

        # 简单趋势判断 (可扩展为更复杂的逻辑)
        最新5 = 价格序列[-5:]
        趋势 = "上升" if 最新5[-1] > 最新5[0] else "下降"
        
        # 趋势强度 (简单计算)
        强度 = abs(最新5[-1] - 最新5[0]) / 最新5[0]

        return {
            "趋势方向": 趋势,
            "趋势强度": f"{强度:.2%}",
            "最新价格": 价格序列[-1]
        }

    def _发布结果(self, 股票代码: str, 结果: Dict):
        """发布处理结果 (可扩展为实际消息推送)"""
        # 实际应用中可替换为WebSocket推送、消息队列等
        logger.debug(f"📤 实时结果发布: {股票代码} | {结果}")

    def 获取状态(self) -> Dict:
        """获取流水线运行状态"""
        return {
            "系统名称": "竹林司马 (Zhulinsma) 实时数据流水线",
            "状态": "运行中",
            "缓冲区大小": self.buffer_size,
            "缓冲区使用": self.buffer.qsize(),
            "处理计数": self.处理计数,
            "错误计数": self.错误计数,
            "平均延迟": f"{np.mean(self.延迟监控) * 1000:.2f}ms" if self.延迟监控 else "N/A",
            "运行时长": str(datetime.now() - self.开始时间)
        }


# ====================
# 示例使用
# ====================
async def 模拟数据源():
    """模拟实时数据源"""
    import random
    股票列表 = ["000001.SZ", "600000.SH", "300750.SZ"]
    基准价 = {code: random.uniform(10, 50) for code in 股票列表}
    
    for _ in range(1000):
        for 股票代码 in 股票列表:
            # 模拟价格波动
            基准价[股票代码] *= (1 + random.uniform(-0.005, 0.005))
            
            yield {
                "股票代码": 股票代码,
                "时间戳": datetime.now().isoformat(),
                "价格": 基准价[股票代码],
                "成交量": random.randint(1000, 100000)
            }
        await asyncio.sleep(0.1)


async def main():
    # 初始化流水线
    pipeline = RealTimeDataPipeline(buffer_size=50, batch_interval=0.2)
    
    # 启动数据处理任务
    处理任务 = asyncio.create_task(pipeline.处理流水线())
    
    # 接入模拟数据源
    await pipeline.数据源接入(模拟数据源())
    
    # 演示用，实际应持续运行
    await asyncio.sleep(5)
    处理任务.cancel()
    
    print("\n📊 实时数据流水线状态:")
    print(pipeline.获取状态())


if __name__ == "__main__":
    asyncio.run(main())