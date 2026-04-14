#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量检查器
检查单个数据源的数据质量，包括异常值检测、缺失值处理等
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class DataQualityIssue(Enum):
    """数据质量问题类型"""
    MISSING_VALUES = "missing_values"  # 缺失值
    OUTLIERS = "outliers"  # 异常值
    INCONSISTENT_FORMAT = "inconsistent_format"  # 格式不一致
    DATA_TYPE_ERROR = "data_type_error"  # 数据类型错误
    LOGICAL_ERROR = "logical_error"  # 逻辑错误
    DUPLICATE_DATA = "duplicate_data"  # 重复数据
    TIMESTAMP_ISSUE = "timestamp_issue"  # 时间戳问题

@dataclass
class QualityIssue:
    """数据质量问题"""
    issue_type: DataQualityIssue
    severity: str  # high, medium, low
    field: str
    description: str
    value: Any
    expected: Any = None
    suggestion: str = ""
    affected_rows: Optional[List[int]] = None

@dataclass
class DataQualityReport:
    """数据质量报告"""
    source_name: str
    timestamp: datetime
    total_records: int
    total_fields: int
    issues_found: List[QualityIssue]
    quality_score: float  # 0-100
    issue_summary: Dict[str, int]
    recommendations: List[str]

class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化数据质量检查器
        
        Parameters:
        -----------
        config : Dict
            配置参数，包括各种检查的阈值和规则
        """
        self.config = config or self._get_default_config()
        self.issue_history = []
        
        logger.info("初始化数据质量检查器")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'missing_values': {
                'allowed_missing_rate': 0.05,  # 允许5%的缺失率
                'critical_fields': ['price', 'volume', 'timestamp']
            },
            'outliers': {
                'z_score_threshold': 3.0,  # Z分数阈值
                'iqr_multiplier': 1.5,  # IQR倍数
                'price_outlier_threshold': 0.10  # 价格异常阈值（相对前收盘价）
            },
            'data_types': {
                'price': float,
                'volume': int,
                'amount': float,
                'timestamp': (str, datetime),
                'change_pct': float
            },
            'logical_checks': {
                'high_low_consistency': True,  # 检查最高价>最低价
                'price_range_check': True,  # 检查价格在合理范围内
                'volume_positive': True  # 检查成交量为正
            },
            'timestamp_checks': {
                'max_age_days': 30,  # 最大数据年龄
                'future_timestamp_allowed': False,  # 是否允许未来时间戳
                'chronological_order': True  # 检查时间顺序
            }
        }
    
    def check_data_quality(self, data: pd.DataFrame, source_name: str = "unknown") -> DataQualityReport:
        """
        检查数据质量
        
        Parameters:
        -----------
        data : pd.DataFrame
            待检查的数据
        source_name : str
            数据源名称
            
        Returns:
        --------
        DataQualityReport: 数据质量报告
        """
        logger.info(f"开始检查数据质量: {source_name}")
        
        issues = []
        
        # 1. 检查缺失值
        missing_issues = self._check_missing_values(data)
        issues.extend(missing_issues)
        
        # 2. 检查异常值
        outlier_issues = self._check_outliers(data)
        issues.extend(outlier_issues)
        
        # 3. 检查数据类型
        dtype_issues = self._check_data_types(data)
        issues.extend(dtype_issues)
        
        # 4. 检查逻辑一致性
        logic_issues = self._check_logical_consistency(data)
        issues.extend(logic_issues)
        
        # 5. 检查时间戳
        timestamp_issues = self._check_timestamps(data)
        issues.extend(timestamp_issues)
        
        # 6. 检查重复数据
        duplicate_issues = self._check_duplicates(data)
        issues.extend(duplicate_issues)
        
        # 计算质量分数
        quality_score = self._calculate_quality_score(data, issues)
        
        # 生成问题摘要
        issue_summary = self._generate_issue_summary(issues)
        
        # 生成建议
        recommendations = self._generate_recommendations(issues)
        
        # 创建报告
        report = DataQualityReport(
            source_name=source_name,
            timestamp=datetime.now(),
            total_records=len(data),
            total_fields=len(data.columns),
            issues_found=issues,
            quality_score=quality_score,
            issue_summary=issue_summary,
            recommendations=recommendations
        )
        
        # 记录历史
        self.issue_history.append(report)
        
        logger.info(f"数据质量检查完成: {source_name}, 质量分数: {quality_score:.1f}, 发现问题: {len(issues)}个")
        
        return report
    
    def _check_missing_values(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查缺失值"""
        issues = []
        
        for column in data.columns:
            missing_count = data[column].isna().sum()
            total_count = len(data)
            
            if missing_count > 0:
                missing_rate = missing_count / total_count
                allowed_rate = self.config['missing_values']['allowed_missing_rate']
                
                # 确定严重性
                if missing_rate > allowed_rate or column in self.config['missing_values']['critical_fields']:
                    severity = "high"
                elif missing_rate > allowed_rate * 0.5:
                    severity = "medium"
                else:
                    severity = "low"
                
                issue = QualityIssue(
                    issue_type=DataQualityIssue.MISSING_VALUES,
                    severity=severity,
                    field=column,
                    description=f"字段 '{column}' 有 {missing_count} 个缺失值，缺失率 {missing_rate:.2%}",
                    value=missing_count,
                    expected=f"缺失率 ≤ {allowed_rate:.0%}",
                    suggestion="考虑插值或删除缺失值"
                )
                issues.append(issue)
        
        return issues
    
    def _check_outliers(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查异常值"""
        issues = []
        
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        
        for column in numeric_cols:
            if column not in data.columns or data[column].isna().all():
                continue
            
            values = data[column].dropna()
            
            # 使用Z分数检测异常值
            mean = values.mean()
            std = values.std()
            
            if std > 0:
                z_scores = (values - mean) / std
                outliers_z = values[np.abs(z_scores) > self.config['outliers']['z_score_threshold']]
                
                if len(outliers_z) > 0:
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.OUTLIERS,
                        severity="medium",
                        field=column,
                        description=f"字段 '{column}' 发现 {len(outliers_z)} 个Z分数异常值",
                        value=len(outliers_z),
                        expected=f"Z分数 ≤ {self.config['outliers']['z_score_threshold']}",
                        suggestion="检查数据源或使用稳健统计量"
                    )
                    issues.append(issue)
            
            # 对于价格字段，检查相对变化
            if column == 'price' and 'prev_close' in data.columns:
                price_changes = data['price'] / data['prev_close'] - 1
                extreme_changes = price_changes[np.abs(price_changes) > self.config['outliers']['price_outlier_threshold']]
                
                if len(extreme_changes) > 0:
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.OUTLIERS,
                        severity="high",
                        field=column,
                        description=f"价格变化异常，{len(extreme_changes)} 条记录变化超过 {self.config['outliers']['price_outlier_threshold']:.0%}",
                        value=len(extreme_changes),
                        expected=f"价格变化 ≤ {self.config['outliers']['price_outlier_threshold']:.0%}",
                        suggestion="检查价格数据是否正确"
                    )
                    issues.append(issue)
        
        return issues
    
    def _check_data_types(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查数据类型"""
        issues = []
        
        type_mapping = self.config['data_types']
        
        for column, expected_type in type_mapping.items():
            if column not in data.columns:
                continue
            
            # 检查数据类型
            if expected_type == float:
                if not pd.api.types.is_numeric_dtype(data[column]):
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.DATA_TYPE_ERROR,
                        severity="high",
                        field=column,
                        description=f"字段 '{column}' 应为数值类型，实际为 {data[column].dtype}",
                        value=data[column].dtype,
                        expected="float",
                        suggestion="转换数据类型"
                    )
                    issues.append(issue)
            elif expected_type == int:
                if not pd.api.types.is_integer_dtype(data[column]):
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.DATA_TYPE_ERROR,
                        severity="medium",
                        field=column,
                        description=f"字段 '{column}' 应为整数类型，实际为 {data[column].dtype}",
                        value=data[column].dtype,
                        expected="int",
                        suggestion="转换数据类型"
                    )
                    issues.append(issue)
        
        return issues
    
    def _check_logical_consistency(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查逻辑一致性"""
        issues = []
        checks = self.config['logical_checks']
        
        if checks['high_low_consistency'] and 'high' in data.columns and 'low' in data.columns:
            invalid_high_low = data[data['high'] < data['low']]
            if len(invalid_high_low) > 0:
                issue = QualityIssue(
                    issue_type=DataQualityIssue.LOGICAL_ERROR,
                    severity="high",
                    field="high/low",
                    description=f"发现 {len(invalid_high_low)} 条记录最高价低于最低价",
                    value=len(invalid_high_low),
                    expected="high >= low",
                    suggestion="检查数据源或修正数据"
                )
                issues.append(issue)
        
        if checks['price_range_check'] and 'price' in data.columns:
            # 检查价格是否为正
            negative_prices = data[data['price'] <= 0]
            if len(negative_prices) > 0:
                issue = QualityIssue(
                    issue_type=DataQualityIssue.LOGICAL_ERROR,
                    severity="high",
                    field="price",
                    description=f"发现 {len(negative_prices)} 条记录价格非正",
                    value=len(negative_prices),
                    expected="price > 0",
                    suggestion="检查价格数据"
                )
                issues.append(issue)
        
        if checks['volume_positive'] and 'volume' in data.columns:
            negative_volumes = data[data['volume'] < 0]
            if len(negative_volumes) > 0:
                issue = QualityIssue(
                    issue_type=DataQualityIssue.LOGICAL_ERROR,
                    severity="high",
                    field="volume",
                    description=f"发现 {len(negative_volumes)} 条记录成交量为负",
                    value=len(negative_volumes),
                    expected="volume >= 0",
                    suggestion="检查成交量数据"
                )
                issues.append(issue)
        
        return issues
    
    def _check_timestamps(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查时间戳"""
        issues = []
        checks = self.config['timestamp_checks']
        
        if 'timestamp' not in data.columns:
            return issues
        
        # 转换时间戳为datetime
        try:
            if data['timestamp'].dtype == 'object':
                data['timestamp'] = pd.to_datetime(data['timestamp'], errors='coerce')
            
            # 检查未来时间戳
            if not checks['future_timestamp_allowed']:
                future_timestamps = data[data['timestamp'] > pd.Timestamp.now()]
                if len(future_timestamps) > 0:
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.TIMESTAMP_ISSUE,
                        severity="high",
                        field="timestamp",
                        description=f"发现 {len(future_timestamps)} 条记录时间戳在未来",
                        value=len(future_timestamps),
                        expected="timestamp <= now",
                        suggestion="检查时间戳数据"
                    )
                    issues.append(issue)
            
            # 检查数据年龄
            max_age_days = checks['max_age_days']
            if max_age_days > 0:
                now = pd.Timestamp.now()
                data_age_days = (now - data['timestamp']).dt.days
                old_data = data[data_age_days > max_age_days]
                
                if len(old_data) > 0:
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.TIMESTAMP_ISSUE,
                        severity="medium",
                        field="timestamp",
                        description=f"发现 {len(old_data)} 条记录超过 {max_age_days} 天",
                        value=len(old_data),
                        expected=f"数据年龄 ≤ {max_age_days} 天",
                        suggestion="更新数据或设置更长的保留期限"
                    )
                    issues.append(issue)
            
            # 检查时间顺序
            if checks['chronological_order'] and len(data) > 1:
                time_diff = data['timestamp'].diff()
                non_chronological = data[time_diff < pd.Timedelta(0)]
                if len(non_chronological) > 0:
                    issue = QualityIssue(
                        issue_type=DataQualityIssue.TIMESTAMP_ISSUE,
                        severity="medium",
                        field="timestamp",
                        description=f"发现 {len(non_chronological)} 条记录时间顺序错误",
                        value=len(non_chronological),
                        expected="时间递增",
                        suggestion="按时间戳排序数据"
                    )
                    issues.append(issue)
        
        except Exception as e:
            issue = QualityIssue(
                issue_type=DataQualityIssue.TIMESTAMP_ISSUE,
                severity="high",
                field="timestamp",
                description=f"时间戳处理失败: {str(e)}",
                value=str(e),
                expected="有效的时间戳格式",
                suggestion="检查时间戳格式"
            )
            issues.append(issue)
        
        return issues
    
    def _check_duplicates(self, data: pd.DataFrame) -> List[QualityIssue]:
        """检查重复数据"""
        issues = []
        
        # 检查完全重复的记录
        duplicate_rows = data[data.duplicated()]
        if len(duplicate_rows) > 0:
            issue = QualityIssue(
                issue_type=DataQualityIssue.DUPLICATE_DATA,
                severity="medium",
                field="all",
                description=f"发现 {len(duplicate_rows)} 条完全重复的记录",
                value=len(duplicate_rows),
                expected="无重复记录",
                suggestion="删除重复记录"
            )
            issues.append(issue)
        
        # 检查关键字段重复
        key_fields = ['timestamp', 'price', 'volume']
        available_key_fields = [f for f in key_fields if f in data.columns]
        
        if available_key_fields:
            duplicate_keys = data.duplicated(subset=available_key_fields)
            duplicate_key_rows = data[duplicate_keys]
            
            if len(duplicate_key_rows) > 0:
                issue = QualityIssue(
                    issue_type=DataQualityIssue.DUPLICATE_DATA,
                    severity="low",
                    field="key_fields",
                    description=f"发现 {len(duplicate_key_rows)} 条关键字段重复的记录",
                    value=len(duplicate_key_rows),
                    expected="关键字段唯一",
                    suggestion="检查数据来源或合并重复记录"
                )
                issues.append(issue)
        
        return issues
    
    def _calculate_quality_score(self, data: pd.DataFrame, issues: List[QualityIssue]) -> float:
        """计算质量分数（0-100）"""
        if len(data) == 0:
            return 0.0
        
        base_score = 100.0
        
        # 根据问题严重性扣分
        severity_weights = {
            'high': 5.0,
            'medium': 2.0,
            'low': 0.5
        }
        
        total_deduction = 0
        for issue in issues:
            deduction = severity_weights.get(issue.severity, 1.0)
            
            # 对于缺失值问题，根据缺失率调整扣分
            if issue.issue_type == DataQualityIssue.MISSING_VALUES:
                if isinstance(issue.value, (int, float)):
                    missing_rate = issue.value / len(data)
                    deduction *= min(missing_rate * 10, 2.0)  # 缺失率影响扣分
            
            total_deduction += deduction
        
        # 考虑数据规模，大样本允许更多问题
        scale_factor = min(len(data) / 1000, 2.0)  # 每1000条记录为一个基准
        adjusted_deduction = total_deduction / scale_factor
        
        final_score = max(0.0, base_score - adjusted_deduction)
        
        return final_score
    
    def _generate_issue_summary(self, issues: List[QualityIssue]) -> Dict[str, int]:
        """生成问题摘要"""
        summary = {
            'total': len(issues),
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0
        }
        
        # 按严重性统计
        for issue in issues:
            if issue.severity == 'high':
                summary['high_severity'] += 1
            elif issue.severity == 'medium':
                summary['medium_severity'] += 1
            elif issue.severity == 'low':
                summary['low_severity'] += 1
        
        # 按问题类型统计
        for issue_type in DataQualityIssue:
            type_count = sum(1 for issue in issues if issue.issue_type == issue_type)
            summary[f"{issue_type.value}_count"] = type_count
        
        return summary
    
    def _generate_recommendations(self, issues: List[QualityIssue]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 根据问题类型生成建议
        high_severity_issues = [i for i in issues if i.severity == 'high']
        medium_severity_issues = [i for i in issues if i.severity == 'medium']
        
        if high_severity_issues:
            recommendations.append("优先处理高严重性问题，特别是数据类型和逻辑错误")
        
        if any(i.issue_type == DataQualityIssue.MISSING_VALUES for i in issues):
            recommendations.append("处理缺失值，可以使用插值、前向填充或删除方法")
        
        if any(i.issue_type == DataQualityIssue.OUTLIERS for i in issues):
            recommendations.append("检查异常值，考虑使用稳健统计方法或删除极端值")
        
        if any(i.issue_type == DataQualityIssue.DUPLICATE_DATA for i in issues):
            recommendations.append("删除重复记录，确保数据唯一性")
        
        if any(i.issue_type == DataQualityIssue.TIMESTAMP_ISSUE for i in issues):
            recommendations.append("修正时间戳问题，确保数据时间顺序正确")
        
        # 如果没有问题或问题较少
        if len(issues) == 0:
            recommendations.append("数据质量良好，继续保持当前数据收集和处理流程")
        elif len(issues) <= 3 and len(high_severity_issues) == 0:
            recommendations.append("数据质量基本良好，可以继续使用")
        
        return recommendations
    
    def generate_quality_report(self, report: DataQualityReport, output_format: str = "text") -> str:
        """生成质量报告"""
        if output_format == "json":
            import json
            
            report_dict = {
                'source_name': report.source_name,
                'timestamp': report.timestamp.isoformat(),
                'total_records': report.total_records,
                'total_fields': report.total_fields,
                'quality_score': report.quality_score,
                'issue_summary': report.issue_summary,
                'issues_found': [
                    {
                        'issue_type': issue.issue_type.value,
                        'severity': issue.severity,
                        'field': issue.field,
                        'description': issue.description,
                        'suggestion': issue.suggestion
                    }
                    for issue in report.issues_found
                ],
                'recommendations': report.recommendations
            }
            
            return json.dumps(report_dict, ensure_ascii=False, indent=2)
        
        else:  # text格式
            lines = []
            lines.append("=" * 60)
            lines.append(f"数据质量报告 - {report.source_name}")
            lines.append("=" * 60)
            lines.append(f"检查时间: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"数据记录: {report.total_records} 条")
            lines.append(f"数据字段: {report.total_fields} 个")
            lines.append(f"质量分数: {report.quality_score:.1f}/100")
            lines.append("")
            
            lines.append("问题摘要:")
            lines.append(f"  总问题数: {report.issue_summary['total']}")
            lines.append(f"  高严重性: {report.issue_summary['high_severity']}")
            lines.append(f"  中严重性: {report.issue_summary['medium_severity']}")
            lines.append(f"  低严重性: {report.issue_summary['low_severity']}")
            lines.append("")
            
            if report.issues_found:
                lines.append("详细问题:")
                for i, issue in enumerate(report.issues_found, 1):
                    lines.append(f"  {i}. [{issue.severity.upper()}] {issue.issue_type.value}")
                    lines.append(f"     字段: {issue.field}")
                    lines.append(f"     描述: {issue.description}")
                    lines.append(f"     建议: {issue.suggestion}")
                    lines.append("")
            else:
                lines.append("未发现数据质量问题")
                lines.append("")
            
            lines.append("改进建议:")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            
            lines.append("=" * 60)
            
            return "\n".join(lines)


# 使用示例
def example_usage():
    """数据质量检查示例"""
    print("=" * 60)
    print("Zhulinsma数据质量检查器示例")
    print("=" * 60)
    
    # 创建示例数据（包含各种问题）
    import pandas as pd
    import numpy as np
    
    data = pd.DataFrame({
        'timestamp': pd.date_range('2026-03-25', periods=100, freq='H'),
        'price': np.random.normal(100, 10, 100),
        'volume': np.random.randint(10000, 1000000, 100),
        'change_pct': np.random.normal(0, 2, 100),
        'high': np.random.normal(105, 5, 100),
        'low': np.random.normal(95, 5, 100)
    })
    
    # 故意添加一些问题
    data.loc[10, 'price'] = np.nan  # 缺失值
    data.loc[20, 'price'] = 1000  # 异常值
    data.loc[30, 'volume'] = -100  # 逻辑错误
    data.loc[40, 'timestamp'] = pd.Timestamp('2026-04-01')  # 未来时间戳
    data.loc[50:51, :] = data.loc[60:61, :]  # 重复数据
    
    # 创建检查器
    checker = DataQualityChecker()
    
    # 检查数据质量
    print("\n1. 检查数据质量...")
    report = checker.check_data_quality(data, source_name="示例数据")
    
    # 生成报告
    print("\n2. 生成质量报告...")
    report_text = checker.generate_quality_report(report, output_format="text")
    print(report_text)
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    example_usage()