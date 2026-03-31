"""
竹林司马 - 为杨总定制的技术分析工具
广州优化，双重验证，模块化架构
"""

__version__ = "2.0.0"
__author__ = "竹林司马 Team"
__email__ = "zhulinsma@example.com"

# 标准的中英文名称定义
ZH_CHINESE_NAME = "竹林司马"
ZH_ENGLISH_NAME = "Zhulinsma"
ZH_FULL_NAME = f"{ZH_CHINESE_NAME} ({ZH_ENGLISH_NAME})"

# 导入核心模块
from zhulinsma.core.data import *
from zhulinsma.core.indicators import *
from zhulinsma.core.analysis import *
from zhulinsma.utils import *

# 导入API接口
from zhulinsma.interface import *
from zhulinsma.external_api import (
    竹林司马API,
    获取API实例,
    分析股票,
    批量分析股票,
    计算指标,
    验证数据,
    系统状态,
    API文档
)

# 向后兼容的旧版本类
class 竹林司马:
    """竹林司马主类 - 向后兼容接口"""
    
    def __init__(self, 验证模式=True):
        """初始化竹林司马分析器"""
        self.验证模式 = 验证模式
        print(f"🔄 竹林司马 2.0 初始化完成")
        print(f"   模块化架构版本")
        print(f"   位置: 广州")
    
    def 技术分析综合(self, 股票数据, 股票代码='未知'):
        """综合技术分析（兼容旧版本）"""
        # 使用新的API接口
        from zhulinsma.interface.analysis_api import AnalysisAPI
        api = AnalysisAPI(验证模式=self.验证模式)
        return api.执行技术分析(股票代码, 股票数据)
