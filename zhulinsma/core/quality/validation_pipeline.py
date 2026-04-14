#!/usr/bin/env python3
"""
验证管道模块
构建完整的数据验证管道，整合多源验证、质量检查和实时监控
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import time

from zhulinsma.core.validation.multisource_validator import MultiSourceDataValidator, DataSource, ValidationLevel
from zhulinsma.core.validation.data_quality_checker import DataQualityChecker
from zhulinsma.core.validation.consistency_validator import ConsistencyValidator
from zhulinsma.core.monitoring.realtime_monitor import RealtimeDataMonitor, AlertLevel, AlertChannel
from zhulinsma.core.monitoring.quality_metrics import QualityMetricsTracker

class PipelineStage(Enum):
    """管道阶段枚举"""
    RAW_DATA = "raw_data"               # 原始数据
    DATA_CLEANING = "data_cleaning"     # 数据清洗
    MULTISOURCE_VALIDATION = "multisource_validation"  # 多源验证
    QUALITY_CHECK = "quality_check"     # 质量检查
    CONSISTENCY_VALIDATION = "consistency_validation"  # 一致性验证
    FINAL_REVIEW = "final_review"       # 最终审查


class ValidationPipeline:
    """
    验证管道
    构建完整的数据验证管道，整合多源验证、质量检查和实时监控
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化验证管道
        
        参数:
            config: 配置字典
        """
        self.config = config or self._get_default_config()
        
        # 初始化验证组件
        self.multisource_validator = MultiSourceDataValidator()
        self.quality_checker = DataQualityChecker()
        self.consistency_validator = ConsistencyValidator()
        
        # 初始化监控组件
        self.monitor = RealtimeDataMonitor(
            check_interval_minutes=self.config['monitoring_interval_minutes'],
            alert_cooldown_minutes=self.config['alert_cooldown_minutes'],
            enable_log_alerts=self.config['enable_log_alerts'],
            enable_email_alerts=self.config['enable_email_alerts'],
            enable_webhook_alerts=self.config['enable_webhook_alerts'],
            enable_dashboard=self.config['enable_dashboard']
        )
        
        # 初始化质量指标追踪器
        self.metrics_tracker = QualityMetricsTracker(
            retention_days=self.config['metrics_retention_days']
        )
        
        # 管道状态
        self.pipeline_history: List[Dict] = []
        self.max_history_size = 500
        
        print(f"🚀 验证管道初始化完成")
        print(f"   监控间隔: {self.config['monitoring_interval_minutes']}分钟")
        print(f"   报警冷却: {self.config['alert_cooldown_minutes']}分钟")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'monitoring_interval_minutes': 30,
            'alert_cooldown_minutes': 60,
            'enable_log_alerts': True,
            'enable_email_alerts': False,
            'enable_webhook_alerts': False,
            'enable_dashboard': True,
            'metrics_retention_days': 7,
            'strict_mode': True,
            'enable_auto_fix': False,
            'validation_timeout_seconds': 30
        }
    
    def run_pipeline(self, 
                    data_sources: List[Dict],
                    stock_code: str,
                    validate_mode: bool = True,
                    monitor_enabled: bool = True) -> Dict[str, Any]:
        """
        运行完整的验证管道
        
        参数:
            data_sources: 数据源列表
            stock_code: 股票代码
            validate_mode: 是否启用验证
            monitor_enabled: 是否启用监控
        
        返回:
            管道执行报告
        """
        pipeline_start = datetime.now()
        pipeline_id = f"pipeline_{stock_code}_{pipeline_start.strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n🔧 开始运行验证管道 [{pipeline_id}]")
        print(f"   股票代码: {stock_code}")
        print(f"   数据源数量: {len(data_sources)}")
        print(f"   验证模式: {'启用' if validate_mode else '禁用'}")
        
        # 记录管道开始
        pipeline_record = {
            'pipeline_id': pipeline_id,
            'start_time': pipeline_start.isoformat(),
            'stock_code': stock_code,
            'data_source_count': len(data_sources),
            'validate_mode': validate_mode,
            'monitor_enabled': monitor_enabled,
            'stages': []
        }
        
        try:
            # 阶段1: 原始数据检查和清洗
            print(f"\n📊 阶段1: 原始数据检查和清洗")
            原始数据报告 = self._process_raw_data(data_sources, stock_code)
            管道记录 = self._add_stage_record(PipelineStage.RAW_DATA, 原始数据报告)
            pipeline_record['stages'].append(管道记录)
            
            if not 原始数据报告.get('valid', False):
                print(f"❌ 原始数据检查失败: {原始数据报告.get('error', '未知错误')}")
                return self._create_failed_pipeline_report(pipeline_record, pipeline_start)
            
            # 阶段2: 多源数据验证
            if validate_mode:
                print(f"\n🔍 阶段2: 多源数据验证")
                多源验证报告 = self._run_multisource_validation(data_sources, stock_code)
                管道记录 = self._add_stage_record(PipelineStage.MULTISOURCE_VALIDATION, 多源验证报告)
                pipeline_record['stages'].append(管道记录)
                
                if not 多源验证报告.get('passed', False):
                    print(f"⚠️ 多源验证失败: {多源验证报告.get('failure_reason', '未知原因')}")
            
            # 阶段3: 数据质量检查
            print(f"\n📈 阶段3: 数据质量检查")
            质量检查报告 = self._run_quality_checks(data_sources, stock_code)
            管道记录 = self._add_stage_record(PipelineStage.QUALITY_CHECK, 质量检查报告)
            pipeline_record['stages'].append(管道记录)
            
            # 阶段4: 一致性验证

            print(f"\n🔗 阶段4: 一致性验证")
            一致性验证报告 = self._run_consistency_validation(data_sources, stock_code)
            管道记录 = self._add_stage_record(PipelineStage.CONSISTENCY_VALIDATION, 一致性验证报告)
            pipeline_record['stages'].append(管道记录)
            
            # 阶段5: 综合质量评估
            print(f"\n📋 阶段5: 综合质量评估")
            综合报告 = self._generate_comprehensive_report(
                stock_code, 
                [原始数据报告, 多源验证报告 if validate_mode else None, 质量检查报告, 一致性验证报告]
            )
            
            # 添加综合质量报告
            pipeline_record['comprehensive_report'] = 综合报告
            
            # 阶段6: 监控更新（如果启用）
            if monitor_enabled:
                print(f"\n🔍 阶段6: 更新监控系统")
                监控更新报告 = self._update_monitoring_system(stock_code, 综合报告)
                pipeline_record['monitoring_update'] = 监控更新报告
            
            # 记录管道完成
            pipeline_end = datetime.now()
            pipeline_duration = (pipeline_end - pipeline_start).total_seconds()
            
            pipeline_record['end_time'] = pipeline_end.isoformat()
            pipeline_record['duration_seconds'] = pipeline_duration
            pipeline_record['status'] = 'completed'
            pipeline_record['overall_quality_score'] = 综合报告.get('overall_quality_score', 0)
            
            # 保存管道历史
            self._save_pipeline_history(pipeline_record)
            
            # 更新质量指标
            self._update_quality_metrics(stock_code, 综合报告)
            
            print(f"\n✅ 验证管道完成!")
            print(f"   总耗时: {pipeline_duration:.2f}秒")
            print(f"   综合质量分数: {综合报告.get('overall_quality_score', 0):.1f}")
            print(f"   验证状态: {'通过' if validate_mode and 多源验证报告.get('passed', False) else '未通过'}")
            
            return pipeline_record
            
        except Exception as e:
            print(f"\n❌ 验证管道执行异常: {e}")
            import traceback
            traceback.print_exc()
            
            return self._create_failed_pipeline_report(pipeline_record, pipeline_start, str(e))
    
    def _process_raw_data(self, data_sources: List[Dict], stock_code: str) -> Dict[str, Any]:
        """处理原始数据阶段"""
        阶段报告 = {
            'stage': PipelineStage.RAW_DATA.value,
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'valid': True,
            'details': {}
        }
        
        try:
            # 检查数据源数量
            if len(data_sources) < 1:
                阶段报告['valid'] = False
                阶段报告['error'] = '没有提供数据源'
                return 阶段报告
            
            # 检查每个数据源的基本结构
            for i, source in enumerate(data_sources):
                源编号 = f"source_{i+1}"
                
                # 检查必需字段
                必需字段 = ['close']
                missing_fields = [field for field in 必需字段 if field not in source]
                
                if missing_fields:
                    阶段报告['valid'] = False
                    阶段报告['error'] = f'数据源 {i+1} 缺少必需字段: {missing_fields}'
                    break
                
                # 检查数据格式
                if not isinstance(source['close'], (list, np.ndarray)):
                    阶段报告['valid'] = False
                    阶段报告['error'] = f'数据源 {i+1} 收盘价格式不正确'
                    break
                
                # 记录数据信息
                阶段报告['details'][源编号] = {
                    'data_size': len(source['close']),
                    'data_type': str(type(source['close'])),
                    'has_volume': 'volume' in source,
                    'has_timestamps': 'timestamps' in source
                }
            
            # 简单数据清洗示例
            if 阶段报告['valid']:
                # 检查所有数据源的长度是否一致
                数据长度 = [len(source['close']) for source in data_sources]
                长度一致 = len(set(数据长度)) == 1
                阶段报告['details']['data_consistency'] = {
                    'all_same_length': 长度一致,
                    'lengths': 数据长度,
                    'max_length': max(数据长度) if 数据长度 else 0,
                    'min_length': min(数据长度) if 数据长度 else 0
                }
                
                if not 长度一致:
                    print(f"⚠️ 数据源长度不一致: {数据长度}")
                
                # 检查缺失值
                missing_info = {}
                for i, source in enumerate(data_sources):
                    close_data = np.array(source['close'])
                    missing_count = np.sum(np.isnan(close_data))
                    missing_percentage = missing_count / len(close_data) if len(close_data) > 0 else 0
                    
                    missing_info[f'source_{i+1}'] = {
                        'missing_count': int(missing_count),
                        'missing_percentage': float(missing_percentage)
                    }
                
                阶段报告['details']['missing_values'] = missing_info
            
        except Exception as e:
            阶段报告['valid'] = False
            阶段报告['error'] = f'原始数据处理异常: {str(e)}'
        
        return 阶段报告
    
    def _run_multisource_validation(self, data_sources: List[Dict], stock_code: str) -> Dict[str, Any]:
        """运行多源数据验证阶段"""
        阶段报告 = {
            'stage': PipelineStage.MULTISOURCE_VALIDATION.value,
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'passed': False,
            'details': {}
        }
        
        try:
            # 运行多源验证
            验证结果 = self.multisource_validator.validate(
                data_sources=data_sources,
                stock_code=stock_code
            )
            
            # 解析验证结果
            阶段报告['passed'] = 验证结果.get('passed', False)
            阶段报告['failure_reason'] = 验证结果.get('failure_reason')
            阶段报告['details'] = {
                'validation_report': 验证结果.get('validation_report', {}),
                'failed_checks': 验证结果.get('failed_checks', []),
                'quality_score': 验证结果.get('quality_score', 0)
            }
            
        except Exception as e:
            阶段报告['failure_reason'] = f'多源验证异常: {str(e)}'
        
        return 阶段报告
    
    def _run_quality_checks(self, data_sources: List[Dict], stock_code: str) -> Dict[str, Any]:
        """运行数据质量检查阶段"""
        阶段报告 = {
            'stage': PipelineStage.QUALITY_CHECK.value,
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'details': {}
        }
        
        try:
            # 对每个数据源进行质量检查
            quality_reports = []
            
            for i, source in enumerate(data_sources):
                源编号 = f"source_{i+1}"
                
                # 准备数据
                close_data = np.array(source.get('close', []))
                volume_data = np.array(source.get('volume', [])) if 'volume' in source else None
                timestamps = source.get('timestamps', []) if 'timestamps' in source else None
                metadata = {
                    'stock_code': stock_code,
                    'source_name': 源编号,
                    'check_timestamp': datetime.now().isoformat()
                }

                # 运行质量检查

                质量报告 = self.quality_checker.check_data_quality(
                    close_prices=close_data,
                    volumes=volume_data,
                    timestamps=timestamps,
                    metadata=metadata
                )
                
                quality_reports.append({
                    'source': 源编号,
                    'report': 质量报告
                })
            
            阶段报告['details']['quality_reports'] = quality_reports
            阶段报告['details']['summary'] = {
                'total_checks': len(quality_reports),
                'passed_rate': np.mean([r['report'].get('passed', False) for r in quality_reports]) if quality_reports else 0
            }
            
        except Exception as e:
            阶段报告['details']['error'] = f'质量检查异常: {str(e)}'
        
        return 阶段报告
    
    def _run_consistency_validation(self, data_sources: List[Dict], stock_code: str) -> Dict[str, Any]:
        """运行一致性验证阶段"""
        阶段报告 = {
            'stage': PipelineStage.CONSISTENCY_VALIDATION.value,
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'details': {}
        }
        
        try:
            # 提取所有数据源的收盘价
            all_close_prices = []
            
            for i, source in enumerate(data_sources):
                close_data = np.array(source.get('close', []))
                all_close_prices.append(close_data)
            
            # 运行一致性验证

            一致性报告 = self.consistency_validator.validate_consistency(
                data_arrays=all_close_prices,
                validation_level=ValidationLevel.HIGH
            )
            
            阶段报告['details'] = 一致性报告
            
        except Exception as e:
            阶段报告['details']['error'] = f'一致性验证异常: {str(e)}'
        
        return 阶段报告
    
    def _generate_comprehensive_report(self, 
                                       stock_code: str, 
                                       stage_reports: List[Optional[Dict]]) -> Dict[str, Any]:
        """生成综合质量评估报告"""
        综合报告 = {
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'generated_at': datetime.now().isoformat(),
            'overall_quality_score': 0,
            'component_scores': {},
            'issues_summary': {},
            'recommendations': [],
            'validation_summary': {}
        }
        
        try:
            # 解析各个阶段的报告
            各阶段报告 = {}
            
            for report in stage_reports:
                if report is None:
                    continue
                
                阶段名称 = report.get('stage', 'unknown')
                各阶段报告[阶段名称] = report
            
            # 计算综合质量分数（加权平均）
            组件分数 = {}
            总权重 = 0
            
            # 多源验证分数
            if 'multisource_validation' in 各阶段报告:
                多源报告 = 各阶段报告['multisource_validation']
                多源分数 = 多源报告.get('details', {}).get('quality_score', 0)
                组件分数['multi_source_validation'] = {
                    'score': 多源分数,
                    'weight': 0.30
                }
                总权重 += 0.30
            
            # 质量检查分数
            if 'quality_check' in 各阶段报告:
                质量报告 = 各阶段报告['quality_check']
                质量分数 = 质量报告.get('details', {}).get('summary', {}).get('passed_rate', 0) * 100
                组件分数['quality_check'] = {
                    'score': 质量分数,
                    'weight': 0.40
                }
                总权重 += 0.40
            
            # 一致性验证分数
            if 'consistency_validation' in 各阶段报告:
                一致性报告 = 各阶段报告['consistency_validation']
                # 从一致性报告中提取质量分数
                一致性分数 = 一致性报告.get('details', {}).get('overall_quality_score', 0)
                组件分数['consistency_validation'] = {
                    'score': 一致性分数,
                    'weight': 0.30
                }
                总权重 += 0.30
            
            # 计算综合分数
            if 总权重 > 0:
                加权总分 = sum(comp['score'] * comp['weight'] for comp in 组件分数.values())
                综合质量分数 = 加权总分 / 总权重
            else:
                综合质量分数 = 0
            
            # 收集问题和建议
            所有问题 = []
            所有建议 = []
            
            for 阶段名称, 阶段报告 in 各阶段报告.items():
                详情 = 阶段报告.get('details', {})
                
                # 收集问题
                if 'errors' in 详情:
                    所有问题.extend(详情['errors'])
                if 'failed_checks' in 详情:
                    所有问题.extend(详情['failed_checks'])
                
                # 收集建议
                if 'recommendations' in 详情:
                    所有建议.extend(详情['recommendations'])
            
            # 更新综合报告
            综合报告['overall_quality_score'] = 综合质量分数
            综合报告['component_scores'] = 组件分数
            综合报告['issues_summary'] = {
                'total_issues': len(所有问题),
                'issues_by_type': self._classify_issues(所有问题)
            }
            综合报告['recommendations'] = 所有建议
            
            # 生成验证摘要
            验证摘要 = {
                'data_processed': True,
                'stages_completed': len(各阶段报告),
                'overall_status': 'passed' if 综合质量分数 >= 70 else 'failed',
                'critical_issues': [issue for issue in 所有问题 if 'critical' in issue.lower() or 'fatal' in issue.lower()]
            }
            
            综合报告['validation_summary'] = 验证摘要
            
        except Exception as e:
            综合报告['error'] = f'生成综合报告异常: {str(e)}'
        
        return 综合报告
    
    def _classify_issues(self, issues: List[str]) -> Dict[str, int]:
        """对问题进行分类统计"""
        分类统计 = {
            'data_quality': 0,
            'consistency': 0,
            'validation': 0,
            'format': 0,
            'other': 0
        }
        
        for issue in issues:
            issue_lower = issue.lower()
            
            if any(keyword in issue_lower for keyword in ['missing', 'outlier', 'quality']):
                分类统计['data_quality'] += 1
            elif any(keyword in issue_lower for keyword in ['consistency', 'match', 'alignment']):
                分类统计['consistency'] += 1
            elif any(keyword in issue_lower for keyword in ['validation', 'verify', 'check']):
                分类统计['validation'] += 1
            elif any(keyword in issue_lower for keyword in ['format', 'type', 'structure']):
                分类统计['format'] += 1
            else:
                分类统计['other'] += 1
        
        return 分类统计
    
    def _update_monitoring_system(self, stock_code: str, comprehensive_report: Dict) -> Dict[str, Any]:
        """更新监控系统阶段"""
        阶段报告 = {
            'stage': 'monitoring_update',
            'timestamp': datetime.now().isoformat(),
            'stock_code': stock_code,
            'details': {}
        }
        
        try:
            # 提取监控指标
            质量分数 = comprehensive_report.get('overall_quality_score', 0)
            问题数量 = comprehensive_report.get('issues_summary', {}).get('total_issues', 0)
            
            # 更新监控器指标
            监控指标 = {
                'stock_code': stock_code,
                'timestamp': datetime.now().isoformat(),
                'quality_score': 质量分数,
                'issue_count': 问题数量,
                'validation_status': comprehensive_report.get('validation_summary', {}).get('overall_status', 'unknown')
            }
            
            self.monitor.update_monitoring_metrics(监控指标)
            
            # 根据质量分数决定是否发送报警
            if 质量分数 < 70:
                # 发送中级报警
                self.monitor.send_alert(
                    level=AlertLevel.MEDIUM,
                    title=f"数据质量问题 - {stock_code}",
                    message=f"综合质量分数较低: {质量分数:.1f}，发现{问题数量}个问题",
                    source="validation_pipeline",
                    metadata={
                        'quality_score': 质量分数,
                        'issue_count': 问题数量,
                        'recommendations': comprehensive_report.get('recommendations', [])
                    }
                )
            
            # 记录监控更新
            阶段报告['details'] = {
                'metrics_updated': 监控指标,
                'quality_score': 质量分数,
                'alert_sent': 质量分数 < 70
            }
            
        except Exception as e:
            阶段报告['details']['error'] = f'监控更新异常: {str(e)}'
        
        return 阶段报告
    
    def _add_stage_record(self, stage: PipelineStage, stage_report: Dict) -> Dict:
        """添加阶段记录"""
        return {
            'stage': stage.value,
            'timestamp': stage_report.get('timestamp', datetime.now().isoformat()),
            'status': stage_report.get('status', 'unknown'),
            'details': stage_report.get('details', {})
        }
    
    def _create_failed_pipeline_report(self, 
                                      pipeline_record: Dict, 
                                      start_time: datetime, 
                                      error_message: Optional[str] = None) -> Dict[str, Any]:
        """创建失败的管道报告"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        pipeline_record['end_time'] = end_time.isoformat()
        pipeline_record['duration_seconds'] = duration
        pipeline_record['status'] = 'failed'
        
        if error_message:
            pipeline_record['error'] = error_message
        
        # 保存失败的管道记录
        self._save_pipeline_history(pipeline_record)
        
        return pipeline_record
    
    def _save_pipeline_history(self, pipeline_record: Dict) -> None:
        """保存管道历史"""
        self.pipeline_history.append(pipeline_record)
        
        # 限制历史记录大小

        if len(self.pipeline_history) > self.max_history_size:
            self.pipeline_history = self.pipeline_history[-self.max_history_size:]
    
    def _update_quality_metrics(self, stock_code: str, comprehensive_report: Dict) -> None:
        """更新质量指标"""
        try:
            质量分数 = comprehensive_report.get('overall_quality_score', 0)
        
            # 添加质量分数指标

            self.metrics_tracker.add_metric(
                metric_type='data_quality',
                metric_name='overall_score',
                value=质量分数,
                timestamp=datetime.now(),
                metadata={
                    'stock_code': stock_code,
                    'report_timestamp': comprehensive_report.get('timestamp')
                }
            )
        
        except Exception as e:
            print(f"⚠️ 更新质量指标失败: {e}")
    
    def get_pipeline_history(self, stock_code: Optional[str] = None, 
                           hours: Optional[int] = None) -> List[Dict]:
        """
        获取管道历史
        
        参数:
            stock_code: 股票代码过滤
            hours: 小时数过滤
        
        返回:
            管道历史列表
        """
        filtered_history = self.pipeline_history
        
        # 按时间过滤
        if hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered_history = [
                record for record in filtered_history
                if 'start_time' in record and 
                datetime.fromisoformat(record['start_time']) >= cutoff_time
            ]
        
        # 按股票代码过滤
        if stock_code is not None:
            filtered_history = [
                record for record in filtered_history
                if record.get('stock_code') == stock_code
            ]
        
        return filtered_history
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取性能报告
        
        参数:
            hours: 小时数
        
        返回:
            性能报告
        """
        recent_history = self.get_pipeline_history(hours=hours)
        
        if not recent_history:
            return {
                'total_pipelines': 0,
                'success_rate': 0.0,
                'average_duration': 0.0,
                'average_quality_score': 0.0,
                'timestamp': datetime.now().isoformat()
            }
        
        # 计算统计信息
        成功的管道 = [record for record in recent_history if record.get('status') == 'completed']
        失败的管道 = [record for record in recent_history if record.get('status') == 'failed']
        
        成功率 = len(成功的管道) / len(recent_history) * 100 if recent_history else 0
        
        # 计算平均耗时
        总耗时 = sum(record.get('duration_seconds', 0) for record in 成功的管道)
        平均耗时 = 总耗时 / len(成功的管道) if 成功的管道 else 0
        
        # 计算平均质量分数
        质量分数列表 = [record.get('overall_quality_score', 0) for record in 成功的管道]
        平均质量分数 = np.mean(质量分数列表) if 质量分数列表 else 0
        
        return {
            'total_pipelines': len(recent_history),
            'successful_pipelines': len(成功的管道),
            'failed_pipelines': len(失败的管道),
            'success_rate': 成功率,
            'average_duration_seconds': 平均耗时,
            'average_quality_score': 平均质量分数,
            'timestamp': datetime.now().isoformat(),
            'recent_performance': {
                'total_stages': sum(len(record.get('stages', [])) for record in recent_history),
                'average_stages_per_pipeline': sum(len(record.get('stages', [])) for record in recent_history) / len(recent_history) if len(recent_history) > 0 else 0
            }
        }
    
    def clear_pipeline_history(self) -> None:
        """清空管道历史"""
        self.pipeline_history = []
    
    def export_pipeline_report(self, file_path: str) -> None:
        """
        导出管道报告
        
        参数:
            file_path: 导出文件路径
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.pipeline_history, f, ensure_ascii=False, indent=2)
            print(f"✅ 管道报告已导出到: {file_path}")
        except Exception as e:
            print(f"❌ 管道报告导出失败: {e}")
    
    def start_monitoring(self) -> None:
        """启动监控系统"""
        self.monitor.start_monitoring()
        print("🔍 监控系统已启动")
    
    def stop_monitoring(self) -> None:
        """停止监控系统"""
        self.monitor.stop_monitoring()
        print("⏹️ 监控系统已停止")
    
    def get_monitoring_report(self) -> Dict[str, Any]:
        """获取监控报告"""
        return self.monitor.generate_monitoring_report()
    
    def generate_dashboard_data(self) -> Dict[str, Any]:
        """生成仪表板数据"""
        try:
            # 获取管道性能报告

            性能报告 = self.get_performance_report(hours=24)
            
            # 获取质量趋势

            质量趋势 = self.metrics_tracker.get_quality_trend(hours=24)
            
            # 获取最近的管道记录

            最近记录 = self.get_pipeline_history(hours=1)
            
            # 构建仪表板数据

            仪表板数据 = {
                'timestamp': datetime.now().isoformat(),
                'performance_summary': 性能报告,
                'quality_trend': 质量趋势,
                'recent_activity': {
                    'total_pipelines_last_hour': len(最近记录),
                    'success_rate_last_hour': len([r for r in 最近记录 if r.get('status') == 'completed']) / max(len(最近记录), 1) * 100,
                    'recent_issues': sum(len(r.get('issues', [])) for r in 最近记录) if 最近记录 else 0
                },
                'system_status': {
                    'monitoring_active': self.monitor.is_monitoring_active(),
                    'total_pipelines_executed': len(self.pipeline_history),
                    'average_quality_score_24h': 性能报告.get('average_quality_score', 0)
                },
                'generated_at': datetime.now().isoformat()
            }
            
            return 仪表板数据
            
        except Exception as e:
            return {
                'error': f'生成仪表板数据失败: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }


# 单例实例
_validation_pipeline = None

def get_validation_pipeline(config: Optional[Dict] = None) -> ValidationPipeline:
    """
    获取验证管道单例实例
    
    参数:
        config: 配置字典
    
    返回:
        ValidationPipeline实例
    """
    global _validation_pipeline
    
    if _validation_pipeline is None:
        _validation_pipeline = ValidationPipeline(config)
    
    return _validation_pipeline


if __name__ == "__main__":
    # 测试代码

    print("=== 验证管道测试 ===")
    
    # 创建验证管道

    管道 = ValidationPipeline()
    
    # 生成测试数据源

    print("\n📊 生成测试数据源...")
    np.random.seed(42)
    
    数据源1 = {
        'close': np.random.normal(100, 10, 50).cumsum() * 0.1 + 100,
        'volume': np.random.normal(1000000, 200000, 50),
        'timestamps': [(datetime.now() - timedelta(days=i)).isoformat() for i in range(49, -1, -1)],
        'source': 'test_source_1'
    }
    
    数据源2 = {
        'close': 数据源1['close'] * (1 + np.random.normal(0, 0.01, 50)),
        'volume': 数据源1['volume'] * (1 + np.random.normal(0, 0.05, 50)),
        'timestamps': 数据源1['timestamps'],
        'source': 'test_source_2'
    }
    
    数据源列表 = [数据源1, 数据源2]
    
    print(f"  数据源1长度: {len(数据源1['close'])}")
    print(f"  数据源2长度: {len(数据源2['close'])}")
    
    # 运行验证管道

    print("\n🚀 运行验证管道...")
    管道报告 = 管道.run_pipeline(
        data_sources=数据源列表,
        stock_code='TEST001',
        validate_mode=True,
        monitor_enabled=True
    )
    
    # 显示管道结果

    print(f"\n📋 管道执行结果:")
    print(f"  管道ID: {管道报告.get('pipeline_id')}")
    print(f"  状态: {管道报告.get('status')}")
    print(f"  耗时: {管道报告.get('duration_seconds', 0):.2f}秒")
    
    if 管道报告.get('status') == 'completed':
        print(f"  综合质量分数: {管道报告.get('overall_quality_score', 0):.1f}")
        print(f"  阶段完成: {len(管道报告.get('stages', []))}个")
        
        # 显示各阶段摘要

        print(f"\n📊 各阶段摘要:")
        for 阶段 in 管道报告.get('stages', []):
            print(f"  - {阶段.get('stage')}: {阶段.get('status')}")
    
    # 测试性能报告

    print(f"\n📈 性能报告:")
    性能报告 = 管道.get_performance_report(hours=1)
    print(f"  总管道数: {性能报告.get('total_pipelines', 0)}")
    print(f"  成功率: {性能报告.get('success_rate', 0):.1f}%")
    print(f"  平均质量分数: {性能报告.get('average_quality_score', 0):.1f}")
    
    # 测试仪表板数据生成

    print(f"\n🎯 仪表板数据:")
    仪表板数据 = 管道.generate_dashboard_data()
    
    if 'error' not in 仪表板数据:
        print(f"  监控状态: {'活跃' if 仪表板数据.get('system_status', {}).get('monitoring_active', False) else '未活跃'}")
        print(f"  平均质量分数(24h): {仪表板数据.get('performance_summary', {}).get('average_quality_score', 0):.1f}")
        print(f"  成功率(24h): {仪表板数据.get('performance_summary', {}).get('success_rate', 0):.1f}%")
    else:
        print(f"  生成仪表板数据失败: {仪表板数据.get('error')}")
    
    print("\n✅ 验证管道测试完成")