#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量保证系统
整合多源数据验证、数据质量检查和实时监控的完整质量保证体系
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from ..validation.multisource_validator import MultiSourceDataValidator, DataSource, ValidationLevel
from ..validation.data_quality_checker import DataQualityChecker
from ..validation.consistency_validator import ConsistencyValidator
from ..monitoring.realtime_monitor import RealtimeDataMonitor, AlertLevel

logger = logging.getLogger(__name__)

class QualityAssuranceSystem:
    """数据质量保证系统"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化质量保证系统
        
        Parameters:
        -----------
        config : Dict
            配置参数，包括验证规则、监控配置等
        """
        self.config = config or self._get_default_config()
        
        # 初始化各个组件
        self.multisource_validator = MultiSourceDataValidator(
            min_sources_required=self.config['validation']['min_sources_required']
        )
        
        self.data_quality_checker = DataQualityChecker(
            config=self.config['quality_checking']
        )
        
        self.consistency_validator = ConsistencyValidator(
            config=self.config['consistency_checking']
        )
        
        self.realtime_monitor = RealtimeDataMonitor(
            config=self.config['monitoring']
        )
        
        # 质量历史记录
        self.quality_history = []
        self.max_history_size = self.config.get('max_history_size', 1000)
        
        # 系统状态
        self.is_running = False
        self.monitoring_thread = None
        
        logger.info("数据质量保证系统初始化完成")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'validation': {
                'min_sources_required': 2,
                'price_diff_threshold': 0.05,  # 5%价格差异阈值
                'volume_diff_threshold': 0.20,  # 20%成交量差异阈值
                'max_data_age_minutes': 5,  # 最大数据年龄
                'required_fields': ['price', 'volume', 'timestamp', 'change_pct']
            },
            'quality_checking': {
                'missing_values': {
                    'allowed_missing_rate': 0.05,
                    'critical_fields': ['price', 'volume', 'timestamp']
                },
                'outliers': {
                    'z_score_threshold': 3.0,
                    'price_outlier_threshold': 0.10
                }
            },
            'consistency_checking': {
                'price_range': {
                    'min_price': 0.01,
                    'max_price': 10000,
                    'daily_change_limit': 0.50
                },
                'business_logic': {
                    'high_low_relation': True,
                    'open_close_range': True
                }
            },
            'monitoring': {
                'monitoring_interval': 30,  # 监控间隔（秒）
                'alert_cooldown_minutes': 10,
                'metrics': {
                    'data_freshness': {
                        'description': '数据新鲜度',
                        'unit': '分钟',
                        'threshold': {
                            'critical': 30,
                            'high': 15,
                            'medium': 5,
                            'low': 2
                        }
                    },
                    'data_quality_score': {
                        'description': '数据质量评分',
                        'unit': '分数',
                        'threshold': {
                            'critical': 60,
                            'high': 70,
                            'medium': 80,
                            'low': 90
                        }
                    }
                }
            },
            'max_history_size': 1000,
            'auto_start_monitoring': True
        }
    
    def start_quality_assurance(self):
        """启动质量保证系统"""
        if self.is_running:
            logger.warning("质量保证系统已经在运行中")
            return
        
        self.is_running = True
        
        # 启动实时监控
        if self.config.get('auto_start_monitoring', True):
            self.realtime_monitor.start_monitoring()
            logger.info("实时监控已启动")
        
        # 启动质量监控线程
        self.monitoring_thread = threading.Thread(target=self._quality_monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("数据质量保证系统已启动")
    
    def stop_quality_assurance(self):
        """停止质量保证系统"""
        self.is_running = False
        
        # 停止实时监控
        self.realtime_monitor.stop_monitoring()
        
        # 等待监控线程结束
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("数据质量保证系统已停止")
    
    def _quality_monitoring_loop(self):
        """质量监控循环"""
        logger.info("质量监控循环开始")
        
        while self.is_running:
            try:
                # 更新监控指标
                self._update_monitoring_metrics()
                
                # 清理历史记录
                self._cleanup_history()
                
            except Exception as e:
                logger.error(f"质量监控循环异常: {e}")
            
            # 等待下一次检查
            time.sleep(60)  # 每分钟检查一次
        
        logger.info("质量监控循环结束")
    
    def _update_monitoring_metrics(self):
        """更新监控指标"""
        try:
            # 从历史记录中计算平均质量分数
            if self.quality_history:
                recent_history = self.quality_history[-24:]  # 最近24条记录
                avg_quality_score = sum(h.get('quality_score', 0) for h in recent_history) / len(recent_history)
                avg_consensus_score = sum(h.get('consensus_score', 0) for h in recent_history) / len(recent_history)
                
                # 更新监控指标
                self.realtime_monitor.add_metric('data_quality_score', avg_quality_score)
                self.realtime_monitor.add_metric('data_consistency', avg_consensus_score)
                
                # 计算数据新鲜度（基于最近验证时间）
                if recent_history:
                    latest_timestamp = max(h.get('timestamp', datetime.min) for h in recent_history)
                    if isinstance(latest_timestamp, str):
                        latest_timestamp = datetime.fromisoformat(latest_timestamp.replace('Z', '+00:00'))
                    
                    freshness_minutes = (datetime.now() - latest_timestamp).total_seconds() / 60
                    self.realtime_monitor.add_metric('data_freshness', freshness_minutes)
            
        except Exception as e:
            logger.error(f"更新监控指标失败: {e}")
    
    def _cleanup_history(self):
        """清理历史记录"""
        if len(self.quality_history) > self.max_history_size:
            # 保留最近的历史记录
            self.quality_history = self.quality_history[-self.max_history_size:]
            logger.debug(f"清理历史记录，保留最近 {self.max_history_size} 条")
    
    def validate_multi_source_data(self, stock_code: str, data_sources: List[Tuple[DataSource, Dict]]) -> Dict:
        """
        验证多源数据
        
        Parameters:
        -----------
        stock_code : str
            股票代码
        data_sources : List[Tuple[DataSource, Dict]]
            数据源列表，每个元素为(数据源类型, 数据字典)
            
        Returns:
        --------
        Dict: 验证结果
        """
        logger.info(f"开始多源数据验证: {stock_code}")
        
        # 清空之前的数据源
        self.multisource_validator.data_sources = []
        
        # 添加数据源
        for source_type, data in data_sources:
            self.multisource_validator.add_data_source(source_type, data)
        
        try:
            # 执行多源验证
            multisource_result = self.multisource_validator.validate_multi_source_data(stock_code)
            
            # 转换为DataFrame进行质量检查
            if data_sources:
                # 使用第一个数据源的数据进行质量检查
                first_data = data_sources[0][1]
                df_data = pd.DataFrame([first_data])
                
                # 数据质量检查
                quality_report = self.data_quality_checker.check_data_quality(
                    df_data, 
                    source_name=f"{stock_code}_source1"
                )
                
                # 一致性验证
                consistency_report = self.consistency_validator.validate_consistency(
                    df_data,
                    data_source=stock_code
                )
                
                # 生成综合质量评估
                overall_quality = self._calculate_overall_quality(
                    multisource_result,
                    quality_report,
                    consistency_report
                )
                
                # 记录到历史
                quality_record = {
                    'stock_code': stock_code,
                    'timestamp': datetime.now().isoformat(),
                    'multisource_result': multisource_result,
                    'quality_report': quality_report,
                    'consistency_report': consistency_report,
                    'overall_quality': overall_quality,
                    'quality_score': overall_quality['overall_score'],
                    'consensus_score': multisource_result.consensus_score,
                    'is_reliable': multisource_result.is_reliable
                }
                
                self.quality_history.append(quality_record)
                
                # 更新监控指标
                self._update_metrics_from_validation(quality_record)
                
                # 生成综合报告
                final_report = self._generate_comprehensive_report(quality_record)
                
                logger.info(f"多源数据验证完成: {stock_code}, 总体质量分数: {overall_quality['overall_score']:.1f}")
                
                return final_report
            
            else:
                raise ValueError("没有提供数据源")
                
        except Exception as e:
            logger.error(f"多源数据验证失败: {e}")
            raise
    
    def _calculate_overall_quality(self, multisource_result, quality_report, consistency_report) -> Dict:
        """计算总体质量"""
        # 权重分配
        weights = {
            'multisource_consensus': 0.40,  # 多源一致性权重
            'data_quality': 0.30,           # 数据质量权重
            'consistency': 0.30             # 一致性权重
        }
        
        # 多源一致性分数（0-100）
        multisource_score = multisource_result.quality_score
        
        # 数据质量分数（0-100）
        data_quality_score = quality_report.quality_score
        
        # 一致性分数（0-100）
        consistency_score = consistency_report.overall_consistency_score
        
        # 计算加权平均
        overall_score = (
            multisource_score * weights['multisource_consensus'] +
            data_quality_score * weights['data_quality'] +
            consistency_score * weights['consistency']
        )
        
        # 确定质量等级
        if overall_score >= 90:
            quality_level = "优秀"
        elif overall_score >= 80:
            quality_level = "良好"
        elif overall_score >= 70:
            quality_level = "一般"
        elif overall_score >= 60:
            quality_level = "及格"
        else:
            quality_level = "不及格"
        
        return {
            'overall_score': overall_score,
            'quality_level': quality_level,
            'component_scores': {
                'multisource_consensus': multisource_score,
                'data_quality': data_quality_score,
                'consistency': consistency_score
            },
            'weights': weights,
            'is_acceptable': overall_score >= 70,  # 70分以上为可接受
            'recommendations': self._generate_quality_recommendations(
                multisource_score, data_quality_score, consistency_score
            )
        }
    
    def _generate_quality_recommendations(self, multisource_score: float, data_quality_score: float, consistency_score: float) -> List[str]:
        """生成质量改进建议"""
        recommendations = []
        
        if multisource_score < 80:
            recommendations.append("多源数据一致性不足，建议增加数据源或选择更可靠的数据源")
        
        if data_quality_score < 80:
            recommendations.append("数据质量问题较多，建议检查数据收集和处理流程")
        
        if consistency_score < 80:
            recommendations.append("数据内部一致性有待提高，建议优化数据验证规则")
        
        if all(score >= 90 for score in [multisource_score, data_quality_score, consistency_score]):
            recommendations.append("数据质量优秀，继续保持当前的数据管理策略")
        
        return recommendations
    
    def _update_metrics_from_validation(self, quality_record: Dict):
        """从验证结果更新监控指标"""
        try:
            # 更新数据质量评分
            self.realtime_monitor.add_metric(
                'data_quality_score',
                quality_record['overall_quality']['overall_score']
            )
            
            # 更新数据一致性
            self.realtime_monitor.add_metric(
                'data_consistency',
                quality_record['consensus_score']
            )
            
            # 更新验证失败率（如果有验证失败）
            multisource_result = quality_record['multisource_result']
            total_validations = len(multisource_result.validation_results)
            failed_validations = sum(1 for r in multisource_result.validation_results if not r.passed)
            
            if total_validations > 0:
                failure_rate = (failed_validations / total_validations) * 100
                self.realtime_monitor.add_metric('validation_failure_rate', failure_rate)
            
        except Exception as e:
            logger.error(f"更新监控指标失败: {e}")
    
    def _generate_comprehensive_report(self, quality_record: Dict) -> Dict:
        """生成综合报告"""
        multisource_result = quality_record['multisource_result']
        quality_report = quality_record['quality_report']
        consistency_report = quality_record['consistency_report']
        overall_quality = quality_record['overall_quality']
        
        report = {
            'stock_code': multisource_result.stock_code,
            'validation_time': multisource_result.timestamp.isoformat(),
            'overall_quality': overall_quality,
            'multisource_validation': {
                'sources_used': [s.value for s in multisource_result.sources_used],
                'consensus_score': multisource_result.consensus_score,
                'quality_score': multisource_result.quality_score,
                'is_reliable': multisource_result.is_reliable,
                'validation_summary': {
                    'total': len(multisource_result.validation_results),
                    'passed': sum(1 for r in multisource_result.validation_results if r.passed),
                    'failed': sum(1 for r in multisource_result.validation_results if not r.passed)
                }
            },
            'data_quality': {
                'quality_score': quality_report.quality_score,
                'total_issues': len(quality_report.issues_found),
                'issue_summary': quality_report.issue_summary,
                'recommendations': quality_report.recommendations
            },
            'consistency_validation': {
                'consistency_score': consistency_report.overall_consistency_score,
                'total_checks': consistency_report.total_checks,
                'passed_checks': consistency_report.passed_checks,
                'failed_checks': consistency_report.failed_checks
            },
            'system_status': {
                'monitoring_active': self.realtime_monitor.is_running,
                'total_validations': len(self.quality_history),
                'recent_quality_trend': self._get_recent_quality_trend()
            }
        }
        
        return report
    
    def _get_recent_quality_trend(self, num_points: int = 10) -> List[float]:
        """获取最近质量趋势"""
        if not self.quality_history:
            return []
        
        recent_history = self.quality_history[-num_points:]
        return [record.get('quality_score', 0) for record in recent_history]
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            'is_running': self.is_running,
            'monitoring_active': self.realtime_monitor.is_running,
            'total_quality_records': len(self.quality_history),
            'recent_quality_score': self._get_recent_average_quality(),
            'alerts_last_hour': len(self.realtime_monitor.get_recent_alerts(limit=100)),
            'components_status': {
                'multisource_validator': 'active',
                'data_quality_checker': 'active',
                'consistency_validator': 'active',
                'realtime_monitor': 'active' if self.realtime_monitor.is_running else 'inactive'
            }
        }
    
    def _get_recent_average_quality(self, hours: int = 1) -> Optional[float]:
        """获取最近平均质量分数"""
        if not self.quality_history:
            return None
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_records = []
        for record in self.quality_history:
            timestamp = record.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            if timestamp >= cutoff_time:
                recent_records.append(record)
        
        if not recent_records:
            return None
        
        avg_score = sum(r.get('quality_score', 0) for r in recent_records) / len(recent_records)
        return avg_score
    
    def generate_system_report(self, output_file: str = None) -> str:
        """生成系统报告"""
        system_status = self.get_system_status()
        
        # 获取监控报告
        monitoring_report = self.realtime_monitor.generate_monitoring_report(duration_hours=1)
        
        # 获取最近验证记录
        recent_validations = self.quality_history[-10:] if self.quality_history else []
        
        report = {
            'report_time': datetime.now().isoformat(),
            'system_status': system_status,
            'monitoring_summary': {
                'total_alerts': monitoring_report['total_alerts'],
                'alert_statistics': monitoring_report['alert_statistics'],
                'metric_statistics': monitoring_report['metric_statistics']
            },
            'recent_validations': [
                {
                    'stock_code': v['stock_code'],
                    'timestamp': v['timestamp'],
                    'quality_score': v['quality_score'],
                    'is_reliable': v['is_reliable']
                }
                for v in recent_validations
            ],
            'quality_trend': self._get_recent_quality_trend(),
            'recommendations': self._generate_system_recommendations(system_status, monitoring_report)
        }
        
        # 转换为JSON字符串
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        
        # 保存到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_json)
            logger.info(f"系统报告已保存到: {output_file}")
        
        return report_json
    
    def _generate_system_recommendations(self, system_status: Dict, monitoring_report: Dict) -> List[str]:
        """生成系统改进建议"""
        recommendations = []
        
        # 检查监控状态
        if not system_status['monitoring_active']:
            recommendations.append("实时监控未启动，建议启动监控以获取实时数据质量信息")
        
        # 检查报警数量
        total_alerts = monitoring_report['total_alerts']
        if total_alerts > 50:
            recommendations.append(f"最近一小时报警数量较多 ({total_alerts}个)，建议检查数据质量问题")
        
        # 检查质量趋势
        quality_trend = self._get_recent_quality_trend()
        if len(quality_trend) >= 5:
            # 检查质量是否下降
            if quality_trend[-1] < quality_trend[0] * 0.9:  # 下降超过10%
                recommendations.append("数据质量呈下降趋势，建议检查数据源和验证规则")
        
        # 检查验证频率
        if len(self.quality_history) < 10:
            recommendations.append("验证记录较少，建议增加数据验证频率")
        
        return recommendations


