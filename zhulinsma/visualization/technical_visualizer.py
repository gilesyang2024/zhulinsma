#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竹林司马 - 技术指标可视化模块
专为技术分析设计的可视化功能，支持多种技术指标的可视化展示

作者：杨总的工作助手
日期：2026年3月30日
版本：1.0.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

from .chart_generator import ChartGenerator


class TechnicalVisualizer:
    """技术指标可视化器"""
    
    def __init__(self, 
                 广州模式: bool = True,
                 验证模式: bool = True):
        """
        初始化技术指标可视化器
        
        参数:
           广州模式: 是否启用广州优化（红涨绿跌）
           验证模式: 是否启用数据验证
        """
        self.广州模式 = 广州模式
        self.验证模式 = 验证模式
        self.图表生成器 = ChartGenerator(广州模式=广州模式, 验证模式=验证模式)
        
        # 技术指标配置
        self.指标配置 = {
            'SMA': {
                '名称': '简单移动平均线',
                '描述': '反映价格趋势的平滑线',
                '颜色': '#3498db',
                '样式': 'dash'
            },
            'EMA': {
                '名称': '指数移动平均线',
                '描述': '对近期价格赋予更大权重的移动平均线',
                '颜色': '#e74c3c',
                '样式': 'dash'
            },
            'RSI': {
                '名称': '相对强弱指标',
                '描述': '衡量价格变化速度和幅度的动量指标',
                '颜色': '#9b59b6',
                '样式': 'solid'
            },
            'MACD': {
                '名称': '移动平均收敛发散',
                '描述': '趋势跟踪动量指标',
                '颜色': {
                    'DIF': '#3498db',
                    'DEA': '#e74c3c',
                    '柱状图': '#2c3e50'
                },
                '样式': 'solid'
            },
            '布林带': {
                '名称': '布林带',
                '描述': '基于移动平均线的波动率指标',
                '颜色': {
                    '上轨': '#e74c3c',
                    '中轨': '#f39c12',
                    '下轨': '#27ae60'
                },
            }
        }
        
        print(f"[技术指标可视化器] 初始化完成 - 广州模式: {self.广州模式}")
    
    def 生成综合技术分析图(self,
                        价格数据: Union[np.ndarray, pd.Series, List],
                        技术指标: Dict[str, Any],
                        日期数据: Optional[List] = None,
                        标题: str = "综合技术分析",
                        包含子图: List[str] = ['价格', 'RSI', 'MACD']) -> go.Figure:
        """
        生成综合技术分析图
        
        参数:
            价格数据: 价格数据序列
            技术指标: 技术指标数据字典
            日期数据: 日期序列（可选）
            标题: 图表标题
            包含子图: 要包含的子图类型
            
        返回:
            Plotly图表对象
        """
        if not self._验证数据(价格数据, "价格"):
            return self._生成错误图表("价格数据验证失败")
        
        # 准备数据
        if isinstance(价格数据, pd.Series):
            价格序列 = 价格数据.values
        else:
            价格序列 = np.array(价格数据)
            
        if 日期数据 is None:
            日期序列 = [f"Day {i+1}" for i in range(len(价格序列))]
        else:
            日期序列 = 日期数据
        
        # 确定子图配置
        子图配置 = self._获取子图配置(包含子图, 技术指标)
        n_rows = len(子图配置)
        
        # 创建子图
        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=[配置['标题'] for 配置 in 子图配置.values()]
        )
        
        # 为每个子图添加轨迹
        for row_idx, (子图类型, 配置) in enumerate(子图配置.items(), start=1):
            if 子图类型 == '价格':
                self._添加价格子图(fig, row_idx, 价格序列, 日期序列, 技术指标)
            elif 子图类型 == 'RSI':
                self._添加RSI子图(fig, row_idx, 日期序列, 技术指标)
            elif 子图类型 == 'MACD':
                self._添加MACD子图(fig, row_idx, 日期序列, 技术指标)
            elif 子图类型 == '成交量':
                self._添加成交量子图(fig, row_idx, 日期序列, 技术指标)
            elif 子图类型 == '波动率':
                self._添加波动率子图(fig, row_idx, 日期序列, 技术指标)
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.图表生成器.文字颜色),
                x=0.5
            ),
            height=250 * n_rows,
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=self.图表生成器.字体配置
        )
        
        return fig
    
    def 生成趋势分析图(self,
                    价格数据: Union[np.ndarray, pd.Series, List],
                    移动平均线: Optional[Dict[str, np.ndarray]] = None,
                    趋势线: Optional[List[Tuple[int, int, float]]] = None,
                    日期数据: Optional[List] = None,
                    标题: str = "趋势分析图") -> go.Figure:
        """
        生成趋势分析图
        
        参数:
            价格数据: 价格数据序列
            移动平均线: 移动平均线数据字典 {周期: 数据}
            趋势线: 趋势线数据列表 [(起点, 终点, 斜率)]
            日期数据: 日期序列（可选）
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        if not self._验证数据(价格数据, "价格"):
            return self._生成错误图表("价格数据验证失败")
        
        # 准备数据
        if isinstance(价格数据, pd.Series):
            价格序列 = 价格数据.values
        else:
            价格序列 = np.array(价格数据)
            
        if 日期数据 is None:
            日期序列 = [f"Day {i+1}" for i in range(len(价格序列))]
        else:
            日期序列 = 日期数据
        
        # 创建图表
        fig = go.Figure()
        
        # 添加价格蜡烛图（模拟）
        颜色序列 = self._计算价格颜色序列(价格序列)
        
        # 添加价格线
        fig.add_trace(go.Scatter(
            x=日期序列,
            y=价格序列,
            mode='lines',
            name='价格',
            line=dict(
                color=self.图表生成器.上涨颜色 if self.广州模式 else self.图表生成器.下跌颜色,
                width=1
            )
        ))
        
        # 添加移动平均线
        if 移动平均线 is not None:
            for 周期, 数据 in 移动平均线.items():
                if self._验证数据(数据, f"SMA({周期})"):
                    fig.add_trace(go.Scatter(
                        x=日期序列[int(周期)-1:],
                        y=数据[int(周期)-1:],
                        mode='lines',
                        name=f'SMA({周期})',
                        line=dict(
                            color=self.指标配置['SMA']['颜色'],
                            width=2,
                            dash='dash'
                        )
                    ))
        
        # 添加趋势线
        if 趋势线 is not None:
            for idx, (起点, 终点, 斜率) in enumerate(趋势线):
                if 0 <= 起点 < len(日期序列) and 0 <= 终点 < len(日期序列):
                    x_points = [日期序列[起点], 日期序列[终点]]
                    y_points = [价格序列[起点], 价格序列[起点] + 斜率 * (终点 - 起点)]
                    
                    趋势颜色 = self.图表生成器.上涨颜色 if 斜率 > 0 else self.图表生成器.下跌颜色
                    趋势名称 = '上升趋势' if 斜率 > 0 else '下降趋势'
                    
                    fig.add_trace(go.Scatter(
                        x=x_points,
                        y=y_points,
                        mode='lines',
                        name=f'{趋势名称} {idx+1}',
                        line=dict(
                            color=趋势颜色,
                            width=3,
                            dash='dot'
                        )
                    ))
        
        # 添加支撑阻力线
        支撑线, 阻力线 = self._计算支撑阻力线(价格序列)
        if 支撑线 is not None:
            fig.add_hline(y=支撑线, 
                         line_dash="dash", 
                         line_color=self.图表生成器.下跌颜色,
                         annotation_text="支撑线",
                         annotation_position="bottom right")
        if 阻力线 is not None:
            fig.add_hline(y=阻力线,
                         line_dash="dash",
                         line_color=self.图表生成器.上涨颜色,
                         annotation_text="阻力线",
                         annotation_position="top right")
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.图表生成器.文字颜色),
                x=0.5
            ),
            height=600,
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            xaxis=dict(
                title='日期',
                tickangle=45,
                gridcolor=self.图表生成器.网格颜色
            ),
            yaxis=dict(
                title='价格 (¥)',
                gridcolor=self.图表生成器.网格颜色
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=self.图表生成器.字体配置
        )
        
        return fig
    
    def 生成动量分析图(self,
                    RSI数据: Optional[Union[np.ndarray, pd.Series, List]] = None,
                    MACD数据: Optional[Dict[str, np.ndarray]] = None,
                    KD数据: Optional[Dict[str, np.ndarray]] = None,
                    日期数据: Optional[List] = None,
                    标题: str = "动量分析图") -> go.Figure:
        """
        生成动量分析图
        
        参数:
            RSI数据: RSI指标数据
            MACD数据: MACD指标数据字典 {DIF, DEA, 柱状图}
            KD数据: KD指标数据字典 {K, D}
            日期数据: 日期序列（可选）
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        # 确定子图数量
        子图列表 = []
        if RSI数据 is not None:
            子图列表.append('RSI')
        if MACD数据 is not None:
            子图列表.append('MACD')
        if KD数据 is not None:
            子图列表.append('KD')
            
        if not 子图列表:
            return self._生成错误图表("动量指标数据为空")
        
        n_rows = len(子图列表)
        
        # 创建子图
        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=[self.指标配置[指标]['名称'] for 指标 in 子图列表]
        )
        
        # 为每个子图添加轨迹
        for row_idx, 指标类型 in enumerate(子图列表, start=1):
            if 指标类型 == 'RSI':
                self._添加RSI动量图(fig, row_idx, RSI数据, 日期数据)
            elif 指标类型 == 'MACD':
                self._添加MACD动量图(fig, row_idx, MACD数据, 日期数据)
            elif 指标类型 == 'KD':
                self._添加KD动量图(fig, row_idx, KD数据, 日期数据)
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.图表生成器.文字颜色),
                x=0.5
            ),
            height=250 * n_rows,
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            hovermode='x unified',
            showlegend=True,
            font=self.图表生成器.字体配置
        )
        
        return fig
    
    def 生成模式识别图(self,
                    价格数据: Union[np.ndarray, pd.Series, List],
                    模式列表: List[Dict[str, Any]],
                    日期数据: Optional[List] = None,
                    标题: str = "技术模式识别") -> go.Figure:
        """
        生成技术模式识别图
        
        参数:
            价格数据: 价格数据序列
            模式列表: 识别的技术模式列表
            日期数据: 日期序列（可选）
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        if not self._验证数据(价格数据, "价格"):
            return self._生成错误图表("价格数据验证失败")
        
        # 准备数据
        if isinstance(价格数据, pd.Series):
            价格序列 = 价格数据.values
        else:
            价格序列 = np.array(价格数据)
            
        if 日期数据 is None:
            日期序列 = [f"Day {i+1}" for i in range(len(价格序列))]
        else:
            日期序列 = 日期数据
        
        # 创建图表
        fig = go.Figure()
        
        # 添加价格线
        fig.add_trace(go.Scatter(
            x=日期序列,
            y=价格序列,
            mode='lines',
            name='价格',
            line=dict(
                color='#95a5a6',
                width=1
            )
        ))
        
        # 添加识别的模式
        for 模式 in 模式列表:
            模式类型 = 模式.get('类型', '')
            位置 = 模式.get('位置', [])
            信号 = 模式.get('信号', '中性')
            置信度 = 模式.get('置信度', 50)
            
            if len(位置) >= 2:
                # 获取模式区间的数据
                x_pattern = [日期序列[i] for i in 位置 if i < len(日期序列)]
                y_pattern = [价格序列[i] for i in 位置 if i < len(价格序列)]
                
                if x_pattern and y_pattern:
                    # 根据信号类型确定颜色
                    if 信号 == '看涨':
                        颜色 = self.图表生成器.上涨颜色
                    elif 信号 == '看跌':
                        颜色 = self.图表生成器.下跌颜色
                    else:
                        颜色 = self.图表生成器.中性颜色
                    
                    # 添加模式轨迹
                    fig.add_trace(go.Scatter(
                        x=x_pattern,
                        y=y_pattern,
                        mode='lines+markers',
                        name=f'{模式类型} ({信号})',
                        line=dict(
                            color=颜色,
                            width=3
                        ),
                        marker=dict(
                            size=8,
                            symbol='diamond'
                        ),
                        hovertemplate=f'模式: {模式类型}<br>信号: {信号}<br>置信度: {置信度}%<extra></extra>'
                    ))
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.图表生成器.文字颜色),
                x=0.5
            ),
            height=600,
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            xaxis=dict(
                title='日期',
                tickangle=45,
                gridcolor=self.图表生成器.网格颜色
            ),
            yaxis=dict(
                title='价格 (¥)',
                gridcolor=self.图表生成器.网格颜色
            ),
            hovermode='x unified',
            showlegend=True,
            font=self.图表生成器.字体配置
        )
        
        return fig
    
    def 生成对比分析图(self,
                    数据列表: List[Dict[str, Any]],
                    对比指标: str = '价格',
                    日期数据: Optional[List] = None,
                    标题: str = "对比分析图") -> go.Figure:
        """
        生成多数据对比分析图
        
        参数:
            数据列表: 数据字典列表 [{名称: str, 数据: array, 颜色: str}]
            对比指标: 对比的指标名称
            日期数据: 日期序列（可选）
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        if not 数据列表:
            return self._生成错误图表("对比数据列表为空")
        
        # 创建图表
        fig = go.Figure()
        
        # 添加每个数据序列
        for 数据项 in 数据列表:
            名称 = 数据项.get('名称', '未知')
            数据序列 = 数据项.get('数据', [])
            颜色 = 数据项.get('颜色', self.图表生成器.中性颜色)
            
            if self._验证数据(数据序列, 名称):
                # 生成日期序列
                if 日期数据 is None:
                    日期序列 = [f"Day {i+1}" for i in range(len(数据序列))]
                else:
                    日期序列 = 日期数据
                
                # 标准化数据（便于对比）
                if len(数据序列) > 0:
                    标准化数据 = (数据序列 - np.min(数据序列)) / (np.max(数据序列) - np.min(数据序列) + 1e-10)
                else:
                    标准化数据 = []
                
                # 添加轨迹
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=标准化数据 if len(标准化数据) > 0 else 数据序列,
                    mode='lines',
                    name=名称,
                    line=dict(
                        color=颜色,
                        width=2
                    ),
                    hovertemplate=f'{名称}: %{{y:.2f}}<extra></extra>'
                ))
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.图表生成器.文字颜色),
                x=0.5
            ),
            height=500,
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            xaxis=dict(
                title='日期/时间',
                tickangle=45,
                gridcolor=self.图表生成器.网格颜色
            ),
            yaxis=dict(
                title=f'标准化{对比指标}',
                gridcolor=self.图表生成器.网格颜色
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=self.图表生成器.字体配置
        )
        
        return fig
    
    def _获取子图配置(self, 包含子图: List[str], 技术指标: Dict[str, Any]) -> Dict[str, Dict]:
        """获取子图配置"""
        配置 = {}
        
        for 子图类型 in 包含子图:
            if 子图类型 == '价格':
                配置[子图类型] = {
                    '标题': '价格走势',
                    '高度比例': 0.4
                }
            elif 子图类型 == 'RSI' and 'RSI' in 技术指标:
                配置[子图类型] = {
                    '标题': 'RSI指标',
                    '高度比例': 0.2
                }
            elif 子图类型 == 'MACD' and 'MACD' in 技术指标:
                配置[子图类型] = {
                    '标题': 'MACD指标',
                    '高度比例': 0.2
                }
            elif 子图类型 == '成交量' and '成交量' in 技术指标:
                配置[子图类型] = {
                    '标题': '成交量',
                    '高度比例': 0.2
                }
            elif 子图类型 == '波动率' and '波动率' in 技术指标:
                配置[子图类型] = {
                    '标题': '波动率',
                    '高度比例': 0.2
                }
        
        return 配置
    
    def _添加价格子图(self, fig: go.Figure, row: int, 价格序列: np.ndarray, 日期序列: List, 技术指标: Dict[str, Any]):
        """添加价格子图"""
        # 添加价格线
        fig.add_trace(go.Scatter(
            x=日期序列,
            y=价格序列,
            mode='lines',
            name='价格',
            line=dict(
                color=self.图表生成器.上涨颜色 if self.广州模式 else self.图表生成器.下跌颜色,
                width=2
            ),
            hovertemplate='日期: %{x}<br>价格: ¥%{y:.2f}<extra></extra>'
        ), row=row, col=1)
        
        # 添加移动平均线
        if 'SMA' in 技术指标:
            for 周期, 数据 in 技术指标['SMA'].items():
                if self._验证数据(数据, f"SMA({周期})"):
                    fig.add_trace(go.Scatter(
                        x=日期序列[int(周期)-1:],
                        y=数据[int(周期)-1:],
                        mode='lines',
                        name=f'SMA({周期})',
                        line=dict(
                            color=self.指标配置['SMA']['颜色'],
                            width=1.5,
                            dash='dash'
                        )
                    ), row=row, col=1)
        
        # 添加布林带
        if '布林带' in 技术指标:
            布林带 = 技术指标['布林带']
            if '上轨' in 布林带 and '中轨' in 布林带 and '下轨' in 布林带:
                # 上轨
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带['上轨'],
                    mode='lines',
                    name='布林上轨',
                    line=dict(
                        color=self.指标配置['布林带']['颜色']['上轨'],
                        width=1,
                        dash='dash'
                    )
                ), row=row, col=1)
                
                # 中轨
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带['中轨'],
                    mode='lines',
                    name='布林中轨',
                    line=dict(
                        color=self.指标配置['布林带']['颜色']['中轨'],
                        width=1.5
                    )
                ), row=row, col=1)
                
                # 下轨
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带['下轨'],
                    mode='lines',
                    name='布林下轨',
                    line=dict(
                        color=self.指标配置['布林带']['颜色']['下轨'],
                        width=1,
                        dash='dash'
                    ),
                    fill='tonexty',
                    fillcolor='rgba(231, 76, 60, 0.1)'
                ), row=row, col=1)
    
    def _添加RSI子图(self, fig: go.Figure, row: int, 日期序列: List, 技术指标: Dict[str, Any]):
        """添加RSI子图"""
        if 'RSI' in 技术指标:
            RSI数据 = 技术指标['RSI']
            if self._验证数据(RSI数据, "RSI"):
                if isinstance(RSI数据, pd.Series):
                    RSI序列 = RSI数据.values
                else:
                    RSI序列 = np.array(RSI数据)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=RSI序列,
                    mode='lines',
                    name='RSI',
                    line=dict(
                        color=self.指标配置['RSI']['颜色'],
                        width=2
                    ),
                    hovertemplate='RSI: %{y:.1f}<extra></extra>'
                ), row=row, col=1)
                
                # 添加超买超卖线
                fig.add_hline(y=70, line_dash="dash", line_color=self.图表生成器.上涨颜色,
                             annotation_text="超买线", annotation_position="top right",
                             row=row, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color=self.图表生成器.下跌颜色,
                             annotation_text="超卖线", annotation_position="bottom right",
                             row=row, col=1)
                
                # 填充超买超卖区域
                fig.add_hrect(y0=70, y1=100, 
                            fillcolor="rgba(231, 76, 60, 0.1)", 
                            line_width=0,
                            row=row, col=1)
                fig.add_hrect(y0=0, y1=30,
                            fillcolor="rgba(39, 174, 96, 0.1)",
                            line_width=0,
                            row=row, col=1)
    
    def _添加MACD子图(self, fig: go.Figure, row: int, 日期序列: List, 技术指标: Dict[str, Any]):
        """添加MACD子图"""
        if 'MACD' in 技术指标:
            MACD数据 = 技术指标['MACD']
            
            if isinstance(MACD数据, dict):
                # 添加DIF线
                if 'DIF' in MACD数据 and self._验证数据(MACD数据['DIF'], "DIF"):
                    fig.add_trace(go.Scatter(
                        x=日期序列,
                        y=MACD数据['DIF'],
                        mode='lines',
                        name='DIF',
                        line=dict(
                            color=self.指标配置['MACD']['颜色']['DIF'],
                            width=2
                        ),
                        hovertemplate='DIF: %{y:.3f}<extra></extra>'
                    ), row=row, col=1)
                
                # 添加DEA线
                if 'DEA' in MACD数据 and self._验证数据(MACD数据['DEA'], "DEA"):
                    fig.add_trace(go.Scatch(
                        x=日期序列,
                        y=MACD数据['DEA'],
                        mode='lines',
                        name='DEA',
                        line=dict(
                            color=self.指标配置['MACD']['颜色']['DEA'],
                            width=2
                        ),
                        hovertemplate='DEA: %{y:.3f}<extra></extra>'
                    ), row=row, col=1)
                
                # 添加MACD柱状图
                if '柱状图' in MACD数据 and self._验证数据(MACD数据['柱状图'], "MACD柱"):
                    # 根据正负值确定颜色
                    柱状图颜色 = []
                    for val in MACD数据['柱状图']:
                        if val >= 0:
                            柱状图颜色.append(self.图表生成器.上涨颜色 if self.广州模式 else self.图表生成器.下跌颜色)
                        else:
                            柱状图颜色.append(self.图表生成器.下跌颜色 if self.广州模式 else self.图表生成器.上涨颜色)
                    
                    fig.add_trace(go.Bar(
                        x=日期序列,
                        y=MACD数据['柱状图'],
                        name='MACD柱',
                        marker_color=柱状图颜色,
                        opacity=0.6,
                        hovertemplate='MACD柱: %{y:.3f}<extra></extra>'
                    ), row=row, col=1)
    
    def _添加成交量子图(self, fig: go.Figure, row: int, 日期序列: List, 技术指标: Dict[str, Any]):
        """添加成交量子图"""
        if '成交量' in 技术指标:
            成交量数据 = 技术指标['成交量']
            if self._验证数据(成交量数据, "成交量"):
                if isinstance(成交量数据, pd.Series):
                    成交量序列 = 成交量数据.values
                else:
                    成交量序列 = np.array(成交量数据)
                
                # 使用简单颜色（实际应用中应根据价格涨跌）
                fig.add_trace(go.Bar(
                    x=日期序列,
                    y=成交量序列,
                    name='成交量',
                    marker_color=self.图表生成器.中性颜色,
                    opacity=0.7,
                    hovertemplate='成交量: %{y:,}<extra></extra>'
                ), row=row, col=1)
    
    def _添加波动率子图(self, fig: go.Figure, row: int, 日期序列: List, 技术指标: Dict[str, Any]):
        """添加波动率子图"""
        if '波动率' in 技术指标:
            波动率数据 = 技术指标['波动率']
            if self._验证数据(波动率数据, "波动率"):
                if isinstance(波动率数据, pd.Series):
                    波动率序列 = 波动率数据.values
                else:
                    波动率序列 = np.array(波动率数据)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=波动率序列,
                    mode='lines',
                    name='波动率',
                    line=dict(
                        color='#f39c12',
                        width=2
                    ),
                    fill='tozeroy',
                    fillcolor='rgba(243, 156, 18, 0.1)',
                    hovertemplate='波动率: %{y:.1f}%<extra></extra>'
                ), row=row, col=1)
    
    def _计算价格颜色序列(self, 价格序列: np.ndarray) -> List[str]:
        """计算价格涨跌颜色序列"""
        颜色序列 = [self.图表生成器.中性颜色]  # 第一个点
        
        for i in range(1, len(价格序列)):
            if 价格序列[i] >= 价格序列[i-1]:
                颜色序列.append(self.图表生成器.上涨颜色 if self.广州模式 else self.图表生成器.下跌颜色)
            else:
                颜色序列.append(self.图表生成器.下跌颜色 if self.广州模式 else self.图表生成器.上涨颜色)
        
        return 颜色序列
    
    def _计算支撑阻力线(self, 价格序列: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
        """计算支撑线和阻力线"""
        if len(价格序列) < 10:
            return None, None
        
        # 简单实现：使用近期高低点
        近期数据 = 价格序列[-10:]
        支撑线 = np.min(近期数据) * 0.99  # 支撑线略低于近期低点
        阻力线 = np.max(近期数据) * 1.01  # 阻力线略高于近期高点
        
        return 支撑线, 阻力线
    
    def _验证数据(self, 数据: Any, 数据类型: str) -> bool:
        """数据验证"""
        if not self.验证模式:
            return True
            
        if 数据 is None:
            print(f"[警告] {数据类型}数据为空")
            return False
            
        if isinstance(数据, (list, np.ndarray)):
            if len(数据) == 0:
                print(f"[警告] {数据类型}数据长度为0")
                return False
                
            if isinstance(数据, np.ndarray):
                if np.any(np.isnan(数据)):
                    print(f"[警告] {数据类型}数据包含NaN值")
                    return False
                    
        elif isinstance(数据, pd.Series):
            if 数据.empty:
                print(f"[警告] {数据类型}数据为空")
                return False
                
            if 数据.isnull().any():
                print(f"[警告] {数据类型}数据包含NaN值")
                return False
                
        return True
    
    def _生成错误图表(self, 错误信息: str) -> go.Figure:
        """生成错误提示图表"""
        fig = go.Figure()
        fig.add_annotation(
            text=f"图表生成失败: {错误信息}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color=self.图表生成器.上涨颜色)
        )
        fig.update_layout(
            paper_bgcolor=self.图表生成器.背景颜色,
            plot_bgcolor='white',
            height=300
        )
        return fig


# 测试代码
if __name__ == "__main__":
    print("=== 竹林司马技术指标可视化器测试 ===")
    
    # 创建可视化器
    visualizer = TechnicalVisualizer(广州模式=True, 验证模式=True)
    
    # 生成示例数据
    np.random.seed(42)
    n_days = 100
    日期 = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
    价格 = 100 + np.cumsum(np.random.randn(n_days) * 2)
    
    # 计算技术指标
    rsi = 50 + np.random.randn(n_days) * 20
    rsi = np.clip(rsi, 0, 100)
    
    macd_data = {
        'DIF': np.random.randn(n_days) * 2,
        'DEA': np.random.randn(n_days) * 1.5,
        '柱状图': np.random.randn(n_days) * 1
    }
    
    布林带 = {
        '上轨': 价格 + np.random.randn(n_days) * 5,
        '中轨': 价格,
        '下轨': 价格 - np.random.randn(n_days) * 5
    }
    
    技术指标 = {
        'RSI': rsi,
        'MACD': macd_data,
        '布林带': 布林带
    }
    
    print("1. 生成综合技术分析图...")
    fig1 = visualizer.生成综合技术分析图(价格, 技术指标, 日期, "示例综合技术分析", ['价格', 'RSI', 'MACD'])
    fig1.write_html("test_comprehensive_analysis.html")
    print("   已保存到: test_comprehensive_analysis.html")
    
    print("2. 生成趋势分析图...")
    fig2 = visualizer.生成趋势分析图(价格, {'5': visualizer.图表生成器._计算SMA(价格, 5)}, 
                                   [(10, 30, 1.5), (50, 80, -0.8)], 日期)
    fig2.write_html("test_trend_analysis.html")
    print("   已保存到: test_trend_analysis.html")
    
    print("3. 生成动量分析图...")
    fig3 = visualizer.生成动量分析图(rsi, macd_data, None, 日期)
    fig3.write_html("test_momentum_analysis.html")
    print("   已保存到: test_momentum_analysis.html")
    
    print("4. 生成对比分析图...")
    对比数据 = [
        {'名称': '股票A', '数据': 价格, '颜色': '#e74c3c'},
        {'名称': '股票B', '数据': 价格 * 0.8 + np.random.randn(n_days) * 3, '颜色': '#3498db'},
        {'名称': '股票C', '数据': 价格 * 1.2 + np.random.randn(n_days) * 4, '颜色': '#9b59b6'}
    ]
    fig4 = visualizer.生成对比分析图(对比数据, '价格', 日期, "示例对比分析")
    fig4.write_html("test_comparison_analysis.html")
    print("   已保存到: test_comparison_analysis.html")
    
    print("\n=== 测试完成 ===")