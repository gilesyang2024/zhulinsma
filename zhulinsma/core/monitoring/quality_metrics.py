#!/usr/bin/env python3
"""
质量指标追踪器模块
用于追踪和计算数据质量指标
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

class MetricType(Enum):
    """质量指标类型枚举"""
    DATA_QUALITY = "data_quality"  # 数据质量
    VALIDATION = "validation"      # 验证结果
    PERFORMANCE = "performance"    # 性能指标
    AVAILABILITY = "availability"  # 可用性
    CONSISTENCY = "consistency"    # 一致性


class QualityMetricsTracker:
    """
    质量指标追踪器
    追踪数据质量指标，计算统计信息，生成报告
    """
    
    def __init__(self, retention_days: int = 7):
        """
        初始化质量指标追踪器
        
        参数:
            retention_days: 指标保留天数（默认7天）
        """
        self.retention_days = retention_days
        self.metrics_history: Dict[str, List[Dict]] = {}
        self.cleanup_counter = 0
        
    def add_metric(self, metric_type: str, metric_name: str, value: float, 
                   timestamp: Optional[datetime] = None, 
                   metadata: Optional[Dict] = None) -> None:
        """
        添加质量指标
        
        参数:
            metric_type: 指标类型
            metric_name: 指标名称
            value: 指标值
            timestamp: 时间戳（默认当前时间）
            metadata: 元数据
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # 创建指标记录
        metric_record = {
            'timestamp': timestamp,
            'value': value,
            'metadata': metadata or {}
        }
        
        # 存储指标
        key = f"{metric_type}:{metric_name}"
        if key not in self.metrics_history:
            self.metrics_history[key] = []
        
        self.metrics_history[key].append(metric_record)
        
        # 定期清理旧数据
        self.cleanup_counter += 1
        if self.cleanup_counter >= 10:
            self._cleanup_old_metrics()
            self.cleanup_counter = 0
    
    def get_metric(self, metric_type: str, metric_name: str, 
                   hours: Optional[int] = None) -> List[Dict]:
        """
        获取指定时间段内的指标数据
        
        参数:
            metric_type: 指标类型
            metric_name: 指标名称
            hours: 小时数（获取最近N小时的指标）
        
        返回:
            指标数据列表
        """
        key = f"{metric_type}:{metric_name}"
        
        if key not in self.metrics_history:
            return []
        
        metrics = self.metrics_history[key]
        
        if hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [m for m in metrics if m['timestamp'] >= cutoff_time]
        
        return metrics
    
    def get_latest_metric(self, metric_type: str, metric_name: str) -> Optional[float]:
        """
        获取最新的指标值
        
        参数:
            metric_type: 指标类型
            metric_name: 指标名称
        
        返回:
            最新的指标值，如果没有则返回None
        """
        key = f"{metric_type}:{metric_name}"
        
        if key not in self.metrics_history or not self.metrics_history[key]:
            return None
        
        return self.metrics_history[key][-1]['value']
    
    def calculate_statistics(self, metric_type: str, metric_name: str, 
                            hours: Optional[int] = 24) -> Dict[str, float]:
        """
        计算指标统计信息
        
        参数:
            metric_type: 指标类型
            metric_name: 指标名称
            hours: 小时数（默认24小时）
        
        返回:
            统计信息字典
        """
        metrics = self.get_metric(metric_type, metric_name, hours)
        
        if not metrics:
            return {
                'count': 0,
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0
            }
        
        values = [m['value'] for m in metrics]
        
        return {
            'count': len(values),
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'min': float(np.min(values)),
            'max': float(np.max(values)),
            'median': float(np.median(values))
        }
    
    def get_data_quality_score(self, hours: int = 24) -> Dict[str, Any]:
        """
        计算综合数据质量评分
        
        参数:
            hours: 小时数（默认24小时）
        
        返回:
            数据质量评分报告
        """
        # 获取所有数据质量相关指标
        quality_metrics = {}
        
        for key in self.metrics_history:
            if key.startswith('data_quality:'):
                metric_name = key.split(':')[1]
                stats = self.calculate_statistics('data_quality', metric_name, hours)
                quality_metrics[metric_name] = stats
        
        # 计算综合质量分数
        if not quality_metrics:
            return {
                'overall_score': 0.0,
                'component_scores': {},
                'recommendations': []
            }
        
        # 计算各个指标的权重分数
        component_scores = {}
        total_weight = 0
        
        for metric_name, stats in quality_metrics.items():
            # 根据指标类型分配权重
            weight = self._get_metric_weight(metric_name)
            score = stats['mean'] if stats['count'] > 0 else 0
            
            component_scores[metric_name] = {
                'score': score,
                'weight': weight,
                'weighted_score': score * weight,
                'stats': stats
            }
            
            total_weight += weight
        
        # 计算综合分数
        if total_weight > 0:
            weighted_sum = sum(comp['weighted_score'] for comp in component_scores.values())
            overall_score = weighted_sum / total_weight
        else:
            overall_score = 0.0
        
        # 生成改进建议
        recommendations = self._generate_quality_recommendations(component_scores)
        
        return {
            'overall_score': overall_score,
            'component_scores': component_scores,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_validation_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取验证报告
        
        参数:
            hours: 小时数（默认24小时）
        
        返回:
            验证报告
        """
        # 获取验证相关指标
        validation_metrics = {}
        
        for key in self.metrics_history:
            if key.startswith('validation:'):
                metric_name = key.split(':')[1]
                stats = self.calculate_statistics('validation', metric_name, hours)
                validation_metrics[metric_name] = stats
        
        # 计算验证通过率
        pass_rates = []
        validation_results = {}
        
        for metric_name, stats in validation_metrics.items():
            if metric_name.endswith('_pass_rate'):
                pass_rate = stats['mean'] if stats['count'] > 0 else 0
                pass_rates.append(pass_rate)
                validation_results[metric_name] = {
                    'pass_rate': pass_rate,
                    'stats': stats
                }
        
        # 计算平均通过率
        if pass_rates:
            overall_pass_rate = sum(pass_rates) / len(pass_rates)
        else:
            overall_pass_rate = 0.0
        
        # 识别验证失败
        failed_validations = []
        for metric_name, stats in validation_metrics.items():
            if stats['mean'] < 95 and stats['count'] > 0:  # 低于95%通过率
                failed_validations.append({
                    'metric': metric_name,
                    'pass_rate': stats['mean'],
                    'recommendation': f'检查{metric_name}验证逻辑'
                })
        
        return {
            'overall_pass_rate': overall_pass_rate,
            'validation_results': validation_results,
            'failed_validations': failed_validations,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """
        生成综合质量报告
        
        返回:
            综合质量报告
        """
        数据质量评分 = self.get_data_quality_score(hours=24)
        验证报告 = self.get_validation_report(hours=24)
        
        # 计算综合评分
        综合评分 = (数据质量评分['overall_score'] * 0.6 + 
                   验证报告['overall_pass_rate'] * 0.4)
        
        # 评估系统状态
        if 综合评分 >= 90:
            system_status = "优秀"
        elif 综合评分 >= 80:
            system_status = "良好"
        elif 综合评分 >= 70:
            system_status = "一般"
        elif 综合评分 >= 60:
            system_status = "需要改进"
        else:
            system_status = "需要紧急修复"
        
        return {
            'system_status': system_status,
            'comprehensive_score': 综合评分,
            'data_quality': 数据质量评分,
            'validation': 验证报告,
            'timestamp': datetime.now().isoformat(),
            'metrics_summary': {
                'total_metrics': len(self.metrics_history),
                'total_records': sum(len(records) for records in self.metrics_history.values())
            }
        }
    
    def _get_metric_weight(self, metric_name: str) -> float:
        """
        获取指标权重
        
        参数:
            metric_name: 指标名称
        
        返回:
            权重值
        """
        weight_map = {
            'data_completeness': 0.25,  # 数据完整性
            'data_freshness': 0.20,     # 数据新鲜度
            'data_consistency': 0.20,   # 数据一致性
            'data_accuracy': 0.25,      # 数据准确性
            'data_availability': 0.10   # 数据可用性
        }
        
        # 查找匹配的权重
        for key, weight in weight_map.items():
            if key in metric_name:
                return weight
        
        # 默认权重
        return 0.1
    
    def _generate_quality_recommendations(self, component_scores: Dict) -> List[str]:
        """
        生成质量改进建议
        
        参数:
            component_scores: 组件分数字典
        
        返回:
            改进建议列表
        """
        recommendations = []
        
        for metric_name, scores in component_scores.items():
            score = scores['score']
            
            if score < 80:
                if 'completeness' in metric_name:
                    recommendations.append(f"数据完整性({metric_name})较低({score:.1f}%)，建议检查数据源")
                elif 'freshness' in metric_name:
                    recommendations.append(f"数据新鲜度({metric_name})较低({score:.1f}%)，建议更新数据频率")
                elif 'consistency' in metric_name:
                    recommendations.append(f"数据一致性({metric_name})较低({score:.1f}%)，建议检查多源数据同步")
                elif 'accuracy' in metric_name:
                    recommendations.append(f"数据准确性({metric_name})较低({score:.1f}%)，建议验证数据源准确性")
                elif 'availability' in metric_name:
                    recommendations.append(f"数据可用性({metric_name})较低({score:.1f}%)，建议检查数据源连接")
        
        # 如果没有低分项，添加正面反馈
        if not recommendations and component_scores:
            recommendations.append("所有数据质量指标均表现良好，继续保持")
        
        return recommendations
    
    def _cleanup_old_metrics(self) -> None:
        """清理旧的质量指标数据"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        for key in list(self.metrics_history.keys()):
            # 过滤旧数据
            self.metrics_history[key] = [
                m for m in self.metrics_history[key] 
                if m['timestamp'] >= cutoff_time
            ]
            
            # 如果列表为空，删除该键
            if not self.metrics_history[key]:
                del self.metrics_history[key]
    
    def reset_metrics(self) -> None:
        """重置所有质量指标"""
        self.metrics_history = {}
        self.cleanup_counter = 0
    
    def export_metrics(self, file_path: str) -> None:
        """
        导出质量指标数据
        
        参数:
            file_path: 导出文件路径
        """
        import json
        
        export_data = {
            'export_time': datetime.now().isoformat(),
            'retention_days': self.retention_days,
            'metrics': self.metrics_history
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            # 转换datetime对象为字符串
            def datetime_converter(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            json.dump(export_data, f, default=datetime_converter, ensure_ascii=False, indent=2)
    
    def import_metrics(self, file_path: str) -> None:
        """
        导入质量指标数据
        
        参数:
            file_path: 导入文件路径
        """
        import json
        from datetime import datetime
        
        with open(file_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        # 转换字符串为datetime对象
        def convert_timestamps(metrics_dict):
            for key, records in metrics_dict.items():
                for record in records:
                    if 'timestamp' in record and isinstance(record['timestamp'], str):
                        record['timestamp'] = datetime.fromisoformat(record['timestamp'])
        
        convert_timestamps(import_data['metrics'])
        
        self.metrics_history = import_data['metrics']
        self.retention_days = import_data.get('retention_days', self.retention_days)


# 单例实例
_quality_metrics_tracker = None

def get_quality_metrics_tracker(retention_days: int = 7) -> QualityMetricsTracker:
    """
    获取质量指标追踪器单例实例
    
    参数:
        retention_days: 指标保留天数
    
    返回:
        QualityMetricsTracker实例
    """
    global _quality_metrics_tracker
    
    if _quality_metrics_tracker is None:
        _quality_metrics_tracker = QualityMetricsTracker(retention_days)
    
    return _quality_metrics_tracker


if __name__ == "__main__":
    # 测试代码
    tracker = QualityMetricsTracker(retention_days=1)
    
    # 添加测试指标
    now = datetime.now()
    for i in range(10):
        tracker.add_metric('data_quality', 'data_completeness', 85 + i, 
                          timestamp=now - timedelta(hours=i))
        tracker.add_metric('data_quality', 'data_freshness', 90 + i, 
                          timestamp=now - timedelta(hours=i))
        tracker.add_metric('validation', 'price_consistency_pass_rate', 95 - i, 
                          timestamp=now - timedelta(hours=i))
    
    # 生成报告
    report = tracker.generate_comprehensive_report()
    
    print("质量指标追踪器测试报告:")
    print(f"系统状态: {report['system_status']}")
    print(f"综合评分: {report['comprehensive_score']:.1f}")
    print(f"数据质量评分: {report['data_quality']['overall_score']:.1f}")
    print(f"验证通过率: {report['validation']['overall_pass_rate']:.1f}%")
    print(f"指标总数: {report['metrics_summary']['total_metrics']}")
    print(f"记录总数: {report['metrics_summary']['total_records']}")