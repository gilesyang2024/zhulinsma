"""
竹林司马 (Zhulinsma) - 优化实时数据流模块
提供零拷贝传输、环形缓冲区、内存映射文件等高性能数据流处理能力
"""
from .optimized_stream import (
    OptimizedRealTimeStream,
    ZeroCopyBuffer,
    RingBuffer,
    MMapDataStore,
    StreamConfig,
    StreamStats
)

__all__ = [
    'OptimizedRealTimeStream',
    'ZeroCopyBuffer',
    'RingBuffer',
    'MMapDataStore',
    'StreamConfig',
    'StreamStats'
]

__version__ = "1.0.0"
