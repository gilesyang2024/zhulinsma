#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竹林司马 - 增强版交互式图表生成器
提供更丰富的交互式图表类型和高级可视化功能

主要增强功能:
1. 3D图表支持
2. 动画图表
3. 实时数据流图表
4. 高级交互功能
5. 自定义主题系统

作者：杨总的工作助手
日期：2026年3月30日
版本：2.0.0
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple, Callable
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import base64
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor
import threading


class EnhancedChartGenerator:
    """增强版交互式图表生成器"""
    
    def __init__(self, 
                 广州模式: bool = True,
                 验证模式: bool = True,
                 缓存大小: int = 200,
                 启用3D: bool = True,
                 启用动画: bool = True,
                 启用实时: bool = False):
        """
        初始化增强版图表生成器
        
        参数:
           广州模式: 是否启用广州优化（红涨绿跌）
           验证模式: 是否启用数据验证
           缓存大小: 图表缓存大小
           启用3D: 是否启用3D图表支持
           启用动画: 是否启用动画效果
           启用实时: 是否启用实时数据流
        """
        self.广州模式 = 广州模式
        self.验证模式 = 验证模式
        self.缓存大小 = 缓存大小
        self.启用3D = 启用3D
        self.启用动画 = 启用动画
        self.启用实时 = 启用实时
        
        # 颜色配置（广州模式：红涨绿跌）
        if self.广州模式:
            self.上涨颜色 = '#e74c3c'  # 红色
            self.下跌颜色 = '#27ae60'  # 绿色
        else:
            self.上涨颜色 = '#27ae60'  # 绿色
            self.下跌颜色 = '#e74c3c'  # 红色
            
        self.中性颜色 = '#3498db'  # 蓝色
        self.警告颜色 = '#f39c12'  # 橙色
        self.成功颜色 = '#2ecc71'  # 绿色
        
        # 主题配置
        self.主题配置 = {
            'light': {
                '背景颜色': '#ffffff',
                '文字颜色': '#2c3e50',
                '网格颜色': '#e0e0e0',
                '卡片背景': '#f8f9fa'
            },
            'dark': {
                '背景颜色': '#1a1a2e',
                '文字颜色': '#e0e0e0',
                '网格颜色': '#2d3748',
                '卡片背景': '#2d3748'
            }
        }
        
        self.当前主题 = 'light'
        
        # 图表缓存
        self.图表缓存 = {}
        self.缓存锁 = threading.Lock()
        
        # 实时数据流
        self.实时数据流 = {}
        self.实时订阅者 = {}
        
        # 性能监控
        self.性能统计 = {
            '图表生成次数': 0,
            '平均生成时间': 0,
            '缓存命中率': 0
        }
        
        print(f"[增强图表生成器] 初始化完成 - 3D支持: {启用3D}, 动画: {启用动画}, 实时: {启用实时}")
    
    def _验证数据增强(self, 数据: Any, 数据类型: str = "通用", 严格模式: bool = False) -> Tuple[bool, str]:
        """增强版数据验证"""
        if not self.验证模式:
            return True, "验证已禁用"
            
        if 数据 is None:
            return False, f"{数据类型}数据为空"
            
        # 检查数据类型
        if isinstance(数据, (list, np.ndarray, pd.Series, pd.DataFrame)):
            if isinstance(数据, (list, np.ndarray)):
                if len(数据) == 0:
                    return False, f"{数据类型}数据长度为0"
                    
                # 检查NaN值
                if isinstance(数据, np.ndarray):
                    if np.any(np.isnan(数据)):
                        return False, f"{数据类型}数据包含NaN值"
                        
            elif isinstance(数据, pd.Series):
                if 数据.empty:
                    return False, f"{数据类型}数据为空"
                    
                if 数据.isnull().any():
                    return False, f"{数据类型}数据包含NaN值"
                    
            elif isinstance(数据, pd.DataFrame):
                if 数据.empty:
                    return False, f"{数据类型}数据为空"
                    
                if 数据.isnull().any().any():
                    return False, f"{数据类型}数据包含NaN值"
                    
            # 严格模式：检查数据分布
            if 严格模式:
                if isinstance(数据, (np.ndarray, pd.Series)):
                    # 检查异常值
                    if len(数据) > 10:
                        均值 = np.mean(数据)
                        标准差 = np.std(数据)
                        异常值 = np.sum(np.abs(数据 - 均值) > 3 * 标准差)
                        if 异常值 / len(数据) > 0.1:  # 超过10%的异常值
                            return False, f"{数据类型}数据异常值过多"
                            
        else:
            return False, f"{数据类型}数据类型不支持: {type(数据)}"
            
        return True, "验证通过"
    
    @lru_cache(maxsize=100)
    def _计算技术指标缓存(self, 数据: tuple, 指标类型: str, 参数: tuple) -> np.ndarray:
        """缓存技术指标计算结果"""
        # 将元组转换回数组
        数据数组 = np.array(数据)
        
        if 指标类型 == 'sma':
            周期 = 参数[0]
            if len(数据数组) < 周期:
                return np.array([])
            return np.convolve(数据数组, np.ones(周期)/周期, mode='valid')
        elif 指标类型 == 'ema':
            周期 = 参数[0]
            if len(数据数组) < 周期:
                return np.array([])
            # 简化EMA计算
            权重 = 2 / (周期 + 1)
            ema = np.zeros_like(数据数组)
            ema[0] = 数据数组[0]
            for i in range(1, len(数据数组)):
                ema[i] = (数据数组[i] * 权重) + (ema[i-1] * (1 - 权重))
            return ema
        elif 指标类型 == 'rsi':
            周期 = 参数[0]
            if len(数据数组) < 周期 + 1:
                return np.array([])
            # 简化RSI计算
            变化 = np.diff(数据数组)
            上涨 = np.where(变化 > 0, 变化, 0)
            下跌 = np.where(变化 < 0, -变化, 0)
            
            平均上涨 = np.convolve(上涨, np.ones(周期)/周期, mode='valid')
            平均下跌 = np.convolve(下跌, np.ones(周期)/周期, mode='valid')
            
            rsi = 100 - 100 / (1 + 平均上涨 / (平均下跌 + 1e-10))
            return rsi
            
        return np.array([])
    
    def 生成3D价格曲面图(self, 
                         时间数据: List,
                         价格数据: np.ndarray,
                         波动率数据: np.ndarray,
                         标题: str = "3D价格曲面分析") -> go.Figure:
        """生成3D价格曲面图"""
        if not self.启用3D:
            return self._生成错误图表("3D功能未启用")
            
        验证结果, 消息 = self._验证数据增强(价格数据, "价格", True)
        if not 验证结果:
            return self._生成错误图表(f"数据验证失败: {消息}")
            
        # 创建3D曲面数据
        X = np.arange(len(时间数据))
        Y = np.arange(价格数据.shape[1] if len(价格数据.shape) > 1 else 1)
        
        if len(价格数据.shape) == 1:
            # 一维数据转换为二维
            Z = np.tile(价格数据, (len(Y), 1)).T
        else:
            Z = 价格数据
            
        # 创建3D曲面图
        fig = go.Figure(data=[
            go.Surface(
                x=X, y=Y, z=Z,
                colorscale='RdYlGn' if self.广州模式 else 'YlGnRd',
                opacity=0.8,
                contours={
                    "z": {"show": True, "usecolormap": True, "highlightcolor": "limegreen", "project": {"z": True}}
                }
            )
        ])
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=24, color=self.主题配置[self.当前主题]['文字颜色']),
                x=0.5
            ),
            scene=dict(
                xaxis_title='时间',
                yaxis_title='价格维度',
                zaxis_title='价格',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                ),
                bgcolor=self.主题配置[self.当前主题]['背景颜色']
            ),
            width=1200,
            height=800,
            paper_bgcolor=self.主题配置[self.当前主题]['背景颜色'],
            font=dict(color=self.主题配置[self.当前主题]['文字颜色'])
        )
        
        return fig
    
    def 生成动画价格走势图(self,
                          时间序列: List,
                          价格序列: List[np.ndarray],
                          标题: str = "动画价格走势分析",
                          帧间隔: int = 100) -> go.Figure:
        """生成动画价格走势图"""
        if not self.启用动画:
            return self._生成错误图表("动画功能未启用")
            
        # 创建基础图表
        fig = go.Figure(
            data=[go.Scatter(
                x=时间序列[:1],
                y=价格序列[:1],
                mode='lines',
                line=dict(color=self.上涨颜色, width=3)
            )],
            layout=go.Layout(
                title=dict(
                    text=标题,
                    font=dict(size=20),
                    x=0.5
                ),
                xaxis=dict(
                    range=[0, len(时间序列)],
                    title="时间"
                ),
                yaxis=dict(
                    range=[min(np.concatenate(价格序列)) * 0.9, 
                          max(np.concatenate(价格序列)) * 1.1],
                    title="价格"
                ),
                updatemenus=[dict(
                    type="buttons",
                    buttons=[dict(
                        label="播放",
                        method="animate",
                        args=[None, dict(
                            frame=dict(duration=帧间隔, redraw=True),
                            fromcurrent=True,
                            mode="immediate"
                        )]
                    )]
                )]
            ),
            frames=[
                go.Frame(
                    data=[go.Scatter(
                        x=时间序列[:k+1],
                        y=价格序列[:k+1]
                    )]
                )
                for k in range(1, len(时间序列))
            ]
        )
        
        return fig
    
    def 生成实时数据流图(self,
                        数据源: str,
                        最大数据点: int = 1000,
                        标题: str = "实时数据流分析") -> go.Figure:
        """生成实时数据流图"""
        if not self.启用实时:
            return self._生成错误图表("实时功能未启用")
            
        # 创建初始图表
        fig = go.Figure(
            data=[go.Scatter(
                x=[],
                y=[],
                mode='lines+markers',
                line=dict(color=self.上涨颜色, width=2),
                marker=dict(size=8, color=self.下跌颜色)
            )],
            layout=go.Layout(
                title=dict(text=标题, font=dict(size=20), x=0.5),
                xaxis=dict(title="时间"),
                yaxis=dict(title="数值"),
                hovermode='x unified'
            )
        )
        
        # 注册实时数据源
        self.实时数据流[数据源] = fig
        self.实时订阅者[数据源] = []
        
        return fig
    
    def 更新实时数据(self, 数据源: str, 新数据: Dict):
        """更新实时数据"""
        if 数据源 not in self.实时数据流:
            return
            
        fig = self.实时数据流[数据源]
        
        # 获取当前数据
        当前x = fig.data[0].x
        当前y = fig.data[0].y
        
        # 添加新数据
        新x = list(当前x) + [新数据.get('时间', datetime.now())]
        新y = list(当前y) + [新数据.get('数值', 0)]
        
        # 限制数据点数量
        if len(新x) > 1000:
            新x = 新x[-1000:]
            新y = 新y[-1000:]
        
        # 更新图表数据
        fig.data[0].x = 新x
        fig.data[0].y = 新y
        
        # 通知订阅者
        for 订阅者 in self.实时订阅者[数据源]:
            订阅者(fig)
    
    def 生成高级技术指标仪表盘(self,
                               技术指标数据: Dict[str, Dict],
                               标题: str = "高级技术指标仪表盘") -> go.Figure:
        """生成高级技术指标仪表盘"""
        # 创建子图
        fig = make_subplots(
            rows=2, cols=3,
            subplot_titles=('RSI指标', 'MACD指标', '布林带', 
                           '成交量分析', '波动率分析', '动量分析'),
            specs=[[{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
                   [{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}]],
            vertical_spacing=0.1,
            horizontal_spacing=0.1
        )
        
        # RSI指标图
        if 'RSI' in 技术指标数据:
            rsi_data = 技术指标数据['RSI']
            fig.add_trace(
                go.Scatter(
                    x=rsi_data.get('时间', []),
                    y=rsi_data.get('数值', []),
                    mode='lines',
                    name='RSI',
                    line=dict(color='purple', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(128, 0, 128, 0.1)'
                ),
                row=1, col=1
            )
            # 添加超买超卖线
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)
        
        # MACD指标图
        if 'MACD' in 技术指标数据:
            macd_data = 技术指标数据['MACD']
            fig.add_trace(
                go.Scatter(
                    x=macd_data.get('时间', []),
                    y=macd_data.get('MACD线', []),
                    mode='lines',
                    name='MACD',
                    line=dict(color='blue', width=2)
                ),
                row=1, col=2
            )
            fig.add_trace(
                go.Scatter(
                    x=macd_data.get('时间', []),
                    y=macd_data.get('信号线', []),
                    mode='lines',
                    name='信号线',
                    line=dict(color='orange', width=2, dash='dash')
                ),
                row=1, col=2
            )
        
        # 布林带图
        if '布林带' in 技术指标数据:
            bb_data = 技术指标数据['布林带']
            fig.add_trace(
                go.Scatter(
                    x=bb_data.get('时间', []),
                    y=bb_data.get('上轨', []),
                    mode='lines',
                    name='上轨',
                    line=dict(color='gray', width=1, dash='dash')
                ),
                row=1, col=3
            )
            fig.add_trace(
                go.Scatter(
                    x=bb_data.get('时间', []),
                    y=bb_data.get('中轨', []),
                    mode='lines',
                    name='中轨',
                    line=dict(color='black', width=2)
                ),
                row=1, col=3
            )
            fig.add_trace(
                go.Scatter(
                    x=bb_data.get('时间', []),
                    y=bb_data.get('下轨', []),
                    mode='lines',
                    name='下轨',
                    line=dict(color='gray', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(128, 128, 128, 0.1)'
                ),
                row=1, col=3
            )
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=24, color=self.主题配置[self.当前主题]['文字颜色']),
                x=0.5
            ),
            height=800,
            showlegend=True,
            paper_bgcolor=self.主题配置[self.当前主题]['背景颜色'],
            plot_bgcolor='white'
        )
        
        return fig
    
    def 生成交互式热力图(self,
                        数据矩阵: np.ndarray,
                        行标签: List,
                        列标签: List,
                        标题: str = "交互式热力图") -> go.Figure:
        """生成交互式热力图"""
        # 创建热力图
        fig = go.Figure(data=go.Heatmap(
            z=数据矩阵,
            x=列标签,
            y=行标签,
            colorscale='RdYlGn' if self.广州模式 else 'YlGnRd',
            hoverongaps=False,
            colorbar=dict(
                title="数值",
                titleside="right"
            )
        ))
        
        # 添加交互功能
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.主题配置[self.当前主题]['文字颜色']),
                x=0.5
            ),
            xaxis=dict(
                title="列",
                tickangle=-45
            ),
            yaxis=dict(
                title="行"
            ),
            width=1000,
            height=600,
            paper_bgcolor=self.主题配置[self.当前主题]['背景颜色']
        )
        
        # 添加点击事件
        fig.update_traces(
            hovertemplate="行: %{y}<br>列: %{x}<br>数值: %{z}<extra></extra>"
        )
        
        return fig
    
    def 生成多时间尺度对比图(self,
                            多尺度数据: Dict[str, Dict],
                            标题: str = "多时间尺度对比分析") -> go.Figure:
        """生成多时间尺度对比图"""
        # 创建子图
        fig = make_subplots(
            rows=len(多尺度数据), cols=1,
            subplot_titles=list(多尺度数据.keys()),
            shared_xaxes=True,
            vertical_spacing=0.05
        )
        
        for i, (尺度名称, 尺度数据) in enumerate(多尺度数据.items(), 1):
            fig.add_trace(
                go.Scatter(
                    x=尺度数据.get('时间', []),
                    y=尺度数据.get('价格', []),
                    mode='lines',
                    name=尺度名称,
                    line=dict(
                        color=self.上涨颜色 if i % 2 == 0 else self.下跌颜色,
                        width=2
                    )
                ),
                row=i, col=1
            )
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=24, color=self.主题配置[self.当前主题]['文字颜色']),
                x=0.5
            ),
            height=300 * len(多尺度数据),
            showlegend=True,
            hovermode='x unified',
            paper_bgcolor=self.主题配置[self.当前主题]['背景颜色']
        )
        
        return fig
    
    def 生成风险收益散点图(self,
                          风险数据: np.ndarray,
                          收益数据: np.ndarray,
                          标签数据: Optional[List] = None,
                          标题: str = "风险收益散点分析") -> go.Figure:
        """生成风险收益散点图"""
        # 创建散点图
        scatter = go.Scatter(
            x=风险数据,
            y=收益数据,
            mode='markers',
            marker=dict(
                size=12,
                color=收益数据,  # 颜色表示收益
                colorscale='RdYlGn' if self.广州模式 else 'YlGnRd',
                showscale=True,
                colorbar=dict(title="收益")
            ),
            text=标签数据,
            hoverinfo='text+x+y'
        )
        
        fig = go.Figure(data=[scatter])
        
        # 添加趋势线
        if len(风险数据) > 1:
            # 计算线性回归
            coeffs = np.polyfit(风险数据, 收益数据, 1)
            趋势线 = np.polyval(coeffs, 风险数据)
            
            fig.add_trace(
                go.Scatter(
                    x=风险数据,
                    y=趋势线,
                    mode='lines',
                    name='趋势线',
                    line=dict(color='black', width=2, dash='dash')
                )
            )
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.主题配置[self.当前主题]['文字颜色']),
                x=0.5
            ),
            xaxis=dict(title="风险"),
            yaxis=dict(title="收益"),
            width=900,
            height=600,
            paper_bgcolor=self.主题配置[self.当前主题]['背景颜色']
        )
        
        return fig
    
    def 生成示例增强报告(self, 输出目录: str = "./enhanced_reports") -> Dict[str, str]:
        """生成增强版示例报告"""
        import os
        os.makedirs(输出目录, exist_ok=True)
        
        结果文件 = {}
        
        # 1. 生成3D价格曲面图
        print("[信息] 生成3D价格曲面图...")
        时间数据 = list(range(100))
        价格数据 = np.random.randn(100, 50).cumsum(axis=0) + 100
        波动率数据 = np.random.rand(100, 50)
        
        fig_3d = self.生成3D价格曲面图(时间数据, 价格数据, 波动率数据, "示例3D价格曲面")
        fig_3d.write_html(os.path.join(输出目录, "3d_surface.html"))
        结果文件['3D曲面图'] = os.path.join(输出目录, "3d_surface.html")
        
        # 2. 生成高级技术指标仪表盘
        print("[信息] 生成高级技术指标仪表盘...")
        # 模拟技术指标数据
        技术指标数据 = {
            'RSI': {
                '时间': list(range(100)),
                '数值': np.random.uniform(20, 80, 100)
            },
            'MACD': {
                '时间': list(range(100)),
                'MACD线': np.random.randn(100).cumsum(),
                '信号线': np.random.randn(100).cumsum() * 0.8
            },
            '布林带': {
                '时间': list(range(100)),
                '上轨': np.random.randn(100).cumsum() + 2,
                '中轨': np.random.randn(100).cumsum(),
                '下轨': np.random.randn(100).cumsum() - 2
            }
        }
        
        fig_dashboard = self.生成高级技术指标仪表盘(技术指标数据, "示例高级技术指标仪表盘")
        fig_dashboard.write_html(os.path.join(输出目录, "advanced_dashboard.html"))
        结果文件['高级仪表盘'] = os.path.join(输出目录, "advanced_dashboard.html")
        
        # 3. 生成交互式热力图
        print("[信息] 生成交互式热力图...")
        数据矩阵 = np.random.randn(20, 15).cumsum(axis=0)
        行标签 = [f"行{i+1}" for i in range(20)]
        列标签 = [f"列{j+1}" for j in range(15)]
        
        fig_heatmap = self.生成交互式热力图(数据矩阵, 行标签, 列标签, "示例交互式热力图")
        fig_heatmap.write_html(os.path.join(输出目录, "interactive_heatmap.html"))
        结果文件['交互式热力图'] = os.path.join(输出目录, "interactive_heatmap.html")
        
        # 4. 生成多时间尺度对比图
        print("[信息] 生成多时间尺度对比图...")
        多尺度数据 = {
            '日线': {
                '时间': list(range(100)),
                '价格': np.random.randn(100).cumsum() + 100
            },
            '周线': {
                '时间': list(range(0, 100, 5)),
                '价格': np.random.randn(20).cumsum() + 100
            },
            '月线': {
                '时间': list(range(0, 100, 20)),
                '价格': np.random.randn(5).cumsum() + 100
            }
        }
        
        fig_multiscale = self.生成多时间尺度对比图(多尺度数据, "示例多时间尺度对比")
        fig_multiscale.write_html(os.path.join(输出目录, "multiscale_comparison.html"))
        结果文件['多尺度对比图'] = os.path.join(输出目录, "multiscale_comparison.html")
        
        # 5. 生成风险收益散点图
        print("[信息] 生成风险收益散点图...")
        风险数据 = np.random.uniform(0.1, 0.5, 50)
        收益数据 = np.random.uniform(-0.2, 0.3, 50)
        标签数据 = [f"资产{i+1}" for i in range(50)]
        
        fig_scatter = self.生成风险收益散点图(风险数据, 收益数据, 标签数据, "示例风险收益散点分析")
        fig_scatter.write_html(os.path.join(输出目录, "risk_reward_scatter.html"))
        结果文件['风险收益散点图'] = os.path.join(输出目录, "risk_reward_scatter.html")
        
        print(f"[成功] 增强版示例报告生成完成，文件保存在: {输出目录}")
        return 结果文件
    
    def _生成错误图表(self, 错误信息: str) -> go.Figure:
        """生成错误信息图表"""
        fig = go.Figure()
        fig.add_annotation(
            text=f"图表生成错误: {错误信息}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        fig.update_layout(
            title="错误",
            paper_bgcolor="white",
            plot_bgcolor="white"
        )
        return fig
    
    def _颜色转RGB(self, 颜色代码: str) -> str:
        """转换颜色代码为RGB格式"""
        if 颜色代码.startswith('#'):
            r = int(颜色代码[1:3], 16)
            g = int(颜色代码[3:5], 16)
            b = int(颜色代码[5:7], 16)
            return f"{r}, {g}, {b}"
        return "0, 0, 0"


# 测试代码
if __name__ == "__main__":
    print("=== 竹林司马增强版图表生成器测试 ===")
    
    # 创建增强版图表生成器
    enhanced_gen = EnhancedChartGenerator(
        广州模式=True,
        验证模式=True,
        启用3D=True,
        启用动画=True,
        启用实时=False
    )
    
    # 生成示例增强报告
    results = enhanced_gen.生成示例增强报告("./test_enhanced_reports")
    
    print("\n生成的文件:")
    for name, path in results.items():
        print(f"  {name}: {path}")
    
    print("\n=== 增强版测试完成 ===")