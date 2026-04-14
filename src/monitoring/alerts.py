"""
告警管理系统
支持规则定义、告警触发和通知发送
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.task_queue import MessageQueue, QueueConfig
from src.task_queue.config import get_queue_config
from src.task_queue.models import Message, MessagePriority

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """告警状态"""
    FIRING = "firing"      # 告警触发中
    RESOLVED = "resolved"  # 告警已解决
    ACKNOWLEDGED = "acknowledged"  # 告警已确认
    SILENCED = "silenced"   # 告警被静音


class AlertSource(str, Enum):
    """告警来源"""
    METRICS = "metrics"      # 指标监控
    LOGS = "logs"           # 日志监控
    HEARTBEAT = "heartbeat" # 心跳检测
    MANUAL = "manual"       # 手动触发
    SYSTEM = "system"       # 系统事件


class AlertRule(BaseModel):
    """告警规则定义"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: Optional[str] = None
    query: str  # 告警查询表达式
    duration: str = "1m"  # 持续时间
    severity: AlertSeverity = AlertSeverity.WARNING
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class Alert(BaseModel):
    """告警实例"""
    id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    name: str
    description: Optional[str] = None
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.FIRING
    source: AlertSource
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    starts_at: datetime = Field(default_factory=datetime.utcnow)
    ends_at: Optional[datetime] = None
    generator_url: Optional[str] = None  # 生成告警的URL
    fingerprint: str  # 用于去重的指纹
    silenced_by: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    value: Optional[float] = None  # 触发值
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class NotificationChannel(BaseModel):
    """通知通道配置"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    type: str  # email, slack, webhook, sms, etc.
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class AlertConfig(BaseModel):
    """告警系统配置"""
    check_interval: int = 60  # 检查间隔（秒）
    alert_queue_name: str = "alerts"
    notification_queue_name: str = "notifications"
    retention_days: int = 30  # 告警保留天数
    max_alerts_per_rule: int = 100  # 每个规则最大告警数


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self.queue_config = get_queue_config()
        self.queue = MessageQueue(self.queue_config)
        
        # 存储告警规则和实例
        self.rules: Dict[str, AlertRule] = {}  # rule_id -> AlertRule
        self.active_alerts: Dict[str, Alert] = {}  # fingerprint -> Alert
        self.alert_history: List[Alert] = []  # 历史告警
        self.notification_channels: Dict[str, NotificationChannel] = {}
        
        # 初始化默认规则
        self._init_default_rules()
        
        logger.info("告警管理器已初始化")
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        default_rules = [
            AlertRule(
                name="HighErrorRate",
                description="API错误率超过5%",
                query="rate(http_requests_total{status=~'5..'}[5m]) / rate(http_requests_total[5m]) > 0.05",
                duration="2m",
                severity=AlertSeverity.CRITICAL,
                labels={"service": "api", "component": "http"},
                annotations={
                    "summary": "高错误率检测到",
                    "description": "API错误率超过5%"
                }
            ),
            AlertRule(
                name="HighLatency",
                description="API 95分位延迟超过1秒",
                query="histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1",
                duration="5m",
                severity=AlertSeverity.WARNING,
                labels={"service": "api", "component": "performance"},
                annotations={
                    "summary": "高延迟检测到",
                    "description": "API 95分位延迟超过1秒"
                }
            ),
            AlertRule(
                name="DatabaseHighLatency",
                description="数据库查询95分位延迟超过0.5秒",
                query="histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m])) > 0.5",
                duration="5m",
                severity=AlertSeverity.WARNING,
                labels={"service": "database", "component": "performance"},
                annotations={
                    "summary": "数据库高延迟",
                    "description": "数据库查询延迟过高"
                }
            ),
            AlertRule(
                name="CacheLowHitRate",
                description="缓存命中率低于80%",
                query="cache_hits_total / (cache_hits_total + cache_misses_total) < 0.8",
                duration="10m",
                severity=AlertSeverity.WARNING,
                labels={"service": "cache", "component": "performance"},
                annotations={
                    "summary": "缓存命中率低",
                    "description": "缓存命中率低于80%"
                }
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: AlertRule) -> AlertRule:
        """添加告警规则"""
        self.rules[str(rule.id)] = rule
        logger.info(f"告警规则已添加: {rule.name} ({rule.id})")
        return rule
    
    def update_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> Optional[AlertRule]:
        """更新告警规则"""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            for key, value in rule_data.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            rule.updated_at = datetime.utcnow()
            logger.info(f"告警规则已更新: {rule.name} ({rule_id})")
            return rule
        return None
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除告警规则"""
        if rule_id in self.rules:
            rule_name = self.rules[rule_id].name
            del self.rules[rule_id]
            logger.info(f"告警规则已删除: {rule_name} ({rule_id})")
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取告警规则"""
        return self.rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """列出告警规则"""
        rules = list(self.rules.values())
        if enabled_only:
            rules = [rule for rule in rules if rule.enabled]
        return sorted(rules, key=lambda r: r.name)
    
    def create_alert(self, rule: AlertRule, value: Optional[float] = None, 
                    additional_labels: Dict[str, str] = None) -> Alert:
        """创建告警实例"""
        # 生成告警指纹（用于去重）
        labels = {**rule.labels, **(additional_labels or {})}
        fingerprint = self._generate_fingerprint(rule.name, labels)
        
        # 检查是否已有相同告警
        if fingerprint in self.active_alerts:
            existing_alert = self.active_alerts[fingerprint]
            if existing_alert.status == AlertStatus.FIRING:
                logger.debug(f"告警已存在: {rule.name} ({fingerprint})")
                return existing_alert
        
        # 创建新告警
        alert = Alert(
            rule_id=rule.id,
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            source=AlertSource.METRICS,
            labels=labels,
            annotations=rule.annotations,
            fingerprint=fingerprint,
            value=value
        )
        
        # 存储告警
        self.active_alerts[fingerprint] = alert
        self.alert_history.append(alert)
        
        # 限制历史记录长度
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        logger.info(f"告警已创建: {rule.name} ({fingerprint}), 严重度: {rule.severity.value}")
        
        # 发送告警到队列
        asyncio.create_task(self._send_alert_to_queue(alert))
        
        return alert
    
    def _generate_fingerprint(self, rule_name: str, labels: Dict[str, str]) -> str:
        """生成告警指纹"""
        import hashlib
        label_str = json.dumps(sorted(labels.items()), sort_keys=True)
        fingerprint_data = f"{rule_name}:{label_str}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()
    
    async def _send_alert_to_queue(self, alert: Alert):
        """发送告警到消息队列"""
        try:
            message = Message(
                queue_name=self.config.alert_queue_name,
                body={
                    "type": "alert",
                    "alert": alert.dict(),
                    "timestamp": datetime.utcnow().isoformat()
                },
                priority=MessagePriority.HIGH if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] 
                       else MessagePriority.NORMAL
            )
            
            await self.queue.send(self.config.alert_queue_name, message)
            logger.debug(f"告警已发送到队列: {alert.name}")
            
        except Exception as e:
            logger.error(f"发送告警到队列失败: {e}")
    
    def resolve_alert(self, fingerprint: str, resolved_by: str = "system") -> bool:
        """解决告警"""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            # 从活跃告警中移除
            del self.active_alerts[fingerprint]
            
            logger.info(f"告警已解决: {alert.name} ({fingerprint}), 解决者: {resolved_by}")
            
            # 发送解决通知
            asyncio.create_task(self._send_resolution_to_queue(alert, resolved_by))
            
            return True
        return False
    
    async def _send_resolution_to_queue(self, alert: Alert, resolved_by: str):
        """发送告警解决通知到队列"""
        try:
            message = Message(
                queue_name=self.config.alert_queue_name,
                body={
                    "type": "alert_resolved",
                    "alert": alert.dict(),
                    "resolved_by": resolved_by,
                    "timestamp": datetime.utcnow().isoformat()
                },
                priority=MessagePriority.NORMAL
            )
            
            await self.queue.send(self.config.alert_queue_name, message)
            logger.debug(f"告警解决通知已发送: {alert.name}")
            
        except Exception as e:
            logger.error(f"发送告警解决通知失败: {e}")
    
    def acknowledge_alert(self, fingerprint: str, acknowledged_by: str) -> bool:
        """确认告警"""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.utcnow()
            
            logger.info(f"告警已确认: {alert.name} ({fingerprint}), 确认者: {acknowledged_by}")
            return True
        return False
    
    def silence_alert(self, fingerprint: str, silenced_by: str, duration_minutes: int = 60) -> bool:
        """静音告警"""
        if fingerprint in self.active_alerts:
            alert = self.active_alerts[fingerprint]
            alert.status = AlertStatus.SILENCED
            alert.silenced_by = silenced_by
            
            # 设置静音结束时间
            alert.ends_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
            
            logger.info(f"告警已静音: {alert.name} ({fingerprint}), 静音者: {silenced_by}, 时长: {duration_minutes}分钟")
            return True
        return False
    
    def add_notification_channel(self, channel: NotificationChannel) -> NotificationChannel:
        """添加通知通道"""
        self.notification_channels[str(channel.id)] = channel
        logger.info(f"通知通道已添加: {channel.name} ({channel.type})")
        return channel
    
    def send_notification(self, alert: Alert, channel_id: str) -> bool:
        """发送告警通知"""
        if channel_id in self.notification_channels:
            channel = self.notification_channels[channel_id]
            
            # 这里应该根据通道类型发送实际通知
            # 例如: 发送邮件、Slack消息、Webhook等
            
            notification_data = {
                "channel_id": channel_id,
                "channel_name": channel.name,
                "channel_type": channel.type,
                "alert": alert.dict(),
                "sent_at": datetime.utcnow().isoformat()
            }
            
            # 发送到通知队列
            asyncio.create_task(self._send_notification_to_queue(notification_data))
            
            logger.info(f"告警通知已发送: {alert.name} -> {channel.name} ({channel.type})")
            return True
        
        logger.warning(f"通知通道不存在: {channel_id}")
        return False
    
    async def _send_notification_to_queue(self, notification_data: Dict[str, Any]):
        """发送通知到队列"""
        try:
            message = Message(
                queue_name=self.config.notification_queue_name,
                body={
                    "type": "notification",
                    **notification_data
                },
                priority=MessagePriority.NORMAL
            )
            
            await self.queue.send(self.config.notification_queue_name, message)
            
        except Exception as e:
            logger.error(f"发送通知到队列失败: {e}")
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = list(self.active_alerts.values())
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        return sorted(alerts, key=lambda a: a.starts_at, reverse=True)
    
    def get_alert_history(self, limit: int = 100, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """获取告警历史"""
        alerts = self.alert_history[-limit:] if limit else self.alert_history
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        return alerts
    
    def cleanup_old_alerts(self, days: int = None):
        """清理旧告警"""
        days = days or self.config.retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 清理历史告警
        initial_count = len(self.alert_history)
        self.alert_history = [
            alert for alert in self.alert_history
            if alert.starts_at > cutoff_date
        ]
        
        removed_count = initial_count - len(self.alert_history)
        if removed_count > 0:
            logger.info(f"清理了 {removed_count} 个 {days} 天前的历史告警")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取告警系统统计"""
        active_by_severity = {
            severity.value: len([a for a in self.active_alerts.values() if a.severity == severity])
            for severity in AlertSeverity
        }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "rules": {
                "total": len(self.rules),
                "enabled": len([r for r in self.rules.values() if r.enabled]),
                "disabled": len([r for r in self.rules.values() if not r.enabled]),
            },
            "alerts": {
                "active_total": len(self.active_alerts),
                "active_by_severity": active_by_severity,
                "history_total": len(self.alert_history),
            },
            "notification_channels": {
                "total": len(self.notification_channels),
                "enabled": len([c for c in self.notification_channels.values() if c.enabled]),
            }
        }


# 全局告警管理器实例
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取告警管理器实例"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager