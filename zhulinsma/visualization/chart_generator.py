#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竹林司马 - 交互式图表生成器
基于Plotly和Matplotlib的交互式图表生成模块
支持HTML报告生成和交互式可视化

作者：杨总的工作助手
日期：2026年3月30日
版本：1.0.0
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import base64
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')


class ChartGenerator:
    """交互式图表生成器"""
    
    def __init__(self, 
                 广州模式: bool = True,
                 验证模式: bool = True,
                 缓存大小: int = 100):
        """
        初始化图表生成器
        
        参数:
           广州模式: 是否启用广州优化（红涨绿跌）
           验证模式: 是否启用数据验证
           缓存大小: 图表缓存大小
        """
        self.广州模式 = 广州模式
        self.验证模式 = 验证模式
        self.缓存大小 = 缓存大小
        self.图表缓存 = {}
        
        # 颜色配置（广州模式：红涨绿跌）
        if self.广州模式:
            self.上涨颜色 = '#e74c3c'  # 红色
            self.下跌颜色 = '#27ae60'  # 绿色
        else:
            self.上涨颜色 = '#27ae60'  # 绿色
            self.下跌颜色 = '#e74c3c'  # 红色
            
        self.中性颜色 = '#3498db'  # 蓝色
        self.背景颜色 = '#f8f9fa'  # 浅灰色
        self.网格颜色 = '#e0e0e0'  # 灰色
        self.文字颜色 = '#2c3e50'  # 深蓝色
        
        # 字体配置
        self.字体配置 = dict(
            family="Helvetica Neue, Arial, PingFang SC, Microsoft YaHei, sans-serif",
            size=14,
            color=self.文字颜色
        )
        
        print(f"[图表生成器] 初始化完成 - 广州模式: {self.广州模式}, 验证模式: {self.验证模式}")
    
    def _验证数据(self, 数据: Union[np.ndarray, pd.Series, List], 数据类型: str = "价格") -> bool:
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
                
            # 检查NaN值
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
    
    def 生成价格走势图(self, 
                    价格数据: Union[np.ndarray, pd.Series, List],
                    日期数据: Optional[List] = None,
                    标题: str = "价格走势分析",
                    宽度: int = 1000,
                    高度: int = 500,
                    显示移动平均线: bool = True,
                    显示成交量: bool = False,
                    成交量数据: Optional[Union[np.ndarray, pd.Series, List]] = None) -> go.Figure:
        """
        生成价格走势图
        
        参数:
            价格数据: 价格数据序列
            日期数据: 日期序列（可选）
            标题: 图表标题
            宽度: 图表宽度
            高度: 图表高度
            显示移动平均线: 是否显示移动平均线
            显示成交量: 是否显示成交量
            成交量数据: 成交量数据（可选）
            
        返回:
            Plotly图表对象
        """
        # 数据验证
        if not self._验证数据(价格数据, "价格"):
            return self._生成错误图表("价格数据验证失败")
        
        # 准备数据
        if isinstance(价格数据, pd.Series):
            价格序列 = 价格数据.values
        elif isinstance(价格数据, list):
            价格序列 = np.array(价格数据)
        else:
            价格序列 = 价格数据
            
        # 生成日期序列
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
            name='价格走势',
            line=dict(
                color=self.上涨颜色 if self.广州模式 else self.下跌颜色,
                width=2
            ),
            fill='tozeroy',
            fillcolor=f'rgba({self._颜色转RGB(self.上涨颜色)}, 0.1)' if self.广州模式 else f'rgba({self._颜色转RGB(self.下跌颜色)}, 0.1)',
            hovertemplate='日期: %{x}<br>价格: ¥%{y:.2f}<extra></extra>'
        ))
        
        # 添加移动平均线
        if 显示移动平均线 and len(价格序列) >= 20:
            # 计算5日、10日、20日移动平均线
            for 周期, 颜色 in [(5, '#f39c12'), (10, '#9b59b6'), (20, '#34495e')]:
                if len(价格序列) >= 周期:
                    sma = self._计算SMA(价格序列, 周期)
                    fig.add_trace(go.Scatter(
                        x=日期序列[周期-1:],
                        y=sma[周期-1:],
                        mode='lines',
                        name=f'SMA({周期})',
                        line=dict(
                            color=颜色,
                            width=1.5,
                            dash='dash'
                        ),
                        hovertemplate=f'SMA({周期}): ¥%{{y:.2f}}<extra></extra>'
                    ))
        
        # 添加成交量
        if 显示成交量 and 成交量数据 is not None:
            if self._验证数据(成交量数据, "成交量"):
                # 创建子图
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    subplot_titles=('价格走势', '成交量'),
                    row_heights=[0.7, 0.3]
                )
                
                # 添加价格线到第一个子图
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=价格序列,
                    mode='lines',
                    name='价格',
                    line=dict(color=self.上涨颜色, width=2)
                ), row=1, col=1)
                
                # 添加成交量到第二个子图
                if isinstance(成交量数据, pd.Series):
                    成交量序列 = 成交量数据.values
                elif isinstance(成交量数据, list):
                    成交量序列 = np.array(成交量数据)
                else:
                    成交量序列 = 成交量数据
                    
                # 计算涨跌颜色
                涨跌颜色 = []
                for i in range(1, len(价格序列)):
                    if 价格序列[i] >= 价格序列[i-1]:
                        涨跌颜色.append(self.上涨颜色 if self.广州模式 else self.下跌颜色)
                    else:
                        涨跌颜色.append(self.下跌颜色 if self.广州模式 else self.上涨颜色)
                
                # 添加成交量柱状图
                fig.add_trace(go.Bar(
                    x=日期序列[1:],
                    y=成交量序列[1:],
                    name='成交量',
                    marker_color=涨跌颜色,
                    hovertemplate='成交量: %{y:,}<extra></extra>'
                ), row=2, col=1)
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.文字颜色),
                x=0.5
            ),
            width=宽度,
            height=高度,
            paper_bgcolor=self.背景颜色,
            plot_bgcolor='white',
            xaxis=dict(
                title='日期',
                tickangle=45,
                gridcolor=self.网格颜色,
                showgrid=True
            ),
            yaxis=dict(
                title='价格 (¥)',
                gridcolor=self.网格颜色,
                showgrid=True
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
            font=self.字体配置
        )
        
        return fig
    
    def 生成技术指标图(self,
                    价格数据: Union[np.ndarray, pd.Series, List],
                    RSI数据: Optional[Union[np.ndarray, pd.Series, List]] = None,
                    MACD数据: Optional[Union[np.ndarray, pd.Series, List]] = None,
                    布林带数据: Optional[Dict] = None,
                    日期数据: Optional[List] = None,
                    标题: str = "技术指标分析") -> go.Figure:
        """
        生成技术指标分析图
        
        参数:
            价格数据: 价格数据序列
            RSI数据: RSI指标数据（可选）
            MACD数据: MACD指标数据（可选）
            布林带数据: 布林带数据字典（上轨、中轨、下轨）
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
        
        # 创建子图
        subplot_count = 1
        if RSI数据 is not None:
            subplot_count += 1
        if MACD数据 is not None:
            subplot_count += 1
            
        fig = make_subplots(
            rows=subplot_count, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=['价格走势'] + (['RSI指标'] if RSI数据 is not None else []) + (['MACD指标'] if MACD数据 is not None else [])
        )
        
        row_idx = 1
        
        # 价格走势图
        fig.add_trace(go.Scatter(
            x=日期序列,
            y=价格序列,
            mode='lines',
            name='价格',
            line=dict(color=self.上涨颜色, width=2)
        ), row=row_idx, col=1)
        
        # 添加布林带
        if 布林带数据 is not None:
            if '上轨' in 布林带数据 and '中轨' in 布林带数据 and '下轨' in 布林带数据:
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带数据['上轨'],
                    mode='lines',
                    name='布林带上轨',
                    line=dict(color='#e74c3c', width=1, dash='dash')
                ), row=row_idx, col=1)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带数据['中轨'],
                    mode='lines',
                    name='布林带中轨',
                    line=dict(color='#f39c12', width=1.5)
                ), row=row_idx, col=1)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=布林带数据['下轨'],
                    mode='lines',
                    name='布林带下轨',
                    line=dict(color='#27ae60', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(231, 76, 60, 0.1)'
                ), row=row_idx, col=1)
        
        row_idx += 1
        
        # RSI指标
        if RSI数据 is not None:
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
                    line=dict(color='#9b59b6', width=2)
                ), row=row_idx, col=1)
                
                # 添加超买超卖线
                fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", 
                             annotation_text="超买线", annotation_position="top right",
                             row=row_idx, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="#27ae60",
                             annotation_text="超卖线", annotation_position="bottom right",
                             row=row_idx, col=1)
                
                row_idx += 1
        
        # MACD指标
        if MACD数据 is not None:
            if isinstance(MACD数据, dict) and 'DIF' in MACD数据 and 'DEA' in MACD数据:
                DIF序列 = MACD数据['DIF']
                DEA序列 = MACD数据['DEA']
                柱状图数据 = MACD数据.get('柱状图', None)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=DIF序列,
                    mode='lines',
                    name='DIF',
                    line=dict(color='#3498db', width=2)
                ), row=row_idx, col=1)
                
                fig.add_trace(go.Scatter(
                    x=日期序列,
                    y=DEA序列,
                    mode='lines',
                    name='DEA',
                    line=dict(color='#f39c12', width=2)
                ), row=row_idx, col=1)
                
                if 柱状图数据 is not None:
                    # MACD柱状图
                    柱状图颜色 = [self.上涨颜色 if val >= 0 else self.下跌颜色 for val in 柱状图数据]
                    fig.add_trace(go.Bar(
                        x=日期序列,
                        y=柱状图数据,
                        name='MACD柱',
                        marker_color=柱状图颜色,
                        opacity=0.6
                    ), row=row_idx, col=1)
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.文字颜色),
                x=0.5
            ),
            height=300 * subplot_count,
            paper_bgcolor=self.背景颜色,
            plot_bgcolor='white',
            hovermode='x unified',
            showlegend=True,
            font=self.字体配置
        )
        
        return fig
    
    def 生成风险热力图(self,
                    风险数据: Dict[str, float],
                    标题: str = "风险热力图") -> go.Figure:
        """
        生成风险热力图
        
        参数:
            风险数据: 风险指标字典 {指标名称: 风险值}
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        if not 风险数据:
            return self._生成错误图表("风险数据为空")
        
        # 准备数据
        指标名称 = list(风险数据.keys())
        风险值 = list(风险数据.values())
        
        # 创建热力图数据
        z = [风险值]
        x = 指标名称
        y = ['风险等级']
        
        # 创建热力图
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            colorscale=[[0, '#27ae60'], [0.5, '#f39c12'], [1, '#e74c3c']],  # 绿-黄-红
            zmin=0,
            zmax=100,
            text=[[f"{val:.1f}" for val in 风险值]],
            texttemplate="%{text}",
            textfont={"size": 14, "color": "white"},
            hovertemplate='指标: %{x}<br>风险值: %{z:.1f}<extra></extra>'
        ))
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.文字颜色),
                x=0.5
            ),
            height=200,
            paper_bgcolor=self.背景颜色,
            plot_bgcolor='white',
            xaxis=dict(
                tickangle=45,
                gridcolor=self.网格颜色
            ),
            yaxis=dict(
                gridcolor=self.网格颜色
            ),
            font=self.字体配置
        )
        
        return fig
    
    def 生成仪表盘(self,
                 指标数据: Dict[str, float],
                 标题: str = "技术指标仪表盘") -> go.Figure:
        """
        生成技术指标仪表盘
        
        参数:
            指标数据: 指标数据字典 {指标名称: 指标值}
            标题: 图表标题
            
        返回:
            Plotly图表对象
        """
        if not 指标数据:
            return self._生成错误图表("指标数据为空")
        
        # 确定子图数量
        n_indicators = len(指标数据)
        n_cols = min(3, n_indicators)
        n_rows = (n_indicators + n_cols - 1) // n_cols
        
        # 创建子图
        fig = make_subplots(
            rows=n_rows, cols=n_cols,
            subplot_titles=list(指标数据.keys()),
            specs=[[{"type": "indicator"} for _ in range(n_cols)] for _ in range(n_rows)]
        )
        
        # 添加每个指标
        for idx, (指标名称, 指标值) in enumerate(指标数据.items()):
            row = idx // n_cols + 1
            col = idx % n_cols + 1
            
            # 确定颜色和范围
            if "RSI" in 指标名称:
                颜色 = self._获取RSI颜色(指标值)
                范围 = [0, 100]
                阈值 = {'steps': [
                    {'range': [0, 30], 'color': self.下跌颜色},
                    {'range': [30, 70], 'color': self.中性颜色},
                    {'range': [70, 100], 'color': self.上涨颜色}
                ]}
            elif "波动率" in 指标名称 or "风险" in 指标名称:
                颜色 = self._获取风险颜色(指标值)
                范围 = [0, 100]
                阈值 = {'steps': [
                    {'range': [0, 30], 'color': self.下跌颜色},
                    {'range': [30, 70], 'color': '#f39c12'},
                    {'range': [70, 100], 'color': self.上涨颜色}
                ]}
            else:
                颜色 = self.中性颜色
                范围 = [0, 100]
                阈值 = None
            
            fig.add_trace(go.Indicator(
                mode="gauge+number",
                value=指标值,
                title={'text': 指标名称},
                gauge={
                    'axis': {'range': 范围},
                    'bar': {'color': 颜色},
                    'steps': 阈值.get('steps', []) if 阈值 else None,
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 70
                    } if 阈值 else None
                }
            ), row=row, col=col)
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=标题,
                font=dict(size=20, color=self.文字颜色),
                x=0.5
            ),
            height=300 * n_rows,
            paper_bgcolor=self.背景颜色,
            plot_bgcolor='white',
            font=self.字体配置
        )
        
        return fig
    
    def 生成静态图表(self, fig: go.Figure, 格式: str = "png", 宽度: int = 1200, 高度: int = 600) -> str:
        """
        将Plotly图表转换为静态图片（Base64编码）
        
        参数:
            fig: Plotly图表对象
            格式: 图片格式（png, jpeg, svg, pdf）
            宽度: 图片宽度
            高度: 图片高度
            
        返回:
            Base64编码的图片字符串
        """
        try:
            # 使用kaleido引擎
            import plotly.io as pio
            
            # 设置图片大小
            fig.update_layout(width=宽度, height=高度)
            
            # 转换为图片字节
            img_bytes = pio.to_image(fig, format=格式, engine="kaleido")
            
            # 转换为Base64
            base64_str = base64.b64encode(img_bytes).decode('utf-8')
            
            return f"data:image/{格式};base64,{base64_str}"
            
        except Exception as e:
            print(f"[错误] 生成静态图表失败: {e}")
            # 返回错误占位符
            return self._生成错误占位图(宽度, 高度)
    
    def 保存HTML报告(self, fig: go.Figure, 文件路径: str, 包含plotlyjs: bool = True) -> bool:
        """
        保存图表为HTML文件
        
        参数:
            fig: Plotly图表对象
            文件路径: 保存路径
            包含plotlyjs: 是否包含plotly.js库
            
        返回:
            是否保存成功
        """
        try:
            fig.write_html(文件路径, include_plotlyjs=包含plotlyjs)
            print(f"[成功] 图表已保存到: {文件路径}")
            return True
        except Exception as e:
            print(f"[错误] 保存HTML文件失败: {e}")
            return False
    
    def _计算SMA(self, 数据: np.ndarray, 周期: int) -> np.ndarray:
        """计算简单移动平均线"""
        if len(数据) < 周期:
            return np.full(len(数据), np.nan)
        
        cumsum = np.cumsum(数据, dtype=float)
        sma = (cumsum[周期:] - cumsum[:-周期]) / 周期
        
        result = np.full(len(数据), np.nan)
        result[周期-1:] = sma
        
        return result
    
    def _颜色转RGB(self, 颜色代码: str) -> str:
        """将十六进制颜色代码转换为RGB字符串"""
        颜色代码 = 颜色代码.lstrip('#')
        r = int(颜色代码[0:2], 16)
        g = int(颜色代码[2:4], 16)
        b = int(颜色代码[4:6], 16)
        return f"{r}, {g}, {b}"
    
    def _获取RSI颜色(self, rsi值: float) -> str:
        """根据RSI值获取颜色"""
        if rsi值 < 30:
            return self.下跌颜色  # 超卖，绿色
        elif rsi值 > 70:
            return self.上涨颜色  # 超买，红色
        else:
            return self.中性颜色  # 中性，蓝色
    
    def _获取风险颜色(self, 风险值: float) -> str:
        """根据风险值获取颜色"""
        if 风险值 < 30:
            return self.下跌颜色  # 低风险，绿色
        elif 风险值 < 70:
            return '#f39c12'      # 中风险，黄色
        else:
            return self.上涨颜色  # 高风险，红色
    
    def _生成错误图表(self, 错误信息: str) -> go.Figure:
        """生成错误提示图表"""
        fig = go.Figure()
        fig.add_annotation(
            text=f"图表生成失败: {错误信息}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color=self.上涨颜色)
        )
        fig.update_layout(
            paper_bgcolor=self.背景颜色,
            plot_bgcolor='white',
            height=300
        )
        return fig
    
    def _生成错误占位图(self, 宽度: int, 高度: int) -> str:
        """生成错误占位图（Base64）"""
        try:
            # 创建简单的错误图片
            fig, ax = plt.subplots(figsize=(宽度/100, 高度/100))
            ax.text(0.5, 0.5, "图表生成失败", 
                   ha='center', va='center', fontsize=16, color='red')
            ax.axis('off')
            
            # 保存到缓冲区
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
            plt.close(fig)
            buffer.seek(0)
            
            # 转换为Base64
            base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{base64_str}"
        except:
            return ""
    
    def 生成示例报告(self, 输出目录: str = "./reports") -> Dict[str, str]:
        """
        生成示例报告（用于测试）
        
        参数:
            输出目录: 报告输出目录
            
        返回:
            生成的文件路径字典
        """
        import os
        
        # 创建输出目录
        os.makedirs(输出目录, exist_ok=True)
        
        # 生成示例数据
        np.random.seed(42)
        n_days = 100
        日期 = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
        价格 = 100 + np.cumsum(np.random.randn(n_days) * 2)
        成交量 = np.random.randint(1000, 10000, n_days)
        
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
        
        风险数据 = {
            '波动率风险': 45.6,
            '流动性风险': 32.1,
            '市场风险': 67.8,
            '信用风险': 23.4,
            '操作风险': 54.3
        }
        
        指标数据 = {
            'RSI指标': 65.4,
            'MACD信号': 42.1,
            '波动率': 28.9,
            '夏普比率': 1.23,
            '最大回撤': 15.6
        }
        
        # 生成各种图表
        结果文件 = {}
        
        # 1. 价格走势图
        print("[信息] 生成价格走势图...")
        price_fig = self.生成价格走势图(价格, 日期, "示例价格走势图", 显示成交量=True, 成交量数据=成交量)
        price_html = os.path.join(输出目录, "price_chart.html")
        price_png = os.path.join(输出目录, "price_chart.png")
        
        self.保存HTML报告(price_fig, price_html)
        price_static = self.生成静态图表(price_fig, "png")
        结果文件['价格走势图'] = price_html
        
        # 2. 技术指标图
        print("[信息] 生成技术指标图...")
        indicator_fig = self.生成技术指标图(价格, rsi, macd_data, 布林带, 日期, "示例技术指标分析")
        indicator_html = os.path.join(输出目录, "indicator_chart.html")
        self.保存HTML报告(indicator_fig, indicator_html)
        结果文件['技术指标图'] = indicator_html
        
        # 3. 风险热力图
        print("[信息] 生成风险热力图...")
        heatmap_fig = self.生成风险热力图(风险数据, "示例风险热力图")
        heatmap_html = os.path.join(输出目录, "risk_heatmap.html")
        self.保存HTML报告(heatmap_fig, heatmap_html)
        结果文件['风险热力图'] = heatmap_html
        
        # 4. 技术指标仪表盘
        print("[信息] 生成技术指标仪表盘...")
        dashboard_fig = self.生成仪表盘(指标数据, "示例技术指标仪表盘")
        dashboard_html = os.path.join(输出目录, "indicator_dashboard.html")
        self.保存HTML报告(dashboard_fig, dashboard_html)
        结果文件['指标仪表盘'] = dashboard_html
        
        # 5. 综合报告
        print("[信息] 生成综合报告...")
        from .report_generator import ReportGenerator
        report_gen = ReportGenerator()
        
        report_data = {
            'report_date': '2026-03-30',
            'analysis_period': '2026年1月-3月',
            'analyst': '杨总的工作助手',
            'data_quality': 98.5,
            'executive_summary': '示例分析报告摘要',
            'technical_indicators': [
                {'name': 'RSI', 'value': 65.4, 'value_class': 'positive', 'signal': '超买', 'signal_class': 'warning', 'trend': '上升', 'confidence': 85, 'description': '相对强弱指标'},
                {'name': 'MACD', 'value': 2.34, 'value_class': 'positive', 'signal': '金叉', 'signal_class': 'positive', 'trend': '上升', 'confidence': 78, 'description': '移动平均收敛发散'},
                {'name': '布林带', 'value': '上轨突破', 'value_class': 'positive', 'signal': '强势', 'signal_class': 'positive', 'trend': '上升', 'confidence': 92, 'description': '波动率指标'}
            ],
            'risk_metrics': [
                {'label': '波动率', 'value': '28.9%', 'change': '+2.1%', 'change_class': 'positive', 'change_icon': 'up'},
                {'label': '夏普比率', 'value': '1.23', 'change': '+0.15', 'change_class': 'positive', 'change_icon': 'up'},
                {'label': '最大回撤', 'value': '15.6%', 'change': '-3.2%', 'change_class': 'negative', 'change_icon': 'down'},
                {'label': '贝塔系数', 'value': '1.05', 'change': '+0.08', 'change_class': 'positive', 'change_icon': 'up'}
            ],
            'overall_risk_level': 'medium',
            'overall_risk_text': '中等风险',
            'risk_analysis': '整体风险可控，主要风险来自市场波动',
            'recommendation': '买入',
            'recommendation_class': 'positive',
            'target_price': 128.50,
            'stop_loss': 95.00,
            'price_change_pct': '+15.2%',
            'price_change_class': 'positive',
            'price_change_icon': 'up',
            'expected_return': 18.5,
            'expected_return_class': 'positive',
            'risk_reward_ratio': '1:2.5',
            'recommendation_details': '基于技术分析和基本面评估，建议买入并持有',
            'disclaimer': '本报告仅供参考，不构成投资建议',
            'data_quality_checks': [
                {'item': '价格数据', 'status': '通过', 'status_class': 'success', 'completeness': 100, 'accuracy': 99.8, 'timeliness': 100, 'notes': '数据完整'},
                {'item': '财务数据', 'status': '通过', 'status_class': 'success', 'completeness': 95, 'accuracy': 98.5, 'timeliness': 90, 'notes': '部分数据延迟'},
                {'item': '市场数据', 'status': '通过', 'status_class': 'success', 'completeness': 100, 'accuracy': 99.2, 'timeliness': 100, 'notes': '实时更新'}
            ],
            'overall_quality': 98.5,
            'analysis_method': '双重验证技术分析',
            'data_sources': 'Tushare Pro, 交易所数据, 公司公告',
            'update_frequency': '每日更新',
            'model_version': 'Zhulinsma v2.0.0',
            'generation_time': '2026-03-30 09:00:00',
            'price_dates': 日期.tolist(),
            'price_values': 价格.tolist()
        }
        
        report_html = report_gen.generate_html_report(report_data, os.path.join(输出目录, "comprehensive_report.html"))
        结果文件['综合报告'] = report_html
        
        print(f"[成功] 示例报告生成完成，文件保存在: {输出目录}")
        return 结果文件


# 测试代码
if __name__ == "__main__":
    print("=== 竹林司马图表生成器测试 ===")
    
    # 创建图表生成器
    chart_gen = ChartGenerator(广州模式=True, 验证模式=True)
    
    # 生成示例报告
    results = chart_gen.生成示例报告("./test_reports")
    
    print("\n生成的文件:")
    for name, path in results.items():
        print(f"  {name}: {path}")
    
    print("\n=== 测试完成 ===")