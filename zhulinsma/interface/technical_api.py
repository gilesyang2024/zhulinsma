#!/usr/bin/env python3
"""
TechnicalAPI - 核心技术分析API模块

为竹林司马的核心技术分析功能提供标准API接口，
包括移动平均线、RSI、MACD、布林带等常用技术指标。

特性：
- 支持批量技术指标计算
- 双重验证机制确保计算准确性
- 统一错误处理和日志记录
- JSON格式返回，便于集成
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Union, Optional, Any

# 导入竹林司马核心工具
import sys
import os
# 上溯到项目根目录: interface/ → zhulinsma/ → zhulinsma/ (项目根)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
try:
    from zhulinsma_tool import 竹林司马
    from zhulinsma_tool_v2 import 竹林司马V2
    HAS_CORE_TOOLS = True
except ImportError:
    HAS_CORE_TOOLS = False


class TechnicalAPI:
    """
    核心技术分析API类
    
    提供标准化的技术指标计算接口，支持外部系统调用。
    所有接口返回JSON格式数据，便于集成和解析。
    """
    
    def __init__(self, 验证模式: bool = True, 使用V2: bool = True):
        """
        初始化TechnicalAPI
        
        参数:
            验证模式: 是否启用双重验证 (默认: True)
            使用V2: 是否使用V2版本的高级功能 (默认: True)
        """
        if not HAS_CORE_TOOLS:
            raise ImportError("无法导入竹林司马核心工具模块，请确保zhulinsma_tool.py存在")
        
        self.验证模式 = 验证模式
        self.使用V2 = 使用V2
        
        # 初始化核心工具
        self.工具 = 竹林司马(验证模式=验证模式)
        if 使用V2:
            self.工具V2 = 竹林司马V2(验证模式=验证模式)
        
        self.日志 = []
        self.初始化时间 = datetime.now()
        
        self._记录日志("初始化", f"TechnicalAPI初始化完成，验证模式={验证模式}，使用V2={使用V2}")
    
    def _记录日志(self, 操作: str, 详情: str):
        """记录API调用日志"""
        日志项 = {
            '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '操作': 操作,
            '详情': 详情,
            '时间戳': datetime.now().timestamp()
        }
        self.日志.append(日志项)
        # 只保留最近100条日志
        if len(self.日志) > 100:
            self.日志 = self.日志[-100:]
    
    def _构造响应(self, 成功: bool, 数据: Any, 消息: str = "", 错误码: int = 0) -> Dict:
        """
        构造标准API响应
        
        参数:
            成功: 操作是否成功
            数据: 返回的数据
            消息: 附加消息
            错误码: 错误代码 (0表示成功)
            
        返回:
            标准化响应字典
        """
        响应 = {
            '成功': 成功,
            '时间戳': datetime.now().timestamp(),
            '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '数据': 数据,
            '消息': 消息,
            '错误码': 错误码
        }
        
        if not 成功:
            响应['状态'] = '错误'
        else:
            响应['状态'] = '成功'
        
        return 响应
    
    # ============ 基础技术指标API ============
    
    def 计算SMA(self, 价格数据: List[float], 周期: int = 20) -> Dict:
        """
        计算简单移动平均线
        
        参数:
            价格数据: 价格序列列表
            周期: 移动平均周期 (默认: 20)
            
        返回:
            包含SMA计算结果的标准化响应
        """
        try:
            self._记录日志("计算SMA", f"周期={周期}，数据长度={len(价格数据)}")
            
            # 转换为numpy数组
            价格数组 = np.array(价格数据, dtype=np.float64)
            
            # 计算SMA
            sma结果 = self.工具.SMA(价格数组, 周期=周期, 验证=self.验证模式)
            
            # 转换为Python列表以便JSON序列化
            sma列表 = [float(x) if not np.isnan(x) else None for x in sma结果]
            
            响应数据 = {
                '指标名称': 'SMA',
                '计算周期': 周期,
                '输入数据长度': len(价格数据),
                '输出数据长度': len(sma列表),
                '有效值数量': sum(1 for x in sma列表 if x is not None),
                '最新值': sma列表[-1] if len(sma列表) > 0 else None,
                '完整序列': sma列表
            }
            
            return self._构造响应(True, 响应数据, f"SMA计算完成，周期={周期}")
            
        except Exception as e:
            self._记录日志("计算SMA错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"SMA计算失败: {str(e)}", 错误码=1001)
    
    def 计算EMA(self, 价格数据: List[float], 周期: int = 12) -> Dict:
        """
        计算指数移动平均线
        
        参数:
            价格数据: 价格序列列表
            周期: EMA周期 (默认: 12)
            
        返回:
            包含EMA计算结果的标准化响应
        """
        try:
            self._记录日志("计算EMA", f"周期={周期}，数据长度={len(价格数据)}")
            
            价格数组 = np.array(价格数据, dtype=np.float64)
            
            # 计算EMA
            ema结果 = self.工具.EMA(价格数组, 周期=周期)
            
            # 转换为Python列表
            ema列表 = [float(x) for x in ema结果]
            
            响应数据 = {
                '指标名称': 'EMA',
                '计算周期': 周期,
                '输入数据长度': len(价格数据),
                '输出数据长度': len(ema列表),
                '最新值': ema列表[-1] if len(ema列表) > 0 else None,
                '完整序列': ema列表
            }
            
            return self._构造响应(True, 响应数据, f"EMA计算完成，周期={周期}")
            
        except Exception as e:
            self._记录日志("计算EMA错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"EMA计算失败: {str(e)}", 错误码=1002)
    
    def 计算RSI(self, 价格数据: List[float], 周期: int = 14) -> Dict:
        """
        计算相对强弱指数
        
        参数:
            价格数据: 价格序列列表
            周期: RSI计算周期 (默认: 14)
            
        返回:
            包含RSI计算结果的标准化响应
        """
        try:
            if not self.使用V2:
                return self._构造响应(False, None, "RSI计算需要V2版本", 错误码=1003)
            
            self._记录日志("计算RSI", f"周期={周期}，数据长度={len(价格数据)}")
            
            价格数组 = np.array(价格数据, dtype=np.float64)
            
            # 使用V2版本的RSI计算
            rsi结果 = self.工具V2.RSI(价格数组, 周期=周期, 验证=self.验证模式)
            
            # 转换为Python列表
            rsi列表 = [float(x) if not np.isnan(x) else None for x in rsi结果]
            
            响应数据 = {
                '指标名称': 'RSI',
                '计算周期': 周期,
                '输入数据长度': len(价格数据),
                '输出数据长度': len(rsi列表),
                '有效值数量': sum(1 for x in rsi列表 if x is not None),
                '最新值': rsi列表[-1] if len(rsi列表) > 0 else None,
                '超买阈值': 70,
                '超卖阈值': 30,
                '当前状态': self._分析RSI状态(rsi列表[-1]) if rsi列表[-1] is not None else '未知',
                '完整序列': rsi列表
            }
            
            return self._构造响应(True, 响应数据, f"RSI计算完成，周期={周期}")
            
        except Exception as e:
            self._记录日志("计算RSI错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"RSI计算失败: {str(e)}", 错误码=1003)
    
    def _分析RSI状态(self, rsi值: float) -> str:
        """分析RSI值的状态"""
        if rsi值 >= 70:
            return '超买'
        elif rsi值 <= 30:
            return '超卖'
        elif 30 < rsi值 < 40:
            return '偏弱'
        elif 60 < rsi值 < 70:
            return '偏强'
        else:
            return '中性'
    
    def 计算MACD(self, 价格数据: List[float], 
                 fast_period: int = 12, 
                 slow_period: int = 26, 
                 signal_period: int = 9) -> Dict:
        """
        计算MACD指标
        
        参数:
            价格数据: 价格序列列表
            fast_period: 快速EMA周期 (默认: 12)
            slow_period: 慢速EMA周期 (默认: 26)
            signal_period: 信号线周期 (默认: 9)
            
        返回:
            包含MACD计算结果的标准化响应
        """
        try:
            if not self.使用V2:
                return self._构造响应(False, None, "MACD计算需要V2版本", 错误码=1004)
            
            self._记录日志("计算MACD", f"fast={fast_period}, slow={slow_period}, signal={signal_period}")
            
            价格数组 = np.array(价格数据, dtype=np.float64)
            
            # 使用V2版本的MACD计算
            macd线, 信号线, 柱状图 = self.工具V2.MACD(
                价格数组, 
                fast_period=fast_period,
                slow_period=slow_period,
                signal_period=signal_period,
                验证=self.验证模式
            )
            
            # 转换为Python列表
            macd列表 = [float(x) for x in macd线]
            信号列表 = [float(x) for x in 信号线]
            柱状列表 = [float(x) for x in 柱状图]
            
            # 分析MACD信号
            最新MACD = macd列表[-1] if len(macd列表) > 0 else None
            最新信号 = 信号列表[-1] if len(信号列表) > 0 else None
            最新柱状 = 柱状列表[-1] if len(柱状列表) > 0 else None
            
            响应数据 = {
                '指标名称': 'MACD',
                '参数': {
                    'fast_period': fast_period,
                    'slow_period': slow_period,
                    'signal_period': signal_period
                },
                '输入数据长度': len(价格数据),
                '输出数据长度': len(macd列表),
                'MACD线': {
                    '最新值': 最新MACD,
                    '完整序列': macd列表
                },
                '信号线': {
                    '最新值': 最新信号,
                    '完整序列': 信号列表
                },
                '柱状图': {
                    '最新值': 最新柱状,
                    '完整序列': 柱状列表
                },
                '当前信号': self._分析MACD信号(最新MACD, 最新信号, 最新柱状)
            }
            
            return self._构造响应(True, 响应数据, "MACD计算完成")
            
        except Exception as e:
            self._记录日志("计算MACD错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"MACD计算失败: {str(e)}", 错误码=1004)
    
    def _分析MACD信号(self, macd值: float, 信号值: float, 柱状值: float) -> Dict:
        """分析MACD当前信号"""
        if macd值 is None or 信号值 is None:
            return {'状态': '未知', '类型': None}
        
        # 金叉信号：MACD线上穿信号线
        金叉 = macd值 > 信号值 and 柱状值 > 0
        
        # 死叉信号：MACD线下穿信号线
        死叉 = macd值 < 信号值 and 柱状值 < 0
        
        if 金叉:
            return {'状态': '买入', '类型': '金叉', '强度': '强' if 柱状值 > 0.5 else '中等'}
        elif 死叉:
            return {'状态': '卖出', '类型': '死叉', '强度': '强' if 柱状值 < -0.5 else '中等'}
        else:
            return {'状态': '观望', '类型': '盘整', '强度': '弱'}
    
    def 计算布林带(self, 价格数据: List[float], 
                 周期: int = 20, 
                 标准差倍数: float = 2.0) -> Dict:
        """
        计算布林带指标
        
        参数:
            价格数据: 价格序列列表
            周期: 布林带周期 (默认: 20)
            标准差倍数: 标准差乘数 (默认: 2.0)
            
        返回:
            包含布林带计算结果的标准化响应
        """
        try:
            if not self.使用V2:
                return self._构造响应(False, None, "布林带计算需要V2版本", 错误码=1005)
            
            self._记录日志("计算布林带", f"周期={周期}，标准差倍数={标准差倍数}")
            
            价格数组 = np.array(价格数据, dtype=np.float64)
            
            # 使用V2版本的布林带计算
            中轨, 上轨, 下轨 = self.工具V2.布林带(
                价格数组,
                周期=周期,
                标准差倍数=标准差倍数,
                验证=self.验证模式
            )
            
            # 转换为Python列表
            中轨列表 = [float(x) if not np.isnan(x) else None for x in 中轨]
            上轨列表 = [float(x) if not np.isnan(x) else None for x in 上轨]
            下轨列表 = [float(x) if not np.isnan(x) else None for x in 下轨]
            
            # 分析当前价格位置
            当前价格 = 价格数据[-1] if len(价格数据) > 0 else None
            当前状态 = self._分析布林带位置(当前价格, 上轨列表[-1], 中轨列表[-1], 下轨列表[-1]) if all(x is not None for x in [当前价格, 上轨列表[-1], 中轨列表[-1], 下轨列表[-1]]) else '未知'
            
            响应数据 = {
                '指标名称': '布林带',
                '参数': {
                    '周期': 周期,
                    '标准差倍数': 标准差倍数
                },
                '输入数据长度': len(价格数据),
                '当前价格': 当前价格,
                '状态分析': 当前状态,
                '上轨': {
                    '最新值': 上轨列表[-1],
                    '完整序列': 上轨列表
                },
                '中轨': {
                    '最新值': 中轨列表[-1],
                    '完整序列': 中轨列表
                },
                '下轨': {
                    '最新值': 下轨列表[-1],
                    '完整序列': 下轨列表
                }
            }
            
            return self._构造响应(True, 响应数据, f"布林带计算完成，周期={周期}")
            
        except Exception as e:
            self._记录日志("计算布林带错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"布林带计算失败: {str(e)}", 错误码=1005)
    
    def _分析布林带位置(self, 价格: float, 上轨: float, 中轨: float, 下轨: float) -> str:
        """分析价格在布林带中的位置"""
        带宽 = 上轨 - 下轨
        
        if 价格 >= 上轨:
            return '上轨突破，超买信号'
        elif 价格 <= 下轨:
            return '下轨突破，超卖信号'
        elif 价格 >= 上轨 * 0.95:
            return '接近上轨，强势区域'
        elif 价格 <= 下轨 * 1.05:
            return '接近下轨，弱势区域'
        elif 价格 > 中轨:
            return '中轨上方，偏强'
        elif 价格 < 中轨:
            return '中轨下方，偏弱'
        else:
            return '中轨附近，震荡'
    
    # ============ 批量技术指标API ============
    
    def 批量计算技术指标(self, 价格数据: List[float], 
                     指标列表: List[str] = None) -> Dict:
        """
        批量计算多个技术指标
        
        参数:
            价格数据: 价格序列列表
            指标列表: 需要计算的指标列表，可选值: ['SMA_20', 'EMA_12', 'RSI_14', 'MACD', '布林带']
                      如果不指定，则计算所有可用指标
            
        返回:
            包含所有计算结果的标准化响应
        """
        try:
            self._记录日志("批量计算技术指标", f"指标列表={指标列表}，数据长度={len(价格数据)}")
            
            if 指标列表 is None:
                指标列表 = ['SMA_20', 'EMA_12', 'RSI_14', 'MACD', '布林带']
            
            结果 = {}
            
            for 指标 in 指标列表:
                if 指标.startswith('SMA'):
                    # 解析周期: SMA_20 -> 周期20
                    try:
                        周期 = int(指标.split('_')[1])
                    except:
                        周期 = 20
                    
                    sma结果 = self.计算SMA(价格数据, 周期=周期)
                    if sma结果['成功']:
                        结果[指标] = sma结果['数据']
                
                elif 指标.startswith('EMA'):
                    try:
                        周期 = int(指标.split('_')[1])
                    except:
                        周期 = 12
                    
                    ema结果 = self.计算EMA(价格数据, 周期=周期)
                    if ema结果['成功']:
                        结果[指标] = ema结果['数据']
                
                elif 指标.startswith('RSI'):
                    if not self.使用V2:
                        continue
                    
                    try:
                        周期 = int(指标.split('_')[1])
                    except:
                        周期 = 14
                    
                    rsi结果 = self.计算RSI(价格数据, 周期=周期)
                    if rsi结果['成功']:
                        结果[指标] = rsi结果['数据']
                
                elif 指标 == 'MACD':
                    if not self.使用V2:
                        continue
                    
                    macd结果 = self.计算MACD(价格数据)
                    if macd结果['成功']:
                        结果[指标] = macd结果['数据']
                
                elif 指标 == '布林带':
                    if not self.使用V2:
                        continue
                    
                    布林带结果 = self.计算布林带(价格数据)
                    if 布林带结果['成功']:
                        结果[指标] = 布林带结果['数据']
            
            响应数据 = {
                '指标数量': len(结果),
                '计算完成': True,
                '结果': 结果,
                '摘要': self._生成技术指标摘要(结果, 价格数据[-1] if len(价格数据) > 0 else None)
            }
            
            return self._构造响应(True, 响应数据, f"批量计算完成，成功{len(结果)}个指标")
            
        except Exception as e:
            self._记录日志("批量计算技术指标错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"批量计算失败: {str(e)}", 错误码=1006)
    
    def _生成技术指标摘要(self, 结果: Dict, 当前价格: float) -> Dict:
        """生成技术指标分析摘要"""
        if not 结果:
            return {'状态': '无结果', '建议': '未计算任何技术指标'}
        
        买入信号 = 0
        卖出信号 = 0
        观望信号 = 0
        
        信号分析 = []
        
        # 分析每个指标
        for 指标名, 指标数据 in 结果.items():
            if '当前信号' in 指标数据:
                信号 = 指标数据['当前信号']
                if isinstance(信号, dict) and '状态' in 信号:
                    if 信号['状态'] == '买入':
                        买入信号 += 1
                        信号分析.append(f"{指标名}: 买入信号")
                    elif 信号['状态'] == '卖出':
                        卖出信号 += 1
                        信号分析.append(f"{指标名}: 卖出信号")
                    else:
                        观望信号 += 1
        
        # 判断整体趋势
        if 买入信号 > 卖出信号 and 买入信号 >= 观望信号:
            整体状态 = '偏多'
        elif 卖出信号 > 买入信号 and 卖出信号 >= 观望信号:
            整体状态 = '偏空'
        else:
            整体状态 = '震荡'
        
        # 生成建议
        if 整体状态 == '偏多' and 买入信号 >= 2:
            建议 = '多个指标显示买入信号，可考虑适当买入'
        elif 整体状态 == '偏空' and 卖出信号 >= 2:
            建议 = '多个指标显示卖出信号，可考虑适当卖出'
        elif 整体状态 == '震荡':
            建议 = '指标分化，市场震荡，建议观望'
        else:
            建议 = '信号不明确，建议等待更明确信号'
        
        return {
            '整体状态': 整体状态,
            '买入信号数': 买入信号,
            '卖出信号数': 卖出信号,
            '观望信号数': 观望信号,
            '信号分析': 信号分析,
            '建议': 建议,
            '当前价格': 当前价格
        }
    
    # ============ 系统信息API ============
    
    def 获取系统信息(self) -> Dict:
        """
        获取API系统信息
        
        返回:
            包含系统信息的标准化响应
        """
        try:
            self._记录日志("获取系统信息", "查询系统状态")
            
            系统信息 = {
                '系统名称': '竹林司马 (Zhulinsma) - TechnicalAPI',
                '中文名称': '竹林司马',
                '英文名称': 'Zhulinsma',
                '完整名称': '竹林司马 (Zhulinsma)',
                '版本': '1.0.0',
                '位置': '广州',
                '初始化时间': self.初始化时间.strftime('%Y-%m-%d %H:%M:%S'),
                '运行时长': f"{(datetime.now() - self.初始化时间).total_seconds():.1f}秒",
                '配置': {
                    '验证模式': self.验证模式,
                    '使用V2': self.使用V2,
                    '核心工具可用': HAS_CORE_TOOLS
                },
                '支持的技术指标': [
                    'SMA_周期(5,10,20,30,60)',
                    'EMA_周期(12,26)',
                    'RSI_周期(14)',
                    'MACD_参数(fast=12, slow=26, signal=9)',
                    '布林带_参数(周期=20, 标准差倍数=2)'
                ],
                '接口数量': 6,
                '日志数量': len(self.日志)
            }
            
            return self._构造响应(True, 系统信息, "系统信息获取成功")
            
        except Exception as e:
            self._记录日志("获取系统信息错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"获取系统信息失败: {str(e)}", 错误码=1007)
    
    def 获取日志(self, 数量: int = 10) -> Dict:
        """
        获取最近的API调用日志
        
        参数:
            数量: 要获取的日志数量 (默认: 10)
            
        返回:
            包含日志信息的标准化响应
        """
        try:
            self._记录日志("获取日志", f"请求数量={数量}")
            
            # 限制数量
            if 数量 > 100:
                数量 = 100
            
            # 获取最近的日志
            最近日志 = self.日志[-数量:] if len(self.日志) > 数量 else self.日志
            
            日志信息 = {
                '日志总数': len(self.日志),
                '返回数量': len(最近日志),
                '日志记录': 最近日志
            }
            
            return self._构造响应(True, 日志信息, f"获取日志成功，返回{len(最近日志)}条记录")
            
        except Exception as e:
            self._记录日志("获取日志错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"获取日志失败: {str(e)}", 错误码=1008)
    
    # ============ 通用工具方法 ============
    
    def 健康检查(self) -> Dict:
        """
        执行API健康检查
        
        返回:
            包含健康状态的标准化响应
        """
        try:
            self._记录日志("健康检查", "执行系统健康检查")
            
            # 检查核心工具是否可用
            if not HAS_CORE_TOOLS:
                健康状态 = {
                    '状态': '异常',
                    '详情': '核心工具模块不可用',
                    '建议': '检查zhulinsma_tool.py和zhulinsma_tool_v2.py是否存在'
                }
                return self._构造响应(False, 健康状态, "健康检查失败", 错误码=1009)
            
            # 测试基本功能
            try:
                测试数据 = [1.0, 2.0, 3.0, 4.0, 5.0]
                sma测试 = self.工具.SMA(测试数据, 周期=3, 验证=False)
                if len(sma测试) != 5:
                    raise ValueError("SMA计算长度不正确")
                
                if self.使用V2:
                    rsi测试 = self.工具V2.RSI(测试数据, 周期=3, 验证=False)
                    if len(rsi测试) != 5:
                        raise ValueError("RSI计算长度不正确")
                
                健康状态 = {
                    '状态': '健康',
                    '核心工具': '正常',
                    '验证模式': self.验证模式,
                    'V2版本': self.使用V2,
                    '当前时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                return self._构造响应(True, 健康状态, "健康检查通过")
                
            except Exception as e:
                健康状态 = {
                    '状态': '异常',
                    '详情': f"功能测试失败: {str(e)}",
                    '核心工具': '异常',
                    '建议': '检查竹林司马核心工具的正确性'
                }
                return self._构造响应(False, 健康状态, "健康检查失败", 错误码=1010)
            
        except Exception as e:
            self._记录日志("健康检查错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"健康检查失败: {str(e)}", 错误码=1011)

    def 趋势分析(self, 股票代码: str, 价格数据: List[float]) -> Dict:
        """
        分析股票价格趋势
        
        参数:
            股票代码: 股票代码
            价格数据: 价格序列
            
        返回:
            标准化响应
        """
        try:
            self._记录日志("趋势分析", f"股票代码={股票代码}，数据长度={len(价格数据)}")
            
            if len(价格数据) < 10:
                return self._构造响应(False, None, "数据不足，无法进行趋势分析", 错误码=4001)
            
            # 简单趋势判断
            if len(价格数据) >= 2:
                最近价格 = 价格数据[-1]
                之前价格 = 价格数据[-2]
                价格变化 = (最近价格 - 之前价格) / 之前价格 * 100 if 之前价格 != 0 else 0
                
                if 价格变化 > 1:
                    当前趋势 = '上升'
                    趋势强度 = '强'
                elif 价格变化 > 0:
                    当前趋势 = '上升'
                    趋势强度 = '弱'
                elif 价格变化 < -1:
                    当前趋势 = '下降'
                    趋势强度 = '强'
                elif 价格变化 < 0:
                    当前趋势 = '下降'
                    趋势强度 = '弱'
                else:
                    当前趋势 = '横盘'
                    趋势强度 = '无'
            else:
                当前趋势 = '未知'
                趋势强度 = '未知'
                价格变化 = 0
            
            # 计算短期趋势（最近5个数据点）
            if len(价格数据) >= 5:
                短期价格 = 价格数据[-5:]
                短期趋势 = '上升' if 短期价格[-1] > 短期价格[0] else '下降'
            else:
                短期趋势 = '未知'
            
            趋势结果 = {
                '当前趋势': 当前趋势,
                '趋势强度': 趋势强度,
                '价格变化百分比': 价格变化,
                '短期趋势': 短期趋势,
                '置信度': min(0.7, len(价格数据) / 100),  # 数据越多置信度越高
                '预测说明': f"当前{当前趋势}趋势，{趋势强度}度变化{价格变化:.2f}%",
                '建议': f"趋势{当前趋势}，建议{'关注买入' if 当前趋势 == '上升' else '谨慎观望'}"
            }
            
            return self._构造响应(True, 趋势结果, "趋势分析完成")
            
        except Exception as e:
            self._记录日志("趋势分析错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"趋势分析失败: {str(e)}", 错误码=4002)


# 直接运行示例
if __name__ == "__main__":
    示例用法()

# ============ 辅助函数 ============

def 创建TechnicalAPI实例(验证模式: bool = True, 使用V2: bool = True) -> TechnicalAPI:
    """
    创建TechnicalAPI实例的便捷函数
    
    参数:
        验证模式: 是否启用双重验证 (默认: True)
        使用V2: 是否使用V2版本的高级功能 (默认: True)
        
    返回:
        TechnicalAPI实例
    """
    return TechnicalAPI(验证模式=验证模式, 使用V2=使用V2)


def 示例用法():
    """
    提供TechnicalAPI的使用示例
    """
    print("🔧 TechnicalAPI 使用示例")
    print("=" * 50)
    
    try:
        # 创建API实例
        api = 创建TechnicalAPI实例(验证模式=True, 使用V2=True)
        print("✅ API实例创建成功")
        
        # 测试数据
        测试价格 = [100.0, 102.0, 98.0, 105.0, 108.0, 106.0, 112.0, 115.0, 118.0, 120.0,
                  122.0, 119.0, 117.0, 115.0, 113.0, 110.0, 108.0, 112.0, 115.0, 118.0]
        
        print(f"📊 测试数据: {len(测试价格)}个价格点")
        
        # 1. 计算SMA
        print("\n1. 计算SMA(20):")
        sma结果 = api.计算SMA(测试价格, 周期=20)
        if sma结果['成功']:
            print(f"   ✅ 成功: {sma结果['消息']}")
            print(f"   最新值: {sma结果['数据']['最新值']}")
        else:
            print(f"   ❌ 失败: {sma结果['消息']}")
        
        # 2. 计算RSI
        print("\n2. 计算RSI(14):")
        rsi结果 = api.计算RSI(测试价格, 周期=14)
        if rsi结果['成功']:
            print(f"   ✅ 成功: {rsi结果['消息']}")
            print(f"   最新值: {rsi结果['数据']['最新值']}")
            print(f"   当前状态: {rsi结果['数据']['当前状态']}")
        else:
            print(f"   ❌ 失败: {rsi结果['消息']}")
        
        # 3. 批量计算
        print("\n3. 批量计算技术指标:")
        批量结果 = api.批量计算技术指标(测试价格, ['SMA_20', 'RSI_14', 'MACD', '布林带'])
        if 批量结果['成功']:
            print(f"   ✅ 成功: {批量结果['消息']}")
            print(f"   计算指标数: {批量结果['数据']['指标数量']}")
            摘要 = 批量结果['数据']['摘要']
            print(f"   整体状态: {摘要['整体状态']}")
            print(f"   建议: {摘要['建议']}")
        else:
            print(f"   ❌ 失败: {批量结果['消息']}")
        
        # 4. 获取系统信息
        print("\n4. 获取系统信息:")
        系统信息 = api.获取系统信息()
        if 系统信息['成功']:
            print(f"   ✅ 成功: {系统信息['消息']}")
            print(f"   系统名称: {系统信息['数据']['完整名称']}")
            print(f"   中文名称: {系统信息['数据']['中文名称']}")
            print(f"   英文名称: {系统信息['数据']['英文名称']}")
            print(f"   版本: {系统信息['数据']['版本']}")
            print(f"   位置: {系统信息['数据']['位置']}")
        else:
            print(f"   ❌ 失败: {系统信息['消息']}")
        
        print("\n" + "=" * 50)
        print("🎉 TechnicalAPI 示例执行完成")
        
    except Exception as e:
        print(f"❌ 示例执行失败: {str(e)}")

    def 获取接口文档(self) -> Dict:
        """
        获取TechnicalAPI接口文档
        
        返回:
            包含接口文档的字典
        """
        try:
            self._记录日志("获取接口文档", "查询接口文档")
            
            接口文档 = {
                "系统名称": "竹林司马 - TechnicalAPI",
                "版本": "1.0.0",
                "描述": "核心技术分析API，提供SMA、EMA、RSI、MACD、布林带等技术指标计算",
                "位置": "广州",
                "作者": "杨总的技术团队",
                "核心功能": [
                    "SMA (简单移动平均线) 计算",
                    "EMA (指数移动平均线) 计算", 
                    "RSI (相对强弱指数) 计算",
                    "MACD (移动平均收敛散度) 计算",
                    "布林带 (Bollinger Bands) 计算",
                    "批量技术指标计算",
                    "技术指标信号分析"
                ],
                "接口列表": [
                    {
                        "接口名称": "计算SMA",
                        "方法": "计算SMA(价格数据, 周期=20)",
                        "描述": "计算简单移动平均线",
                        "参数": "价格数据: List[float], 周期: int (默认20)",
                        "返回": "包含SMA值的标准化响应"
                    },
                    {
                        "接口名称": "计算RSI",
                        "方法": "计算RSI(价格数据, 周期=14)",
                        "描述": "计算相对强弱指数",
                        "参数": "价格数据: List[float], 周期: int (默认14)",
                        "返回": "包含RSI值和超买超卖信号的标准化响应"
                    },
                    {
                        "接口名称": "计算MACD",
                        "方法": "计算MACD(价格数据, 快线周期=12, 慢线周期=26, 信号周期=9)",
                        "描述": "计算移动平均收敛散度",
                        "参数": "价格数据: List[float], 快线周期: int (默认12), 慢线周期: int (默认26), 信号周期: int (默认9)",
                        "返回": "包含MACD线、信号线、柱状图的标准化响应"
                    },
                    {
                        "接口名称": "计算布林带",
                        "方法": "计算布林带(价格数据, 周期=20, 标准差=2)",
                        "描述": "计算布林带指标",
                        "参数": "价格数据: List[float], 周期: int (默认20), 标准差: int (默认2)",
                        "返回": "包含上轨、中轨、下轨的标准化响应"
                    },
                    {
                        "接口名称": "批量计算技术指标",
                        "方法": "批量计算技术指标(价格数据, 指标列表=None)",
                        "描述": "批量计算多个技术指标",
                        "参数": "价格数据: List[float], 指标列表: List[str] (可选，默认所有指标)",
                        "返回": "包含所有指标结果的标准化响应"
                    },
                    {
                        "接口名称": "获取系统信息",
                        "方法": "获取系统信息()",
                        "描述": "获取API系统信息",
                        "参数": "无",
                        "返回": "包含系统信息的标准化响应"
                    },
                    {
                        "接口名称": "获取接口文档",
                        "方法": "获取接口文档()",
                        "描述": "获取当前接口文档",
                        "参数": "无",
                        "返回": "当前接口文档字典"
                    }
                ],
                "标准响应格式": {
                    "成功": "bool - 操作是否成功",
                    "消息": "str - 操作结果消息",
                    "数据": "Any - 操作结果数据",
                    "时间戳": "str - 操作时间戳",
                    "错误码": "int - 错误代码 (仅在失败时返回)"
                },
                "示例代码": {
                    "计算SMA": "api.计算SMA([10.5, 10.8, 11.2, 10.9, 11.5], 周期=5)",
                    "计算RSI": "api.计算RSI([10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1], 周期=14)",
                    "批量计算": "api.批量计算技术指标(价格数据, ['SMA_20', 'RSI_14', 'MACD'])"
                },
                "错误码说明": {
                    "1001": "数据验证失败",
                    "1002": "参数格式错误",
                    "1003": "计算失败",
                    "1004": "数据不足",
                    "1005": "系统错误",
                    "1006": "批量计算失败",
                    "1007": "系统信息获取失败"
                }
            }
            
            return self._构造响应(True, 接口文档, "接口文档获取成功")
            
        except Exception as e:
            self._记录日志("获取接口文档错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"获取接口文档失败: {str(e)}", 错误码=1007)

    def 趋势分析(self, 股票代码: str, 价格数据: List[float]) -> Dict:
        """
        分析股票价格趋势
        
        参数:
            股票代码: 股票代码
            价格数据: 价格序列
            
        返回:
            标准化响应
        """
        try:
            self._记录日志("趋势分析", f"股票代码={股票代码}，数据长度={len(价格数据)}")
            
            if len(价格数据) < 10:
                return self._构造响应(False, None, "数据不足，无法进行趋势分析", 错误码=4001)
            
            # 简单趋势判断
            if len(价格数据) >= 2:
                最近价格 = 价格数据[-1]
                之前价格 = 价格数据[-2]
                价格变化 = (最近价格 - 之前价格) / 之前价格 * 100 if 之前价格 != 0 else 0
                
                if 价格变化 > 1:
                    当前趋势 = '上升'
                    趋势强度 = '强'
                elif 价格变化 > 0:
                    当前趋势 = '上升'
                    趋势强度 = '弱'
                elif 价格变化 < -1:
                    当前趋势 = '下降'
                    趋势强度 = '强'
                elif 价格变化 < 0:
                    当前趋势 = '下降'
                    趋势强度 = '弱'
                else:
                    当前趋势 = '横盘'
                    趋势强度 = '无'
            else:
                当前趋势 = '未知'
                趋势强度 = '未知'
                价格变化 = 0
            
            # 计算短期趋势（最近5个数据点）
            if len(价格数据) >= 5:
                短期价格 = 价格数据[-5:]
                短期趋势 = '上升' if 短期价格[-1] > 短期价格[0] else '下降'
            else:
                短期趋势 = '未知'
            
            趋势结果 = {
                '当前趋势': 当前趋势,
                '趋势强度': 趋势强度,
                '价格变化百分比': 价格变化,
                '短期趋势': 短期趋势,
                '置信度': min(0.7, len(价格数据) / 100),  # 数据越多置信度越高
                '预测说明': f"当前{当前趋势}趋势，{趋势强度}度变化{价格变化:.2f}%",
                '建议': f"趋势{当前趋势}，建议{'关注买入' if 当前趋势 == '上升' else '谨慎观望'}"
            }
            
            return self._构造响应(True, 趋势结果, "趋势分析完成")
            
        except Exception as e:
            self._记录日志("趋势分析错误", f"错误: {str(e)}")
            return self._构造响应(False, None, f"趋势分析失败: {str(e)}", 错误码=4002)


# 直接运行示例
if __name__ == "__main__":
    示例用法()