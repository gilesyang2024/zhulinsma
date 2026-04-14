#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据验证器
实现至少2个独立数据源的交叉验证和质量保证
"""

import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)

class DataSource(Enum):
    """数据源类型枚举"""
    TUSHARE_PRO = "Tushare Pro"  # Tushare专业版
    TENCENT_API = "Tencent API"  # 腾讯财经API
    SINA_FINANCE = "Sina Finance"  # 新浪财经
    EASTMONEY = "EastMoney"  # 东方财富
    YAHOO_FINANCE = "Yahoo Finance"  # 雅虎财经
    CUSTOM_SOURCE = "Custom Source"  # 自定义数据源

class ValidationLevel(Enum):
    """验证级别枚举"""
    CRITICAL = "critical"  # 关键验证，失败则数据不可用
    IMPORTANT = "important"  # 重要验证，失败需要警告
    NORMAL = "normal"  # 普通验证
    OPTIONAL = "optional"  # 可选验证

@dataclass
class ValidationResult:
    """验证结果"""
    validation_name: str
    validation_level: ValidationLevel
    passed: bool
    message: str
    details: Dict[str, Any]
    source_comparisons: Optional[List[Dict[str, Any]]] = None

@dataclass
class MultiSourceValidationResult:
    """多源验证结果"""
    stock_code: str
    timestamp: datetime
    sources_used: List[DataSource]
    validation_results: List[ValidationResult]
    consensus_score: float  # 0-1，表示数据源之间的一致性
    quality_score: float  # 0-100，总体质量评分
    is_reliable: bool  # 数据是否可靠
    recommendations: List[str]  # 改进建议

class MultiSourceDataValidator:
    """多源数据验证器"""
    
    def __init__(self, min_sources_required: int = 2):
        """
        初始化多源验证器
        
        Parameters:
        -----------
        min_sources_required : int
            至少需要的数据源数量，默认2个
        """
        self.min_sources_required = min_sources_required
        self.data_sources = []
        self.validation_history = []
        
        # 验证规则配置
        self.validation_rules = {
            'price_comparison': {
                'level': ValidationLevel.CRITICAL,
                'max_price_diff_pct': 0.05,  # 5%最大价格差异
                'required_fields': ['price', 'prev_close']
            },
            'volume_consistency': {
                'level': ValidationLevel.IMPORTANT,
                'max_volume_diff_pct': 0.20,  # 20%最大成交量差异
                'required_fields': ['volume']
            },
            'change_pct_consistency': {
                'level': ValidationLevel.IMPORTANT,
                'max_change_diff_pct': 0.02,  # 2%最大涨跌幅差异
                'required_fields': ['change_pct']
            },
            'data_completeness': {
                'level': ValidationLevel.CRITICAL,
                'required_fields': ['price', 'high', 'low', 'volume', 'amount']
            },
            'timestamp_freshness': {
                'level': ValidationLevel.CRITICAL,
                'max_age_minutes': 5,  # 数据最大年龄5分钟
                'required_fields': ['timestamp']
            }
        }
        
        logger.info(f"初始化多源数据验证器，最少需要 {min_sources_required} 个数据源")
    
    def add_data_source(self, source: DataSource, data: Dict[str, Any]):
        """添加数据源"""
        self.data_sources.append({
            'source': source,
            'data': data,
            'timestamp': datetime.now()
        })
        logger.info(f"添加数据源: {source.value}")
    
    def validate_multi_source_data(self, stock_code: str) -> MultiSourceValidationResult:
        """
        验证多源数据
        
        Parameters:
        -----------
        stock_code : str
            股票代码
            
        Returns:
        --------
        MultiSourceValidationResult: 多源验证结果
        """
        logger.info(f"开始多源数据验证: {stock_code}")
        
        if len(self.data_sources) < self.min_sources_required:
            error_msg = f"数据源不足: 需要 {self.min_sources_required} 个，实际 {len(self.data_sources)} 个"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        validation_results = []
        all_validations_passed = True
        
        # 1. 数据完整性验证
        completeness_result = self._validate_data_completeness()
        validation_results.append(completeness_result)
        if not completeness_result.passed:
            all_validations_passed = False
        
        # 2. 价格一致性验证
        price_result = self._validate_price_consistency()
        validation_results.append(price_result)
        if not price_result.passed and price_result.validation_level == ValidationLevel.CRITICAL:
            all_validations_passed = False
        
        # 3. 成交量一致性验证
        volume_result = self._validate_volume_consistency()
        validation_results.append(volume_result)
        if not volume_result.passed and volume_result.validation_level == ValidationLevel.CRITICAL:
            all_validations_passed = False
        
        # 4. 涨跌幅一致性验证
        change_result = self._validate_change_pct_consistency()
        validation_results.append(change_result)
        if not change_result.passed and change_result.validation_level == ValidationLevel.CRITICAL:
            all_validations_passed = False
        
        # 5. 时间戳新鲜度验证
        timestamp_result = self._validate_timestamp_freshness()
        validation_results.append(timestamp_result)
        if not timestamp_result.passed and timestamp_result.validation_level == ValidationLevel.CRITICAL:
            all_validations_passed = False
        
        # 计算一致性分数
        consensus_score = self._calculate_consensus_score(validation_results)
        
        # 计算总体质量分数
        quality_score = self._calculate_quality_score(validation_results)
        
        # 生成改进建议
        recommendations = self._generate_recommendations(validation_results)
        
        # 创建最终结果
        result = MultiSourceValidationResult(
            stock_code=stock_code,
            timestamp=datetime.now(),
            sources_used=[ds['source'] for ds in self.data_sources],
            validation_results=validation_results,
            consensus_score=consensus_score,
            quality_score=quality_score,
            is_reliable=all_validations_passed and consensus_score >= 0.8,
            recommendations=recommendations
        )
        
        # 记录到历史
        self.validation_history.append(result)
        
        logger.info(f"多源验证完成: {stock_code}, 一致性分数: {consensus_score:.2f}, 质量分数: {quality_score:.1f}, 是否可靠: {result.is_reliable}")
        
        return result
    
    def _validate_data_completeness(self) -> ValidationResult:
        """验证数据完整性"""
        missing_fields_all = []
        
        for source_info in self.data_sources:
            data = source_info['data']
            source = source_info['source']
            
            required_fields = self.validation_rules['data_completeness']['required_fields']
            missing_fields = [field for field in required_fields if field not in data or data[field] is None]
            
            if missing_fields:
                missing_fields_all.append({
                    'source': source.value,
                    'missing_fields': missing_fields
                })
        
        if missing_fields_all:
            message = f"发现数据缺失: {missing_fields_all}"
            passed = False
        else:
            message = "所有数据源数据完整"
            passed = True
        
        return ValidationResult(
            validation_name="data_completeness",
            validation_level=self.validation_rules['data_completeness']['level'],
            passed=passed,
            message=message,
            details={'missing_fields': missing_fields_all}
        )
    
    def _validate_price_consistency(self) -> ValidationResult:
        """验证价格一致性"""
        price_values = []
        source_comparisons = []
        
        for source_info in self.data_sources:
            data = source_info['data']
            source = source_info['source']
            
            if 'price' in data and data['price'] is not None:
                price_values.append(data['price'])
                source_comparisons.append({
                    'source': source.value,
                    'price': data['price']
                })
        
        if len(price_values) < 2:
            return ValidationResult(
                validation_name="price_consistency",
                validation_level=self.validation_rules['price_comparison']['level'],
                passed=True,  # 数据不足，跳过验证
                message="价格数据不足，无法进行一致性验证",
                details={'price_values': price_values},
                source_comparisons=source_comparisons
            )
        
        # 计算价格差异
        max_price = max(price_values)
        min_price = min(price_values)
        
        if max_price > 0:
            price_diff_pct = (max_price - min_price) / max_price
        else:
            price_diff_pct = 0
        
        max_allowed_diff = self.validation_rules['price_comparison']['max_price_diff_pct']
        
        if price_diff_pct <= max_allowed_diff:
            message = f"价格一致性良好，最大差异: {price_diff_pct:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = True
        else:
            message = f"价格差异过大，最大差异: {price_diff_pct:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = False
        
        return ValidationResult(
            validation_name="price_consistency",
            validation_level=self.validation_rules['price_comparison']['level'],
            passed=passed,
            message=message,
            details={
                'price_values': price_values,
                'max_price': max_price,
                'min_price': min_price,
                'price_diff_pct': price_diff_pct,
                'max_allowed_diff': max_allowed_diff
            },
            source_comparisons=source_comparisons
        )
    
    def _validate_volume_consistency(self) -> ValidationResult:
        """验证成交量一致性"""
        volume_values = []
        source_comparisons = []
        
        for source_info in self.data_sources:
            data = source_info['data']
            source = source_info['source']
            
            if 'volume' in data and data['volume'] is not None:
                volume_values.append(data['volume'])
                source_comparisons.append({
                    'source': source.value,
                    'volume': data['volume']
                })
        
        if len(volume_values) < 2:
            return ValidationResult(
                validation_name="volume_consistency",
                validation_level=self.validation_rules['volume_consistency']['level'],
                passed=True,  # 数据不足，跳过验证
                message="成交量数据不足，无法进行一致性验证",
                details={'volume_values': volume_values},
                source_comparisons=source_comparisons
            )
        
        # 计算成交量差异
        # 确保volume_values中的元素是标量或数组
        if all(isinstance(v, (int, float, np.number)) for v in volume_values):
            # 所有值都是标量
            max_volume = max(volume_values)
            min_volume = min(volume_values)
        else:
            # 包含数组，计算平均值进行比较
            avg_volumes = [np.mean(v) if isinstance(v, (np.ndarray, list)) else v for v in volume_values]
            max_volume = max(avg_volumes)
            min_volume = min(avg_volumes)
        
        if max_volume > 0:
            volume_diff_pct = (max_volume - min_volume) / max_volume
        else:
            volume_diff_pct = 0
        
        max_allowed_diff = self.validation_rules['volume_consistency']['max_volume_diff_pct']
        
        if volume_diff_pct <= max_allowed_diff:
            message = f"成交量一致性良好，最大差异: {volume_diff_pct:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = True
        else:
            message = f"成交量差异过大，最大差异: {volume_diff_pct:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = False
        
        return ValidationResult(
            validation_name="volume_consistency",
            validation_level=self.validation_rules['volume_consistency']['level'],
            passed=passed,
            message=message,
            details={
                'volume_values': volume_values,
                'max_volume': max_volume,
                'min_volume': min_volume,
                'volume_diff_pct': volume_diff_pct,
                'max_allowed_diff': max_allowed_diff
            },
            source_comparisons=source_comparisons
        )
    
    def _validate_change_pct_consistency(self) -> ValidationResult:
        """验证涨跌幅一致性"""
        change_values = []
        source_comparisons = []
        
        for source_info in self.data_sources:
            data = source_info['data']
            source = source_info['source']
            
            if 'change_pct' in data and data['change_pct'] is not None:
                change_values.append(data['change_pct'])
                source_comparisons.append({
                    'source': source.value,
                    'change_pct': data['change_pct']
                })
        
        if len(change_values) < 2:
            return ValidationResult(
                validation_name="change_pct_consistency",
                validation_level=self.validation_rules['change_pct_consistency']['level'],
                passed=True,  # 数据不足，跳过验证
                message="涨跌幅数据不足，无法进行一致性验证",
                details={'change_values': change_values},
                source_comparisons=source_comparisons
            )
        
        # 计算涨跌幅差异
        max_change = max(change_values)
        min_change = min(change_values)
        change_diff = abs(max_change - min_change)
        
        max_allowed_diff = self.validation_rules['change_pct_consistency']['max_change_diff_pct']
        
        if change_diff <= max_allowed_diff:
            message = f"涨跌幅一致性良好，最大差异: {change_diff:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = True
        else:
            message = f"涨跌幅差异过大，最大差异: {change_diff:.2%} (阈值: {max_allowed_diff:.0%})"
            passed = False
        
        return ValidationResult(
            validation_name="change_pct_consistency",
            validation_level=self.validation_rules['change_pct_consistency']['level'],
            passed=passed,
            message=message,
            details={
                'change_values': change_values,
                'max_change': max_change,
                'min_change': min_change,
                'change_diff': change_diff,
                'max_allowed_diff': max_allowed_diff
            },
            source_comparisons=source_comparisons
        )
    
    def _validate_timestamp_freshness(self) -> ValidationResult:
        """验证时间戳新鲜度"""
        now = datetime.now()
        freshness_results = []
        
        for source_info in self.data_sources:
            data = source_info['data']
            source = source_info['source']
            
            if 'timestamp' in data and data['timestamp']:
                try:
                    if isinstance(data['timestamp'], str):
                        data_time = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                    elif isinstance(data['timestamp'], datetime):
                        data_time = data['timestamp']
                    else:
                        data_time = source_info['timestamp']  # 使用添加时间
                    
                    age_minutes = (now - data_time).total_seconds() / 60
                    freshness_results.append({
                        'source': source.value,
                        'age_minutes': age_minutes,
                        'timestamp': data_time.isoformat()
                    })
                except Exception as e:
                    logger.warning(f"解析时间戳失败: {e}")
                    freshness_results.append({
                        'source': source.value,
                        'age_minutes': float('inf'),
                        'timestamp': 'unknown'
                    })
            else:
                freshness_results.append({
                    'source': source.value,
                    'age_minutes': float('inf'),
                    'timestamp': 'missing'
                })
        
        # 检查是否有过时数据
        max_allowed_age = self.validation_rules['timestamp_freshness']['max_age_minutes']
        stale_sources = [r for r in freshness_results if r['age_minutes'] > max_allowed_age]
        
        if stale_sources:
            stale_info = ', '.join([f"{r['source']}({r['age_minutes']:.1f}分钟)" for r in stale_sources])
            message = f"发现过时数据: {stale_info} (阈值: {max_allowed_age}分钟)"
            passed = False
        else:
            message = f"所有数据源都在 {max_allowed_age} 分钟内"
            passed = True
        
        return ValidationResult(
            validation_name="timestamp_freshness",
            validation_level=self.validation_rules['timestamp_freshness']['level'],
            passed=passed,
            message=message,
            details={
                'freshness_results': freshness_results,
                'max_allowed_age': max_allowed_age,
                'stale_sources': stale_sources
            }
        )
    
    def _calculate_consensus_score(self, validation_results: List[ValidationResult]) -> float:
        """计算一致性分数（0-1）"""
        if not validation_results:
            return 0.0
        
        # 加权计算一致性分数
        weights = {
            'price_consistency': 0.35,
            'volume_consistency': 0.25,
            'change_pct_consistency': 0.20,
            'data_completeness': 0.10,
            'timestamp_freshness': 0.10
        }
        
        total_weight = 0
        weighted_score = 0
        
        for result in validation_results:
            if result.validation_name in weights:
                weight = weights[result.validation_name]
                total_weight += weight
                
                # 根据验证结果计算分数
                if result.passed:
                    # 对于通过验证的，根据详情计算分数
                    details = result.details
                    if result.validation_name == 'price_consistency' and 'price_diff_pct' in details:
                        # 价格差异越小分数越高
                        max_allowed = details.get('max_allowed_diff', 0.05)
                        actual_diff = details.get('price_diff_pct', 0)
                        score = 1.0 - (actual_diff / max_allowed) if max_allowed > 0 else 1.0
                        weighted_score += weight * max(score, 0)
                    elif result.validation_name == 'timestamp_freshness' and 'freshness_results' in details:
                        # 时间越新鲜分数越高
                        max_age = details.get('max_allowed_age', 5)
                        ages = [r['age_minutes'] for r in details['freshness_results'] if r['age_minutes'] != float('inf')]
                        if ages:
                            avg_age = sum(ages) / len(ages)
                            score = 1.0 - (avg_age / max_age) if max_age > 0 else 1.0
                            weighted_score += weight * max(score, 0)
                        else:
                            weighted_score += weight * 0.5  # 未知时间给中等分数
                    else:
                        weighted_score += weight * 1.0
                else:
                    # 验证失败给0分
                    weighted_score += weight * 0.0
        
        if total_weight > 0:
            return weighted_score / total_weight
        else:
            return 0.0
    
    def _calculate_quality_score(self, validation_results: List[ValidationResult]) -> float:
        """计算总体质量分数（0-100）"""
        # 基本分数：所有验证都通过得100分
        base_score = 100
        
        # 根据验证结果扣分
        deductions = 0
        
        for result in validation_results:
            if not result.passed:
                # 根据验证级别扣分
                if result.validation_level == ValidationLevel.CRITICAL:
                    deductions += 30
                elif result.validation_level == ValidationLevel.IMPORTANT:
                    deductions += 15
                elif result.validation_level == ValidationLevel.NORMAL:
                    deductions += 5
                # OPTIONAL级别不扣分
        
        # 根据一致性分数调整
        consensus_score = self._calculate_consensus_score(validation_results)
        consensus_adjustment = (1.0 - consensus_score) * 20  # 一致性差最多扣20分
        
        final_score = base_score - deductions - consensus_adjustment
        
        return max(0, min(final_score, 100))
    
    def _generate_recommendations(self, validation_results: List[ValidationResult]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for result in validation_results:
            if not result.passed:
                if result.validation_name == 'data_completeness':
                    recommendations.append("增加数据源，确保所有必要字段都有数据")
                elif result.validation_name == 'price_consistency':
                    recommendations.append("检查价格数据源，选择更可靠的数据源")
                elif result.validation_name == 'volume_consistency':
                    recommendations.append("成交量数据差异较大，建议使用成交量加权平均")
                elif result.validation_name == 'change_pct_consistency':
                    recommendations.append("涨跌幅计算不一致，检查涨跌幅计算方法")
                elif result.validation_name == 'timestamp_freshness':
                    recommendations.append("更新数据获取频率，确保使用最新数据")
        
        # 如果没有问题，给出积极建议
        if not recommendations:
            recommendations.append("数据质量良好，继续保持当前验证策略")
        
        return recommendations
    
    def generate_validation_report(self, result: MultiSourceValidationResult) -> Dict:
        """生成验证报告"""
        report = {
            'stock_code': result.stock_code,
            'validation_time': result.timestamp.isoformat(),
            'sources_used': [s.value for s in result.sources_used],
            'consensus_score': result.consensus_score,
            'quality_score': result.quality_score,
            'is_reliable': result.is_reliable,
            'validation_summary': {
                'total_validations': len(result.validation_results),
                'passed_validations': sum(1 for r in result.validation_results if r.passed),
                'failed_validations': sum(1 for r in result.validation_results if not r.passed),
                'critical_issues': sum(1 for r in result.validation_results if not r.passed and r.validation_level == ValidationLevel.CRITICAL)
            },
            'detailed_results': [
                {
                    'validation_name': r.validation_name,
                    'validation_level': r.validation_level.value,
                    'passed': r.passed,
                    'message': r.message,
                    'details': r.details
                }
                for r in result.validation_results
            ],
            'recommendations': result.recommendations
        }
        
        return report
    
    def save_report_to_file(self, result: MultiSourceValidationResult, filename: str = None):
        """保存验证报告到文件"""
        if filename is None:
            filename = f"zhulinsma_multisource_validation_{result.stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = self.generate_validation_report(result)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"多源验证报告已保存到: {filename}")
        return filename
    
    def get_validation_history(self) -> List[MultiSourceValidationResult]:
        """获取验证历史"""
        return self.validation_history
    
    def clear_validation_history(self):
        """清空验证历史"""
        self.validation_history = []
        logger.info("验证历史已清空")


# 使用示例
def example_usage():
    """多源数据验证示例"""
    print("=" * 60)
    print("Zhulinsma多源数据验证系统示例")
    print("=" * 60)
    
    # 创建验证器
    validator = MultiSourceDataValidator(min_sources_required=2)
    
    # 模拟不同数据源的数据
    # 数据源1: Tushare Pro
    tushare_data = {
        'price': 10.94,
        'prev_close': 10.88,
        'high': 11.02,
        'low': 10.85,
        'volume': 74123456,
        'amount': 809740000,
        'change_pct': 0.55,
        'timestamp': datetime.now().isoformat()
    }
    
    # 数据源2: 腾讯财经API
    tencent_data = {
        'price': 10.92,  # 轻微差异
        'prev_close': 10.88,
        'high': 11.01,
        'low': 10.84,
        'volume': 73000000,  # 轻微差异
        'amount': 800000000,
        'change_pct': 0.37,  # 轻微差异
        'timestamp': (datetime.now() - timedelta(minutes=2)).isoformat()
    }
    
    # 添加数据源
    print("\n1. 添加数据源...")
    validator.add_data_source(DataSource.TUSHARE_PRO, tushare_data)
    validator.add_data_source(DataSource.TENCENT_API, tencent_data)
    
    # 执行验证
    print("\n2. 执行多源数据验证...")
    try:
        result = validator.validate_multi_source_data("000001.SZ")
        
        # 生成报告
        print("\n3. 生成验证报告...")
        report = validator.generate_validation_report(result)
        
        print(f"\n股票代码: {report['stock_code']}")
        print(f"使用数据源: {', '.join(report['sources_used'])}")
        print(f"一致性分数: {report['consensus_score']:.3f}")
        print(f"质量分数: {report['quality_score']:.1f}/100")
        print(f"数据是否可靠: {'是' if report['is_reliable'] else '否'}")
        
        print(f"\n验证摘要:")
        summary = report['validation_summary']
        print(f"  总验证数: {summary['total_validations']}")
        print(f"  通过数: {summary['passed_validations']}")
        print(f"  失败数: {summary['failed_validations']}")
        print(f"  关键问题: {summary['critical_issues']}")
        
        print(f"\n详细结果:")
        for validation in report['detailed_results']:
            status = "✅ 通过" if validation['passed'] else "❌ 失败"
            print(f"  {validation['validation_name']} ({validation['validation_level']}): {status}")
            print(f"    信息: {validation['message']}")
        
        print(f"\n改进建议:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
        
        # 保存报告
        print("\n4. 保存验证报告...")
        report_file = validator.save_report_to_file(result)
        print(f"报告已保存到: {report_file}")
        
    except ValueError as e:
        print(f"验证失败: {e}")
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    example_usage()