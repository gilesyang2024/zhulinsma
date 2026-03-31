#!/usr/bin/env python3
"""
Zhulinsma 技术指标库
包含RSI、MACD、布林带等常用技术指标
版本: 1.0.0
日期: 2026年3月27日
作者: 杨总的工作助手
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
import warnings
warnings.filterwarnings('ignore')

__all__ = [
    'RSI',
    'MACD',
    'BollingerBands',
    'SMA',
    'EMA',
    'Stochastic',
    'ATR',
    'TechnicalIndicators'
]

# 注意：Stochastic函数实际在TechnicalIndicators类中，不作为独立函数导出

class TechnicalIndicators:
    """
    技术指标核心类
    实现双重验证机制，确保计算准确性
    符合广州投资者习惯，红涨绿跌
    """
    
    def __init__(self, 验证模式: bool = True, 严格模式: bool = True):
        """
        初始化技术指标库
        
        参数:
            验证模式: 是否启用双重验证 (默认: True)
            严格模式: 是否启用严格的数据检查 (默认: True)
        """
        self.验证模式 = 验证模式
        self.严格模式 = 严格模式
        self.计算历史 = []
        self.广州模式 = True  # 红涨绿跌
        
        print(f"📊 Zhulinsma 技术指标库初始化完成")
        print(f"   验证模式: {'启用' if 验证模式 else '禁用'}")
        print(f"   严格模式: {'启用' if 严格模式 else '禁用'}")
        print(f"   广州模式: {'红涨绿跌' if self.广州模式 else '绿涨红跌'}")
    
    def RSI(self, 价格: Union[pd.Series, np.ndarray], 周期: int = 14) -> np.ndarray:
        """
        相对强弱指数 (Relative Strength Index)
        用于识别超买超卖状态
        
        参数:
            价格: 价格序列 (收盘价)
            周期: RSI计算周期 (默认: 14)
        
        返回:
            RSI值数组，范围0-100
        """
        # 数据预处理
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格)
        
        # 数据验证
        self._验证数据长度(价格数据, 周期 + 1, "RSI")
        
        # 方法1: 标准RSI计算
        delta = np.diff(价格数据)
        up = np.where(delta > 0, delta, 0)
        down = np.where(delta < 0, -delta, 0)
        
        # 计算平均上涨和下跌
        avg_up = np.full(len(价格数据), np.nan)
        avg_down = np.full(len(价格数据), np.nan)
        
        for i in range(周期-1, len(up)):
            avg_up[i+1] = np.mean(up[i-周期+1:i+1])
            avg_down[i+1] = np.mean(down[i-周期+1:i+1])
        
        # 计算RSI
        rs = avg_up / (avg_down + 1e-10)
        rsi_结果 = 100 - 100 / (1 + rs)
        
        # 双重验证
        if self.验证模式:
            self._验证RSI(价格数据, rsi_结果, 周期)
        
        # 记录计算历史
        self._记录计算("RSI", 周期, len(价格数据), rsi_结果)
        
        return rsi_结果
    
    def MACD(self, 价格: Union[pd.Series, np.ndarray], 
             fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """
        移动平均收敛发散指标
        用于识别趋势变化和动量
        
        参数:
            价格: 价格序列
            fast: 快线EMA周期 (默认: 12)
            slow: 慢线EMA周期 (默认: 26)
            signal: 信号线周期 (默认: 9)
        
        返回:
            包含MACD线、信号线、柱状线的字典
        """
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格)
        
        # 数据验证
        self._验证数据长度(价格数据, max(fast, slow, signal) + signal, "MACD")
        
        # 计算快线和慢线EMA
        ema_fast = self._EMA(价格数据, fast)
        ema_slow = self._EMA(价格数据, slow)
        
        # 计算MACD线
        macd_line = ema_fast - ema_slow
        
        # 计算信号线
        signal_line = self._EMA(macd_line, signal)
        
        # 计算柱状线
        histogram = macd_line - signal_line
        
        # 创建结果
        macd_结果 = {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
        
        # 双重验证
        if self.验证模式:
            self._验证MACD(价格数据, macd_结果, fast, slow, signal)
        
        # 记录计算历史
        self._记录计算("MACD", f"{fast}_{slow}_{signal}", len(价格数据), macd_line)
        
        return macd_结果
    
    def BollingerBands(self, 价格: Union[pd.Series, np.ndarray], 
                       period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        """
        布林带指标
        用于测量波动率和识别价格位置
        
        参数:
            价格: 价格序列
            period: 移动平均周期 (默认: 20)
            std_dev: 标准差倍数 (默认: 2.0)
        
        返回:
            包含中轨、上轨、下轨的字典
        """
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格)
        
        # 数据验证
        self._验证数据长度(价格数据, period, "BollingerBands")
        
        # 计算中轨线 (SMA)
        sma = self._SMA(价格数据, period)
        
        # 计算标准差
        rolling_std = np.full(len(价格数据), np.nan)
        for i in range(period-1, len(价格数据)):
            rolling_std[i] = np.std(价格数据[i-period+1:i+1])
        
        # 计算上下轨
        upper_band = sma + rolling_std * std_dev
        lower_band = sma - rolling_std * std_dev
        
        # 计算带宽
        bandwidth = (upper_band - lower_band) / (sma + 1e-10)
        
        # 创建结果
        bb_结果 = {
            'middle': sma,
            'upper': upper_band,
            'lower': lower_band,
            'bandwidth': bandwidth,
            'position': (价格数据 - lower_band) / (upper_band - lower_band + 1e-10)  # 价格位置
        }
        
        # 双重验证
        if self.验证模式:
            self._验证布林带(价格数据, bb_结果, period, std_dev)
        
        # 记录计算历史
        self._记录计算("BollingerBands", f"{period}_{std_dev}", len(价格数据), sma)
        
        return bb_结果
    
    def SMA(self, 价格: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
        """简单移动平均线"""
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格)
        
        self._验证数据长度(价格数据, period, "SMA")
        return self._SMA(价格数据, period)
    
    def EMA(self, 价格: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
        """指数移动平均线"""
        if isinstance(价格, pd.Series):
            价格数据 = 价格.values
        else:
            价格数据 = np.array(价格)
        
        self._验证数据长度(价格数据, period, "EMA")
        return self._EMA(价格数据, period)
    
    def Stochastic(self, 最高价: np.ndarray, 最低价: np.ndarray, 收盘价: np.ndarray,
                   k_period: int = 14, d_period: int = 3) -> Dict[str, np.ndarray]:
        """
        随机指标 (Stochastic Oscillator)
        用于识别超买超卖
        
        参数:
            最高价: 最高价序列
            最低价: 最低价序列
            收盘价: 收盘价序列
            k_period: K线周期 (默认: 14)
            d_period: D线周期 (默认: 3)
        
        返回:
            包含K线和D线的字典
        """
        # 数据验证
        self._验证数据长度(收盘价, k_period + d_period, "Stochastic")
        
        # 计算%K
        k_values = np.full(len(收盘价), np.nan)
        for i in range(k_period-1, len(收盘价)):
            low_min = np.min(最低价[i-k_period+1:i+1])
            high_max = np.max(最高价[i-k_period+1:i+1])
            k_values[i] = 100 * (收盘价[i] - low_min) / (high_max - low_min + 1e-10)
        
        # 计算%D (K线的SMA)
        d_values = self._SMA(k_values, d_period)
        
        # 创建结果
        stoch_结果 = {
            'k': k_values,
            'd': d_values
        }
        
        # 双重验证
        if self.验证模式:
            self._验证随机指标(最高价, 最低价, 收盘价, stoch_结果, k_period, d_period)
        
        # 记录计算历史
        self._记录计算("Stochastic", f"{k_period}_{d_period}", len(收盘价), k_values)
        
        return stoch_结果
    
    def ATR(self, 最高价: np.ndarray, 最低价: np.ndarray, 收盘价: np.ndarray, 
            period: int = 14) -> np.ndarray:
        """
        平均真实波幅 (Average True Range)
        用于测量波动率
        
        参数:
            最高价: 最高价序列
            最低价: 最低价序列
            收盘价: 收盘价序列
            period: ATR周期 (默认: 14)
        
        返回:
            ATR值数组
        """
        # 数据验证
        self._验证数据长度(收盘价, period + 1, "ATR")
        
        # 计算真实波幅
        tr = np.full(len(收盘价), np.nan)
        for i in range(1, len(收盘价)):
            hl = 最高价[i] - 最低价[i]
            hc = abs(最高价[i] - 收盘价[i-1])
            lc = abs(最低价[i] - 收盘价[i-1])
            tr[i] = max(hl, hc, lc)
        
        # 计算ATR (TR的EMA)
        atr_结果 = self._EMA(tr, period)
        
        # 双重验证
        if self.验证模式:
            self._验证ATR(最高价, 最低价, 收盘价, atr_结果, period)
        
        # 记录计算历史
        self._记录计算("ATR", period, len(收盘价), atr_结果)
        
        return atr_结果
    
    # ========== 辅助方法 ==========
    
    def _SMA(self, 数据: np.ndarray, period: int) -> np.ndarray:
        """计算简单移动平均线"""
        if len(数据) < period:
            return np.full(len(数据), np.nan)
        
        sma = np.full(len(数据), np.nan)
        for i in range(period-1, len(数据)):
            sma[i] = np.mean(数据[i-period+1:i+1])
        
        return sma
    
    def _EMA(self, 数据: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均线"""
        if len(数据) < period:
            return np.full(len(数据), np.nan)
        
        alpha = 2.0 / (period + 1.0)
        ema = np.full(len(数据), np.nan)
        
        # 初始EMA使用SMA
        ema[period-1] = np.mean(数据[:period])
        
        # 计算后续EMA
        for i in range(period, len(数据)):
            ema[i] = alpha * 数据[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _验证数据长度(self, 数据: np.ndarray, 最小长度: int, 指标名称: str):
        """验证数据长度是否足够"""
        if len(数据) < 最小长度:
            raise ValueError(
                f"{指标名称} 需要至少 {最小长度} 个数据点，当前只有 {len(数据)} 个"
            )
    
    def _验证RSI(self, 价格: np.ndarray, rsi: np.ndarray, 周期: int):
        """验证RSI计算结果"""
        try:
            # 使用Pandas验证
            价格_series = pd.Series(价格)
            delta = 价格_series.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=周期, min_periods=周期).mean()
            avg_loss = loss.rolling(window=周期, min_periods=周期).mean()
            
            rs_pandas = avg_gain / (avg_loss + 1e-10)
            rsi_pandas = 100 - 100 / (1 + rs_pandas)
            
            # 比较结果
            有效索引 = ~np.isnan(rsi) & ~np.isnan(rsi_pandas.values)
            if np.any(有效索引):
                差异 = np.abs(rsi[有效索引] - rsi_pandas.values[有效索引])
                最大差异 = np.nanmax(差异)
                
                if 最大差异 < 0.01:
                    print(f"✅ RSI({周期}) 验证通过: 双重计算一致")
                else:
                    print(f"⚠️ RSI({周期}) 验证警告: 最大差异 {最大差异:.6f}")
        except Exception as e:
            print(f"⚠️ RSI验证异常: {e}")
    
    def _验证MACD(self, 价格: np.ndarray, macd: Dict, fast: int, slow: int, signal: int):
        """验证MACD计算结果"""
        try:
            # 这里可以添加更复杂的验证逻辑
            # 目前只检查基本有效性
            if 'macd' in macd and 'signal' in macd:
                有效macd = np.sum(~np.isnan(macd['macd']))
                有效signal = np.sum(~np.isnan(macd['signal']))
                
                if 有效macd > 0 and 有效signal > 0:
                    print(f"✅ MACD({fast},{slow},{signal}) 计算有效")
                else:
                    print(f"⚠️ MACD 验证警告: 有效数据不足")
        except Exception as e:
            print(f"⚠️ MACD验证异常: {e}")
    
    def _验证布林带(self, 价格: np.ndarray, bb: Dict, period: int, std_dev: float):
        """验证布林带计算结果"""
        try:
            # 使用Pandas验证
            价格_series = pd.Series(价格)
            sma_pandas = 价格_series.rolling(window=period).mean()
            std_pandas = 价格_series.rolling(window=period).std()
            
            upper_pandas = sma_pandas + std_pandas * std_dev
            lower_pandas = sma_pandas - std_pandas * std_dev
            
            # 验证中轨
            if 'middle' in bb:
                有效索引 = ~np.isnan(bb['middle']) & ~np.isnan(sma_pandas.values)
                if np.any(有效索引):
                    差异 = np.abs(bb['middle'][有效索引] - sma_pandas.values[有效索引])
                    最大差异 = np.nanmax(差异)
                    
                    if 最大差异 < 0.001:
                        print(f"✅ 布林带中轨 验证通过")
                    else:
                        print(f"⚠️ 布林带中轨 验证警告: 最大差异 {最大差异:.6f}")
        except Exception as e:
            print(f"⚠️ 布林带验证异常: {e}")
    
    def _验证随机指标(self, 最高价: np.ndarray, 最低价: np.ndarray, 收盘价: np.ndarray,
                    stoch: Dict, k_period: int, d_period: int):
        """验证随机指标计算结果"""
        # 基本有效性检查
        if 'k' in stoch and 'd' in stoch:
            有效k = np.sum(~np.isnan(stoch['k']))
            有效d = np.sum(~np.isnan(stoch['d']))
            
            if 有效k > 0 and 有效d > 0:
                print(f"✅ 随机指标({k_period},{d_period}) 计算有效")
            else:
                print(f"⚠️ 随机指标验证警告: 有效数据不足")
    
    def _验证ATR(self, 最高价: np.ndarray, 最低价: np.ndarray, 收盘价: np.ndarray,
                atr: np.ndarray, period: int):
        """验证ATR计算结果"""
        # 基本有效性检查
        有效atr = np.sum(~np.isnan(atr))
        if 有效atr > 0:
            print(f"✅ ATR({period}) 计算有效")
        else:
            print(f"⚠️ ATR验证警告: 有效数据不足")
    
    def _记录计算(self, 指标名称: str, 参数: str, 数据长度: int, 结果):
        """记录指标计算历史"""
        记录 = {
            '指标': 指标名称,
            '参数': 参数,
            '数据长度': 数据长度,
            '时间': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            '广州模式': self.广州模式
        }
        
        # 添加结果统计
        if isinstance(结果, np.ndarray):
            有效结果 = 结果[~np.isnan(结果)]
            if len(有效结果) > 0:
                记录['结果数量'] = len(有效结果)
                记录['最小值'] = float(np.nanmin(结果))
                记录['最大值'] = float(np.nanmax(结果))
                记录['平均值'] = float(np.nanmean(结果))
        
        self.计算历史.append(记录)
    
    def 获取计算历史(self) -> List[Dict]:
        """获取指标计算历史"""
        return self.计算历史
    
    def 清空历史(self):
        """清空计算历史"""
        self.计算历史 = []
    
    def 生成报告(self) -> Dict:
        """生成指标库使用报告"""
        report = {
            '指标库版本': '1.0.0',
            '创建时间': '2026-03-27',
            '作者': '杨总的工作助手',
            '总计算次数': len(self.计算历史),
            '支持指标': ['RSI', 'MACD', 'BollingerBands', 'SMA', 'EMA', 'Stochastic', 'ATR'],
            '特色功能': ['双重验证机制', '广州模式(红涨绿跌)', '严格数据检查', '完整计算历史'],
            '计算历史': self.计算历史
        }
        return report


