#!/usr/bin/env python3
"""
四大选股战法模块

包含：
1. 锁仓K线策略 - 主力锁仓识别
2. 竞价弱转强 - 竞价异动捕捉
3. 利刃出鞘 - 洗盘完毕信号
4. 涨停版法 - 涨停后回调买点
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from .base import BaseStrategy, Signal, SignalType, StockData, StrategyType


class LockupKlineStrategy(BaseStrategy):
    """
    战法一：锁仓K线策略
    
    核心逻辑：成交量萎缩 + 股价横盘 = 主力锁仓
    适用场景：趋势确认阶段
    持仓周期：3-10天
    
    识别条件：
    1. 近5日成交量持续萎缩（每日成交量 < 前5日均量的60%）
    2. 近5日股价振幅 < 3%（横盘整理）
    3. 股价在20日均线上方
    4. MACD 在零轴上方
    """
    
    def get_name(self) -> str:
        return "锁仓K线策略"
    
    def get_description(self) -> str:
        return "成交量萎缩+股价横盘=主力锁仓，适用于趋势确认阶段"
    
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """分析锁仓K线信号"""
        if not self.validate_data(stock_data):
            return None
        
        close = stock_data.close
        volume = stock_data.volume
        
        # 取最近5日数据
        recent_close = close[-5:]
        recent_vol = volume[-5:]
        
        # 条件1：量能萎缩
        vol_ma5 = np.mean(volume[-10:-5])  # 前5日平均
        vol_shrink = all(v < vol_ma5 * 0.6 for v in recent_vol)
        
        # 条件2：横盘（近5日振幅 < 3%）
        amplitude = (np.max(recent_close) - np.min(recent_close)) / np.mean(recent_close)
        flat = amplitude < 0.03
        
        # 条件3：20日均线支撑
        ma20 = self.calculate_ma(close, 20)
        above_ma20 = close[-1] > ma20[-1]
        
        # 条件4：MACD零轴上方
        macd = self.calculate_macd(close)
        macd_above_zero = macd["dif"][-1] > 0
        
        # 综合判断
        conditions = {
            "量能萎缩": vol_shrink,
            "价格横盘": flat,
            "站上MA20": above_ma20,
            "MACD零轴上方": macd_above_zero
        }
        
        triggered = sum(conditions.values())
        
        if triggered >= 3:  # 至少满足3个条件
            current_price = close[-1]
            signal = Signal(
                code=stock_data.code,
                name=stock_data.name,
                strategy=self.name,
                strategy_type=StrategyType.LOCKUP_KLINE,
                signal_type=SignalType.BUY if triggered == 4 else SignalType.WATCH,
                current_price=current_price,
                entry_price=current_price,
                stop_loss=np.min(recent_close) * 0.97,
                target_price=current_price * 1.10,
                score=7.5 if triggered == 4 else 6.5,
                confidence=0.82 if triggered == 4 else 0.65,
                holding_days="3-10天",
                details={
                    "量能收缩": vol_shrink,
                    "价格横盘": flat,
                    "振幅%": round(amplitude * 100, 2),
                    "MA20支撑": above_ma20,
                    "MACD零轴上方": macd_above_zero,
                    "触发条件数": triggered
                },
                signals=conditions
            )
            return signal
        
        return None


class WeakToStrongStrategy(BaseStrategy):
    """
    战法二：竞价弱转强
    
    核心逻辑：前日弱势 + 竞价巨量高开 = 主力做多
    适用场景：连板断板、情绪回流
    持仓周期：T+0 / T+1
    
    识别条件：
    1. 前日收盘涨幅 < 0%（弱势）
    2. 今日竞价额 > 前日总成交额 5%（主力异动）
    3. 竞价涨幅 > 2%（高开）
    4. 开盘后 30 分钟内封板或涨幅 > 5%
    
    注：此策略需要竞价数据，日线数据模拟时仅作参考
    """
    
    def get_name(self) -> str:
        return "竞价弱转强"
    
    def get_description(self) -> str:
        return "前日弱势+竞价巨量高开=主力做多，适用于连板断板"
    
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """分析竞价弱转强信号"""
        if not self.validate_data(stock_data):
            return None
        
        close = stock_data.close
        volume = stock_data.volume
        
        # 需要至少2天数据
        if len(close) < 2:
            return None
        
        # 前日数据（模拟竞价分析）
        prev_close = close[-2]
        curr_close = close[-1]
        prev_volume = volume[-2]
        
        # 条件1：前日弱势（涨幅<0%）
        prev_change = (close[-1] - close[-2]) / close[-2] * 100  # 实际应为当日涨幅
        # 修正：用前两日计算
        if len(close) >= 3:
            prev_change = (close[-2] - close[-3]) / close[-3] * 100
        else:
            prev_change = 0
        
        prev_weak = prev_change < 0
        
        # 条件2：今日强势（涨幅>2%）
        curr_change = (curr_close - prev_close) / prev_close * 100
        strong_today = curr_change > 2.0
        
        # 条件3：量能异动（今日量/前5日量比）
        vol_ratio = volume[-1] / (np.mean(volume[-6:-1]) + 1e-10)
        volume_surge = vol_ratio > 1.5
        
        # 条件4：高开确认（使用日内高低价判断）
        if stock_data.high is not None and stock_data.low is not None:
            high_open = (stock_data.high[-1] - prev_close) / prev_close * 100 > 2.0
        else:
            high_open = curr_change > 2.0
        
        conditions = {
            "前日弱势": prev_weak,
            "今日强势": strong_today,
            "量能异动": volume_surge,
            "高开确认": high_open
        }
        
        triggered = sum(conditions.values())
        
        if triggered >= 3:
            current_price = close[-1]
            signal = Signal(
                code=stock_data.code,
                name=stock_data.name,
                strategy=self.name,
                strategy_type=StrategyType.WEAK_TO_STRONG,
                signal_type=SignalType.STRONG_BUY if triggered == 4 else SignalType.BUY,
                current_price=current_price,
                entry_price=current_price,
                stop_loss=prev_close * 0.98,
                target_price=current_price * 1.05,
                score=8.0 if triggered == 4 else 7.0,
                confidence=0.78 if triggered == 4 else 0.65,
                holding_days="T+0/T+1",
                details={
                    "前日涨幅%": round(prev_change, 2),
                    "今日涨幅%": round(curr_change, 2),
                    "量比": round(vol_ratio, 2),
                    "触发条件数": triggered
                },
                signals=conditions
            )
            return signal
        
        return None


class BladeOutStrategy(BaseStrategy):
    """
    战法三：利刃出鞘
    
    核心逻辑：倍量阴 + 创新高长上影 = 洗盘完毕
    适用场景：涨停后判断洗盘/出货
    持仓周期：3-10天
    
    识别条件：
    1. 昨日涨停，今日出现长上影线（上影线 > 实体的2倍）
    2. 今日成交量是昨日1.5倍以上（倍量）
    3. 收盘价未跌破涨停日实体中点
    4. 股价创N日新高（N = 参数，默认20）
    """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.lookback_days = config.get("lookback_days", 20) if config else 20
    
    def get_name(self) -> str:
        return "利刃出鞘"
    
    def get_description(self) -> str:
        return "倍量阴+创新高长上影=洗盘完毕，适用于涨停后判断"
    
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """分析利刃出鞘信号"""
        if not self.validate_data(stock_data):
            return None
        
        # 需要至少20天数据
        if len(stock_data.close) < self.lookback_days + 5:
            return None
        
        close = stock_data.close
        high = stock_data.high if stock_data.high is not None else close
        low = stock_data.low if stock_data.low is not None else close
        volume = stock_data.volume
        
        # 找最近N日的涨停日（涨幅>=9.8%）
        returns = np.diff(close) / close[:-1] * 100
        limit_up_mask = returns >= 9.8
        
        if not np.any(limit_up_mask):
            return None
        
        # 找最近的一个涨停日
        limit_up_indices = np.where(limit_up_mask)[0]
        if len(limit_up_indices) == 0:
            return None
        
        limit_idx = limit_up_indices[-1]  # 最近涨停日索引
        
        # 条件1：今日有长上影线（需要OHLC数据）
        today_idx = -1
        if stock_data.open is not None:
            today_open = stock_data.open[today_idx]
            today_high = high[today_idx]
            today_close = close[today_idx]
            
            body = abs(today_close - today_open)
            upper_shadow = today_high - max(today_open, today_close)
            long_shadow = upper_shadow > body * 2 if body > 0 else False
        else:
            long_shadow = False
        
        # 条件2：倍量
        double_vol = volume[today_idx] > volume[today_idx - 1] * 1.5
        
        # 条件3：未跌破涨停日实体中点
        if stock_data.open is not None:
            limit_open = stock_data.open[limit_idx]
            limit_close = close[limit_idx]
            limit_mid = (limit_open + limit_close) / 2
            not_broken = close[today_idx] > limit_mid
        else:
            not_broken = True
        
        # 条件4：创N日新高
        new_high = close[today_idx] >= np.max(close[-self.lookback_days:]) * 0.97
        
        conditions = {
            "长上影线": long_shadow,
            "倍量": double_vol,
            "未跌破中点": not_broken,
            "接近新高": new_high
        }
        
        triggered = sum(conditions.values())
        
        if triggered >= 3:
            current_price = close[-1]
            signal = Signal(
                code=stock_data.code,
                name=stock_data.name,
                strategy=self.name,
                strategy_type=StrategyType.BLADE_OUT,
                signal_type=SignalType.BUY,
                current_price=current_price,
                entry_price=current_price,
                stop_loss=close[limit_idx] * 0.97 if limit_idx >= 0 else current_price * 0.95,
                target_price=current_price * 1.15,
                score=7.5 if triggered == 4 else 6.5,
                confidence=0.75 if triggered == 4 else 0.60,
                holding_days="3-10天",
                details={
                    "涨停日距今天数": len(close) - limit_idx - 1,
                    "上影线比例": round(upper_shadow / body, 2) if body > 0 else None,
                    "量比": round(volume[today_idx] / volume[today_idx - 1], 2),
                    "触发条件数": triggered
                },
                signals=conditions
            )
            return signal
        
        return None


class LimitUpStrategy(BaseStrategy):
    """
    战法四：涨停版法
    
    核心逻辑：涨停后缩量回踩 + 均线支撑 = 安全低吸点
    适用场景：涨停后找安全买点
    持仓周期：3-8天
    
    识别条件：
    1. N日前涨停（N = 1~5）
    2. 涨停后缩量调整（成交量 < 涨停日70%）
    3. 回踩20日或10日均线企稳
    4. 企稳后放量阳线确认
    """
    
    def get_name(self) -> str:
        return "涨停版法"
    
    def get_description(self) -> str:
        return "涨停后缩量回踩+均线支撑=安全低吸点"
    
    def analyze(self, stock_data: StockData) -> Optional[Signal]:
        """分析涨停版法信号"""
        if not self.validate_data(stock_data):
            return None
        
        close = stock_data.close
        volume = stock_data.volume
        
        if len(close) < 30:
            return None
        
        # 找最近5日内的涨停日
        returns = np.diff(close) / close[:-1] * 100
        
        limit_up_found = False
        limit_idx = -1
        
        for i in range(-5, 0):
            if i < len(returns) and returns[i] >= 9.8:
                limit_up_found = True
                limit_idx = i
                break
        
        if not limit_up_found:
            return None
        
        # 条件2：涨停后缩量
        post_limit_volume = volume[limit_idx + 1:]
        limit_volume = volume[limit_idx]
        
        if len(post_limit_volume) > 0:
            volume_shrink = np.mean(post_limit_volume) < limit_volume * 0.7
        else:
            volume_shrink = False
        
        # 条件3：回踩均线企稳
        ma10 = self.calculate_ma(close, 10)
        ma20 = self.calculate_ma(close, 20)
        
        current_price = close[-1]
        near_ma10 = abs(current_price - ma10[-1]) / ma10[-1] < 0.03
        near_ma20 = abs(current_price - ma20[-1]) / ma20[-1] < 0.03
        
        # 均线支撑
        ma_support = near_ma10 or near_ma20
        
        # 条件4：企稳确认（今日涨幅>0）
        today_rise = returns[-1] > 0 if len(returns) > 0 else False
        
        conditions = {
            "近期涨停": limit_up_found,
            "缩量调整": volume_shrink,
            "均线支撑": ma_support,
            "企稳阳线": today_rise
        }
        
        triggered = sum(conditions.values())
        
        if triggered >= 3:
            signal = Signal(
                code=stock_data.code,
                name=stock_data.name,
                strategy=self.name,
                strategy_type=StrategyType.LIMIT_UP,
                signal_type=SignalType.BUY if triggered == 4 else SignalType.WATCH,
                current_price=current_price,
                entry_price=current_price,
                stop_loss=ma20[-1] * 0.97,
                target_price=current_price * 1.08,
                score=7.5 if triggered == 4 else 6.5,
                confidence=0.70 if triggered == 4 else 0.55,
                holding_days="3-8天",
                details={
                    "涨停日距今天数": abs(limit_idx),
                    "缩量比例": round(np.mean(post_limit_volume) / limit_volume, 2) if len(post_limit_volume) > 0 else None,
                    "距MA10": round(abs(current_price - ma10[-1]) / ma10[-1] * 100, 2),
                    "距MA20": round(abs(current_price - ma20[-1]) / ma20[-1] * 100, 2),
                    "触发条件数": triggered
                },
                signals=conditions
            )
            return signal
        
        return None
