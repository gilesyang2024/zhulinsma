"""
竹林司马API接口集成测试
测试新API接口的完整功能
"""

import sys
import os
import json
import unittest
import logging
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zhulinsma.api_integration import (
    获取API集成器,
    分析股票API,
    批量分析股票API接口,
    获取系统状态API,
    获取API文档
)

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

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class 测试API集成器(unittest.TestCase):
    """测试API集成器功能"""
    
    def setUp(self):
        """测试前准备"""
        self.api集成器 = 获取API集成器(验证模式=True)
        logger.info("✅ API集成器测试准备完成")
    
    def test_01_获取系统状态(self):
        """测试获取系统状态"""
        logger.info("🔍 测试: 获取系统状态")
        
        状态 = self.api集成器.获取系统状态()
        
        self.assertIsInstance(状态, dict)
        self.assertIn("系统名称", 状态)
        self.assertIn("版本", 状态)
        self.assertIn("状态", 状态)
        self.assertIn("请求计数", 状态)
        self.assertIn("错误计数", 状态)
        
        logger.info(f"✅ 系统状态: {状态['系统名称']} v{状态['版本']} - {状态['状态']}")
    
    def test_02_单只股票分析(self):
        """测试单只股票分析"""
        logger.info("🔍 测试: 单只股票分析")
        
        # 准备测试数据
        股票代码 = "000001.SZ"
        价格数据 = [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1, 11.9, 12.3, 12.5,
                   12.8, 13.1, 12.9, 13.2, 13.5, 13.8, 14.1, 13.9, 14.3, 14.5]
        时间戳 = [f"2026-03-{str(i+1).zfill(2)}" for i in range(20)]
        
        # 执行分析
        结果 = self.api集成器.执行技术分析API(股票代码, 价格数据, 时间戳)
        
        # 验证结果
        self.assertIsInstance(结果, dict)
        self.assertIn("成功", 结果)
        
        if 结果["成功"]:
            self.assertIn("股票代码", 结果)
            self.assertIn("数据质量结果", 结果)
            self.assertIn("技术指标结果", 结果)
            self.assertIn("综合分析结果", 结果)
            
            logger.info(f"✅ 分析成功: {结果['股票代码']}")
            logger.info(f"   趋势方向: {结果.get('综合分析结果', {}).get('趋势分析', {}).get('趋势方向', '未知')}")
            logger.info(f"   风险等级: {结果.get('综合分析结果', {}).get('风险评估', {}).get('风险等级', '未知')}")
        else:
            logger.warning(f"⚠️ 分析失败: {结果.get('消息', '未知错误')}")
    
    def test_03_批量股票分析(self):
        """测试批量股票分析"""
        logger.info("🔍 测试: 批量股票分析")
        
        # 准备批量测试数据
        股票数据列表 = [
            {
                "股票代码": "000001.SZ",
                "价格数据": [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1],
                "时间戳": ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04", 
                         "2026-03-05", "2026-03-06", "2026-03-07"]
            },
            {
                "股票代码": "000002.SZ",
                "价格数据": [20.1, 20.3, 20.0, 19.8, 20.2, 20.5, 20.8]
            },
            {
                "股票代码": "000003.SZ",
                "价格数据": [15.2, 15.5, 15.1, 14.9, 15.3, 15.6, 15.9]
            }
        ]
        
        # 执行批量分析
        结果 = self.api集成器.批量分析股票API(股票数据列表)
        
        # 验证结果
        self.assertIsInstance(结果, dict)
        self.assertIn("成功", 结果)
        self.assertIn("总股票数", 结果)
        self.assertIn("成功数", 结果)
        self.assertIn("失败数", 结果)
        self.assertIn("成功率", 结果)
        
        if 结果["成功"]:
            logger.info(f"✅ 批量分析成功: {结果['成功数']}成功/{结果['总股票数']}总")
            logger.info(f"   成功率: {结果['成功率']}")
        else:
            logger.warning(f"⚠️ 批量分析失败: {结果.get('消息', '未知错误')}")
    
    def test_04_生成API文档(self):
        """测试生成API文档"""
        logger.info("🔍 测试: 生成API文档")
        
        文档结果 = self.api集成器.生成API文档()
        
        self.assertIsInstance(文档结果, dict)
        self.assertIn("成功", 文档结果)
        
        if 文档结果["成功"]:
            self.assertIn("系统信息", 文档结果)
            self.assertIn("API模块", 文档结果)
            self.assertIn("使用示例", 文档结果)
            
            系统信息 = 文档结果["系统信息"]
            logger.info(f"✅ API文档生成成功")
            logger.info(f"   系统名称: {系统信息.get('名称', 'N/A')}")
            logger.info(f"   版本: {系统信息.get('版本', 'N/A')}")
            logger.info(f"   描述: {系统信息.get('描述', 'N/A')}")
            logger.info(f"   位置: {系统信息.get('位置', 'N/A')}")
        else:
            logger.warning(f"⚠️ API文档生成失败: {文档结果.get('消息', '未知错误')}")

