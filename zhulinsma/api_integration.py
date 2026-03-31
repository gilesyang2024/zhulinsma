"""
竹林司马API集成模块
将新的API接口集成到现有系统架构中
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np

from zhulinsma.interface.technical_api import TechnicalAPI
from zhulinsma.interface.data_quality_api import DataQualityAPI
from zhulinsma.interface.analysis_api import AnalysisAPI
from zhulinsma.interface.web_api import WebAPI
from zhulinsma.core.indicators import TechnicalIndicators
from zhulinsma.core.quality import DataQualityManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class 竹林司马API集成器:
    """竹林司马API集成器 - 将新API接口集成到现有系统"""
    
    def __init__(self, 验证模式: bool = True, 日志级别: str = "INFO"):
        """初始化API集成器"""
        self.验证模式 = 验证模式
        self.日志级别 = 日志级别
        
        # 初始化核心组件
        self.技术指标工具 = TechnicalIndicators(验证模式=self.验证模式)
        self.数据质量监控器 = DataQualityManager(config={"验证模式": self.验证模式})
        
        # 初始化API模块
        self.技术API = TechnicalAPI(验证模式=self.验证模式)
        self.数据质量API = DataQualityAPI(启用监控=True, 报警阈值=0.95)
        self.分析API = AnalysisAPI(验证模式=self.验证模式)
        self.WebAPI = WebAPI()
        
        # 系统状态
        self.初始化时间 = datetime.now()
        self.请求计数 = 0
        self.错误计数 = 0
        
        logger.info(f"🔄 竹林司马API集成器初始化完成")
        logger.info(f"   验证模式: {self.验证模式}")
        logger.info(f"   日志级别: {self.日志级别}")
        logger.info(f"   初始化时间: {self.初始化时间}")
    
    def 获取系统状态(self) -> Dict:
        """获取系统状态信息"""
        系统状态数据 = {
            "系统名称": "竹林司马 (Zhulinsma) API集成器",
            "中文名称": "竹林司马",
            "英文名称": "Zhulinsma",
            "完整名称": "竹林司马 (Zhulinsma)",
            "版本": "2.0.0",
            "状态": "运行中",
            "验证模式": self.验证模式,
            "初始化时间": self.初始化时间.isoformat(),
            "运行时长(秒)": (datetime.now() - self.初始化时间).total_seconds(),
            "请求计数": self.请求计数,
            "错误计数": self.错误计数,
            "错误率": f"{self.错误计数 / max(self.请求计数, 1) * 100:.2f}%" if self.请求计数 > 0 else "0.00%",
            "API模块": {
                "技术API": "已加载",
                "数据质量API": "已加载",
                "分析API": "已加载",
                "WebAPI": "已加载"
            },
            "核心组件": {
                "技术指标工具": "已加载",
                "技术分析工具": "已加载",
                "数据质量监控器": "已加载"
            }
        }
        
        # 返回包含成功键的标准化响应
        return {
            "成功": True,
            "消息": "系统状态获取成功",
            "数据": 系统状态数据,
            "时间戳": datetime.now().isoformat()
        }
    
    def 执行技术分析API(self, 股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
        """通过技术API执行技术分析"""
        self.请求计数 += 1
        try:
            logger.info(f"📊 执行技术分析API - 股票: {股票代码}, 数据长度: {len(价格数据)}")
            
            # 1. 数据质量验证
            数据质量结果 = self.数据质量API.验证股票数据(股票代码, 价格数据, 时间戳)
            
            if not 数据质量结果["成功"]:
                self.错误计数 += 1
                return {
                    "成功": False,
                    "消息": "数据质量验证失败",
                    "数据质量结果": 数据质量结果,
                    "技术分析结果": None
                }
            
            # 2. 计算技术指标
            技术指标结果 = {}
            
            # 计算SMA
            sma结果 = self.技术API.计算SMA(价格数据, 周期=20)
            if sma结果["成功"]:
                技术指标结果["SMA_20"] = sma结果
            
            # 计算RSI
            rsi结果 = self.技术API.计算RSI(价格数据, 周期=14)
            if rsi结果["成功"]:
                技术指标结果["RSI_14"] = rsi结果
            
            # 计算MACD
            macd结果 = self.技术API.计算MACD(价格数据)
            if macd结果["成功"]:
                技术指标结果["MACD"] = macd结果
            
            # 3. 执行综合分析
            分析结果 = self.分析API.执行技术分析(股票代码, 价格数据, 时间戳)
            
            return {
                "成功": True,
                "消息": "技术分析完成",
                "股票代码": 股票代码,
                "数据质量结果": 数据质量结果,
                "技术指标结果": 技术指标结果,
                "综合分析结果": 分析结果,
                "时间戳": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.错误计数 += 1
            logger.error(f"❌ 技术分析API执行失败: {e}")
            return {
                "成功": False,
                "消息": f"技术分析API执行失败: {str(e)}",
                "错误详情": str(e),
                "时间戳": datetime.now().isoformat()
            }
    
    def 批量分析股票API(self, 股票数据列表: List[Dict]) -> Dict:
        """通过API批量分析多只股票"""
        self.请求计数 += 1
        try:
            logger.info(f"📈 批量分析股票API - 股票数量: {len(股票数据列表)}")
            
            批量结果 = []
            成功计数 = 0
            失败计数 = 0
            
            for 股票数据 in 股票数据列表:
                股票代码 = 股票数据.get("股票代码", "未知")
                价格数据 = 股票数据.get("价格数据", [])
                时间戳 = 股票数据.get("时间戳", None)
                
                try:
                    # 使用分析API执行分析
                    分析结果 = self.分析API.执行技术分析(股票代码, 价格数据, 时间戳)
                    
                    if 分析结果["成功"]:
                        成功计数 += 1
                        批量结果.append({
                            "股票代码": 股票代码,
                            "成功": True,
                            "分析结果": 分析结果,
                            "时间戳": datetime.now().isoformat()
                        })
                    else:
                        失败计数 += 1
                        批量结果.append({
                            "股票代码": 股票代码,
                            "成功": False,
                            "错误": 分析结果.get("消息", "分析失败"),
                            "时间戳": datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    失败计数 += 1
                    批量结果.append({
                        "股票代码": 股票代码,
                        "成功": False,
                        "错误": str(e),
                        "时间戳": datetime.now().isoformat()
                    })
            
            return {
                "成功": True,
                "消息": f"批量分析完成 - 成功: {成功计数}, 失败: {失败计数}",
                "总股票数": len(股票数据列表),
                "成功数": 成功计数,
                "失败数": 失败计数,
                "成功率": f"{成功计数 / len(股票数据列表) * 100:.2f}%",
                "分析结果": 批量结果,
                "时间戳": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.错误计数 += 1
            logger.error(f"❌ 批量分析股票API执行失败: {e}")
            return {
                "成功": False,
                "消息": f"批量分析股票API执行失败: {str(e)}",
                "错误详情": str(e),
                "时间戳": datetime.now().isoformat()
            }
    
    def 处理Web请求(self, 路径: str, 方法: str, 请求数据: Dict = None) -> Dict:
        """处理Web API请求"""
        self.请求计数 += 1
        try:
            logger.info(f"🌐 处理Web请求 - 路径: {路径}, 方法: {方法}")
            
            # 使用WebAPI处理请求
            web响应 = self.WebAPI.处理请求(路径, 方法, 请求数据)
            
            return {
                "成功": True,
                "消息": "Web请求处理完成",
                "Web响应": web响应,
                "时间戳": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.错误计数 += 1
            logger.error(f"❌ Web请求处理失败: {e}")
            return {
                "成功": False,
                "消息": f"Web请求处理失败: {str(e)}",
                "错误详情": str(e),
                "时间戳": datetime.now().isoformat()
            }
    
    def 生成API文档(self) -> Dict:
        """生成API接口文档"""
        try:
            # 获取各API的文档
            技术API文档 = self.技术API.获取接口文档()
            数据质量API文档 = self.数据质量API.获取接口文档()
            分析API文档 = self.分析API.获取接口文档()
            WebAPI文档 = self.WebAPI.获取接口文档()
            
            # 系统信息
            系统状态 = self.获取系统状态()
            
            return {
                "成功": True,
                "消息": "API文档生成完成",
                "系统信息": {
                    "名称": "竹林司马API系统",
                    "版本": "2.0.0",
                    "描述": "为杨总定制的专业级技术分析API系统",
                    "位置": "广州",
                    "特点": ["双重验证机制", "模块化架构", "RESTful API", "数据质量监控"],
                    "状态": 系统状态
                },
                "API模块": {
                    "技术API": 技术API文档,
                    "数据质量API": 数据质量API文档,
                    "分析API": 分析API文档,
                    "WebAPI": WebAPI文档
                },
                "使用示例": {
                    "技术分析": {
                        "描述": "执行单只股票技术分析",
                        "请求": {
                            "股票代码": "000001.SZ",
                            "价格数据": [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1, 11.9, 12.3, 12.5],
                            "时间戳": ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", 
                                     "2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10"]
                        },
                        "响应": "包含数据质量验证、技术指标计算、趋势分析、风险评估的综合结果"
                    },
                    "批量分析": {
                        "描述": "批量分析多只股票",
                        "请求": {
                            "股票数据列表": [
                                {"股票代码": "000001.SZ", "价格数据": [10.5, 10.8, 11.2]},
                                {"股票代码": "000002.SZ", "价格数据": [20.1, 20.3, 20.0]}
                            ]
                        },
                        "响应": "每只股票的独立分析结果汇总"
                    },
                    "Web API": {
                        "描述": "通过HTTP接口调用",
                        "端点": {
                            "/api/health": "健康检查",
                            "/api/analyze": "技术分析",
                            "/api/batch-analyze": "批量分析",
                            "/api/indicators/sma": "计算SMA",
                            "/api/indicators/rsi": "计算RSI"
                        },
                        "请求格式": "JSON",
                        "响应格式": "JSON"
                    }
                },
                "时间戳": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ API文档生成失败: {e}")
            return {
                "成功": False,
                "消息": f"API文档生成失败: {str(e)}",
                "错误详情": str(e),
                "时间戳": datetime.now().isoformat()
            }


# 创建全局API集成器实例
_全局API集成器 = None

def 获取API集成器(验证模式: bool = True) -> 竹林司马API集成器:
    """获取全局API集成器实例（单例模式）"""
    global _全局API集成器
    if _全局API集成器 is None:
        _全局API集成器 = 竹林司马API集成器(验证模式=验证模式)
    return _全局API集成器

def 分析股票API(股票代码: str, 价格数据: List[float], 时间戳: List[str] = None) -> Dict:
    """API接口：分析单只股票"""
    api集成器 = 获取API集成器()
    return api集成器.执行技术分析API(股票代码, 价格数据, 时间戳)

def 批量分析股票API接口(股票数据列表: List[Dict]) -> Dict:
    """API接口：批量分析多只股票"""
    api集成器 = 获取API集成器()
    return api集成器.批量分析股票API(股票数据列表)

def 获取系统状态API() -> Dict:
    """API接口：获取系统状态"""
    api集成器 = 获取API集成器()
    return api集成器.获取系统状态()

def 获取API文档() -> Dict:
    """API接口：获取API文档"""
    api集成器 = 获取API集成器()
    return api集成器.生成API文档()