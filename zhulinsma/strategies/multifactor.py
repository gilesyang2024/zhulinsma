#!/usr/bin/env python3
"""
多因子打分策略

基于EasyFactor分析框架，从五个维度对股票进行综合评分：
1. 趋势强度 (25%) - MA多头排列、20日涨幅
2. 动量信号 (25%) - RSI、MACD、KDJ
3. 波动特征 (15%) - ATR、年化波动率、布林带位置
4. 量价关系 (20%) - OBV、量比、价量配合
5. 基本面 (15%) - PE、PB、市值
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .base import BaseStrategy, Signal, SignalType, StockData, StrategyType


class MultiFactorStrategy(BaseStrategy):
    """
    多因子打分策略
    
    综合评估股票的五个维度，给出量化评分
    适用于：中长期选股、股票对比
    """
    
    def get_name(self) -> str:
        return "多因子打分"
    
    def get_description(self) -> str:
        return """基于五维因子的量化评分系统：
        - 趋势强度(25%): MA多头排列、20日涨幅
        - 动量信号(25%): RSI、MACD、KDJ
        - 波动特征(15%): ATR、波动率、布林带
        - 量价关系(20%): OBV、量比
        - 基本面(15%): PE、PB、市值
        """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.weights = {
            "趋势强度": 0.25,
            "动量信号": 0.25,
            "波动特征": 0.15,
            "量价关系": 0.20,
            "基本面": 0.15
        }
    
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """执行多因子打分分析"""
        if not self.validate_data(stock_data):
            return None
        
        # 各维度评分
        trend_score, trend_detail = self._score_trend(stock_data)
        momentum_score, momentum_detail = self._score_momentum(stock_data)
        volatility_score, vol_detail = self._score_volatility(stock_data)
        vp_score, vp_detail = self._score_volume_price(stock_data)
        fundamental_score, fund_detail = self._score_fundamental(stock_data)
        
        # 计算综合评分
        scores = {
            "趋势强度": trend_score,
            "动量信号": momentum_score,
            "波动特征": volatility_score,
            "量价关系": vp_score,
            "基本面": fundamental_score
        }
        
        total_score = sum(scores[k] * self.weights[k] for k in scores)
        
        # 确定信号类型
        if total_score >= 8.0:
            signal_type = SignalType.STRONG_BUY
        elif total_score >= 7.0:
            signal_type = SignalType.BUY
        elif total_score >= 6.0:
            signal_type = SignalType.HOLD
        elif total_score >= 5.0:
            signal_type = SignalType.WATCH
        else:
            signal_type = SignalType.SELL
        
        current_price = stock_data.close[-1]
        
        signal = Signal(
            code=stock_data.code,
            name=stock_data.name,
            strategy=self.name,
            strategy_type=StrategyType.MULTIFACTOR,
            signal_type=signal_type,
            current_price=current_price,
            score=round(total_score, 2),
            confidence=min(total_score / 10, 0.95),
            holding_days="1-3个月",
            details={
                "趋势指标": trend_detail,
                "动量指标": momentum_detail,
                "波动指标": vol_detail,
                "量价指标": vp_detail,
                "基本面": fund_detail,
                "各维度得分": scores,
                "权重配置": self.weights
            },
            signals={
                "趋势良好": trend_score >= 7,
                "动量积极": momentum_score >= 7,
                "风险可控": volatility_score >= 5,
                "量价配合": vp_score >= 7,
                "基本面稳健": fundamental_score >= 6
            }
        )
        
        return signal
    
    def _score_trend(self, stock_data: StockData) -> Tuple[float, Dict]:
        """趋势强度得分（0-10）"""
        close = stock_data.close
        
        # MA计算
        ma5 = self.calculate_ma(close, 5)[-1]
        ma10 = self.calculate_ma(close, 10)[-1]
        ma20 = self.calculate_ma(close, 20)[-1]
        ma60 = self.calculate_ma(close, 60)[-1] if len(close) >= 60 else ma20
        
        cur = close[-1]
        
        # MA多头排列得分
        ma_score = 0
        if cur > ma5: ma_score += 1
        if cur > ma10: ma_score += 1
        if cur > ma20: ma_score += 1.5
        if cur > ma60: ma_score += 1.5
        if ma5 > ma10 > ma20: ma_score += 2
        if ma10 > ma60: ma_score += 2
        
        # 20日涨跌幅得分
        change_20 = (cur - close[-20]) / close[-20] * 100 if len(close) >= 20 else 0
        trend_score = min(max(change_20 / 10, -2), 2) + 5
        
        # 综合
        final = min((ma_score / 9 * 6) + (trend_score / 10 * 4), 10)
        
        details = {
            "MA5": round(ma5, 3),
            "MA10": round(ma10, 3),
            "MA20": round(ma20, 3),
            "MA60": round(ma60, 3),
            "20日涨幅%": round(change_20, 2),
            "多头排列": ma5 > ma10 > ma20,
            "站上60日线": cur > ma60
        }
        
        return round(final, 2), details
    
    def _score_momentum(self, stock_data: StockData) -> Tuple[float, Dict]:
        """动量得分（0-10）"""
        close = stock_data.close
        high = stock_data.high if stock_data.high is not None else close
        low = stock_data.low if stock_data.low is not None else close
        
        # RSI
        rsi = self.calculate_rsi(close, 14)[-1]
        
        # MACD
        macd = self.calculate_macd(close)
        dif = macd["dif"][-1]
        hist = macd["hist"][-1]
        
        # KDJ
        k, d, j = self._calculate_kdj(high, low, close)
        
        # RSI得分
        if 45 <= rsi <= 70:
            rsi_score = 8 + (rsi - 45) / 25 * 2
        elif rsi < 30:
            rsi_score = 6
        elif rsi > 80:
            rsi_score = 3
        else:
            rsi_score = 5
        
        # MACD得分
        macd_score = 7 if hist > 0 else 4
        if dif > 0 and hist > macd["hist"][-2] if len(macd["hist"]) > 1 else hist > 0:
            macd_score += 2
        
        # KDJ得分
        kv, dv = k[-1], d[-1]
        if 20 <= kv <= 80 and kv > dv:
            kdj_score = 7
        elif kv < 20:
            kdj_score = 6
        else:
            kdj_score = 4
        
        final = rsi_score * 0.35 + macd_score * 0.40 + kdj_score * 0.25
        
        details = {
            "RSI14": round(rsi, 2) if not np.isnan(rsi) else None,
            "MACD_DIF": round(dif, 4) if not np.isnan(dif) else None,
            "MACD_柱": round(hist, 4) if not np.isnan(hist) else None,
            "KDJ_K": round(kv, 2) if not np.isnan(kv) else None,
            "KDJ_D": round(dv, 2) if not np.isnan(dv) else None
        }
        
        return round(final, 2), details
    
    def _score_volatility(self, stock_data: StockData) -> Tuple[float, Dict]:
        """波动/风险得分（0-10），分越高风险越低"""
        close = stock_data.close
        high = stock_data.high if stock_data.high is not None else close
        low = stock_data.low if stock_data.low is not None else close
        
        # ATR
        atr = self._calculate_atr(high, low, close)
        atr_pct = atr / close[-1] * 100 if close[-1] > 0 else 0
        
        # 20日波动率
        returns = pd.Series(close).pct_change().dropna()
        if len(returns) >= 20:
            vol_20 = returns.tail(20).std() * np.sqrt(252) * 100
        else:
            vol_20 = 0
        
        # 布林带位置
        boll = self.calculate_bollinger(close, 20, 2)
        upper, middle, lower = boll["upper"][-1], boll["middle"][-1], boll["lower"][-1]
        if upper > lower:
            boll_pct = (close[-1] - lower) / (upper - lower)
        else:
            boll_pct = 0.5
        
        # 波动得分
        if vol_20 < 20:
            vol_score = 8
        elif vol_20 < 35:
            vol_score = 6
        elif vol_20 < 50:
            vol_score = 4
        else:
            vol_score = 2
        
        # 布林带位置得分
        if 0.3 <= boll_pct <= 0.7:
            boll_score = 8
        elif boll_pct > 0.9:
            boll_score = 3
        elif boll_pct < 0.1:
            boll_score = 5
        else:
            boll_score = 6
        
        final = vol_score * 0.5 + boll_score * 0.5
        
        details = {
            "ATR": round(atr, 3),
            "ATR%": round(atr_pct, 2),
            "年化波动率%": round(vol_20, 2),
            "布林带位置": round(boll_pct, 3),
            "布林上轨": round(upper, 3),
            "布林中轨": round(middle, 3),
            "布林下轨": round(lower, 3)
        }
        
        return round(final, 2), details
    
    def _score_volume_price(self, stock_data: StockData) -> Tuple[float, Dict]:
        """量价关系得分（0-10）"""
        close = stock_data.close
        volume = stock_data.volume
        
        # OBV
        obv = self._calculate_obv(close, volume)
        obv_5ma = pd.Series(obv).rolling(5, min_periods=1).mean().values[-1]
        obv_up = obv[-1] > obv_5ma
        
        # 量比
        vol_3 = np.mean(volume[-3:])
        vol_20 = np.mean(volume[-20:])
        vol_ratio = vol_3 / (vol_20 + 1e-9)
        
        # 近期价量配合
        price_up = close[-1] > close[-5] if len(close) >= 5 else False
        vol_up = volume[-1] > volume[-5] if len(volume) >= 5 else False
        
        # PV得分
        if price_up and vol_up:
            pv_score = 9
        elif not price_up and not vol_up:
            pv_score = 5
        elif price_up and not vol_up:
            pv_score = 6
        else:
            pv_score = 7
        
        # 量比得分
        if 1.2 <= vol_ratio <= 2.5:
            vr_score = 8
        elif vol_ratio > 3:
            vr_score = 7
        elif vol_ratio < 0.5:
            vr_score = 4
        else:
            vr_score = 6
        
        obv_score = 8 if obv_up else 4
        
        final = pv_score * 0.4 + vr_score * 0.35 + obv_score * 0.25
        
        pv_status = "量价齐升" if (price_up and vol_up) else ("价涨量缩" if (price_up and not vol_up) else ("放量下跌" if (not price_up and vol_up) else "量价齐跌"))
        
        details = {
            "OBV方向": "上升" if obv_up else "下降",
            "量比(3d/20d)": round(vol_ratio, 2),
            "价量配合": pv_status,
            "当日成交量": f"{volume[-1]/10000:.1f}万手",
            "20日均量": f"{vol_20/10000:.1f}万手"
        }
        
        return round(final, 2), details
    
    def _score_fundamental(self, stock_data: StockData) -> Tuple[float, Dict]:
        """基本面得分（0-10）"""
        pe = stock_data.pe
        pb = stock_data.pb
        market_cap = stock_data.market_cap
        
        score = 5.0
        details = {}
        
        # PE评分
        if pe is not None and pe > 0:
            details["市盈率"] = round(pe, 2)
            if 0 < pe < 15:
                score += 2
                details["PE评价"] = "低估"
            elif 15 <= pe < 30:
                score += 1
                details["PE评价"] = "合理"
            elif pe > 60:
                score -= 1
                details["PE评价"] = "高估"
        
        # PB评分
        if pb is not None and pb > 0:
            details["市净率"] = round(pb, 2)
            if 0 < pb < 1.5:
                score += 1.5
            elif pb < 3:
                score += 0.5
        
        # 市值评分
        if market_cap is not None:
            details["市值(亿)"] = market_cap
            if market_cap > 1000:
                score += 0.5
        
        return round(min(score, 10), 2), details
    
    def _calculate_kdj(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                       n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """计算KDJ"""
        low_min = pd.Series(low).rolling(window=n, min_periods=1).min().values
        high_max = pd.Series(high).rolling(window=n, min_periods=1).max().values
        
        rsv = (close - low_min) / (high_max - low_min + 1e-9) * 100
        k = pd.Series(rsv).ewm(com=m1 - 1, adjust=False).mean().values
        d = pd.Series(k).ewm(com=m2 - 1, adjust=False).mean().values
        j = 3 * k - 2 * d
        
        return k, d, j
    
    def _calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
        """计算ATR"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        atr = pd.Series(tr).rolling(window=period, min_periods=1).mean().values[-1]
        
        return atr
    
    def _calculate_obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """计算OBV"""
        direction = np.sign(np.diff(close))
        direction = np.insert(direction, 0, 0)
        obv = np.cumsum(volume * direction)
        return obv