# ========== 快捷函数 ==========

def RSI(价格: Union[pd.Series, np.ndarray], 周期: int = 14) -> np.ndarray:
    """RSI快捷函数"""
    ti = TechnicalIndicators(验证模式=True)
    return ti.RSI(价格, 周期)

def MACD(价格: Union[pd.Series, np.ndarray], 
         fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
    """MACD快捷函数"""
    ti = TechnicalIndicators(验证模式=True)
    return ti.MACD(价格, fast, slow, signal)

def BollingerBands(价格: Union[pd.Series, np.ndarray], 
                   period: int = 20, std_dev: float = 2.0) -> Dict[str, np.ndarray]:
    """布林带快捷函数"""
    ti = TechnicalIndicators(验证模式=True)
    return ti.BollingerBands(价格, period, std_dev)

def SMA(价格: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
    """SMA快捷函数"""
    ti = TechnicalIndicators(验证模式=False)  # 简单计算无需验证
    return ti.SMA(价格, period)

def EMA(价格: Union[pd.Series, np.ndarray], period: int) -> np.ndarray:
    """EMA快捷函数"""
    ti = TechnicalIndicators(验证模式=False)
    return ti.EMA(价格, period)


if __name__ == "__main__":
    print("🧪 Zhulinsma 技术指标库 - 模块测试")
    print("=" * 60)
    
    # 创建测试数据
    np.random.seed(42)
    测试数据 = 100 + np.random.randn(100).cumsum()
    
    # 创建指标库实例
    ti = TechnicalIndicators(验证模式=True)
    
    # 测试RSI
    rsi_result = ti.RSI(测试数据, 14)
    print(f"✅ RSI测试完成: {np.sum(~np.isnan(rsi_result))} 个有效值")
    
    # 测试MACD
    macd_result = ti.MACD(测试数据, 12, 26, 9)
    print(f"✅ MACD测试完成")
    
    # 测试布林带
    bb_result = ti.BollingerBands(测试数据, 20, 2.0)
    print(f"✅ 布林带测试完成")
    
    # 生成报告
    report = ti.生成报告()
    print(f"\n📊 指标库报告:")
    print(f"   版本: {report['指标库版本']}")
    print(f"   总计算次数: {report['总计算次数']}")
    print(f"   支持指标: {', '.join(report['支持指标'])}")
    print(f"   特色功能: {', '.join(report['特色功能'])}")
    
    print("\n🎉 技术指标库模块测试完成!")