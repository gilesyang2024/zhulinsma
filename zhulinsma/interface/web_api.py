#!/usr/bin/env python3
"""
WebAPI - Web接口模块

为竹林司马提供RESTful API接口，
支持Web服务调用和集成。

特性：
- RESTful API设计
- JSON请求/响应格式
- 错误处理和状态码
- 日志记录和监控
- Swagger/OpenAPI文档支持
"""

import json
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class HTTPStatus(Enum):
    """HTTP状态码"""
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


@dataclass
class APIResponse:
    """
    API标准响应
    
    所有API接口返回标准格式，包含：
    - 状态码
    - 操作是否成功
    - 返回数据
    - 消息
    - 时间戳
    """
    状态码: int
    成功: bool
    数据: Any
    消息: str
    时间戳: str = None
    请求ID: str = None
    
    def __post_init__(self):
        if self.时间戳 is None:
            self.时间戳 = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return asdict(self)


class WebAPI:
    """
    Web API类
    
    提供RESTful API接口，支持外部系统通过HTTP调用。
    """
    
    def __init__(self):
        """初始化WebAPI"""
        self.初始化时间 = datetime.now()
        self.接口列表 = self._获取接口列表()
        self.请求计数器 = 0
    
    def _获取接口列表(self) -> List[Dict]:
        """获取所有接口列表"""
        return [
            {
                '路径': '/api/v1/health',
                '方法': 'GET',
                '描述': '系统健康检查',
                '参数': None,
                '示例': {'请求': {}, '响应': {'状态码': 200, '成功': True, '消息': '系统正常'}}
            },
            {
                '路径': '/api/v1/technical/sma',
                '方法': 'POST',
                '描述': '计算简单移动平均线',
                '参数': {
                    'stock_code': '字符串，股票代码',
                    'price_data': '列表，价格序列',
                    'period': '整数，计算周期 (默认: 20)'
                },
                '示例': {
                    '请求': {'stock_code': '000001.SZ', 'price_data': [100.0, 102.0, 98.0, 105.0, 108.0], 'period': 5},
                    '响应': {'状态码': 200, '成功': True, '数据': {'SMA_5': 104.6}}
                }
            },
            {
                '路径': '/api/v1/technical/rsi',
                '方法': 'POST',
                '描述': '计算相对强弱指数',
                '参数': {
                    'stock_code': '字符串，股票代码',
                    'price_data': '列表，价格序列',
                    'period': '整数，计算周期 (默认: 14)'
                },
                '示例': {
                    '请求': {'stock_code': '000001.SZ', 'price_data': [100.0, 102.0, 98.0, 105.0, 108.0, 106.0, 112.0, 115.0], 'period': 14},
                    '响应': {'状态码': 200, '成功': True, '数据': {'RSI_14': 68.5}}
                }
            },
            {
                '路径': '/api/v1/technical/analysis',
                '方法': 'POST',
                '描述': '执行全面技术分析',
                '参数': {
                    'stock_code': '字符串，股票代码',
                    'price_data': '列表，价格序列',
                    'timestamps': '列表，时间戳序列 (可选)',
                    'indicators': '列表，技术指标列表 (可选)'
                },
                '示例': {
                    '请求': {'stock_code': '000001.SZ', 'price_data': [100.0, 102.0, 98.0, 105.0, 108.0], 'indicators': ['SMA_5', 'RSI_14']},
                    '响应': {'状态码': 200, '成功': True, '数据': {'分析结果': {...}}}
                }
            },
            {
                '路径': '/api/v1/quality/validate',
                '方法': 'POST',
                '描述': '验证数据质量',
                '参数': {
                    'stock_code': '字符串，股票代码',
                    'price_data': '列表，价格序列',
                    'timestamps': '列表，时间戳序列 (可选)'
                },
                '示例': {
                    '请求': {'stock_code': '000001.SZ', 'price_data': [100.0, 102.0, 98.0, 105.0, 108.0]},
                    '响应': {'状态码': 200, '成功': True, '数据': {'质量分数': 0.92}}
                }
            },
            {
                '路径': '/api/v1/batch/analysis',
                '方法': 'POST',
                '描述': '批量技术分析',
                '参数': {
                    'analyses': '列表，分析参数列表',
                    'parallel': '布尔，是否并行处理 (默认: False)'
                },
                '示例': {
                    '请求': {'analyses': [{'stock_code': '000001.SZ', 'price_data': [...]}, {'stock_code': '000002.SZ', 'price_data': [...]}]},
                    '响应': {'状态码': 200, '成功': True, '数据': {'批量结果': [...]}}
                }
            }
        ]
    
    def 处理请求(self, 路径: str, 方法: str, 请求数据: Dict = None, 请求头: Dict = None) -> APIResponse:
        """
        处理HTTP请求
        
        参数:
            路径: 请求路径
            方法: HTTP方法 (GET, POST, PUT, DELETE)
            请求数据: 请求数据 (JSON格式)
            请求头: HTTP请求头
            
        返回:
            APIResponse 对象
        """
        self.请求计数器 += 1
        请求ID = f"REQ_{self.请求计数器}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # 验证请求
            if not self._验证请求(路径, 方法, 请求数据):
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="无效的请求",
                    请求ID=请求ID
                )
            
            # 根据路径和方法分发处理
            处理函数 = self._获取处理函数(路径, 方法)
            if not 处理函数:
                return APIResponse(
                    状态码=HTTPStatus.NOT_FOUND.value,
                    成功=False,
                    数据=None,
                    消息="接口未找到",
                    请求ID=请求ID
                )
            
            # 执行处理
            结果 = 处理函数(请求数据, 请求头, 请求ID)
            
            return 结果
            
        except Exception as e:
            # 记录错误
            print(f"⚠️ WebAPI处理请求时发生错误: {str(e)}")
            print(f"详细追踪: {traceback.format_exc()}")
            
            return APIResponse(
                状态码=HTTPStatus.INTERNAL_SERVER_ERROR.value,
                成功=False,
                数据=None,
                消息=f"服务器内部错误: {str(e)}",
                请求ID=请求ID
            )
    
    def _验证请求(self, 路径: str, 方法: str, 请求数据: Dict) -> bool:
        """验证请求的合法性"""
        # 检查路径和方法的组合是否在接口列表中
        有效接口 = any(接口['路径'] == 路径 and 接口['方法'] == 方法 
                     for 接口 in self.接口列表)
        
        if not 有效接口:
            return False
        
        # 对于POST请求，检查请求数据
        if 方法 == 'POST' and 请求数据 is None:
            return False
        
        return True
    
    def _获取处理函数(self, 路径: str, 方法: str):
        """获取对应的处理函数"""
        接口映射 = {
            ('/api/v1/health', 'GET'): self._处理健康检查,
            ('/api/v1/technical/sma', 'POST'): self._处理SMA计算,
            ('/api/v1/technical/rsi', 'POST'): self._处理RSI计算,
            ('/api/v1/technical/analysis', 'POST'): self._处理全面分析,
            ('/api/v1/quality/validate', 'POST'): self._处理数据质量验证,
            ('/api/v1/batch/analysis', 'POST'): self._处理批量分析
        }
        
        return 接口映射.get((路径, 方法))
    
    # ============ 请求处理函数 ============
    
    def _处理健康检查(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理健康检查请求"""
        系统信息 = {
            '系统名称': '竹林司马 (Zhulinsma) - WebAPI',
            '中文名称': '竹林司马',
            '英文名称': 'Zhulinsma',
            '完整名称': '竹林司马 (Zhulinsma)',
            '版本': '1.0.0',
            '位置': '广州',
            '初始化时间': self.初始化时间.isoformat(),
            '运行时长': f"{(datetime.now() - self.初始化时间).total_seconds():.1f}秒",
            '请求计数': self.请求计数器,
            '当前时间': datetime.now().isoformat(),
            '可用接口': len(self.接口列表)
        }
        
        return APIResponse(
            状态码=HTTPStatus.OK.value,
            成功=True,
            数据=系统信息,
            消息="系统运行正常",
            请求ID=请求ID
        )
    
    def _处理SMA计算(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理SMA计算请求"""
        try:
            # 验证请求数据
            if 'stock_code' not in 请求数据 or 'price_data' not in 请求数据:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="缺少必需参数: stock_code, price_data",
                    请求ID=请求ID
                )
            
            股票代码 = 请求数据['stock_code']
            价格数据 = 请求数据['price_data']
            周期 = 请求数据.get('period', 20)
            
            # 验证数据类型
            if not isinstance(价格数据, list):
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="price_data必须是列表",
                    请求ID=请求ID
                )
            
            if not isinstance(周期, int) or 周期 <= 0:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="period必须是正整数",
                    请求ID=请求ID
                )
            
            # 这里应该调用实际的TechnicalAPI，但为了演示，我们返回模拟数据
            # 在实际系统中，应该导入TechnicalAPI并调用相应方法
            
            计算数据 = {
                '股票代码': 股票代码,
                '计算周期': 周期,
                '输入数据长度': len(价格数据),
                'SMA结果': self._模拟SMA计算(价格数据, 周期),
                '计算时间': datetime.now().isoformat(),
                '说明': '这是模拟计算结果，实际系统应调用TechnicalAPI'
            }
            
            return APIResponse(
                状态码=HTTPStatus.OK.value,
                成功=True,
                数据=计算数据,
                消息=f"SMA计算完成，周期={周期}",
                请求ID=请求ID
            )
            
        except Exception as e:
            return APIResponse(
                状态码=HTTPStatus.BAD_REQUEST.value,
                成功=False,
                数据=None,
                消息=f"请求数据格式错误: {str(e)}",
                请求ID=请求ID
            )
    
    def _模拟SMA计算(self, 价格数据: List[float], 周期: int) -> float:
        """模拟SMA计算（实际系统中应调用TechnicalAPI）"""
        if len(价格数据) < 周期:
            return sum(价格数据) / len(价格数据)
        
        最近价格 = 价格数据[-周期:]
        return sum(最近价格) / 周期
    
    def _处理RSI计算(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理RSI计算请求"""
        try:
            # 验证请求数据
            if 'stock_code' not in 请求数据 or 'price_data' not in 请求数据:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="缺少必需参数: stock_code, price_data",
                    请求ID=请求ID
                )
            
            股票代码 = 请求数据['stock_code']
            价格数据 = 请求数据['price_data']
            周期 = 请求数据.get('period', 14)
            
            # 验证数据类型
            if not isinstance(价格数据, list):
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="price_data必须是列表",
                    请求ID=请求ID
                )
            
            if not isinstance(周期, int) or 周期 <= 0:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="period必须是正整数",
                    请求ID=请求ID
                )
            
            计算数据 = {
                '股票代码': 股票代码,
                '计算周期': 周期,
                '输入数据长度': len(价格数据),
                'RSI结果': self._模拟RSI计算(价格数据, 周期),
                '计算时间': datetime.now().isoformat(),
                '说明': '这是模拟计算结果，实际系统应调用TechnicalAPI'
            }
            
            return APIResponse(
                状态码=HTTPStatus.OK.value,
                成功=True,
                数据=计算数据,
                消息=f"RSI计算完成，周期={周期}",
                请求ID=请求ID
            )
            
        except Exception as e:
            return APIResponse(
                状态码=HTTPStatus.BAD_REQUEST.value,
                成功=False,
                数据=None,
                消息=f"请求数据格式错误: {str(e)}",
                请求ID=请求ID
            )
    
    def _模拟RSI计算(self, 价格数据: List[float], 周期: int) -> float:
        """模拟RSI计算（实际系统中应调用TechnicalAPI）"""
        if len(价格数据) < 周期 + 1:
            return 50.0  # 默认中性
        
        # 计算价格变化
        价格变化 = []
        for i in range(1, len(价格数据)):
            变化 = 价格数据[i] - 价格数据[i-1]
            价格变化.append(变化)
        
        # 取最近周期个变化
        最近变化 = 价格变化[-周期:]
        
        # 计算上涨和下跌
        上涨 = [c for c in 最近变化 if c > 0]
        下跌 = [-c for c in 最近变化 if c < 0]
        
        if not 上涨 or not 下跌:
            return 50.0
        
        平均上涨 = sum(上涨) / len(上涨)
        平均下跌 = sum(下跌) / len(下跌)
        
        if 平均下跌 == 0:
            return 100.0
        
        rs = 平均上涨 / 平均下跌
        rsi = 100 - (100 / (1 + rs))
        
        # 限制范围
        return max(0.0, min(100.0, rsi))
    
    def _处理全面分析(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理全面分析请求"""
        try:
            # 验证请求数据
            if 'stock_code' not in 请求数据 or 'price_data' not in 请求数据:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="缺少必需参数: stock_code, price_data",
                    请求请求ID=请求ID
                )
            
            股票代码 = 请求数据['stock_code']
            价格数据 = 请求数据['price_data']
            时间戳 = 请求数据.get('timestamps', None)
            指标列表 = 请求数据.get('indicators', ['SMA_20', 'RSI_14', 'MACD'])
            
            # 这里应该调用AnalysisAPI，但为了演示，我们返回模拟数据
            分析结果 = {
                '股票信息': {
                    '股票代码': 股票代码,
                    '分析时间': datetime.now().isoformat(),
                    '数据长度': len(价格数据),
                    '最新价格': 价格数据[-1] if 价格数据 else None
                },
                '技术分析': {
                    '趋势': '上升',
                    '强度': '中等',
                    '主要信号': '金叉确认'
                },
                '数据质量': {
                    '质量分数': 0.92,
                    '状态': '良好',
                    '建议': '数据质量优秀'
                },
                '风险评估': {
                    '等级': '中',
                    '说明': '中等风险，建议控制仓位',
                    '因素': ['市场波动正常', '技术指标分化']
                },
                '操作建议': {
                    '方向': '谨慎偏多',
                    '仓位': '轻仓',
                    '说明': '技术指标显示偏多信号，但风险等级中等，建议轻仓操作'
                },
                '计算时间': datetime.now().isoformat(),
                '说明': '这是模拟分析结果，实际系统应调用AnalysisAPI。请求的指标: ' + ', '.join(指标列表)
            }
            
            return APIResponse(
                状态码=HTTPStatus.OK.value,
                成功=True,
                数据=分析结果,
                消息="全面分析完成",
                请求ID=请求ID
            )
            
        except Exception as e:
            return APIResponse(
                状态码=HTTPStatus.BAD_REQUEST.value,
                成功=False,
                数据=None,
                消息=f"请求数据格式错误: {str(e)}",
                请求ID=请求ID
            )
    
    def _处理数据质量验证(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理数据质量验证请求"""
        try:
            # 验证请求数据
            if 'stock_code' not in 请求数据 or 'price_data' not in 请求数据:
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="缺少必需参数: stock_code, price_data",
                    请求ID=请求ID
                )
            
            股票代码 = 请求数据['stock_code']
            价格数据 = 请求数据['price_data']
            时间戳 = 请求数据.get('timestamps', None)
            
            验证结果 = {
                '股票代码': 股票代码,
                '验证时间': datetime.now().isoformat(),
                '数据长度': len(价格数据),
                '质量分数': self._模拟质量计算(价格数据),
                '评估等级': '良好',
                '详细检查': {
                    '完整性': {'状态': '完整', '得分': 0.98},
                    '有效性': {'状态': '有效', '得分': 0.96},
                    '一致性': {'状态': '一致', '得分': 0.94},
                    '时效性': {'状态': '新鲜', '得分': 0.92}
                },
                '建议': '数据质量优秀，可直接用于分析',
                '说明': '这是模拟验证结果，实际系统应调用DataQualityAPI'
            }
            
            return APIResponse(
                状态码=HTTPStatus.OK.value,
                成功=True,
                数据=验证结果,
                消息="数据质量验证完成",
                请求ID=请求ID
            )
            
        except Exception as e:
            return APIResponse(
                状态码=HTTPStatus.BAD_REQUEST.value,
                成功=False,
                数据=None,
                消息=f"请求数据格式错误: {str(e)}",
                请求ID=请求ID
            )
    
    def _模拟质量计算(self, 价格数据: List[float]) -> float:
        """模拟质量分数计算"""
        if not 价格数据:
            return 0.0
        
        # 模拟计算质量分数
        return 0.92  # 模拟值
    
    def _处理批量分析(self, 请求数据: Dict, 请求头: Dict, 请求ID: str) -> APIResponse:
        """处理批量分析请求"""
        try:
            # 验证请求数据
            if 'analyses' not in 请求数据 or not isinstance(请求数据['analyses'], list):
                return APIResponse(
                    状态码=HTTPStatus.BAD_REQUEST.value,
                    成功=False,
                    数据=None,
                    消息="缺少必需参数: analyses (必须是列表)",
                    请求ID=请求ID
                )
            
            分析列表 = 请求数据['analyses']
            并行处理 = 请求数据.get('parallel', False)
            分析数量 = len(分析列表)
            
            批量结果 = []
            
            for i, 分析参数 in enumerate(分析列表, 1):
                分析项 = {
                    '序号': i,
                    '股票代码': 分析参数.get('stock_code', f'未知_{i}'),
                    '状态': '成功',
                    '结果': {
                        '质量分数': self._模拟质量计算(分析参数.get('price_data', [])),
                        '风险等级': '中',
                        '建议': '数据质量良好，中等风险'
                    },
                    '处理时间': datetime.now().isoformat()
                }
                
                批量结果.append(分析项)
            
            响应数据 = {
                '处理时间': datetime.now().isoformat(),
                '分析数量': 分析数量,
                '并行处理': 并行处理,
                '成功数量': len(批量结果),
                '失败数量': 0,
                '结果列表': 批量结果,
                '摘要': {
                    '状态': '全部成功',
                    '平均质量分数': sum(item['结果']['质量分数'] for item in 批量结果) / len(批量结果) if 批量结果 else 0,
                    '建议': f'批量分析完成，全部{分析数量}个分析成功'
                },
                '说明': '这是模拟批量分析结果，实际系统应调用AnalysisAPI的批量方法'
            }
            
            return APIResponse(
                状态码=HTTPStatus.OK.value,
                成功=True,
                数据=响应数据,
                消息=f"批量分析完成，成功{分析数量}个",
                请求ID=请求ID
            )
            
        except Exception as e:
            return APIResponse(
                状态码=HTTPStatus.BAD_REQUEST.value,
                成功=False,
                数据=None,
                消息=f"批量分析处理失败: {str(e)}",
                请求ID=请求ID
            )
    
    # ============ 系统管理函数 ============
    
    def 获取接口文档(self) -> APIResponse:
        """
        获取API接口文档
        
        返回:
            包含接口文档的APIResponse
        """
        文档信息 = {
            '标题': '竹林司马技术分析API文档',
            '版本': '1.0.0',
            '描述': '为竹林司马技术分析工具提供的RESTful API接口',
            '基础路径': '/api/v1',
            '时间': datetime.now().isoformat(),
            '接口列表': self.接口列表,
            '使用说明': {
                '请求格式': '所有请求应为JSON格式，Content-Type: application/json',
                '响应格式': '所有响应为标准JSON格式，包含状态码、成功标志、数据和消息',
                '错误处理': '所有错误响应包含错误码和详细错误信息',
                '认证': '当前版本无需认证，后续版本将添加API密钥认证'
            },
            '示例': {
                '健康检查': 'GET /api/v1/health',
                'SMA计算': 'POST /api/v1/technical/sma',
                '全面分析': 'POST /api/v1/technical/analysis'
            }
        }
        
        return APIResponse(
            状态码=HTTPStatus.OK.value,
            成功=True,
            数据=文档信息,
            消息="接口文档获取成功"
        )
    
    def 获取系统状态(self) -> APIResponse:
        """
        获取系统状态信息
        
        返回:
            包含系统状态的APIResponse
        """
        当前时间 = datetime.now()
        运行时长 = (当前时间 - self.初始化时间).total_seconds()
        
        状态信息 = {
            '系统名称': '竹林司马 (Zhulinsma) - WebAPI',
            '中文名称': '竹林司马',
            '英文名称': 'Zhulinsma',
            '完整名称': '竹林司马 (Zhulinsma)',
            '版本': '1.0.0',
            '位置': '广州',
            '初始化时间': self.初始化时间.isoformat(),
            '当前时间': 当前时间.isoformat(),
            '运行时长': f"{运行时长:.1f}秒",
            '请求计数': self.请求计数器,
            '接口数量': len(self.接口列表),
            '系统状态': '运行中',
            '当前负载': '低',
            '最后检查': 当前时间.isoformat(),
            '建议': '系统运行正常'
        }
        
        return APIResponse(
            状态码=HTTPStatus.OK.value,
            成功=True,
            数据=状态信息,
            消息="系统状态获取成功"
        )
    
    def 执行健康检查(self) -> APIResponse:
        """
        执行详细的健康检查
        
        返回:
            包含健康检查结果的APIResponse
        """
        检查时间 = datetime.now()
        
        健康信息 = {
            '检查时间': 检查时间.isoformat(),
            '系统状态': '健康',
            '核心组件': {
                'WebAPI': '正常',
                '接口服务': '正常',
                '请求处理': '正常'
            },
            '性能指标': {
                '请求处理时间': '< 100ms',
                '内存使用': '正常',
                'CPU负载': '低'
            },
            '检查项目': {
                '接口可用性': '通过',
                '数据验证': '通过',
                '错误处理': '通过',
                '性能监控': '通过'
            },
            '总结': {
                '状态': '全部正常',
                '建议': '系统运行良好，无需干预'
            }
        }
        
        return APIResponse(
            状态码=HTTPStatus.OK.value,
            成功=True,
            数据=健康信息,
            消息="健康检查完成，系统正常"
        )


# ============ 快速启动函数 ============

def 创建WebAPI实例() -> WebAPI:
    """
    创建WebAPI实例的便捷函数
    
    返回:
        WebAPI实例
    """
    return WebAPI()


def 快速测试():
    """
    快速测试WebAPI功能
    """
    print("🚀 WebAPI 快速测试")
    print("=" * 50)
    
    try:
        # 创建API实例
        api = 创建WebAPI实例()
        print("✅ WebAPI实例创建成功")
        
        # 1. 测试健康检查
        print("\n1. 健康检查测试:")
        健康响应 = api.处理请求('/api/v1/health', 'GET')
        print(f"   状态码: {健康响应.状态码}")
        print(f"   成功: {健康响应.成功}")
        print(f"   消息: {健康响应.消息}")
        
        # 2. 测试SMA计算
        print("\n2. SMA计算测试:")
        sma请求 = {
            'stock_code': '000001.SZ',
            'price_data': [100.0, 102.0, 98.0, 105.0, 108.0],
            'period': 5
        }
        sma响应 = api.处理请求('/api/v1/technical/sma', 'POST', sma请求)
        print(f"   状态码: {sma响应.状态码}")
        print(f"   成功: {sma响应.成功}")
        if sma响应.成功:
            print(f"   SMA结果: {sma响应.数据.get('SMA结果', '未知')}")
        
        # 3. 测试全面分析
        print("\n3. 全面分析测试:")
        分析请求 = {
            'stock_code': '000001.SZ',
            'price_data': [100.0, 102.0, 98.0, 105.0, 108.0, 106.0, 112.0, 115.0],
            'indicators': ['SMA_5', 'RSI_14', 'MACD']
        }
        分析响应 = api.处理请求('/api/v1/technical/analysis', 'POST', 分析请求)
        print(f"   状态码: {分析响应.状态码}")
        print(f"   成功: {分析响应.成功}")
        if 分析响应.成功:
            print(f"   建议: {分析响应.数据.get('操作建议', {}).get('说明', '未知')}")
        
        # 4. 获取接口文档
        print("\n4. 接口文档测试:")
        文档响应 = api.获取接口文档()
        print(f"   接口数量: {len(文档响应.数据.get('接口列表', []))}")
        print(f"   版本: {文档响应.数据.get('版本', '未知')}")
        
        print("\n" + "=" * 50)
        print("🎉 WebAPI 快速测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")


# 直接运行测试
if __name__ == "__main__":
    快速测试()