#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时数据质量监控器
实现连续数据质量监控、异常检测和报警功能
"""

import json
import logging
import time
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from collections import deque
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """报警级别"""
    CRITICAL = "critical"    # 关键问题，需要立即处理
    HIGH = "high"           # 严重问题，需要尽快处理
    MEDIUM = "medium"       # 中等问题，需要关注
    LOW = "low"             # 轻微问题，可稍后处理
    INFO = "info"           # 信息通知

class AlertChannel(Enum):
    """报警渠道"""
    LOG = "log"             # 日志记录
    EMAIL = "email"         # 电子邮件
    WEBHOOK = "webhook"     # Webhook通知
    DASHBOARD = "dashboard" # 仪表板显示

@dataclass
class Alert:
    """报警信息"""
    alert_id: str
    level: AlertLevel
    channel: AlertChannel
    title: str
    message: str
    timestamp: datetime
    source: str
    metric: str
    value: Any
    threshold: Any
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    
    def to_dict(self):
        """转换为字典"""
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'channel': self.channel.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'metric': self.metric,
            'value': self.value,
            'threshold': self.threshold,
            'details': self.details,
            'acknowledged': self.acknowledged,
            'acknowledged_by': self.acknowledged_by,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None
        }

@dataclass
class MonitoringMetric:
    """监控指标"""
    name: str
    current_value: Any
    historical_values: deque
    threshold: Dict[AlertLevel, Any]  # 不同级别的阈值
    unit: str
    description: str
    last_updated: datetime
    
    def check_threshold(self) -> Optional[AlertLevel]:
        """检查阈值，返回触发的报警级别"""
        for level in [AlertLevel.CRITICAL, AlertLevel.HIGH, AlertLevel.MEDIUM, AlertLevel.LOW]:
            if level.value in self.threshold:
                threshold_value = self.threshold[level.value]
                if self._exceeds_threshold(threshold_value):
                    return level
        return None
    
    def _exceeds_threshold(self, threshold: Any) -> bool:
        """检查是否超过阈值"""
        try:
            if isinstance(threshold, (int, float)) and isinstance(self.current_value, (int, float)):
                return self.current_value > threshold
            return False
        except Exception:
            return False

class RealtimeDataMonitor:
    """实时数据质量监控器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化实时监控器
        
        Parameters:
        -----------
        config : Dict
            配置参数，包括监控指标、阈值、报警渠道等
        """
        self.config = config or self._get_default_config()
        self.metrics: Dict[str, MonitoringMetric] = {}
        self.alerts: List[Alert] = []
        self.is_running = False
        self.monitor_thread = None
        self.alert_handlers = {}
        self.cooldown_tracker: Dict[str, datetime] = {}  # 报警冷却追踪
        
        # 初始化报警处理器
        self._init_alert_handlers()
        
        logger.info("初始化实时数据质量监控器")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'monitoring_interval': 10,  # 监控间隔（秒）
            'alert_cooldown_minutes': 5,  # 报警冷却时间（分钟）
            'max_alerts_per_hour': 100,  # 每小时最大报警数
            'metrics': {
                'data_freshness': {
                    'description': '数据新鲜度',
                    'unit': '分钟',
                    'threshold': {
                        'critical': 30,  # 超过30分钟为critical
                        'high': 15,      # 超过15分钟为high
                        'medium': 5,     # 超过5分钟为medium
                        'low': 2         # 超过2分钟为low
                    }
                },
                'data_completeness': {
                    'description': '数据完整度',
                    'unit': '%',
                    'threshold': {
                        'critical': 50,   # 低于50%为critical
                        'high': 70,       # 低于70%为high
                        'medium': 85,     # 低于85%为medium
                        'low': 95         # 低于95%为low
                    }
                },
                'data_consistency': {
                    'description': '数据一致性',
                    'unit': '分数',
                    'threshold': {
                        'critical': 0.5,  # 低于0.5为critical
                        'high': 0.7,      # 低于0.7为high
                        'medium': 0.8,    # 低于0.8为medium
                        'low': 0.9        # 低于0.9为low
                    }
                },
                'validation_failure_rate': {
                    'description': '验证失败率',
                    'unit': '%',
                    'threshold': {
                        'critical': 20,   # 超过20%为critical
                        'high': 10,       # 超过10%为high
                        'medium': 5,      # 超过5%为medium
                        'low': 2          # 超过2%为low
                    }
                },
                'data_source_availability': {
                    'description': '数据源可用率',
                    'unit': '%',
                    'threshold': {
                        'critical': 50,   # 低于50%为critical
                        'high': 70,       # 低于70%为high
                        'medium': 85,     # 低于85%为medium
                        'low': 95         # 低于95%为low
                    }
                },
                'data_quality_score': {
                    'description': '数据质量评分',
                    'unit': '分数',
                    'threshold': {
                        'critical': 60,   # 低于60为critical
                        'high': 70,       # 低于70为high
                        'medium': 80,     # 低于80为medium
                        'low': 90         # 低于90为low
                    }
                }
            },
            'alert_channels': {
                'log': {
                    'enabled': True,
                    'level': 'info'  # 记录级别
                },
                'email': {
                    'enabled': False,
                    'smtp_server': 'smtp.example.com',
                    'smtp_port': 587,
                    'username': 'user@example.com',
                    'password': 'password',
                    'recipients': ['admin@example.com']
                },
                'webhook': {
                    'enabled': False,
                    'url': 'https://webhook.example.com/alerts'
                },
                'dashboard': {
                    'enabled': True
                }
            }
        }
    
    def _init_alert_handlers(self):
        """初始化报警处理器"""
        self.alert_handlers[AlertChannel.LOG] = self._handle_log_alert
        self.alert_handlers[AlertChannel.EMAIL] = self._handle_email_alert
        self.alert_handlers[AlertChannel.WEBHOOK] = self._handle_webhook_alert
        self.alert_handlers[AlertChannel.DASHBOARD] = self._handle_dashboard_alert
    
    def add_metric(self, name: str, value: Any, description: str = "", unit: str = ""):
        """添加或更新监控指标"""
        if name not in self.metrics:
            # 从配置获取阈值
            threshold_config = self.config['metrics'].get(name, {}).get('threshold', {})
            
            metric = MonitoringMetric(
                name=name,
                current_value=value,
                historical_values=deque(maxlen=60),  # 保留最近60个值
                threshold=threshold_config,
                unit=unit or self.config['metrics'].get(name, {}).get('unit', ''),
                description=description or self.config['metrics'].get(name, {}).get('description', ''),
                last_updated=datetime.now()
            )
            self.metrics[name] = metric
        else:
            # 更新现有指标
            self.metrics[name].current_value = value
            self.metrics[name].last_updated = datetime.now()
        
        # 记录历史值
        self.metrics[name].historical_values.append(value)
    
    def start_monitoring(self):
        """开始实时监控"""
        if self.is_running:
            logger.warning("监控已经在运行中")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("实时数据质量监控已启动")
    
    def stop_monitoring(self):
        """停止实时监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("实时数据质量监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        logger.info("监控循环开始")
        
        while self.is_running:
            try:
                # 检查所有指标
                self._check_all_metrics()
                
                # 清理过期报警
                self._cleanup_old_alerts()
                
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
            
            # 等待下一次检查
            time.sleep(self.config['monitoring_interval'])
        
        logger.info("监控循环结束")
    
    def _check_all_metrics(self):
        """检查所有指标"""
        for metric_name, metric in self.metrics.items():
            # 检查阈值
            alert_level = metric.check_threshold()
            
            if alert_level:
                # 检查冷却时间
                cooldown_key = f"{metric_name}_{alert_level.value}"
                if self._is_in_cooldown(cooldown_key):
                    continue
                
                # 创建报警
                alert = self._create_alert(
                    level=alert_level,
                    metric_name=metric_name,
                    metric_value=metric.current_value,
                    threshold=metric.threshold[alert_level.value]
                )
                
                # 发送报警
                self._send_alert(alert)
                
                # 设置冷却时间
                cooldown_minutes = self.config['alert_cooldown_minutes']
                self.cooldown_tracker[cooldown_key] = datetime.now() + timedelta(minutes=cooldown_minutes)
    
    def _is_in_cooldown(self, cooldown_key: str) -> bool:
        """检查是否在冷却时间内"""
        if cooldown_key not in self.cooldown_tracker:
            return False
        
        cooldown_until = self.cooldown_tracker[cooldown_key]
        return datetime.now() < cooldown_until
    
    def _create_alert(self, level: AlertLevel, metric_name: str, metric_value: Any, threshold: Any) -> Alert:
        """创建报警"""
        metric = self.metrics.get(metric_name, None)
        
        alert_id = f"alert_{metric_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 根据级别选择报警渠道
        if level == AlertLevel.CRITICAL:
            channels = [AlertChannel.LOG, AlertChannel.DASHBOARD]
            if self.config['alert_channels']['email']['enabled']:
                channels.append(AlertChannel.EMAIL)
            if self.config['alert_channels']['webhook']['enabled']:
                channels.append(AlertChannel.WEBHOOK)
        elif level == AlertLevel.HIGH:
            channels = [AlertChannel.LOG, AlertChannel.DASHBOARD]
            if self.config['alert_channels']['email']['enabled']:
                channels.append(AlertChannel.EMAIL)
        elif level == AlertLevel.MEDIUM:
            channels = [AlertChannel.LOG, AlertChannel.DASHBOARD]
        else:  # LOW or INFO
            channels = [AlertChannel.LOG]
        
        # 创建报警消息
        title = f"{metric_name} {level.value} 报警"
        message = f"指标 '{metric_name}' 当前值: {metric_value}{metric.unit if metric else ''}，超过阈值: {threshold}"
        
        if metric:
            message += f"\n描述: {metric.description}"
        
        alert = Alert(
            alert_id=alert_id,
            level=level,
            channel=channels[0],  # 主要渠道
            title=title,
            message=message,
            timestamp=datetime.now(),
            source="zhulinsma_monitor",
            metric=metric_name,
            value=metric_value,
            threshold=threshold,
            details={
                'metric_description': metric.description if metric else '',
                'metric_unit': metric.unit if metric else '',
                'historical_trend': list(metric.historical_values)[-5:] if metric else [],
                'channels': [c.value for c in channels]
            }
        )
        
        return alert
    
    def _send_alert(self, alert: Alert):
        """发送报警"""
        # 记录到报警列表
        self.alerts.append(alert)
        
        # 发送到所有配置的渠道
        for channel in alert.details.get('channels', []):
            channel_enum = AlertChannel(channel)
            if channel_enum in self.alert_handlers:
                try:
                    self.alert_handlers[channel_enum](alert)
                except Exception as e:
                    logger.error(f"发送报警到 {channel} 失败: {e}")
        
        logger.info(f"报警已发送: {alert.title} - {alert.message}")
    
    def _handle_log_alert(self, alert: Alert):
        """处理日志报警"""
        log_level = getattr(logging, self.config['alert_channels']['log']['level'].upper())
        logger.log(log_level, f"[{alert.level.value}] {alert.title}: {alert.message}")
    
    def _handle_email_alert(self, alert: Alert):
        """处理邮件报警"""
        email_config = self.config['alert_channels']['email']
        
        if not email_config['enabled']:
            return
        
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = email_config['username']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"[Zhulinsma] {alert.title}"
            
            # 邮件正文
            body = f"""
            Zhulinsma数据质量报警
            
            报警级别: {alert.level.value.upper()}
            报警时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            指标名称: {alert.metric}
            当前值: {alert.value}
            阈值: {alert.threshold}
            
            详细信息:
            {alert.message}
            
            请及时处理。
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # 发送邮件
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
                
        except Exception as e:
            logger.error(f"发送邮件报警失败: {e}")
    
    def _handle_webhook_alert(self, alert: Alert):
        """处理Webhook报警"""
        webhook_config = self.config['alert_channels']['webhook']
        
        if not webhook_config['enabled']:
            return
        
        try:
            payload = alert.to_dict()
            response = requests.post(webhook_config['url'], json=payload, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"Webhook请求失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"发送Webhook报警失败: {e}")
    
    def _handle_dashboard_alert(self, alert: Alert):
        """处理仪表板报警"""
        # 这里可以集成到仪表板系统
        # 目前只记录日志
        logger.info(f"仪表板报警: {alert.title} - {alert.message}")
    
    def _cleanup_old_alerts(self, max_age_hours: int = 24):
        """清理过期报警"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        original_count = len(self.alerts)
        
        self.alerts = [alert for alert in self.alerts if alert.timestamp > cutoff_time]
        
        removed_count = original_count - len(self.alerts)
        if removed_count > 0:
            logger.debug(f"清理了 {removed_count} 个过期报警")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标状态"""
        return {
            name: {
                'value': metric.current_value,
                'unit': metric.unit,
                'description': metric.description,
                'last_updated': metric.last_updated.isoformat(),
                'historical_trend': list(metric.historical_values)[-10:]  # 最近10个值
            }
            for name, metric in self.metrics.items()
        }
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """获取最近的报警"""
        recent_alerts = sorted(self.alerts, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [alert.to_dict() for alert in recent_alerts]
    
    def generate_monitoring_report(self, duration_hours: int = 1) -> Dict:
        """生成监控报告"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=duration_hours)
        
        # 筛选时间范围内的报警
        period_alerts = [alert for alert in self.alerts if start_time <= alert.timestamp <= end_time]
        
        # 统计报警
        alert_stats = {}
        for level in AlertLevel:
            level_alerts = [a for a in period_alerts if a.level == level]
            alert_stats[level.value] = len(level_alerts)
        
        # 计算指标平均值
        metric_stats = {}
        for name, metric in self.metrics.items():
            if metric.historical_values:
                values_in_period = [v for v in metric.historical_values]  # 简化处理
                if values_in_period:
                    metric_stats[name] = {
                        'avg': sum(values_in_period) / len(values_in_period),
                        'min': min(values_in_period),
                        'max': max(values_in_period),
                        'current': metric.current_value,
                        'unit': metric.unit
                    }
        
        report = {
            'report_time': end_time.isoformat(),
            'duration_hours': duration_hours,
            'total_alerts': len(period_alerts),
            'alert_statistics': alert_stats,
            'metric_statistics': metric_stats,
            'system_status': {
                'is_running': self.is_running,
                'total_metrics': len(self.metrics),
                'total_tracked_alerts': len(self.alerts)
            },
            'recent_alerts': [alert.to_dict() for alert in period_alerts[-10:]] if period_alerts else []
        }
        
        return report
    
    def save_report_to_file(self, report: Dict, filename: str = None):
        """保存报告到文件"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"zhulinsma_monitoring_report_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"监控报告已保存到: {filename}")
        return filename


# 使用示例
def example_usage():
    """实时监控示例"""
    print("=" * 60)
    print("Zhulinsma实时数据质量监控系统示例")
    print("=" * 60)
    
    # 创建监控器
    monitor = RealtimeDataMonitor()
    
    # 初始化指标
    print("\n1. 初始化监控指标...")
    monitor.add_metric('data_freshness', 2.5)
    monitor.add_metric('data_completeness', 92.5)
    monitor.add_metric('data_consistency', 0.85)
    monitor.add_metric('validation_failure_rate', 1.2)
    monitor.add_metric('data_source_availability', 98.7)
    monitor.add_metric('data_quality_score', 88.5)
    
    # 获取当前指标状态
    print("\n2. 获取当前指标状态...")
    metrics = monitor.get_current_metrics()
    for name, data in metrics.items():
        print(f"  {name}: {data['value']}{data['unit']} - {data['description']}")
    
    # 模拟触发报警
    print("\n3. 模拟触发报警...")
    monitor.add_metric('data_freshness', 35)  # 超过critical阈值
    monitor.add_metric('data_completeness', 45)  # 超过critical阈值
    
    # 开始监控
    print("\n4. 开始实时监控...")
    monitor.start_monitoring()
    
    # 等待一段时间
    print("\n5. 等待监控运行...")
    time.sleep(2)
    
    # 获取报警
    print("\n6. 获取最近报警...")
    alerts = monitor.get_recent_alerts(limit=5)
    if alerts:
        for alert in alerts:
            print(f"  [{alert['level']}] {alert['title']}: {alert['message']}")
    else:
        print("  无报警")
    
    # 生成报告
    print("\n7. 生成监控报告...")
    report = monitor.generate_monitoring_report(duration_hours=0.1)  # 6分钟报告
    print(f"  报告时间段: {report['duration_hours']}小时")
    print(f"  总报警数: {report['total_alerts']}")
    print(f"  系统状态: {'运行中' if report['system_status']['is_running'] else '已停止'}")
    
    # 停止监控
    print("\n8. 停止监控...")
    monitor.stop_monitoring()
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例
    example_usage()