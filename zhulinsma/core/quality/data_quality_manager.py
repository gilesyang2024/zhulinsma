#!/usr/bin/env python3
"""
数据质量管理器模块
管理数据质量检查、评估和报告
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

class DataQualityIssue(Enum):
    """数据质量问题类型枚举"""
    MISSING_VALUES = "missing_values"          # 缺失值
    OUTLIERS = "outliers"                      # 异常值
    INCONSISTENCIES = "inconsistencies"        # 不一致性
    DUPLICATES = "duplicates"                  # 重复数据
    FORMAT_ERRORS = "format_errors"            # 格式错误
    TIMESTAMP_ISSUES = "timestamp_issues"      # 时间戳问题
    BUSINESS_RULE_VIOLATIONS = "business_rule_violations"  # 业务规则违反


class DataQualityLevel(Enum):
    """数据质量等级枚举"""
    EXCELLENT = "excellent"    # 优秀：质量分数 >= 90
    GOOD = "good"              # 良好：质量分数 >= 80
    FAIR = "fair"              # 一般：质量分数 >= 70
    POOR = "poor"              # 较差：质量分数 >= 60
    BAD = "bad"                # 差：质量分数 < 60


class DataQualityManager:
    """
    数据质量管理器
    管理数据质量检查、评估和报告
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化数据质量管理器
        
        参数:
            config: 配置字典
        """
        self.config = config or self._get_default_config()
        self.quality_history: List[Dict] = []
        self.max_history_size = 1000
        
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'missing_value_threshold': 0.05,      # 缺失值阈值（5%）
            'outlier_threshold': 3.0,             # 异常值阈值（3倍标准差）
            'consistency_threshold': 0.95,        # 一致性阈值（95%）
            'freshness_threshold_hours': 24,      # 新鲜度阈值（24小时）
            'completeness_threshold': 0.90,       # 完整性阈值（90%）
            'accuracy_threshold': 0.95,           # 准确性阈值（95%）
            'weight_missing_values': 0.20,        # 缺失值权重
            'weight_outliers': 0.15,              # 异常值权重
            'weight_inconsistencies': 0.25,       # 不一致性权重
            'weight_freshness': 0.15,             # 新鲜度权重
            'weight_completeness': 0.15,          # 完整性权重
            'weight_accuracy': 0.10,              # 准确性权重
            'enable_auto_fix': False,             # 启用自动修复
            'enable_quality_reports': True,       # 启用质量报告
            'enable_alerting': True               # 启用报警
        }
    
    def check_data_quality(self, data: np.ndarray, 
                          data_type: str = "numeric",
                          metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        检查数据质量
        
        参数:
            data: 数据数组
            data_type: 数据类型（numeric, timestamp, categorical）
            metadata: 元数据
        
        返回:
            数据质量检查结果
        """
        if data is None or len(data) == 0:
            return self._create_empty_quality_report()
        
        # 执行各项质量检查
        checks = {
            'missing_values': self._check_missing_values(data),
            'outliers': self._check_outliers(data, data_type),
            'inconsistencies': self._check_inconsistencies(data, data_type),
            'duplicates': self._check_duplicates(data),
            'freshness': self._check_freshness(metadata),
            'completeness': self._check_completeness(data, metadata),
            'accuracy': self._check_accuracy(data, metadata)
        }
        
        # 计算质量分数
        quality_score = self._calculate_quality_score(checks)
        quality_level = self._determine_quality_level(quality_score)
        
        # 识别问题
        issues = self._identify_issues(checks)
        
        # 生成建议
        recommendations = self._generate_recommendations(checks, issues)
        
        # 创建质量报告
        quality_report = {
            'timestamp': datetime.now().isoformat(),
            'data_type': data_type,
            'data_size': len(data),
            'quality_score': quality_score,
            'quality_level': quality_level.value,
            'checks': checks,
            'issues': issues,
            'recommendations': recommendations,
            'metadata': metadata or {}
        }
        
        # 记录质量历史
        self._record_quality_history(quality_report)
        
        return quality_report
    
    def _check_missing_values(self, data: np.ndarray) -> Dict[str, Any]:
        """检查缺失值"""
        if data is None or len(data) == 0:
            return {
                'status': 'failed',
                'missing_count': 0,
                'missing_percentage': 0.0,
                'threshold': self.config['missing_value_threshold'],
                'passed': True
            }
        
        # 计算缺失值
        missing_mask = np.isnan(data) if data.dtype.kind in 'fc' else (data == None)
        missing_count = np.sum(missing_mask)
        missing_percentage = missing_count / len(data)
        
        passed = missing_percentage <= self.config['missing_value_threshold']
        
        return {
            'status': 'passed' if passed else 'failed',
            'missing_count': int(missing_count),
            'missing_percentage': float(missing_percentage),
            'threshold': self.config['missing_value_threshold'],
            'passed': passed
        }
    
    def _check_outliers(self, data: np.ndarray, data_type: str) -> Dict[str, Any]:
        """检查异常值"""
        if data is None or len(data) < 3 or data_type != "numeric":
            return {
                'status': 'skipped',
                'outlier_count': 0,
                'outlier_percentage': 0.0,
                'threshold': self.config['outlier_threshold'],
                'passed': True
            }
        
        # 移除缺失值
        clean_data = data[~np.isnan(data)]
        if len(clean_data) < 3:
            return {
                'status': 'skipped',
                'outlier_count': 0,
                'outlier_percentage': 0.0,
                'threshold': self.config['outlier_threshold'],
                'passed': True
            }
        
        # 使用IQR方法检测异常值
        Q1 = np.percentile(clean_data, 25)
        Q3 = np.percentile(clean_data, 75)
        IQR = Q3 - Q1
        
        if IQR == 0:
            # 如果IQR为0，使用标准差方法
            mean = np.mean(clean_data)
            std = np.std(clean_data)
            lower_bound = mean - self.config['outlier_threshold'] * std
            upper_bound = mean + self.config['outlier_threshold'] * std
        else:
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
        
        # 统计异常值
        outliers = clean_data[(clean_data < lower_bound) | (clean_data > upper_bound)]
        outlier_count = len(outliers)
        outlier_percentage = outlier_count / len(clean_data)
        
        # 异常值百分比阈值设为5%
        passed = outlier_percentage <= 0.05
        
        return {
            'status': 'passed' if passed else 'failed',
            'outlier_count': outlier_count,
            'outlier_percentage': float(outlier_percentage),
            'lower_bound': float(lower_bound),
            'upper_bound': float(upper_bound),
            'threshold': 0.05,  # 5%异常值阈值
            'passed': passed
        }
    
    def _check_inconsistencies(self, data: np.ndarray, data_type: str) -> Dict[str, Any]:
        """检查不一致性"""
        if data is None or len(data) < 2:
            return {
                'status': 'skipped',
                'inconsistency_count': 0,
                'inconsistency_percentage': 0.0,
                'threshold': self.config['consistency_threshold'],
                'passed': True
            }
        
        # 检查数据内部一致性
        inconsistencies = []
        
        if data_type == "numeric":
            # 检查数值范围是否合理
            if len(data) > 1:
                data_range = np.max(data) - np.min(data)
                if data_range == 0:
                    # 所有值相同，可能有问题
                    inconsistencies.append("zero_data_range")
        
        elif data_type == "timestamp":
            # 检查时间戳顺序
            if len(data) > 1:
                # 假设时间戳是datetime对象或Unix时间戳
                try:
                    # 检查是否按时间排序
                    diffs = np.diff(data)
                    if np.any(diffs < 0):
                        inconsistencies.append("timestamp_out_of_order")
                except:
                    pass
        
        inconsistency_count = len(inconsistencies)
        inconsistency_percentage = inconsistency_count / max(len(data), 1)
        passed = inconsistency_percentage <= (1 - self.config['consistency_threshold'])
        
        return {
            'status': 'passed' if passed else 'failed',
            'inconsistency_count': inconsistency_count,
            'inconsistency_percentage': float(inconsistency_percentage),
            'inconsistencies': inconsistencies,
            'threshold': self.config['consistency_threshold'],
            'passed': passed
        }
    
    def _check_duplicates(self, data: np.ndarray) -> Dict[str, Any]:
        """检查重复数据"""
        if data is None or len(data) == 0:
            return {
                'status': 'skipped',
                'duplicate_count': 0,
                'duplicate_percentage': 0.0,
                'threshold': 0.05,  # 5%重复数据阈值
                'passed': True
            }
        
        # 计算唯一值数量
        unique_values, counts = np.unique(data, return_counts=True)
        duplicate_counts = counts[counts > 1]
        duplicate_count = np.sum(duplicate_counts) - len(duplicate_counts)
        duplicate_percentage = duplicate_count / len(data)
        
        # 重复数据阈值设为5%
        passed = duplicate_percentage <= 0.05
        
        return {
            'status': 'passed' if passed else 'failed',
            'duplicate_count': int(duplicate_count),
            'duplicate_percentage': float(duplicate_percentage),
            'unique_count': len(unique_values),
            'threshold': 0.05,
            'passed': passed
        }
    
    def _check_freshness(self, metadata: Optional[Dict]) -> Dict[str, Any]:
        """检查数据新鲜度"""
        if metadata is None or 'timestamp' not in metadata:
            return {
                'status': 'skipped',
                'freshness_hours': None,
                'threshold_hours': self.config['freshness_threshold_hours'],
                'passed': True
            }
        
        try:
            # 解析时间戳
            data_timestamp = metadata['timestamp']
            if isinstance(data_timestamp, str):
                # 尝试解析ISO格式时间戳
                from datetime import datetime
                data_time = datetime.fromisoformat(data_timestamp.replace('Z', '+00:00'))
            elif isinstance(data_timestamp, (int, float)):
                # Unix时间戳
                from datetime import datetime
                data_time = datetime.fromtimestamp(data_timestamp)
            else:
                data_time = data_timestamp
            
            # 计算新鲜度（小时）
            now = datetime.now()
            freshness_hours = (now - data_time).total_seconds() / 3600
            
            passed = freshness_hours <= self.config['freshness_threshold_hours']
            
            return {
                'status': 'passed' if passed else 'failed',
                'freshness_hours': float(freshness_hours),
                'threshold_hours': self.config['freshness_threshold_hours'],
                'passed': passed
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'threshold_hours': self.config['freshness_threshold_hours'],
                'passed': False
            }
    
    def _check_completeness(self, data: np.ndarray, metadata: Optional[Dict]) -> Dict[str, Any]:
        """检查数据完整性"""
        if data is None or len(data) == 0:
            return {
                'status': 'failed',
                'completeness_score': 0.0,
                'threshold': self.config['completeness_threshold'],
                'passed': False
            }
        
        # 检查数据是否完整（无None或NaN）
        if data.dtype.kind in 'fc':  # 浮点数或复数
            valid_count = np.sum(~np.isnan(data))
        else:
            valid_count = np.sum(data != None)
        
        completeness_score = valid_count / len(data)
        passed = completeness_score >= self.config['completeness_threshold']
        
        return {
            'status': 'passed' if passed else 'failed',
            'completeness_score': float(completeness_score),
            'valid_count': int(valid_count),
            'total_count': len(data),
            'threshold': self.config['completeness_threshold'],
            'passed': passed
        }
    
    def _check_accuracy(self, data: np.ndarray, metadata: Optional[Dict]) -> Dict[str, Any]:
        """检查数据准确性"""
        if data is None or len(data) == 0:
            return {
                'status': 'failed',
                'accuracy_score': 0.0,
                'threshold': self.config['accuracy_threshold'],
                'passed': False
            }
        
        # 这里可以根据具体业务规则检查准确性
        # 例如：价格是否在合理范围内，交易量是否合理等
        
        # 简单实现：检查数据是否在合理范围内
        if metadata and 'expected_range' in metadata:
            expected_min, expected_max = metadata['expected_range']
            within_range = np.sum((data >= expected_min) & (data <= expected_max))
            accuracy_score = within_range / len(data)
        else:
            # 如果没有预期范围，默认通过
            accuracy_score = 1.0
        
        passed = accuracy_score >= self.config['accuracy_threshold']
        
        return {
            'status': 'passed' if passed else 'failed',
            'accuracy_score': float(accuracy_score),
            'threshold': self.config['accuracy_threshold'],
            'passed': passed
        }
    
    def _calculate_quality_score(self, checks: Dict[str, Dict]) -> float:
        """计算综合质量分数"""
        if not checks:
            return 0.0
        
        # 各项检查的权重
        weights = {
            'missing_values': self.config['weight_missing_values'],
            'outliers': self.config['weight_outliers'],
            'inconsistencies': self.config['weight_inconsistencies'],
            'duplicates': 0.05,  # 固定权重
            'freshness': self.config['weight_freshness'],
            'completeness': self.config['weight_completeness'],
            'accuracy': self.config['weight_accuracy']
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for check_name, check_result in checks.items():
            if check_name not in weights:
                continue
            
            weight = weights[check_name]
            
            if check_result['status'] == 'skipped':
                # 跳过的检查给满分
                score = 1.0
            elif check_result['status'] == 'error':
                # 出错的检查给0分
                score = 0.0
            else:
                # 根据检查结果计算分数
                if check_name == 'missing_values':
                    missing_pct = check_result['missing_percentage']
                    threshold = check_result['threshold']
                    score = max(0, 1 - (missing_pct / threshold)) if threshold > 0 else 1.0
                
                elif check_name == 'outliers':
                    outlier_pct = check_result.get('outlier_percentage', 0)
                    threshold = check_result.get('threshold', 0.05)
                    score = max(0, 1 - (outlier_pct / threshold)) if threshold > 0 else 1.0
                
                elif check_name == 'inconsistencies':
                    inconsistency_pct = check_result.get('inconsistency_percentage', 0)
                    threshold = check_result.get('threshold', 0.05)
                    score = max(0, 1 - (inconsistency_pct / threshold)) if threshold > 0 else 1.0
                
                elif check_name == 'duplicates':
                    duplicate_pct = check_result.get('duplicate_percentage', 0)
                    threshold = check_result.get('threshold', 0.05)
                    score = max(0, 1 - (duplicate_pct / threshold)) if threshold > 0 else 1.0
                
                elif check_name == 'freshness':
                    if check_result.get('freshness_hours') is None:
                        score = 1.0
                    else:
                        freshness_hours = check_result['freshness_hours']
                        threshold = check_result['threshold_hours']
                        score = max(0, 1 - (freshness_hours / (threshold * 2)))  # 更宽松的阈值
                
                elif check_name == 'completeness':
                    completeness_score = check_result.get('completeness_score', 0)
                    score = completeness_score
                
                elif check_name == 'accuracy':
                    accuracy_score = check_result.get('accuracy_score', 0)
                    score = accuracy_score
                
                else:
                    score = 1.0 if check_result.get('passed', False) else 0.0
            
            total_score += score * weight
            total_weight += weight
        
        # 归一化到0-100
        if total_weight > 0:
            final_score = (total_score / total_weight) * 100
        else:
            final_score = 0.0
        
        return min(100.0, max(0.0, final_score))
    
    def _determine_quality_level(self, quality_score: float) -> DataQualityLevel:
        """确定数据质量等级"""
        if quality_score >= 90:
            return DataQualityLevel.EXCELLENT
        elif quality_score >= 80:
            return DataQualityLevel.GOOD
        elif quality_score >= 70:
            return DataQualityLevel.FAIR
        elif quality_score >= 60:
            return DataQualityLevel.POOR
        else:
            return DataQualityLevel.BAD
    
    def _identify_issues(self, checks: Dict[str, Dict]) -> List[Dict]:
        """识别数据质量问题"""
        issues = []
        
        for check_name, check_result in checks.items():
            if check_result['status'] in ['failed', 'error'] and not check_result.get('passed', True):
                issue = {
                    'type': check_name,
                    'severity': self._get_issue_severity(check_name, check_result),
                    'description': self._get_issue_description(check_name, check_result),
                    'check_result': check_result
                }
                issues.append(issue)
        
        return issues
    
    def _get_issue_severity(self, check_name: str, check_result: Dict) -> str:
        """获取问题严重性"""
        severity_map = {
            'missing_values': 'high',
            'outliers': 'medium',
            'inconsistencies': 'high',
            'duplicates': 'low',
            'freshness': 'medium',
            'completeness': 'high',
            'accuracy': 'high'
        }
        
        return severity_map.get(check_name, 'medium')
    
    def _get_issue_description(self, check_name: str, check_result: Dict) -> str:
        """获取问题描述"""
        descriptions = {
            'missing_values': f"缺失值比例过高 ({check_result.get('missing_percentage', 0):.1%})",
            'outliers': f"异常值比例过高 ({check_result.get('outlier_percentage', 0):.1%})",
            'inconsistencies': f"数据不一致性 ({check_result.get('inconsistency_percentage', 0):.1%})",
            'duplicates': f"重复数据比例过高 ({check_result.get('duplicate_percentage', 0):.1%})",
            'freshness': f"数据不够新鲜 ({check_result.get('freshness_hours', 0):.1f}小时)",
            'completeness': f"数据完整性不足 ({check_result.get('completeness_score', 0):.1%})",
            'accuracy': f"数据准确性不足 ({check_result.get('accuracy_score', 0):.1%})"
        }
        
        return descriptions.get(check_name, f"{check_name}检查失败")
    
    def _generate_recommendations(self, checks: Dict[str, Dict], issues: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for issue in issues:
            check_name = issue['type']
            
            if check_name == 'missing_values':
                recommendations.append("检查数据源，确保数据完整上传")
            
            elif check_name == 'outliers':
                recommendations.append("验证异常值是否为真实数据，必要时进行修正或排除")
            
            elif check_name == 'inconsistencies':
                recommendations.append("检查数据处理流程，确保数据一致性")
            
            elif check_name == 'duplicates':
                recommendations.append("清理重复数据，确保数据唯一性")
            
            elif check_name == 'freshness':
                recommendations.append("更新数据源，获取最新数据")
            
            elif check_name == 'completeness':
                recommendations.append("补充缺失数据，提高数据完整性")
            
            elif check_name == 'accuracy':
                recommendations.append("验证数据准确性，检查数据采集和处理过程")
        
        # 如果没有问题，添加正面反馈
        if not recommendations and any(check.get('passed', False) for check in checks.values()):
            recommendations.append("数据质量良好，继续保持")
        
        return recommendations
    
    def _create_empty_quality_report(self) -> Dict[str, Any]:
        """创建空的质量报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'data_type': 'unknown',
            'data_size': 0,
            'quality_score': 0.0,
            'quality_level': DataQualityLevel.BAD.value,
            'checks': {},
            'issues': [{
                'type': 'no_data',
                'severity': 'critical',
                'description': '没有提供数据'
            }],
            'recommendations': ['请提供有效数据进行质量检查'],
            'metadata': {}
        }
    
    def _record_quality_history(self, quality_report: Dict) -> None:
        """记录质量历史"""
        self.quality_history.append(quality_report)
        
        # 限制历史记录大小
        if len(self.quality_history) > self.max_history_size:
            self.quality_history = self.quality_history[-self.max_history_size:]
    
    def get_quality_history(self, hours: Optional[int] = None) -> List[Dict]:
        """
        获取质量历史
        
        参数:
            hours: 小时数（获取最近N小时的历史）
        
        返回:
            质量历史列表
        """
        if hours is None:
            return self.quality_history
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_history = []
        for report in self.quality_history:
            try:
                report_time = datetime.fromisoformat(report['timestamp'])
                if report_time >= cutoff_time:
                    filtered_history.append(report)
            except:
                pass
        
        return filtered_history
    
    def get_quality_trend(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取质量趋势
        
        参数:
            hours: 小时数
        
        返回:
            质量趋势报告
        """
        recent_history = self.get_quality_history(hours)
        
        if not recent_history:
            return {
                'trend': 'no_data',
                'average_score': 0.0,
                'score_trend': 0.0,
                'improvement_count': 0,
                'deterioration_count': 0
            }
        
        # 计算平均分数
        scores = [report['quality_score'] for report in recent_history]
        average_score = np.mean(scores) if scores else 0.0
        
        # 计算趋势
        if len(scores) >= 2:
            # 简单线性趋势
            x = np.arange(len(scores))
            coef = np.polyfit(x, scores, 1)[0]
            score_trend = coef * len(scores)  # 总变化量
        else:
            score_trend = 0.0
        
        # 统计改进和恶化次数
        improvement_count = 0
        deterioration_count = 0
        
        for i in range(1, len(scores)):
            if scores[i] > scores[i-1]:
                improvement_count += 1
            elif scores[i] < scores[i-1]:
                deterioration_count += 1
        
        # 确定趋势方向
        if score_trend > 1.0:
            trend = 'improving'
        elif score_trend < -1.0:
            trend = 'deteriorating'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'average_score': float(average_score),
            'score_trend': float(score_trend),
            'improvement_count': improvement_count,
            'deterioration_count': deterioration_count,
            'total_reports': len(recent_history),
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_quality_history(self) -> None:
        """清空质量历史"""
        self.quality_history = []
    
    def export_quality_report(self, file_path: str) -> None:
        """
        导出质量报告
        
        参数:
            file_path: 导出文件路径
        """
        import json
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'config': self.config,
            'quality_history': self.quality_history
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def auto_fix_data(self, data: np.ndarray, 
                     data_type: str = "numeric",
                     fix_strategy: str = "conservative") -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        自动修复数据
        
        参数:
            data: 数据数组
            data_type: 数据类型
            fix_strategy: 修复策略（conservative, moderate, aggressive）
        
        返回:
            修复后的数据和修复报告
        """
        if not self.config['enable_auto_fix']:
            return data, {'status': 'auto_fix_disabled'}
        
        if data is None or len(data) == 0:
            return data, {'status': 'no_data'}
        
        original_data = data.copy()
        fix_report = {
            'timestamp': datetime.now().isoformat(),
            'fix_strategy': fix_strategy,
            'fixes_applied': [],
            'original_size': len(data),
            'final_size': len(data)
        }
        
        # 根据策略选择修复方法
        if fix_strategy == "conservative":
            # 保守策略：只处理明显问题
            fix_report['fixes_applied'].append("conservative_fix_strategy")
        
        elif fix_strategy == "moderate":
            # 中等策略：处理常见问题
            fix_report['fixes_applied'].append("moderate_fix_strategy")
            
            # 处理缺失值（用中位数填充）
            if data.dtype.kind in 'fc':
                missing_mask = np.isnan(data)
                if np.any(missing_mask):
                    median_value = np.median(data[~missing_mask])
                    data[missing_mask] = median_value
                    fix_report['fixes_applied'].append(f"filled_{np.sum(missing_mask)}_missing_values")
        
        elif fix_strategy == "aggressive":
            # 激进策略：全面修复
            fix_report['fixes_applied'].append("aggressive_fix_strategy")
            
            # 处理缺失值
            if data.dtype.kind in 'fc':
                missing_mask = np.isnan(data)
                if np.any(missing_mask):
                    # 使用线性插值
                    from scipy import interpolate
                    try:
                        x = np.arange(len(data))
                        valid_mask = ~missing_mask
                        if np.sum(valid_mask) >= 2:
                            f = interpolate.interp1d(x[valid_mask], data[valid_mask], 
                                                    kind='linear', fill_value='extrapolate')
                            data[missing_mask] = f(x[missing_mask])
                            fix_report['fixes_applied'].append(f"interpolated_{np.sum(missing_mask)}_missing_values")
                    except:
                        # 插值失败，使用中位数填充
                        median_value = np.median(data[valid_mask])
                        data[missing_mask] = median_value
                        fix_report['fixes_applied'].append(f"filled_{np.sum(missing_mask)}_missing_values_with_median")
        
        fix_report['final_data'] = data.tolist() if len(data) <= 100 else data[:100].tolist()
        fix_report['status'] = 'completed'
        
        return data, fix_report


# 单例实例
_data_quality_manager = None

def get_data_quality_manager(config: Optional[Dict] = None) -> DataQualityManager:
    """
    获取数据质量管理器单例实例
    
    参数:
        config: 配置字典
    
    返回:
        DataQualityManager实例
    """
    global _data_quality_manager
    
    if _data_quality_manager is None:
        _data_quality_manager = DataQualityManager(config)
    
    return _data_quality_manager


if __name__ == "__main__":
    # 测试代码
    print("=== 数据质量管理器测试 ===")
    
    # 创建数据质量管理器
    manager = DataQualityManager()
    
    # 生成测试数据
    print("\n📊 生成测试数据...")
    np.random.seed(42)
    test_data = np.random.normal(100, 10, 100)
    
    # 添加一些质量问题
    test_data[10:15] = np.nan  # 缺失值
    test_data[50] = 500        # 异常值
    test_data[60:65] = test_data[70:75]  # 重复数据
    
    print(f"  数据大小: {len(test_data)}")
    print(f"  数据范围: {np.nanmin(test_data):.2f} - {np.nanmax(test_data):.2f}")
    
    # 检查数据质量
    print("\n🔍 检查数据质量...")
    quality_report = manager.check_data_quality(
        data=test_data,
        data_type="numeric",
        metadata={'timestamp': datetime.now().isoformat()}
    )
    
    print(f"  质量分数: {quality_report['quality_score']:.1f}")
    print(f"  质量等级: {quality_report['quality_level']}")
    print(f"  发现问题: {len(quality_report['issues'])}个")
    
    # 显示问题详情
    print("\n📋 问题详情:")
    for issue in quality_report['issues']:
        print(f"  - {issue['description']} (严重性: {issue['severity']})")
    
    # 显示改进建议
    print("\n💡 改进建议:")
    for recommendation in quality_report['recommendations']:
        print(f"  - {recommendation}")
    
    # 获取质量趋势
    print("\n📈 质量趋势:")
    trend_report = manager.get_quality_trend(hours=1)
    print(f"  趋势: {trend_report['trend']}")
    print(f"  平均分数: {trend_report['average_score']:.1f}")
    print(f"  改进次数: {trend_report['improvement_count']}")
    
    # 测试自动修复
    print("\n🔧 测试自动修复...")
    fixed_data, fix_report = manager.auto_fix_data(
        data=test_data.copy(),
        data_type="numeric",
        fix_strategy="moderate"
    )
    
    print(f"  修复状态: {fix_report['status']}")
    print(f"  应用修复: {len(fix_report['fixes_applied'])}个")
    
    # 检查修复后的数据质量
    print("\n🔍 检查修复后数据质量...")
    fixed_quality_report = manager.check_data_quality(
        data=fixed_data,
        data_type="numeric"
    )
    
    print(f"  修复后质量分数: {fixed_quality_report['quality_score']:.1f}")
    print(f"  质量改进: {fixed_quality_report['quality_score'] - quality_report['quality_score']:.1f}分")
    
    print("\n✅ 数据质量管理器测试完成")