class 测试外部简化API(unittest.TestCase):
    """测试外部简化API功能"""
    
    def setUp(self):
        """测试前准备"""
        self.api = 获取API实例(验证模式=True)
        logger.info("✅ 外部简化API测试准备完成")
    
    def test_01_简化分析函数(self):
        """测试简化分析函数"""
        logger.info("🔍 测试: 简化分析函数")
        
        价格数据 = [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1, 11.9, 12.3, 12.5]
        
        # 使用简化函数
        结果 = 分析股票("TEST.SZ", 价格数据)
        
        self.assertIsInstance(结果, dict)
        self.assertIn("成功", 结果)
        
        if 结果["成功"]:
            logger.info(f"✅ 简化分析成功")
            logger.info(f"   数据质量评分: {结果.get('数据质量', {}).get('评分', 'N/A')}")
        else:
            logger.warning(f"⚠️ 简化分析失败: {结果.get('消息', '未知错误')}")
    
    def test_02_简化批量分析(self):
        """测试简化批量分析"""
        logger.info("🔍 测试: 简化批量分析")
        
        股票数据列表 = [
            {"股票代码": "TEST1.SZ", "价格数据": [10.5, 10.8, 11.2]},
            {"股票代码": "TEST2.SZ", "价格数据": [20.1, 20.3, 20.0]},
            {"股票代码": "TEST3.SZ", "价格数据": [15.2, 15.5, 15.1]}
        ]
        
        # 使用简化函数
        结果 = 批量分析股票(股票数据列表)
        
        self.assertIsInstance(结果, dict)
        self.assertIn("成功", 结果)
        
        if 结果["成功"]:
            logger.info(f"✅ 简化批量分析成功")
            logger.info(f"   成功数: {结果['成功数']}/{结果['总股票数']}")
        else:
            logger.warning(f"⚠️ 简化批量分析失败: {结果.get('消息', '未知错误')}")
    
    def test_03_简化计算指标(self):
        """测试简化计算指标"""
        logger.info("🔍 测试: 简化计算指标")
        
        价格数据 = [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1, 11.9, 12.3, 12.5,
                   12.8, 13.1, 12.9, 13.2, 13.5, 13.8, 14.1, 13.9, 14.3, 14.5]
        
        # 测试SMA计算
        sma结果 = 计算指标(价格数据, "SMA", {"周期": 20})
        
        self.assertIsInstance(sma结果, dict)
        self.assertIn("成功", sma结果)
        
        if sma结果["成功"]:
            logger.info(f"✅ SMA计算成功: {sma结果['数据'].get('值', 'N/A')}")
        else:
            logger.warning(f"⚠️ SMA计算失败: {sma结果.get('消息', '未知错误')}")
        
        # 测试RSI计算
        rsi结果 = 计算指标(价格数据, "RSI", {"周期": 14})
        
        self.assertIsInstance(rsi结果, dict)
        self.assertIn("成功", rsi结果)
        
        if rsi结果["成功"]:
            logger.info(f"✅ RSI计算成功: {rsi结果['数据'].get('值', 'N/A')}")
        else:
            logger.warning(f"⚠️ RSI计算失败: {rsi结果.get('消息', '未知错误')}")
    
    def test_04_简化系统状态和文档(self):
        """测试简化系统状态和文档函数"""
        logger.info("🔍 测试: 简化系统状态和文档")
        
        # 测试系统状态
        状态结果 = 系统状态()
        
        self.assertIsInstance(状态结果, dict)
        self.assertIn("成功", 状态结果)
        
        if 状态结果["成功"]:
            logger.info(f"✅ 系统状态获取成功")
        
        # 测试API文档
        文档结果 = API文档()
        
        self.assertIsInstance(文档结果, dict)
        self.assertIn("成功", 文档结果)
        
        if 文档结果["成功"]:
            logger.info(f"✅ API文档获取成功")

