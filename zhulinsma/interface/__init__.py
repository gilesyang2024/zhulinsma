"""
竹林司马 API 接口模块

为竹林司马技术分析工具提供标准化的API接口，
支持外部系统调用和集成。

版本: 1.0.0
创建时间: 2026年3月26日
位置: 广州
作者: 杨总的技术团队
"""

from .technical_api import TechnicalAPI
from .data_quality_api import DataQualityAPI
from .analysis_api import AnalysisAPI
from .web_api import WebAPI

__all__ = [
    'TechnicalAPI',
    'DataQualityAPI',
    'AnalysisAPI',
    'WebAPI'
]

__version__ = '1.0.0'
__author__ = '杨总的技术团队'
__location__ = '广州'