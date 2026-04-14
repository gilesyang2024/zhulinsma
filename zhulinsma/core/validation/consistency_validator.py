#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一致性验证器
检查数据内部一致性、跨时间一致性和业务逻辑一致性
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class ConsistencyIssue(Enum):
    """一致性验证问题类型"""
    PRICE_RANGE_VIOLATION = "price_range_violation"  # 价格范围违规
    VOLUME_PRICE_CONSISTENCY = "volume_price_consistency"  # 成交量价格一致性
    TIMESERIES_CONSISTENCY = "timeseries_consistency"  # 时间序列一致性
    BUSINESS_LOGIC_CONSISTENCY = "business_logic_consistency"  # 业务逻辑一致性
    CROSS_FIELD_CONSISTENCY = "cross_field_consistency"  # 跨字段一致性

@dataclass
class ConsistencyCheckResult:
    """一致性检查结果"""
    check_name: str
    issue_type: ConsistencyIssue
    passed: bool
    severity: str  # high, medium, low
    message: str
    details: Dict[str, Any]
    affected_records: Optional[List[int]] = None

@dataclass
class ConsistencyValidationReport:
    """一致性验证报告"""
    data_source: str
    timestamp: datetime
    total_checks: int
    passed_checks: int
    failed_checks: int
    check_results: List[ConsistencyCheckResult]
    overall_consistency_score: float  # 0-100
    recommendations: List[str]