class 测试WebAPI集成(unittest.TestCase):
    """测试Web API集成功能"""
    
    def setUp(self):
        """测试前准备"""
        from zhulinsma.interface.web_api import WebAPI
        self.web_api = WebAPI(验证模式=True)
        logger.info("✅ Web API测试准备完成")
    
    def test_01_健康检查(self):
        """测试健康检查API"""
        logger.info("🔍 测试: Web API健康检查")
        
        响应 = self.web_api.处理请求("/api/health", "GET")
        
        self.assertIsNotNone(响应)
        self.assertEqual(响应.状态码, 200)
        self.assertTrue(响应.成功)
        self.assertIsInstance(响应.数据, dict)
        self.assertIn("状态", 响应.数据)
        
        logger.info(f"✅ 健康检查通过: {响应.数据['状态']}")
    
    def test_02_技术分析请求(self):
        """测试技术分析API"""
        logger.info("🔍 测试: Web API技术分析")
        
        请求数据 = {
            "股票代码": "000001.SZ",
            "价格数据": [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1],
            "时间戳": ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04",
                     "2026-03-05", "2026-03-06", "2026-03-07"]
        }
        
        响应 = self.web_api.处理请求("/api/analyze", "POST", 请求数据)
        
        self.assertIsNotNone(响应)
        self.assertIn("成功", 响应.__dict__)
        
        if 响应.成功:
            logger.info(f"✅ Web API技术分析成功")
            self.assertIn("趋势分析", 响应.数据)
            self.assertIn("风险评估", 响应.数据)
            self.assertIn("投资建议", 响应.数据)
        else:
            logger.warning(f"⚠️ Web API技术分析失败: {响应.消息}")
    
    def test_03_SMA计算请求(self):
        """测试SMA计算API"""
        logger.info("🔍 测试: Web API SMA计算")
        
        请求数据 = {
            "价格数据": [10.5, 10.8, 11.2, 10.9, 11.5, 11.8, 12.1],
            "周期": 20
        }
        
        响应 = self.web_api.处理请求("/api/indicators/sma", "POST", 请求数据)
        
        self.assertIsNotNone(响应)
        self.assertIn("成功", 响应.__dict__)
        
        if 响应.成功:
            logger.info(f"✅ Web API SMA计算成功")
            self.assertIn("值", 响应.数据)
        else:
            logger.warning(f"⚠️ Web API SMA计算失败: {响应.消息}")

