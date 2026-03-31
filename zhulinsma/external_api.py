"""
竹林司马外部API接口
为外部用户提供统一、简化的API调用接口
"""

import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import numpy as np

from zhulinsma.api_integration import (
    获取API集成器,
    分析股票API,
    批量分析股票API接口,
    获取系统状态API,
    获取API文档
)

class 竹林司马API:
    """竹林司马对外API接口（简化版）"""
    
    def __init__(self, 验证模式: bool = True, 日志级别: str = "INFO"):
        """初始化API接口"""
        self.验证模式 = 验证模式
        self.日志级别 = 日志级别
        
        # 获取API集成器
        self.api集成器 = 获取API集成器(验证模式=验证模式)
        
        print(f"✅ 竹林司马API接口初始化完成")
        print(f"   版本: 2.0.0")
        print(f"   位置: 广州")
        print(f"   验证模式: {验证模式}")
        print(f"   特点: 双重验证机制，模块化架构，RESTful API支持")
    
    def 分析(self, 股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
        """
        分析单只股票的技术面
        
        参数:
            股票代码: 股票代码（如 '000001.SZ'）
            价格数据: 价格序列列表
            时间戳: 可选的时间戳列表
        
        返回:
            技术分析结果字典
        """
        print(f"🔍 正在分析股票 {股票代码}...")
        
        # 调用API集成器
        结果 = 分析股票API(股票代码, 价格数据, 时间戳)
        
        if 结果["成功"]:
            print(f"✅ 分析完成 - 股票: {股票代码}")
            return self._格式化分析结果(结果)
        else:
            print(f"❌ 分析失败 - 错误: {结果.get('消息', '未知错误')}")
            return 结果
    
    def 批量分析(self, 股票数据列表: List[Dict]) -> Dict:
        """
        批量分析多只股票
        
        参数:
            股票数据列表: 每只股票的字典列表
                [
                    {"股票代码": "000001.SZ", "价格数据": [10.5, 10.8, 11.2]},
                    {"股票代码": "000002.SZ", "价格数据": [20.1, 20.3, 20.0]}
                ]
        
        返回:
            批量分析结果字典
        """
        print(f"📊 正在批量分析 {len(股票数据列表)} 只股票...")
        
        # 调用API集成器
        结果 = 批量分析股票API接口(股票数据列表)
        
        if 结果["成功"]:
            print(f"✅ 批量分析完成 - 成功: {结果['成功数']}, 失败: {结果['失败数']}")
            return self._格式化批量结果(结果)
        else:
            print(f"❌ 批量分析失败 - 错误: {结果.get('消息', '未知错误')}")
            return 结果
    
    def 计算技术指标(self, 价格数据: List[float], 指标类型: str = "SMA", 参数: Dict = None) -> Dict:
        """
        计算单个技术指标
        
        参数:
            价格数据: 价格序列列表
            指标类型: 指标类型（'SMA', 'EMA', 'RSI', 'MACD', '布林带'）
            参数: 可选的自定义参数
        
        返回:
            指标计算结果
        """
        print(f"📈 正在计算 {指标类型} 指标...")
        
        try:
            # 通过技术API计算
            if 指标类型.upper() == "SMA":
                周期 = 参数.get("周期", 20) if 参数 else 20
                结果 = self.api集成器.技术API.计算SMA(价格数据, 周期=周期)
                
            elif 指标类型.upper() == "EMA":
                周期 = 参数.get("周期", 12) if 参数 else 12
                结果 = self.api集成器.技术API.计算EMA(价格数据, 周期=周期)
                
            elif 指标类型.upper() == "RSI":
                周期 = 参数.get("周期", 14) if 参数 else 14
                结果 = self.api集成器.技术API.计算RSI(价格数据, 周期=周期)
                
            elif 指标类型.upper() == "MACD":
                快线周期 = 参数.get("快线周期", 12) if 参数 else 12
                慢线周期 = 参数.get("慢线周期", 26) if 参数 else 26
                信号周期 = 参数.get("信号周期", 9) if 参数 else 9
                结果 = self.api集成器.技术API.计算MACD(
                    价格数据, 
                    快线周期=快线周期, 
                    慢线周期=慢线周期, 
                    信号周期=信号周期
                )
                
            elif 指标类型.upper() == "布林带" or 指标类型.upper() == "BOLL":
                周期 = 参数.get("周期", 20) if 参数 else 20
                标准差 = 参数.get("标准差", 2) if 参数 else 2
                结果 = self.api集成器.技术API.计算布林带(价格数据, 周期=周期, 标准差=标准差)
                
            else:
                结果 = {
                    "成功": False,
                    "消息": f"不支持的指标类型: {指标类型}"
                }
            
            if 结果["成功"]:
                print(f"✅ {指标类型} 计算完成")
            else:
                print(f"❌ {指标类型} 计算失败")
                
            return 结果
            
        except Exception as e:
            print(f"❌ 计算失败: {str(e)}")
            return {
                "成功": False,
                "消息": f"指标计算失败: {str(e)}",
                "错误详情": str(e)
            }
    
    def 验证数据质量(self, 股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
        """
        验证股票数据质量
        
        参数:
            股票代码: 股票代码
            价格数据: 价格序列列表
            时间戳: 可选的时间戳列表
        
        返回:
            数据质量验证结果
        """
        print(f"🔬 正在验证 {股票代码} 数据质量...")
        
        try:
            结果 = self.api集成器.数据质量API.验证股票数据(股票代码, 价格数据, 时间戳)
            
            if 结果["成功"]:
                print(f"✅ 数据质量验证通过 - 评分: {结果.get('质量评分', 'N/A')}")
            else:
                print(f"⚠️ 数据质量存在问题 - 详情查看结果")
                
            return 结果
            
        except Exception as e:
            print(f"❌ 数据质量验证失败: {str(e)}")
            return {
                "成功": False,
                "消息": f"数据质量验证失败: {str(e)}",
                "错误详情": str(e)
            }
    
    def 获取状态(self) -> Dict:
        """获取系统状态信息"""
        return 获取系统状态API()
    
    def 获取文档(self) -> Dict:
        """获取API文档"""
        return 获取API文档()
    
    def _格式化分析结果(self, 原始结果: Dict) -> Dict:
        """格式化分析结果，提取关键信息"""
        try:
            分析结果 = 原始结果.get("综合分析结果", {})
            
            if not 分析结果.get("成功", False):
                return 原始结果
            
            # 提取关键指标
            趋势分析 = 分析结果.get("趋势分析", {})
            风险评估 = 分析结果.get("风险评估", {})
            投资建议 = 分析结果.get("投资建议", {})
            
            格式化结果 = {
                "成功": True,
                "股票代码": 原始结果.get("股票代码", "未知"),
                "分析时间": datetime.now().isoformat(),
                
                "数据质量": {
                    "评分": 原始结果.get("数据质量结果", {}).get("质量评分", "N/A"),
                    "状态": 原始结果.get("数据质量结果", {}).get("状态", "未知"),
                    "检查项": len(原始结果.get("数据质量结果", {}).get("检查结果", []))
                },
                
                "技术指标": {
                    "SMA_20": self._提取指标值(原始结果.get("技术指标结果", {}).get("SMA_20", {})),
                    "RSI_14": self._提取指标值(原始结果.get("技术指标结果", {}).get("RSI_14", {})),
                    "MACD": self._提取指标值(原始结果.get("技术指标结果", {}).get("MACD", {}))
                },
                
                "趋势分析": {
                    "趋势方向": 趋势分析.get("趋势方向", "未知"),
                    "趋势强度": 趋势分析.get("趋势强度", "未知"),
                    "支撑位": 趋势分析.get("支撑位", []),
                    "阻力位": 趋势分析.get("阻力位", [])
                },
                
                "风险评估": {
                    "风险等级": 风险评估.get("风险等级", "未知"),
                    "风险分数": 风险评估.get("风险分数", 0),
                    "风险描述": 风险评估.get("风险描述", "")
                },
                
                "投资建议": {
                    "操作方向": 投资建议.get("操作方向", "未知"),
                    "建议强度": 投资建议.get("建议强度", "中"),
                    "建议理由": 投资建议.get("建议理由", [])
                },
                
                "原始结果": {
                    "数据质量": 原始结果.get("数据质量结果"),
                    "技术指标": 原始结果.get("技术指标结果"),
                    "综合分析": 原始结果.get("综合分析结果")
                }
            }
            
            return 格式化结果
            
        except Exception as e:
            print(f"⚠️ 结果格式化失败: {str(e)}")
            return 原始结果
    
    def _提取指标值(self, 指标结果: Dict) -> Any:
        """从指标结果中提取关键值"""
        if not 指标结果.get("成功", False):
            return None
        
        数据 = 指标结果.get("数据", {})
        if isinstance(数据, dict):
            return {
                "值": 数据.get("值", None),
                "状态": 数据.get("状态", "未知")
            }
        else:
            return 数据
    
    def _格式化批量结果(self, 原始结果: Dict) -> Dict:
        """格式化批量分析结果"""
        try:
            if not 原始结果.get("成功", False):
                return 原始结果
            
            分析结果 = 原始结果.get("分析结果", [])
            成功股票 = []
            失败股票 = []
            
            for 结果 in 分析结果:
                if 结果.get("成功", False):
                    成功股票.append({
                        "股票代码": 结果.get("股票代码", "未知"),
                        "趋势方向": 结果.get("分析结果", {}).get("趋势分析", {}).get("趋势方向", "未知"),
                        "风险等级": 结果.get("分析结果", {}).get("风险评估", {}).get("风险等级", "未知"),
                        "建议": 结果.get("分析结果", {}).get("投资建议", {}).get("操作方向", "未知")
                    })
                else:
                    失败股票.append({
                        "股票代码": 结果.get("股票代码", "未知"),
                        "错误": 结果.get("错误", "未知错误")
                    })
            
            格式化结果 = {
                "成功": True,
                "总股票数": len(分析结果),
                "成功数": len(成功股票),
                "失败数": len(失败股票),
                "成功率": f"{len(成功股票) / len(分析结果) * 100:.2f}%",
                "成功股票": 成功股票,
                "失败股票": 失败股票,
                "详细结果": 分析结果,
                "汇总时间": datetime.now().isoformat()
            }
            
            return 格式化结果
            
        except Exception as e:
            print(f"⚠️ 批量结果格式化失败: {str(e)}")
            return 原始结果


# 全局API实例
_全局API实例 = None

def 获取API实例(验证模式: bool = True) -> 竹林司马API:
    """获取全局API实例（单例模式）"""
    global _全局API实例
    if _全局API实例 is None:
        _全局API实例 = 竹林司马API(验证模式=验证模式)
    return _全局API实例

# 简化函数接口
def 分析股票(股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
    """简化接口：分析单只股票"""
    api = 获取API实例()
    return api.分析(股票代码, 价格数据, 时间戳)

def 批量分析股票(股票数据列表: List[Dict]) -> Dict:
    """简化接口：批量分析多只股票"""
    api = 获取API实例()
    return api.批量分析(股票数据列表)

def 计算指标(价格数据: List[float], 指标类型: str = "SMA", 参数: Dict = None) -> Dict:
    """简化接口：计算技术指标"""
    api = 获取API实例()
    return api.计算技术指标(价格数据, 指标类型, 参数)

def 验证数据(股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
    """简化接口：验证数据质量"""
    api = 获取API实例()
    return api.验证数据质量(股票代码, 价格数据, 时间戳)

def 系统状态() -> Dict:
    """简化接口：获取系统状态"""
    api = 获取API实例()
    return api.获取状态()

def API文档() -> Dict:
    """简化接口：获取API文档"""
    api = 获取API实例()
    return api.获取文档()