# 使用示例
def example_usage():
    """质量保证系统示例"""
    print("=" * 60)
    print("Zhulinsma数据质量保证系统示例")
    print("=" * 60)
    
    # 创建质量保证系统
    print("\n1. 创建质量保证系统...")
    qas = QualityAssuranceSystem()
    
    # 启动系统
    print("\n2. 启动质量保证系统...")
    qas.start_quality_assurance()
    
    # 模拟数据源
    print("\n3. 准备模拟数据源...")
    from datetime import datetime, timedelta
    
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
        'price': 10.92,
        'prev_close': 10.88,
        'high': 11.01,
        'low': 10.84,
        'volume': 73000000,
        'amount': 800000000,
        'change_pct': 0.37,
        'timestamp': (datetime.now() - timedelta(minutes=2)).isoformat()
    }
    
    data_sources = [
        (DataSource.TUSHARE_PRO, tushare_data),
        (DataSource.TENCENT_API, tencent_data)
    ]
    
    # 执行验证
    print("\n4. 执行多源数据验证...")
    try:
        report = qas.validate_multi_source_data("000001.SZ", data_sources)
        
        print(f"\n验证完成:")
        print(f"  股票代码: {report['stock_code']}")
        print(f"  总体质量分数: {report['overall_quality']['overall_score']:.1f}")
        print(f"  质量等级: {report['overall_quality']['quality_level']}")
        print(f"  是否可接受: {'是' if report['overall_quality']['is_acceptable'] else '否'}")
        
        print(f"\n多源验证:")
        ms_val = report['multisource_validation']
        print(f"  使用数据源: {', '.join(ms_val['sources_used'])}")
        print(f"  一致性分数: {ms_val['consensus_score']:.3f}")
        print(f"  质量分数: {ms_val['quality_score']:.1f}")
        print(f"  是否可靠: {'是' if ms_val['is_reliable'] else '否'}")
        
        print(f"\n数据质量:")
        dq = report['data_quality']
        print(f"  质量分数: {dq['quality_score']:.1f}")
        print(f"  发现问题: {dq['total_issues']}个")
        
        print(f"\n一致性验证:")
        cv = report['consistency_validation']
        print(f"  一致性分数: {cv['consistency_score']:.1f}")
        print(f"  通过检查: {cv['passed_checks']}/{cv['total_checks']}")
        
    except Exception as e:
        print(f"验证失败: {e}")
    
    # 获取系统状态
    print("\n5. 获取系统状态...")
    status = qas.get_system_status()
    print(f"  系统运行中: {'是' if status['is_running'] else '否'}")
    print(f"  监控运行中: {'是' if status['monitoring_active'] else '否'}")
    print(f"  质量记录数: {status['total_quality_records']}")
    print(f"  最近质量分数: {status['recent_quality_score']:.1f if status['recent_quality_score'] else 'N/A'}")
    
    # 生成系统报告
    print("\n6. 生成系统报告...")
    system_report = qas.generate_system_report()
    print("  系统报告生成完成")
    
    # 停止系统
    print("\n7. 停止质量保证系统...")
    qas.stop_quality_assurance()
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    example_usage()