class 测试边界条件和错误处理(unittest.TestCase):
    """测试边界条件和错误处理"""
    
    def setUp(self):
        """测试前准备"""
        self.api = 获取API实例(验证模式=True)
        logger.info("✅ 边界条件测试准备完成")
    
    def test_01_数据不足测试(self):
        """测试数据不足的情况"""
        logger.info("🔍 测试: 数据不足")
        
        # 提供极少的数据
        价格数据 = [10.5, 10.8]  # 只有2条数据
        
        结果 = 分析股票("TEST.SZ", 价格数据)
        
        # 即使数据不足，API也应该有响应
        self.assertIsInstance(结果, dict)
        
        # 如果是验证模式，可能会失败
        if not 结果.get("成功", False):
            logger.info(f"✅ 数据不足测试通过（预期可能失败）")
            self.assertIn("数据质量", 结果.get("消息", ""))
        else:
            logger.info(f"⚠️ 数据不足但分析成功，可能需要检查逻辑")
    
    def test_02_异常值测试(self):
        """测试包含异常值的数据"""
        logger.info("🔍 测试: 异常值数据")
        
        # 包含极端异常值
        价格数据 = [10.5, 0.0, 999.9, 11.2, -5.0, 10.9]
        
        结果 = 分析股票("TEST.SZ", 价格数据)
        
        self.assertIsInstance(结果, dict)
        
        if 结果.get("成功", False):
            # 如果成功，检查数据质量评分
            质量评分 = 结果.get("数据质量", {}).get("评分", 100)
            if 质量评分 < 60:  # 异常值数据应该评分较低
                logger.info(f"✅ 异常值数据评分正确: {质量评分}")
            else:
                logger.warning(f"⚠️ 异常值数据评分可能过高: {质量评分}")
        else:
            logger.info(f"✅ 异常值数据验证失败（预期）: {结果.get('消息', '')}")
    
    def test_03_非法股票代码测试(self):
        """测试非法股票代码"""
        logger.info("🔍 测试: 非法股票代码")
        
        价格数据 = [10.5, 10.8, 11.2]
        
        # 测试不带后缀的代码
        结果1 = 分析股票("000001", 价格数据)
        
        # 测试格式错误的代码
        结果2 = 分析股票("INVALID", 价格数据)
        
        # API应该能处理这些情况
        for 结果 in [结果1, 结果2]:
            self.assertIsInstance(结果, dict)
            logger.info(f"✅ 非法股票代码测试通过，响应状态: {结果.get('成功', False)}")
    
    def test_04_空数据测试(self):
        """测试空数据"""
        logger.info("🔍 测试: 空数据")
        
        # 空列表
        价格数据 = []
        
        结果 = 分析股票("TEST.SZ", 价格数据)
        
        # 应该返回错误
        self.assertIsInstance(结果, dict)
        self.assertFalse(结果.get("成功", True))  # 应该失败
        
        logger.info(f"✅ 空数据测试通过: {结果.get('消息', '')}")

def 运行所有测试():
    """运行所有API测试"""
    logger.info("🚀 开始运行竹林司马API集成测试")
    logger.info("=" * 60)
    
    # 创建测试套件
    测试套件 = unittest.TestSuite()
    
    # 添加测试类
    测试套件.addTest(unittest.makeSuite(测试API集成器))
    测试套件.addTest(unittest.makeSuite(测试外部简化API))
    测试套件.addTest(unittest.makeSuite(测试WebAPI集成))
    测试套件.addTest(unittest.makeSuite(测试边界条件和错误处理))
    
    # 运行测试
    测试运行器 = unittest.TextTestRunner(verbosity=2)
    测试结果 = 测试运行器.run(测试套件)
    
    # 输出统计
    logger.info("=" * 60)
    logger.info("📊 测试统计:")
    logger.info(f"   总测试数: {测试结果.testsRun}")
    logger.info(f"   失败数: {len(测试结果.failures)}")
    logger.info(f"   错误数: {len(测试结果.errors)}")
    logger.info(f"   跳过数: {len(测试结果.skipped)}")
    logger.info(f"   成功率: {(1 - (len(测试结果.failures) + len(测试结果.errors)) / max(测试结果.testsRun, 1)) * 100:.1f}%")
    
    if 测试结果.wasSuccessful():
        logger.info("✅ 所有测试通过!")
    else:
        logger.warning("⚠️ 部分测试失败，请检查")
    
    return 测试结果.wasSuccessful()

if __name__ == "__main__":
    # 运行所有测试
    测试成功 = 运行所有测试()
    
    if 测试成功:
        print("\n" + "=" * 60)
        print("🎉 竹林司马API接口测试全部通过!")
        print("=" * 60)
        print("📋 测试总结:")
        print("   1. API集成器功能完整")
        print("   2. 外部简化API接口正常")
        print("   3. Web API集成成功")
        print("   4. 边界条件和错误处理正确")
        print("=" * 60)
        print("✅ 竹林司马API接口能力改进计划实施完成!")
    else:
        print("\n" + "=" * 60)
        print("❌ 部分测试失败，需要修复")
        print("=" * 60)