class ConsistencyValidator:
    """一致性验证器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化一致性验证器
        
        Parameters:
        -----------
        config : Dict
            配置参数，包括各种一致性检查的规则
        """
        self.config = config or self._get_default_config()
        self.validation_history = []
        
        logger.info("初始化一致性验证器")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'price_range': {
                'min_price': 0.01,  # 最低价格
                'max_price': 10000,  # 最高价格
                'daily_change_limit': 0.50,  # 日涨跌幅限制
                'intraday_volatility_limit': 0.20  # 日内波动限制
            },
            'volume_price_consistency': {
                'min_volume_price_ratio': 0.000001,  # 最小成交量/价格比率
                'max_volume_price_ratio': 100,  # 最大成交量/价格比率
                'volume_amount_consistency': True  # 检查成交量与成交额一致性
            },
            'timeseries_consistency': {
                'max_gap_days': 7,  # 最大时间间隔（天）
                'allow_future_dates': False,
                'require_chronological_order': True
            },
            'business_logic': {
                'high_low_relation': True,  # 检查最高价>最低价
                'open_close_range': True,  # 检查开盘收盘价在最高最低之间
                'price_trend_consistency': True  # 检查价格趋势一致性
            }
        }
    
    def validate_consistency(self, data: pd.DataFrame, data_source: str = "unknown") -> ConsistencyValidationReport:
        """
        验证数据一致性
        
        Parameters:
        -----------
        data : pd.DataFrame
            待验证的数据
        data_source : str
            数据源名称
            
        Returns:
        --------
        ConsistencyValidationReport: 一致性验证报告
        """
        logger.info(f"开始一致性验证: {data_source}")
        
        check_results = []
        
        # 1. 价格范围检查
        price_range_result = self._check_price_range(data)
        check_results.append(price_range_result)
        
        # 2. 成交量价格一致性检查
        volume_price_result = self._check_volume_price_consistency(data)
        check_results.append(volume_price_result)
        
        # 3. 时间序列一致性检查
        timeseries_result = self._check_timeseries_consistency(data)
        check_results.append(timeseries_result)
        
        # 4. 业务逻辑一致性检查
        business_logic_result = self._check_business_logic_consistency(data)
        check_results.append(business_logic_result)
        
        # 5. 跨字段一致性检查
        cross_field_result = self._check_cross_field_consistency(data)
        check_results.append(cross_field_result)
        
        # 计算统计信息
        total_checks = len(check_results)
        passed_checks = sum(1 for r in check_results if r.passed)
        failed_checks = total_checks - passed_checks
        
        # 计算总体一致性分数
        overall_score = self._calculate_overall_score(check_results)
        
        # 生成改进建议
        recommendations = self._generate_recommendations(check_results)
        
        # 创建报告
        report = ConsistencyValidationReport(
            data_source=data_source,
            timestamp=datetime.now(),
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            check_results=check_results,
            overall_consistency_score=overall_score,
            recommendations=recommendations
        )
        
        # 记录历史
        self.validation_history.append(report)
        
        logger.info(f"一致性验证完成: {data_source}, 总体分数: {overall_score:.1f}, 通过检查: {passed_checks}/{total_checks}")
        
        return report
    
    def _check_price_range(self, data: pd.DataFrame) -> ConsistencyCheckResult:
        """检查价格范围"""
        issues = []
        affected_records = []
        
        if 'price' not in data.columns:
            return ConsistencyCheckResult(
                check_name="price_range_check",
                issue_type=ConsistencyIssue.PRICE_RANGE_VIOLATION,
                passed=True,
                severity="info",
                message="价格字段不存在，跳过价格范围检查",
                details={'missing_field': 'price'},
                affected_records=[]
            )
        
        price_data = data['price'].dropna()
        
        # 检查价格是否在合理范围内
        min_allowed = self.config['price_range']['min_price']
        max_allowed = self.config['price_range']['max_price']
        
        low_price_records = price_data[price_data < min_allowed]
        high_price_records = price_data[price_data > max_allowed]
        
        if len(low_price_records) > 0:
            issues.append(f"{len(low_price_records)} 条记录价格低于 {min_allowed}")
            affected_records.extend(low_price_records.index.tolist())
        
        if len(high_price_records) > 0:
            issues.append(f"{len(high_price_records)} 条记录价格高于 {max_allowed}")
            affected_records.extend(high_price_records.index.tolist())
        
        # 检查日涨跌幅
        if 'prev_close' in data.columns and 'price' in data.columns:
            price_change = data['price'] / data['prev_close'] - 1
            extreme_changes = price_change[np.abs(price_change) > self.config['price_range']['daily_change_limit']]
            
            if len(extreme_changes) > 0:
                issues.append(f"{len(extreme_changes)} 条记录日涨跌幅超过 {self.config['price_range']['daily_change_limit']:.0%}")
                affected_records.extend(extreme_changes.index.tolist())
        
        if issues:
            return ConsistencyCheckResult(
                check_name="price_range_check",
                issue_type=ConsistencyIssue.PRICE_RANGE_VIOLATION,
                passed=False,
                severity="high",
                message=f"价格范围问题: {'; '.join(issues)}",
                details={
                    'issues': issues,
                    'min_allowed': min_allowed,
                    'max_allowed': max_allowed,
                    'daily_change_limit': self.config['price_range']['daily_change_limit']
                },
                affected_records=affected_records
            )
        else:
            return ConsistencyCheckResult(
                check_name="price_range_check",
                issue_type=ConsistencyIssue.PRICE_RANGE_VIOLATION,
                passed=True,
                severity="info",
                message="价格范围检查通过，所有价格在合理范围内",
                details={
                    'min_allowed': min_allowed,
                    'max_allowed': max_allowed,
                    'daily_change_limit': self.config['price_range']['daily_change_limit']
                }
            )
    
    def _check_volume_price_consistency(self, data: pd.DataFrame) -> ConsistencyCheckResult:
        """检查成交量价格一致性"""
        issues = []
        affected_records = []
        
        required_fields = ['volume', 'price']
        missing_fields = [f for f in required_fields if f not in data.columns]
        
        if missing_fields:
            return ConsistencyCheckResult(
                check_name="volume_price_consistency_check",
                issue_type=ConsistencyIssue.VOLUME_PRICE_CONSISTENCY,
                passed=True,
                severity="info",
                message=f"缺失必要字段: {missing_fields}，跳过成交量价格一致性检查",
                details={'missing_fields': missing_fields}
            )
        
        volume = data['volume'].dropna()
        price = data['price'].dropna()
        
        # 计算成交量/价格比率
        if len(volume) > 0 and len(price) > 0:
            # 对齐数据
            common_index = volume.index.intersection(price.index)
            volume_aligned = volume.loc[common_index]
            price_aligned = price.loc[common_index]
            
            # 避免除以零
            valid_price = price_aligned[price_aligned > 0]
            valid_volume = volume_aligned.loc[valid_price.index]
            
            if len(valid_volume) > 0:
                volume_price_ratio = valid_volume / valid_price
                
                min_ratio = self.config['volume_price_consistency']['min_volume_price_ratio']
                max_ratio = self.config['volume_price_consistency']['max_volume_price_ratio']
                
                low_ratio_records = volume_price_ratio[volume_price_ratio < min_ratio]
                high_ratio_records = volume_price_ratio[volume_price_ratio > max_ratio]
                
                if len(low_ratio_records) > 0:
                    issues.append(f"{len(low_ratio_records)} 条记录成交量/价格比率过低 (< {min_ratio})")
                    affected_records.extend(low_ratio_records.index.tolist())
                
                if len(high_ratio_records) > 0:
                    issues.append(f"{len(high_ratio_records)} 条记录成交量/价格比率过高 (> {max_ratio})")
                    affected_records.extend(high_ratio_records.index.tolist())
        
        # 检查成交量与成交额一致性
        if self.config['volume_price_consistency']['volume_amount_consistency'] and 'amount' in data.columns:
            amount = data['amount'].dropna()
            common_index = volume.index.intersection(amount.index)
            
            if len(common_index) > 0:
                volume_amount_ratio = amount.loc[common_index] / volume.loc[common_index]
                
                # 成交量应该近似等于成交额/价格
                if 'price' in data.columns:
                    price_at_common = data.loc[common_index, 'price']
                    expected_ratio = price_at_common
                    
                    # 计算差异百分比
                    ratio_diff = np.abs(volume_amount_ratio - expected_ratio) / expected_ratio
                    large_diff_records = ratio_diff[ratio_diff > 0.1]  # 10%差异阈值
                    
                    if len(large_diff_records) > 0:
                        issues.append(f"{len(large_diff_records)} 条记录成交量与成交额不一致")
                        affected_records.extend(large_diff_records.index.tolist())
        
        if issues:
            return ConsistencyCheckResult(
                check_name="volume_price_consistency_check",
                issue_type=ConsistencyIssue.VOLUME_PRICE_CONSISTENCY,
                passed=False,
                severity="medium",
                message=f"成交量价格一致性问题: {'; '.join(issues)}",
                details={'issues': issues},
                affected_records=affected_records
            )
        else:
            return ConsistencyCheckResult(
                check_name="volume_price_consistency_check",
                issue_type=ConsistencyIssue.VOLUME_PRICE_CONSISTENCY,
                passed=True,
                severity="info",
                message="成交量价格一致性检查通过",
                details={}
            )
    
    def _check_timeseries_consistency(self, data: pd.DataFrame) -> ConsistencyCheckResult:
        """检查时间序列一致性"""
        issues = []
        affected_records = []
        
        if 'timestamp' not in data.columns:
            return ConsistencyCheckResult(
                check_name="timeseries_consistency_check",
                issue_type=ConsistencyIssue.TIMESERIES_CONSISTENCY,
                passed=True,
                severity="info",
                message="时间戳字段不存在，跳过时间序列一致性检查",
                details={'missing_field': 'timestamp'}
            )
        
        # 转换时间戳
        try:
            if data['timestamp'].dtype == 'object':
                timestamps = pd.to_datetime(data['timestamp'], errors='coerce')
            else:
                timestamps = data['timestamp']
            
            # 检查未来时间戳
            if not self.config['timeseries_consistency']['allow_future_dates']:
                future_timestamps = timestamps[timestamps > pd.Timestamp.now()]
                if len(future_timestamps) > 0:
                    issues.append(f"{len(future_timestamps)} 条记录时间戳在未来")
                    affected_records.extend(future_timestamps.index.tolist())
            
            # 检查时间顺序
            if self.config['timeseries_consistency']['require_chronological_order']:
                time_diff = timestamps.diff()
                non_chronological = timestamps[time_diff < pd.Timedelta(0)]
                if len(non_chronological) > 0:
                    issues.append(f"{len(non_chronological)} 条记录时间顺序错误")
                    affected_records.extend(non_chronological.index.tolist())
            
            # 检查时间间隔
            if len(timestamps) > 1:
                time_gaps = timestamps.diff().dropna()
                max_gap_days = self.config['timeseries_consistency']['max_gap_days']
                
                large_gaps = time_gaps[time_gaps > pd.Timedelta(days=max_gap_days)]
                if len(large_gaps) > 0:
                    issues.append(f"{len(large_gaps)} 处时间间隔超过 {max_gap_days} 天")
                    affected_records.extend(large_gaps.index.tolist())
        
        except Exception as e:
            issues.append(f"时间戳处理失败: {str(e)}")
        
        if issues:
            return ConsistencyCheckResult(
                check_name="timeseries_consistency_check",
                issue_type=ConsistencyIssue.TIMESERIES_CONSISTENCY,
                passed=False,
                severity="medium",
                message=f"时间序列一致性问题: {'; '.join(issues)}",
                details={'issues': issues},
                affected_records=affected_records
            )
        else:
            return ConsistencyCheckResult(
                check_name="timeseries_consistency_check",
                issue_type=ConsistencyIssue.TIMESERIES_CONSISTENCY,
                passed=True,
                severity="info",
                message="时间序列一致性检查通过",
                details={}
            )
    
    def _check_business_logic_consistency(self, data: pd.DataFrame) -> ConsistencyCheckResult:
        """检查业务逻辑一致性"""
        issues = []
        affected_records = []
        
        checks = self.config['business_logic']
        
        # 检查最高价>最低价
        if checks['high_low_relation'] and 'high' in data.columns and 'low' in data.columns:
            invalid_high_low = data[data['high'] < data['low']]
            if len(invalid_high_low) > 0:
                issues.append(f"{len(invalid_high_low)} 条记录最高价低于最低价")
                affected_records.extend(invalid_high_low.index.tolist())
        
        # 检查开盘收盘价在最高最低之间
        if checks['open_close_range']:
            required_fields = ['open', 'close', 'high', 'low']
            available_fields = [f for f in required_fields if f in data.columns]
            
            if len(available_fields) == 4:
                # 检查开盘价在最高最低之间
                open_outside = data[(data['open'] < data['low']) | (data['open'] > data['high'])]
                if len(open_outside) > 0:
                    issues.append(f"{len(open_outside)} 条记录开盘价不在最高最低价范围内")
                    affected_records.extend(open_outside.index.tolist())
                
                # 检查收盘价在最高最低之间
                close_outside = data[(data['close'] < data['low']) | (data['close'] > data['high'])]
                if len(close_outside) > 0:
                    issues.append(f"{len(close_outside)} 条记录收盘价不在最高最低价范围内")
                    affected_records.extend(close_outside.index.tolist())
        
        if issues:
            return ConsistencyCheckResult(
                check_name="business_logic_consistency_check",
                issue_type=ConsistencyIssue.BUSINESS_LOGIC_CONSISTENCY,
                passed=False,
                severity="high",
                message=f"业务逻辑一致性问题: {'; '.join(issues)}",
                details={'issues': issues},
                affected_records=affected_records
            )
        else:
            return ConsistencyCheckResult(
                check_name="business_logic_consistency_check",
                issue_type=ConsistencyIssue.BUSINESS_LOGIC_CONSISTENCY,
                passed=True,
                severity="info",
                message="业务逻辑一致性检查通过",
                details={}
            )
    
    def _check_cross_field_consistency(self, data: pd.DataFrame) -> ConsistencyCheckResult:
        """检查跨字段一致性"""
        issues = []
        affected_records = []
        
        # 检查涨跌幅与价格变化一致性
        if 'change_pct' in data.columns and 'price' in data.columns and 'prev_close' in data.columns:
            calculated_change = (data['price'] / data['prev_close'] - 1) * 100
            reported_change = data['change_pct']
            
            # 计算差异
            change_diff = np.abs(calculated_change - reported_change)
            large_diff = change_diff[change_diff > 0.01]  # 0.01%差异阈值
            
            if len(large_diff) > 0:
                issues.append(f"{len(large_diff)} 条记录计算涨跌幅与报告涨跌幅不一致")
                affected_records.extend(large_diff.index.tolist())
        
        # 检查成交额与价格成交量一致性
        if 'amount' in data.columns and 'price' in data.columns and 'volume' in data.columns:
            calculated_amount = data['price'] * data['volume']
            reported_amount = data['amount']
            
            # 计算差异百分比
            amount_diff = np.abs(calculated_amount - reported_amount) / reported_amount
            large_amount_diff = amount_diff[amount_diff > 0.01]  # 1%差异阈值
            
            if len(large_amount_diff) > 0:
                issues.append(f"{len(large_amount_diff)} 条记录计算成交额与报告成交额不一致")
                affected_records.extend(large_amount_diff.index.tolist())
        
        if issues:
            return ConsistencyCheckResult(
                check_name="cross_field_consistency_check",
                issue_type=ConsistencyIssue.CROSS_FIELD_CONSISTENCY,
                passed=False,
                severity="medium",
                message=f"跨字段一致性问题: {'; '.join(issues)}",
                details={'issues': issues},
                affected_records=affected_records
            )
        else:
            return ConsistencyCheckResult(
                check_name="cross_field_consistency_check",
                issue_type=ConsistencyIssue.CROSS_FIELD_CONSISTENCY,
                passed=True,
                severity="info",
                message="跨字段一致性检查通过",
                details={}
            )
    
    def _calculate_overall_score(self, check_results: List[ConsistencyCheckResult]) -> float:
        """计算总体一致性分数（0-100）"""
        if not check_results:
            return 100.0
        
        # 根据检查结果计算分数
        base_score = 100.0
        total_weight = 0
        weighted_score = 0
        
        # 不同检查的权重
        weights = {
            'price_range_check': 0.25,
            'business_logic_consistency_check': 0.25,
            'cross_field_consistency_check': 0.20,
            'volume_price_consistency_check': 0.15,
            'timeseries_consistency_check': 0.15
        }
        
        for result in check_results:
            weight = weights.get(result.check_name, 0.1)
            total_weight += weight
            
            if result.passed:
                # 通过的检查根据严重性给予分数
                if result.severity == 'info':
                    weighted_score += weight * 1.0
                elif result.severity == 'low':
                    weighted_score += weight * 0.9
                elif result.severity == 'medium':
                    weighted_score += weight * 0.8
                elif result.severity == 'high':
                    weighted_score += weight * 0.7
            else:
                # 失败的检查根据严重性扣分
                if result.severity == 'high':
                    weighted_score += weight * 0.3
                elif result.severity == 'medium':
                    weighted_score += weight * 0.5
                elif result.severity == 'low':
                    weighted_score += weight * 0.7
        
        if total_weight > 0:
            final_score = (weighted_score / total_weight) * 100
        else:
            final_score = 100.0
        
        return final_score
    
    def _generate_recommendations(self, check_results: List[ConsistencyCheckResult]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        failed_checks = [r for r in check_results if not r.passed]
        
        for check in failed_checks:
            if check.issue_type == ConsistencyIssue.PRICE_RANGE_VIOLATION:
                recommendations.append("检查价格数据源，确保价格在合理范围内")
            elif check.issue_type == ConsistencyIssue.BUSINESS_LOGIC_CONSISTENCY:
                recommendations.append("修复业务逻辑错误，确保最高价≥最低价，开盘收盘价在范围内")
            elif check.issue_type == ConsistencyIssue.CROSS_FIELD_CONSISTENCY:
                recommendations.append("检查跨字段计算一致性，确保涨跌幅、成交额等计算正确")
            elif check.issue_type == ConsistencyIssue.VOLUME_PRICE_CONSISTENCY:
                recommendations.append("检查成交量与价格关系，确保成交量/价格比率合理")
            elif check.issue_type == ConsistencyIssue.TIMESERIES_CONSISTENCY:
                recommendations.append("修复时间序列问题，确保时间戳正确且按顺序排列")
        
        # 如果没有失败检查
        if not failed_checks:
            recommendations.append("所有一致性检查通过，数据质量良好")
        
        return recommendations
    
    def generate_consistency_report(self, report: ConsistencyValidationReport, output_format: str = "text") -> str:
        """生成一致性报告"""
        if output_format == "json":
            import json
            
            report_dict = {
                'data_source': report.data_source,
                'timestamp': report.timestamp.isoformat(),
                'total_checks': report.total_checks,
                'passed_checks': report.passed_checks,
                'failed_checks': report.failed_checks,
                'overall_consistency_score': report.overall_consistency_score,
                'check_results': [
                    {
                        'check_name': result.check_name,
                        'issue_type': result.issue_type.value,
                        'passed': result.passed,
                        'severity': result.severity,
                        'message': result.message
                    }
                    for result in report.check_results
                ],
                'recommendations': report.recommendations
            }
            
            return json.dumps(report_dict, ensure_ascii=False, indent=2)
        
        else:  # text格式
            lines = []
            lines.append("=" * 60)
            lines.append(f"一致性验证报告 - {report.data_source}")
            lines.append("=" * 60)
            lines.append(f"验证时间: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"总检查数: {report.total_checks}")
            lines.append(f"通过检查: {report.passed_checks}")
            lines.append(f"失败检查: {report.failed_checks}")
            lines.append(f"总体一致性分数: {report.overall_consistency_score:.1f}/100")
            lines.append("")
            
            lines.append("详细检查结果:")
            for result in report.check_results:
                status = "✅ 通过" if result.passed else "❌ 失败"
                lines.append(f"  {result.check_name}: {status}")
                lines.append(f"    级别: {result.severity.upper()}")
                lines.append(f"    信息: {result.message}")
                lines.append("")
            
            lines.append("改进建议:")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            
            lines.append("=" * 60)
            
            return "\n".join(lines)


# 使用示例
def example_usage():
    """一致性验证示例"""
    print("=" * 60)
    print("Zhulinsma一致性验证器示例")
    print("=" * 60)
    
    # 创建示例数据
    import pandas as pd
    import numpy as np
    
    data = pd.DataFrame({
        'timestamp': pd.date_range('2026-03-25', periods=50, freq='H'),
        'price': np.random.uniform(50, 150, 50),
        'prev_close': np.random.uniform(50, 150, 50),
        'high': np.random.uniform(150, 200, 50),
        'low': np.random.uniform(40, 100, 50),
        'open': np.random.uniform(60, 140, 50),
        'close': np.random.uniform(60, 140, 50),
        'volume': np.random.randint(10000, 1000000, 50),
        'amount': np.random.uniform(500000, 50000000, 50),
        'change_pct': np.random.normal(0, 2, 50)
    })
    
    # 故意添加一些问题
    data.loc[10, 'high'] = 30  # 最高价低于最低价
    data.loc[20, 'price'] = 0.001  # 价格过低
    data.loc[30, 'volume'] = 1000000000  # 成交量过高
    data.loc[40, 'timestamp'] = pd.Timestamp('2027-01-01')  # 未来时间戳
    
    # 创建验证器
    validator = ConsistencyValidator()
    
    # 执行一致性验证
    print("\n1. 执行一致性验证...")
    report = validator.validate_consistency(data, data_source="示例数据")
    
    # 生成报告
    print("\n2. 生成一致性报告...")
    report_text = validator.generate_consistency_report(report, output_format="text")
    print(report_text)
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    example_usage()