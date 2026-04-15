#!/usr/bin/env python3
"""
五步选股法策略

选股5步实战法：
1. 看趋势 - MA多头排列判断
2. 看资金 - 量比和成交量分析
3. 看基本面 - PE/ROE/负债率评估
4. 看板块 - 板块热度评分
5. 看形态 - RSI/MACD技术指标
"""

from typing import Any, Dict, Optional
import numpy as np

from .base import BaseStrategy, Signal, SignalType, StockData, StrategyType


class FiveStepStrategy(BaseStrategy):
    """
    五步选股法策略
    
    适用场景：中长期选股，综合评估
    持仓周期：1-3个月
    """
    
    def get_name(self) -> str:
        return "五步选股法"
    
    def get_description(self) -> str:
        return """选股5步实战法：
        1. 看趋势 - MA多头排列判断
        2. 看资金 - 量比和成交量分析
        3. 看基本面 - PE/ROE/负债率评估
        4. 看板块 - 板块热度评分
        5. 看形态 - RSI/MACD技术指标
        """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.weights = {
            "趋势": 0.30,
            "资金": 0.25,
            "基本面": 0.20,
            "板块": 0.15,
            "形态": 0.10
        }
        
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """
        执行五步选股法分析
        
        Returns:
            Signal对象，包含各维度评分和综合评分
        """
        if not self.validate_data(stock_data):
            return None
        
        close = stock_data.close
        volume = stock_data.volume
        
        # Step 1: 看趋势
        trend_score, trend_details = self._analyze_trend(close)
        
        # Step 2: 看资金
        fund_score, fund_details = self._analyze_fund(volume)
        
        # Step 3: 看基本面
        fundamental_score, fundamental_details = self._analyze_fundamental(stock_data)
        
        # Step 4: 看板块
        sector_score, sector_details = self._analyze_sector(stock_data)
        
        # Step 5: 看形态
        pattern_score, pattern_details = self._analyze_pattern(close)
        
        # 计算综合评分
        scores = {
            "趋势": trend_score,
            "资金": fund_score,
            "基本面": fundamental_score,
            "板块": sector_score,
            "形态": pattern_score
        }
        
        total_score = sum(scores[k] * self.weights[k] for k in scores)
        
        # 确定信号类型
        if total_score >= 8.0:
            signal_type = SignalType.STRONG_BUY
        elif total_score >= 7.0:
            signal_type = SignalType.BUY
        elif total_score >= 6.0:
            signal_type = SignalType.HOLD
        else:
            signal_type = SignalType.WATCH
        
        # 构建Signal
        current_price = float(close[-1])
        
        signal = Signal(
            code=stock_data.code,
            name=stock_data.name,
            strategy=self.name,
            strategy_type=StrategyType.FIVE_STEP,
            signal_type=signal_type,
            current_price=current_price,
            score=round(total_score, 2),
            confidence=min(total_score / 10, 0.95),
            holding_days="1-3个月",
            details={
                "趋势分析": trend_details,
                "资金分析": fund_details,
                "基本面分析": fundamental_details,
                "板块分析": sector_details,
                "形态分析": pattern_details,
                "各维度得分": scores,
                "权重配置": self.weights
            },
            signals={
                "多头排列": trend_details.get("多头排列", False),
                "站上60日线": trend_details.get("站上60日线", False),
                "量能健康": fund_details.get("量比健康", False),
                "基本面良好": fundamental_score >= 7.0,
                "形态良好": pattern_score >= 7.0
            }
        )
        
        return signal
    
    def _analyze_trend(self, close: np.ndarray) -> tuple:
        """Step 1: 趋势分析"""
        # 计算均线
        ma5 = self.calculate_ma(close, 5)[-1]
        ma10 = self.calculate_ma(close, 10)[-1]
        ma20 = self.calculate_ma(close, 20)[-1]
        ma60 = self.calculate_ma(close, 60)[-1] if len(close) >= 60 else ma20
        
        current_price = close[-1]
        
        # 判断条件
        多头排列 = ma5 > ma10 > ma20 > ma60
        站上60日 = current_price > ma60
        
        # 计算得分
        ma_score = 0
        if current_price > ma5:
            ma_score += 1
        if current_price > ma10:
            ma_score += 1
        if current_price > ma20:
            ma_score += 1.5
        if current_price > ma60:
            ma_score += 1.5
        if ma5 > ma10 > ma20:
            ma_score += 2
        if ma10 > ma60:
            ma_score += 2
        
        # 20日涨跌幅
        change_20 = (current_price - close[-20]) / close[-20] * 100 if len(close) >= 20 else 0
        trend_score = min(max(change_20 / 10, -2), 2) + 5
        
        final_score = min((ma_score / 9 * 6) + (trend_score / 10 * 4), 10)
        
        details = {
            "MA5": round(ma5, 3),
            "MA10": round(ma10, 3),
            "MA20": round(ma20, 3),
            "MA60": round(ma60, 3),
            "当前价": round(current_price, 3),
            "多头排列": 多头排列,
            "站上60日线": 站上60日,
            "20日涨幅%": round(change_20, 2),
            "MA得分": round(ma_score, 2)
        }
        
        return round(final_score, 2), details
    
    def _analyze_fund(self, volume: np.ndarray) -> tuple:
        """Step 2: 资金分析"""
        # 量比计算（近5日均量 vs 近20日均量）
        vol_5 = np.mean(volume[-5:])
        vol_20 = np.mean(volume[-20:])
        ratio = vol_5 / (vol_20 + 1e-10)
        
        # 量能得分
        if 1.2 <= ratio <= 1.8:
            score = 8.0
        elif 1.0 <= ratio <= 2.5:
            score = 6.0
        else:
            score = 4.0
        
        details = {
            "近5日均量": round(vol_5, 0),
            "近20日均量": round(vol_20, 0),
            "量比": round(ratio, 2),
            "量比健康": 1.0 <= ratio <= 2.5
        }
        
        return score, details
    
    def _analyze_fundamental(self, stock_data: StockData) -> tuple:
        """Step 3: 基本面分析"""
        pe = stock_data.pe
        pb = stock_data.pb
        
        # 默认中等得分
        score = 5.0
        details = {"PE": pe, "PB": pb}
        
        # PE评分
        if pe is not None and pe > 0:
            if pe < 15:
                score += 2
                details["PE评价"] = "低估"
            elif pe < 30:
                score += 1
                details["PE评价"] = "合理"
            elif pe > 60:
                score -= 1
                details["PE评价"] = "高估"
        
        # PB评分
        if pb is not None and pb > 0:
            if pb < 1.5:
                score += 1.5
            elif pb < 3:
                score += 0.5
        
        # 市值评分（大盘股稳定性更好）
        if stock_data.market_cap is not None:
            if stock_data.market_cap > 1000:  # 千亿市值
                score += 0.5
            details["市值(亿)"] = stock_data.market_cap
        
        return round(min(score, 10), 2), details
    
    def _analyze_sector(self, stock_data: StockData) -> tuple:
        """Step 4: 板块分析"""
        # 板块评分需要外部数据输入，这里提供框架
        # 实际使用时应从stock_data获取板块信息
        
        score = 7.0  # 默认中等偏上
        details = {
            "板块": stock_data.metadata.get("sector", "未知"),
            "政策利好": stock_data.metadata.get("policy_benefit", True),
            "板块热度": stock_data.metadata.get("sector_heat", "中等")
        }
        
        return score, details
    
    def _analyze_pattern(self, close: np.ndarray) -> tuple:
        """Step 5: 形态分析"""
        # RSI
        rsi = self.calculate_rsi(close, 14)[-1]
        
        # MACD
        macd = self.calculate_macd(close)
        hist = macd["hist"][-1]
        
        # 形态得分
        if 40 <= rsi <= 65 and hist > 0:
            score = 8.0
        elif 30 <= rsi <= 70:
            score = 6.0
        else:
            score = 5.0
        
        details = {
            "RSI14": round(rsi, 1) if not np.isnan(rsi) else None,
            "MACD柱": round(hist, 4) if not np.isnan(hist) else None,
            "RSI状态": "超买" if rsi > 70 else ("超卖" if rsi < 30 else "正常")
        }
        
        return score, details
