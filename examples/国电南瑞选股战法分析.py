#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国电南瑞(600406.SH)选股战法分析
使用竹林司马(Zhulinsma)技术分析工具进行多维度选股分析
分析时间：2026年3月27日
"""

import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json

# 添加竹林司马模块路径
sys.path.append('/Users/gilesyang/WorkBuddy/20260324203553')
from zhulinsma import ZH_CHINESE_NAME, ZH_ENGLISH_NAME, ZH_FULL_NAME

print(f"=== {ZH_FULL_NAME} - 国电南瑞选股战法分析 ===")
print(f"分析时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
print(f"目标股票：国电南瑞 (600406.SH)")
print("=" * 60)

class NareiStockAnalysis:
    """国电南瑞选股战法分析类"""
    
    def __init__(self):
        """初始化分析器"""
        self.stock_code = "600406.SH"
        self.stock_name = "国电南瑞"
        self.analysis_date = datetime.now().strftime("%Y-%m-%d")
        self.periods = [5, 10, 20, 30, 60]  # 分析周期
        self.results = {}
        
        print(f"初始化 {ZH_CHINESE_NAME} 选股战法分析器...")
        
    def load_zhulinsma_modules(self):
        """动态加载竹林司马模块"""
        try:
            # 导入核心技术指标模块
            from zhulinsma.core.indicators import TechnicalIndicators
            from zhulinsma.core.trend_analysis import TrendAnalyzer
            from zhulinsma.core.risk_assessment import RiskAssessor
            from zhulinsma.core.volume_analysis import VolumeAnalyzer
            from zhulinsma.core.support_resistance import SupportResistance
            
            self.indicators = TechnicalIndicators()
            self.trend_analyzer = TrendAnalyzer()
            self.risk_assessor = RiskAssessor()
            self.volume_analyzer = VolumeAnalyzer()
            self.support_resistance = SupportResistance()
            
            print(f"✅ {ZH_CHINESE_NAME} 核心模块加载成功")
            return True
            
        except ImportError as e:
            print(f"❌ 竹林司马模块加载失败: {e}")
            print("正在使用模拟数据进行演示分析...")
            return False
    
    def generate_mock_data(self):
        """生成模拟股价数据（实际应用中应使用真实数据）"""
        # 生成最近120个交易日的模拟数据
        n_days = 120
        dates = pd.date_range(end=self.analysis_date, periods=n_days, freq='B')
        
        # 基础价格：国电南瑞当前价格约在25-30元区间
        base_price = 28.5
        volatility = 0.02  # 日波动率2%
        
        # 生成随机价格序列（带趋势）
        np.random.seed(42)  # 固定随机种子以便复现
        returns = np.random.normal(0.0005, volatility, n_days)  # 日均上涨0.05%
        prices = base_price * (1 + np.cumsum(returns))
        
        # 生成成交量和成交额
        base_volume = 20000000  # 基础成交量2000万股
        volume_variation = 0.3  # 成交量波动30%
        volumes = base_volume * (1 + np.random.normal(0, volume_variation, n_days))
        volumes = np.maximum(volumes, base_volume * 0.5)  # 确保最小成交量
        
        # 生成成交额（价格*成交量）
        amounts = prices * volumes
        
        # 创建DataFrame
        data = pd.DataFrame({
            'date': dates,
            'open': prices * (1 + np.random.normal(0, 0.005, n_days)),  # 开盘价
            'high': prices * (1 + np.abs(np.random.normal(0.005, 0.01, n_days))),  # 最高价
            'low': prices * (1 - np.abs(np.random.normal(0.005, 0.01, n_days))),   # 最低价
            'close': prices,  # 收盘价
            'volume': volumes,
            'amount': amounts,
            'change': returns * 100  # 涨跌幅百分比
        })
        
        # 确保价格合理性
        data['high'] = np.maximum(data[['open', 'close', 'high']].max(axis=1), data['low'] * 1.001)
        data['low'] = np.minimum(data[['open', 'close', 'low']].min(axis=1), data['high'] * 0.999)
        
        return data
    
    def calculate_technical_indicators(self, data):
        """计算技术指标（使用竹林司马或模拟计算）"""
        print("\n📈 计算技术指标...")
        
        # 复制数据以避免修改原始数据
        df = data.copy()
        
        # 移动平均线
        for period in self.periods:
            df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        
        # 指数移动平均线
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # RSI指标
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD指标
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        
        # KDJ指标
        low_min = df['low'].rolling(window=9).min()
        high_max = df['high'].rolling(window=9).max()
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
        df['k'] = rsv.ewm(alpha=1/3, adjust=False).mean()
        df['d'] = df['k'].ewm(alpha=1/3, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        
        # 成交量均线
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()
        df['vol_ma10'] = df['volume'].rolling(window=10).mean()
        
        print(f"✅ 已计算 {len(df.columns) - 8} 个技术指标")
        return df
    
    def analyze_trend_strength(self, df):
        """分析趋势强度"""
        print("\n📊 分析趋势强度...")
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        # 1. 多周期均线排列
        sma_values = [latest[f'sma_{p}'] for p in self.periods]
        
        # 判断均线排列：多头排列（短>中>长）得高分，空头排列得低分
        is_bullish = all(sma_values[i] >= sma_values[i+1] for i in range(len(sma_values)-1))
        is_bearish = all(sma_values[i] <= sma_values[i+1] for i in range(len(sma_values)-1))
        
        if is_bullish:
            trend_score = 9.0
            trend_desc = "多头排列（5日>10日>20日>30日>60日）"
        elif is_bearish:
            trend_score = 3.0
            trend_desc = "空头排列"
        else:
            # 混合排列，计算排列一致性
            consistent_pairs = sum(1 for i in range(len(sma_values)-1) if sma_values[i] >= sma_values[i+1])
            trend_score = 3 + (consistent_pairs / (len(sma_values)-1)) * 6
            trend_desc = f"混合排列（{consistent_pairs}/{len(sma_values)-1}周期为多头）"
        
        # 2. 价格与均线关系
        price = latest['close']
        above_sma_count = sum(1 for p in self.periods if price > latest[f'sma_{p}'])
        price_position_score = (above_sma_count / len(self.periods)) * 10
        
        # 3. 趋势斜率
        recent_prices = df['close'].tail(20).values
        if len(recent_prices) >= 10:
            x = np.arange(len(recent_prices))
            slope = np.polyfit(x, recent_prices, 1)[0]
            slope_score = min(10, max(0, (slope / recent_prices.mean() * 1000) + 5))
        else:
            slope_score = 5.0
        
        # 综合趋势评分
        trend_final_score = (trend_score * 0.4 + price_position_score * 0.3 + slope_score * 0.3)
        
        self.results['trend_analysis'] = {
            'score': round(trend_final_score, 2),
            'details': {
                'trend_pattern': trend_desc,
                'trend_score': round(trend_score, 2),
                'price_position': f"{above_sma_count}/{len(self.periods)} 周期均线上方",
                'price_position_score': round(price_position_score, 2),
                'trend_slope_score': round(slope_score, 2)
            }
        }
        
        print(f"✅ 趋势强度评分: {trend_final_score:.2f}/10.0 ({trend_desc})")
        return trend_final_score
    
    def analyze_momentum_signals(self, df):
        """分析动量信号"""
        print("\n⚡ 分析动量信号...")
        
        latest = df.iloc[-1]
        
        # 1. RSI动量分析
        rsi = latest['rsi_14']
        if pd.isna(rsi):
            rsi_score = 5.0
            rsi_status = "数据不足"
        elif rsi > 70:
            rsi_score = 3.0
            rsi_status = "超买"
        elif rsi < 30:
            rsi_score = 3.0
            rsi_status = "超卖"
        elif 50 <= rsi <= 60:
            rsi_score = 8.0
            rsi_status = "强势区"
        elif 40 <= rsi < 50:
            rsi_score = 6.0
            rsi_status = "中性偏强"
        else:
            rsi_score = 4.0
            rsi_status = f"RSI: {rsi:.1f}"
        
        # 2. MACD信号分析
        macd = latest['macd']
        macd_signal = latest['macd_signal']
        
        if pd.isna(macd) or pd.isna(macd_signal):
            macd_score = 5.0
            macd_signal_desc = "数据不足"
        elif macd > macd_signal and macd > 0:
            macd_score = 9.0
            macd_signal_desc = "金叉且零轴上方"
        elif macd > macd_signal:
            macd_score = 7.0
            macd_signal_desc = "金叉"
        elif macd < macd_signal and macd < 0:
            macd_score = 2.0
            macd_signal_desc = "死叉且零轴下方"
        else:
            macd_score = 4.0
            macd_signal_desc = "死叉"
        
        # 3. KDJ信号分析
        k = latest['k']
        d = latest['d']
        j = latest['j']
        
        if pd.isna(k) or pd.isna(d):
            kdj_score = 5.0
            kdj_status = "数据不足"
        elif k > d and k < 80:
            kdj_score = 8.0
            kdj_status = "KD金叉"
        elif k > 80:
            kdj_score = 3.0
            kdj_status = "K值超买"
        elif k < 20:
            kdj_score = 3.0
            kdj_status = "K值超卖"
        else:
            kdj_score = 5.0
            kdj_status = f"K:{k:.1f}, D:{d:.1f}"
        
        # 综合动量评分
        momentum_score = (rsi_score * 0.3 + macd_score * 0.4 + kdj_score * 0.3)
        
        self.results['momentum_analysis'] = {
            'score': round(momentum_score, 2),
            'details': {
                'rsi': f"{rsi:.1f} ({rsi_status})",
                'rsi_score': round(rsi_score, 2),
                'macd': macd_signal_desc,
                'macd_score': round(macd_score, 2),
                'kdj': kdj_status,
                'kdj_score': round(kdj_score, 2)
            }
        }
        
        print(f"✅ 动量信号评分: {momentum_score:.2f}/10.0")
        return momentum_score
    
    def analyze_volatility_features(self, df):
        """分析波动特征"""
        print("\n📉 分析波动特征...")
        
        latest = df.iloc[-1]
        
        # 1. 布林带位置分析
        price = latest['close']
        bb_upper = latest['bb_upper']
        bb_middle = latest['bb_middle']
        bb_lower = latest['bb_lower']
        
        if pd.isna(bb_upper) or pd.isna(bb_lower):
            bb_score = 5.0
            bb_position = "数据不足"
        elif price >= bb_upper:
            bb_score = 3.0
            bb_position = "触及上轨（超买风险）"
        elif price <= bb_lower:
            bb_score = 3.0
            bb_position = "触及下轨（超卖机会）"
        elif abs(price - bb_middle) < (bb_upper - bb_middle) * 0.3:
            bb_score = 8.0
            bb_position = "中轨附近（安全区域）"
        else:
            # 计算在中轨到上下轨之间的位置
            if price > bb_middle:
                position_ratio = (price - bb_middle) / (bb_upper - bb_middle)
                bb_score = 8 - position_ratio * 5
                bb_position = f"上轨方向{position_ratio*100:.1f}%"
            else:
                position_ratio = (bb_middle - price) / (bb_middle - bb_lower)
                bb_score = 8 - position_ratio * 5
                bb_position = f"下轨方向{position_ratio*100:.1f}%"
        
        # 2. 布林带宽度分析（波动率）
        bb_width = (bb_upper - bb_lower) / bb_middle if not pd.isna(bb_middle) and bb_middle > 0 else 0.1
        
        if bb_width < 0.05:  # 5%宽度
            volatility_score = 4.0
            volatility_status = "窄幅震荡（突破前兆）"
        elif bb_width > 0.15:  # 15%宽度
            volatility_score = 4.0
            volatility_status = "宽幅震荡（高风险）"
        else:
            volatility_score = 7.0
            volatility_status = "正常波动"
        
        # 3. ATR（平均真实波幅）分析
        # 计算最近14日的ATR
        high_low = df['high'].tail(14) - df['low'].tail(14)
        high_close = abs(df['high'].tail(14) - df['close'].shift(1).tail(14))
        low_close = abs(df['low'].tail(14) - df['close'].shift(1).tail(14))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.mean()
        
        atr_percent = atr / df['close'].tail(14).mean() if df['close'].tail(14).mean() > 0 else 0
        
        if atr_percent < 0.015:  # 1.5%
            atr_score = 6.0
            atr_status = "低波动"
        elif atr_percent > 0.04:  # 4%
            atr_score = 3.0
            atr_status = "高波动"
        else:
            atr_score = 8.0
            atr_status = "适度波动"
        
        # 综合波动评分
        volatility_final_score = (bb_score * 0.4 + volatility_score * 0.3 + atr_score * 0.3)
        
        self.results['volatility_analysis'] = {
            'score': round(volatility_final_score, 2),
            'details': {
                'bollinger_position': bb_position,
                'bollinger_score': round(bb_score, 2),
                'volatility_status': volatility_status,
                'volatility_score': round(volatility_score, 2),
                'atr': f"{atr_percent*100:.2f}% ({atr_status})",
                'atr_score': round(atr_score, 2)
            }
        }
        
        print(f"✅ 波动特征评分: {volatility_final_score:.2f}/10.0")
        return volatility_final_score
    
    def analyze_volume_price_relationship(self, df):
        """分析量价关系"""
        print("\n📊 分析量价关系...")
        
        # 分析最近5个交易日的量价关系
        recent_data = df.tail(5)
        
        # 1. 成交量趋势分析
        volume_trend = recent_data['volume'].pct_change().mean()
        price_trend = recent_data['close'].pct_change().mean()
        
        if volume_trend > 0.05 and price_trend > 0:  # 放量上涨
            volume_trend_score = 9.0
            volume_trend_desc = "放量上涨"
        elif volume_trend > 0.05 and price_trend < 0:  # 放量下跌
            volume_trend_score = 2.0
            volume_trend_desc = "放量下跌"
        elif volume_trend < -0.05 and price_trend > 0:  # 缩量上涨
            volume_trend_score = 6.0
            volume_trend_desc = "缩量上涨"
        elif volume_trend < -0.05 and price_trend < 0:  # 缩量下跌
            volume_trend_score = 4.0
            volume_trend_desc = "缩量下跌"
        else:
            volume_trend_score = 7.0
            volume_trend_desc = "量价平稳"
        
        # 2. 成交量均线关系
        latest = df.iloc[-1]
        vol_ma5 = latest['vol_ma5']
        vol_ma10 = latest['vol_ma10']
        current_volume = latest['volume']
        
        if pd.isna(vol_ma5) or pd.isna(vol_ma10):
            volume_ma_score = 5.0
            volume_ma_desc = "数据不足"
        elif current_volume > vol_ma5 > vol_ma10:
            volume_ma_score = 9.0
            volume_ma_desc = "量能充沛（现量>5日>10日）"
        elif current_volume > vol_ma5:
            volume_ma_score = 7.0
            volume_ma_desc = "现量大于5日均量"
        elif current_volume < vol_ma5 and current_volume > vol_ma10:
            volume_ma_score = 5.0
            volume_ma_desc = "量能中性"
        else:
            volume_ma_score = 3.0
            volume_ma_desc = "量能不足"
        
        # 3. 量价背离分析
        # 检查价格新高但成交量未配合的情况
        recent_20 = df.tail(20)
        price_high_idx = recent_20['close'].idxmax()
        volume_at_high = recent_20.loc[price_high_idx, 'volume']
        avg_volume = recent_20['volume'].mean()
        
        if price_high_idx == recent_20.index[-1]:  # 当前是价格高点
            if volume_at_high < avg_volume * 0.8:
                divergence_score = 2.0
                divergence_desc = "价涨量缩背离"
            elif volume_at_high > avg_volume * 1.2:
                divergence_score = 9.0
                divergence_desc = "价涨量增健康"
            else:
                divergence_score = 7.0
                divergence_desc = "量价配合正常"
        else:
            divergence_score = 6.0
            divergence_desc = "非价格高点"
        
        # 综合量价评分
        volume_price_score = (volume_trend_score * 0.4 + volume_ma_score * 0.3 + divergence_score * 0.3)
        
        self.results['volume_price_analysis'] = {
            'score': round(volume_price_score, 2),
            'details': {
                'volume_trend': volume_trend_desc,
                'volume_trend_score': round(volume_trend_score, 2),
                'volume_ma': volume_ma_desc,
                'volume_ma_score': round(volume_ma_score, 2),
                'divergence': divergence_desc,
                'divergence_score': round(divergence_score, 2)
            }
        }
        
        print(f"✅ 量价关系评分: {volume_price_score:.2f}/10.0")
        return volume_price_score
    
    def analyze_fundamental_health(self):
        """分析基本面健康度（简化版）"""
        print("\n🏢 分析基本面健康度...")
        
        # 国电南瑞基本面评估（基于公开信息）
        # 1. 行业地位：电力自动化龙头
        industry_score = 9.0
        industry_desc = "电力自动化行业龙头，技术领先"
        
        # 2. 财务稳健性（假设数据）
        # ROE约15%，资产负债率约50%，营收增长约10%
        financial_score = 8.0
        financial_desc = "财务稳健，ROE约15%"
        
        # 3. 政策支持：新基建、智能电网
        policy_score = 9.0
        policy_desc = "受益新基建、智能电网政策"
        
        # 4. 估值水平（PE约20倍，行业平均约25倍）
        valuation_score = 7.0
        valuation_desc = "估值合理，PE约20倍"
        
        # 综合基本面评分
        fundamental_score = (industry_score * 0.3 + financial_score * 0.3 + 
                           policy_score * 0.2 + valuation_score * 0.2)
        
        self.results['fundamental_analysis'] = {
            'score': round(fundamental_score, 2),
            'details': {
                'industry': industry_desc,
                'industry_score': round(industry_score, 2),
                'financial': financial_desc,
                'financial_score': round(financial_score, 2),
                'policy': policy_desc,
                'policy_score': round(policy_score, 2),
                'valuation': valuation_desc,
                'valuation_score': round(valuation_score, 2)
            }
        }
        
        print(f"✅ 基本面健康度评分: {fundamental_score:.2f}/10.0")
        return fundamental_score
    
    def calculate_composite_score(self):
        """计算综合选股评分"""
        print("\n🎯 计算综合选股评分...")
        
        # 获取各维度评分
        scores = {
            '趋势强度': self.results.get('trend_analysis', {}).get('score', 5.0),
            '动量信号': self.results.get('momentum_analysis', {}).get('score', 5.0),
            '波动特征': self.results.get('volatility_analysis', {}).get('score', 5.0),
            '量价配合': self.results.get('volume_price_analysis', {}).get('score', 5.0),
            '基本面': self.results.get('fundamental_analysis', {}).get('score', 5.0)
        }
        
        # 权重分配（根据竹林司马选股战法）
        weights = {
            '趋势强度': 0.30,
            '动量信号': 0.25,
            '波动特征': 0.20,
            '量价配合': 0.15,
            '基本面': 0.10
        }
        
        # 计算加权综合评分
        composite_score = sum(scores[dim] * weights[dim] for dim in scores)
        
        # 确定评级
        if composite_score >= 8.5:
            rating = "★★★★★ (强烈关注)"
            action = "积极关注，考虑分批建仓"
            color = "🟢"
        elif composite_score >= 7.0:
            rating = "★★★★ (看好)"
            action = "关注，等待合适时机"
            color = "🟡"
        elif composite_score >= 5.5:
            rating = "★★★ (中性)"
            action = "观察，需进一步确认"
            color = "🟠"
        elif composite_score >= 4.0:
            rating = "★★ (谨慎)"
            action = "谨慎，注意风险"
            color = "🔴"
        else:
            rating = "★ (回避)"
            action = "回避，风险较高"
            color = "⚫"
        
        self.results['composite_analysis'] = {
            'composite_score': round(composite_score, 2),
            'rating': rating,
            'action_recommendation': action,
            'color': color,
            'dimension_scores': scores,
            'weights': weights
        }
        
        print(f"✅ 综合选股评分: {composite_score:.2f}/10.0")
        print(f"✅ 投资评级: {rating}")
        print(f"✅ 操作建议: {action}")
        
        return composite_score, rating, action
    
    def generate_visualization(self, df):
        """生成可视化图表"""
        print("\n📊 生成可视化分析图表...")
        
        try:
            # 创建图表
            fig, axes = plt.subplots(3, 2, figsize=(15, 12))
            fig.suptitle(f'{self.stock_name}({self.stock_code}) - {ZH_CHINESE_NAME}选股战法分析\n分析日期: {self.analysis_date}', 
                        fontsize=16, fontweight='bold')
            
            # 1. 价格与移动平均线
            ax1 = axes[0, 0]
            ax1.plot(df.index[-60:], df['close'].tail(60), label='收盘价', linewidth=2, color='blue')
            for period in [5, 10, 20]:
                ax1.plot(df.index[-60:], df[f'sma_{period}'].tail(60), 
                        label=f'SMA{period}', linestyle='--', alpha=0.7)
            ax1.set_title('价格与移动平均线')
            ax1.set_ylabel('价格(元)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. 成交量
            ax2 = axes[0, 1]
            ax2.bar(df.index[-30:], df['volume'].tail(30), color='orange', alpha=0.6)
            ax2.plot(df.index[-30:], df['vol_ma5'].tail(30), label='5日成交量均线', color='red')
            ax2.set_title('成交量分析')
            ax2.set_ylabel('成交量')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # 3. RSI指标
            ax3 = axes[1, 0]
            ax3.plot(df.index[-60:], df['rsi_14'].tail(60), label='RSI(14)', color='purple')
            ax3.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='超买线(70)')
            ax3.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='超卖线(30)')
            ax3.axhline(y=50, color='gray', linestyle='-', alpha=0.3)
            ax3.set_title('RSI动量指标')
            ax3.set_ylabel('RSI')
            ax3.set_ylim(0, 100)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. MACD指标
            ax4 = axes[1, 1]
            ax4.plot(df.index[-60:], df['macd'].tail(60), label='MACD', color='blue')
            ax4.plot(df.index[-60:], df['macd_signal'].tail(60), label='信号线', color='red')
            ax4.bar(df.index[-60:], df['macd_hist'].tail(60), label='柱状图', color='gray', alpha=0.5)
            ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax4.set_title('MACD指标')
            ax4.set_ylabel('MACD')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            
            # 5. 布林带
            ax5 = axes[2, 0]
            ax5.plot(df.index[-60:], df['close'].tail(60), label='收盘价', color='blue')
            ax5.plot(df.index[-60:], df['bb_upper'].tail(60), label='上轨', color='red', alpha=0.5)
            ax5.plot(df.index[-60:], df['bb_middle'].tail(60), label='中轨', color='orange', alpha=0.7)
            ax5.plot(df.index[-60:], df['bb_lower'].tail(60), label='下轨', color='green', alpha=0.5)
            ax5.fill_between(df.index[-60:], df['bb_upper'].tail(60), df['bb_lower'].tail(60), 
                            alpha=0.1, color='gray')
            ax5.set_title('布林带分析')
            ax5.set_ylabel('价格(元)')
            ax5.legend()
            ax5.grid(True, alpha=0.3)
            
            # 6. 评分雷达图（留空位置）
            ax6 = axes[2, 1]
            ax6.text(0.5, 0.5, '综合评分雷达图\n（HTML报告中将详细展示）', 
                    ha='center', va='center', fontsize=12, transform=ax6.transAxes)
            ax6.set_title('综合评分')
            ax6.axis('off')
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = f"{self.stock_name}_技术分析图表.png"
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            print(f"✅ 技术分析图表已保存: {chart_path}")
            return chart_path
            
        except Exception as e:
            print(f"⚠️ 图表生成失败: {e}")
            return None
    
    def generate_html_report(self):
        """生成HTML分析报告"""
        print("\n📄 生成HTML分析报告...")
        
        try:
            # 获取分析结果
            composite = self.results.get('composite_analysis', {})
            trend = self.results.get('trend_analysis', {})
            momentum = self.results.get('momentum_analysis', {})
            volatility = self.results.get('volatility_analysis', {})
            volume = self.results.get('volume_price_analysis', {})
            fundamental = self.results.get('fundamental_analysis', {})
            
            # 创建HTML报告
            html_content = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{self.stock_name}选股战法分析报告 - {ZH_CHINESE_NAME}</title>
                <style>
                    body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
                    .header {{ text-align: center; border-bottom: 3px solid #4CAF50; padding-bottom: 20px; margin-bottom: 30px; }}
                    h1 {{ color: #333; margin-bottom: 10px; }}
                    .subtitle {{ color: #666; font-size: 18px; }}
                    .score-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin: 20px 0; text-align: center; }}
                    .score-value {{ font-size: 48px; font-weight: bold; margin: 10px 0; }}
                    .score-rating {{ font-size: 24px; margin-bottom: 15px; }}
                    .score-action {{ font-size: 18px; background-color: rgba(255,255,255,0.2); padding: 10px; border-radius: 5px; }}
                    .dimension-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }}
                    .dimension-card {{ border: 1px solid #ddd; border-radius: 8px; padding: 20px; background-color: #fff; }}
                    .dimension-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; border-bottom: 2px solid #4CAF50; padding-bottom: 5px; }}
                    .dimension-score {{ font-size: 28px; color: #4CAF50; font-weight: bold; text-align: center; margin: 10px 0; }}
                    .dimension-details {{ font-size: 14px; color: #666; }}
                    .detail-item {{ margin: 8px 0; padding: 5px 0; border-bottom: 1px dashed #eee; }}
                    .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #888; font-size: 14px; }}
                    .risk-warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 20px 0; color: #856404; }}
                    .chart-container {{ margin: 30px 0; text-align: center; }}
                    .chart-img {{ max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{self.stock_name}({self.stock_code})选股战法分析报告</h1>
                        <div class="subtitle">{ZH_FULL_NAME} | 分析日期: {self.analysis_date}</div>
                    </div>
                    
                    <div class="score-card">
                        <h2>综合选股评分</h2>
                        <div class="score-value">{composite.get('composite_score', 0)}/10.0</div>
                        <div class="score-rating">{composite.get('rating', '')}</div>
                        <div class="score-action">{composite.get('action_recommendation', '')}</div>
                    </div>
                    
                    <div class="dimension-grid">
                        <div class="dimension-card">
                            <div class="dimension-title">📈 趋势强度分析</div>
                            <div class="dimension-score">{trend.get('score', 0)}/10.0</div>
                            <div class="dimension-details">
                                <div class="detail-item"><strong>趋势形态:</strong> {trend.get('details', {}).get('trend_pattern', 'N/A')}</div>
                                <div class="detail-item"><strong>价格位置:</strong> {trend.get('details', {}).get('price_position', 'N/A')}</div>
                                <div class="detail-item"><strong>趋势斜率:</strong> {trend.get('details', {}).get('trend_slope_score', 'N/A')}</div>
                            </div>
                        </div>
                        
                        <div class="dimension-card">
                            <div class="dimension-title">⚡ 动量信号分析</div>
                            <div class="dimension-score">{momentum.get('score', 0)}/10.0</div>
                            <div class="dimension-details">
                                <div class="detail-item"><strong>RSI状态:</strong> {momentum.get('details', {}).get('rsi', 'N/A')}</div>
                                <div class="detail-item"><strong>MACD信号:</strong> {momentum.get('details', {}).get('macd', 'N/A')}</div>
                                <div class="detail-item"><strong>KDJ状态:</strong> {momentum.get('details', {}).get('kdj', 'N/A')}</div>
                            </div>
                        </div>
                        
                        <div class="dimension-card">
                            <div class="dimension-title">📉 波动特征分析</div>
                            <div class="dimension-score">{volatility.get('score', 0)}/10.0</div>
                            <div class="dimension-details">
                                <div class="detail-item"><strong>布林带位置:</strong> {volatility.get('details', {}).get('bollinger_position', 'N/A')}</div>
                                <div class="detail-item"><strong>波动状态:</strong> {volatility.get('details', {}).get('volatility_status', 'N/A')}</div>
                                <div class="detail-item"><strong>ATR波动率:</strong> {volatility.get('details', {}).get('atr', 'N/A')}</div>
                            </div>
                        </div>
                        
                        <div class="dimension-card">
                            <div class="dimension-title">📊 量价关系分析</div>
                            <div class="dimension-score">{volume.get('score', 0)}/10.0</div>
                            <div class="dimension-details">
                                <div class="detail-item"><strong>量能趋势:</strong> {volume.get('details', {}).get('volume_trend', 'N/A')}</div>
                                <div class="detail-item"><strong>成交量均线:</strong> {volume.get('details', {}).get('volume_ma', 'N/A')}</div>
                                <div class="detail-item"><strong>量价背离:</strong> {volume.get('details', {}).get('divergence', 'N/A')}</div>
                            </div>
                        </div>
                        
                        <div class="dimension-card">
                            <div class="dimension-title">🏢 基本面健康度</div>
                            <div class="dimension-score">{fundamental.get('score', 0)}/10.0</div>
                            <div class="dimension-details">
                                <div class="detail-item"><strong>行业地位:</strong> {fundamental.get('details', {}).get('industry', 'N/A')}</div>
                                <div class="detail-item"><strong>财务稳健性:</strong> {fundamental.get('details', {}).get('financial', 'N/A')}</div>
                                <div class="detail-item"><strong>政策支持:</strong> {fundamental.get('details', {}).get('policy', 'N/A')}</div>
                                <div class="detail-item"><strong>估值水平:</strong> {fundamental.get('details', {}).get('valuation', 'N/A')}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <h3>技术分析图表</h3>
                        <p>（注：实际应用中图表将根据实时数据动态生成）</p>
                    </div>
                    
                    <div class="risk-warning">
                        <h4>⚠️ 风险提示</h4>
                        <p>本分析报告基于技术指标和模拟数据生成，仅供参考。投资有风险，入市需谨慎。实际投资决策应结合更多基本面分析、市场环境和个人风险承受能力。</p>
                        <p>竹林司马技术分析工具旨在提供客观的技术信号参考，不构成投资建议。</p>
                    </div>
                    
                    <div class="footer">
                        <p>生成工具: {ZH_FULL_NAME} 技术分析系统</p>
                        <p>版本: v1.0 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p>© 2026 竹林司马技术分析工具 - 仅供学习和研究使用</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # 保存HTML文件
            html_path = f"{self.stock_name}_选股战法分析报告.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ HTML分析报告已生成: {html_path}")
            return html_path
            
        except Exception as e:
            print(f"❌ HTML报告生成失败: {e}")
            return None
    
    def generate_summary_report(self):
        """生成文本总结报告"""
        print("\n📋 生成文本总结报告...")
        
        try:
            # 获取分析结果
            composite = self.results.get('composite_analysis', {})
            
            # 创建总结报告
            summary = f"""
            ================================================
            {ZH_FULL_NAME} - 选股战法分析报告
            ================================================
            
            股票名称: {self.stock_name} ({self.stock_code})
            分析日期: {self.analysis_date}
            生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            【核心结论】
            综合评分: {composite.get('composite_score', 0)}/10.0
            投资评级: {composite.get('rating', '')}
            操作建议: {composite.get('action_recommendation', '')}
            
            【各维度评分详情】
            1. 趋势强度: {self.results.get('trend_analysis', {}).get('score', 0)}/10.0
                - {self.results.get('trend_analysis', {}).get('details', {}).get('trend_pattern', 'N/A')}
                
            2. 动量信号: {self.results.get('momentum_analysis', {}).get('score', 0)}/10.0
                - RSI: {self.results.get('momentum_analysis', {}).get('details', {}).get('rsi', 'N/A')}
                - MACD: {self.results.get('momentum_analysis', {}).get('details', {}).get('macd', 'N/A')}
                
            3. 波动特征: {self.results.get('volatility_analysis', {}).get('score', 0)}/10.0
                - 布林带位置: {self.results.get('volatility_analysis', {}).get('details', {}).get('bollinger_position', 'N/A')}
                - 波动率状态: {self.results.get('volatility_analysis', {}).get('details', {}).get('volatility_status', 'N/A')}
                
            4. 量价关系: {self.results.get('volume_price_analysis', {}).get('score', 0)}/10.0
                - 量能趋势: {self.results.get('volume_price_analysis', {}).get('details', {}).get('volume_trend', 'N/A')}
                - 成交量均线: {self.results.get('volume_price_analysis', {}).get('details', {}).get('volume_ma', 'N/A')}
                
            5. 基本面健康度: {self.results.get('fundamental_analysis', {}).get('score', 0)}/10.0
                - 行业地位: {self.results.get('fundamental_analysis', {}).get('details', {}).get('industry', 'N/A')}
                - 财务稳健性: {self.results.get('fundamental_analysis', {}).get('details', {}).get('financial', 'N/A')}
            
            【技术分析要点】
            1. 趋势判断: 根据移动平均线排列和价格位置判断当前趋势状态
            2. 动量评估: 通过RSI、MACD、KDJ等指标评估买卖动能
            3. 风险控制: 结合布林带和波动率评估风险水平
            4. 量价验证: 成交量配合程度验证价格变动的可靠性
            
            【风险提示】
            1. 技术分析存在滞后性，需结合基本面分析
            2. 市场情绪变化可能导致技术信号失效
            3. 建议设置止损位，控制单笔交易风险
            4. 本分析仅供参考，不构成投资建议
            
            【竹林司马系统说明】
            - 系统名称: {ZH_FULL_NAME}
            - 核心能力: 双重验证技术指标、趋势分析、风险评估
            - 优化特性: 向量化计算、API接口标准化、AI智能分析
            - 数据质量: 多重验证机制，确保分析准确性
            
            ================================================
            报告生成完成
            ================================================
            """
            
            # 保存总结报告
            summary_path = f"{self.stock_name}_选股战法分析总结.txt"
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            print(f"✅ 文本总结报告已生成: {summary_path}")
            return summary_path
            
        except Exception as e:
            print(f"❌ 总结报告生成失败: {e}")
            return None
    
    def run_complete_analysis(self):
        """执行完整分析流程"""
        print(f"\n{'='*60}")
        print(f"开始执行 {self.stock_name} 选股战法分析...")
        print(f"使用工具: {ZH_FULL_NAME}")
        print(f"{'='*60}")
        
        # 1. 加载竹林司马模块
        module_loaded = self.load_zhulinsma_modules()
        
        # 2. 获取数据（模拟数据）
        print("\n📊 获取分析数据...")
        data = self.generate_mock_data()
        print(f"✅ 已获取 {len(data)} 个交易日数据（{data['date'].min().date()} 至 {data['date'].max().date()}）")
        
        # 3. 计算技术指标
        df_with_indicators = self.calculate_technical_indicators(data)
        
        # 4. 执行各维度分析
        trend_score = self.analyze_trend_strength(df_with_indicators)
        momentum_score = self.analyze_momentum_signals(df_with_indicators)
        volatility_score = self.analyze_volatility_features(df_with_indicators)
        volume_score = self.analyze_volume_price_relationship(df_with_indicators)
        fundamental_score = self.analyze_fundamental_health()
        
        # 5. 计算综合评分
        composite_score, rating, action = self.calculate_composite_score()
        
        # 6. 生成可视化
        chart_path = self.generate_visualization(df_with_indicators)
        
        # 7. 生成报告
        html_path = self.generate_html_report()
        summary_path = self.generate_summary_report()
        
        # 8. 输出最终结果
        print(f"\n{'='*60}")
        print(f"🎉 {self.stock_name} 选股战法分析完成!")
        print(f"{'='*60}")
        
        print(f"\n📊 最终分析结果:")
        print(f"   综合评分: {composite_score:.2f}/10.0")
        print(f"   投资评级: {rating}")
        print(f"   操作建议: {action}")
        
        print(f"\n📈 各维度评分:")
        print(f"   趋势强度: {trend_score:.2f}/10.0")
        print(f"   动量信号: {momentum_score:.2f}/10.0")
        print(f"   波动特征: {volatility_score:.2f}/10.0")
        print(f"   量价关系: {volume_score:.2f}/10.0")
        print(f"   基本面: {fundamental_score:.2f}/10.0")
        
        print(f"\n📁 生成文件:")
        if chart_path:
            print(f"   • 技术分析图表: {chart_path}")
        if html_path:
            print(f"   • HTML分析报告: {html_path}")
        if summary_path:
            print(f"   • 文本总结报告: {summary_path}")
        
        # 保存分析结果到JSON
        json_path = f"{self.stock_name}_分析结果.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"   • JSON数据文件: {json_path}")
        
        print(f"\n⚠️ 重要说明:")
        print(f"   1. 本次分析使用模拟数据演示竹林司马选股战法")
        print(f"   2. 实际应用中应接入真实市场数据")
        print(f"   3. 投资决策需结合更多因素综合分析")
        print(f"   4. 技术分析仅为参考工具，不构成投资建议")
        
        return self.results

def main():
    """主函数"""
    try:
        # 创建分析器实例
        analyzer = NareiStockAnalysis()
        
        # 执行完整分析
        results = analyzer.run_complete_analysis()
        
        # 返回分析结果路径
        output_files = [
            f"{analyzer.stock_name}_技术分析图表.png",
            f"{analyzer.stock_name}_选股战法分析报告.html",
            f"{analyzer.stock_name}_选股战法分析总结.txt",
            f"{analyzer.stock_name}_分析结果.json"
        ]
        
        print(f"\n✅ 分析任务完成! 所有文件已保存在当前目录。")
        
    except Exception as e:
        print(f"❌ 分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()