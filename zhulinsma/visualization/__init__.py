#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竹林司马 - 可视化模块
提供交互式图表、HTML报告生成和性能优化功能

主要组件:
1. ChartGenerator - 交互式图表生成器
2. TechnicalVisualizer - 技术指标可视化器
3. ReportGenerator - HTML报告生成器
4. PerformanceOptimizer - 性能优化器

作者：杨总的工作助手
日期：2026年3月30日
版本：1.0.0
"""

from .chart_generator import ChartGenerator
from .technical_visualizer import TechnicalVisualizer
from .report_generator import ReportGenerator
from .performance_optimizer import PerformanceOptimizer, PerformanceUtils

__version__ = '1.0.0'
__author__ = '杨总的工作助手'
__all__ = [
    'ChartGenerator',
    'TechnicalVisualizer',
    'ReportGenerator',
    'PerformanceOptimizer',
    'PerformanceUtils'
]

print(f"竹林司马可视化模块 v{__version__} 已加载")