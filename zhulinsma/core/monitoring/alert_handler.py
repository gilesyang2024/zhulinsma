#!/usr/bin/env python3
"""
报警处理器模块
处理数据质量监控中的报警事件
支持多种报警渠道：日志、邮件、Webhook、仪表板等
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import requests

class AlertChannel(Enum):
    """报警渠道枚举"""
    LOG = "log"           # 日志报警
    EMAIL = "email"       # 邮件报警
    WEBHOOK = "webhook"   # Webhook报警
    DASHBOARD = "dashboard"  # 仪表板报警
    CONSOLE = "console"   # 控制台报警

class AlertLevel(Enum):
    """报警级别枚举"""
    CRITICAL = "critical"  # 关键：需要立即处理
    HIGH = "high"          # 严重：需要尽快处理
    MEDIUM = "medium"      # 中等：需要关注
    LOW = "low"            # 轻微：可稍后处理
    INFO = "info"          # 信息：仅记录


class AlertHandler:
    """
    报警处理器
    处理数据质量监控中的报警事件
    """
    
    def __init__(self, 
                 enable_log_alerts: bool = True,
                 enable_email_alerts: bool = False,
                 enable_webhook_alerts: bool = False,
                 enable_dashboard: bool = True,
                 enable_console: bool = True,
                 email_config: Optional[Dict] = None,
                 webhook_url: Optional[str] = None):
        """
        初始化报警处理器
        
        参数:
            enable_log_alerts: 启用日志报警
            enable_email_alerts: 启用邮件报警
            enable_webhook_alerts: 启用Webhook报警
            enable_dashboard: 启用仪表板报警
            enable_console: 启用控制台报警
            email_config: 邮件配置
            webhook_url: Webhook URL
        """
        self.enable_log_alerts = enable_log_alerts
        self.enable_email_alerts = enable_email_alerts
        self.enable_webhook_alerts = enable_webhook_alerts
        self.enable_dashboard = enable_dashboard
        self.enable_console = enable_console
        
        # 邮件配置
        self.email_config = email_config or {
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587,
            'username': 'alerts@example.com',
            'password': 'password',
            'from_email': 'alerts@example.com',
            'to_emails': ['admin@example.com']
        }
        
        # Webhook配置
        self.webhook_url = webhook_url
        
        # 报警历史记录
        self.alert_history: List[Dict] = []
        self.max_history_size = 1000
        
        # 报警冷却时间（防止重复报警）
        self.alert_cooldown: Dict[str, datetime] = {}
        self.default_cooldown_minutes = 60
        
        # 初始化日志
        if enable_log_alerts:
            self._setup_logging()
        
        print(f"🔔 报警处理器初始化完成")
        print(f"   日志报警: {'启用' if enable_log_alerts else '禁用'}")
        print(f"   邮件报警: {'启用' if enable_email_alerts else '禁用'}")
        print(f"   Webhook报警: {'启用' if enable_webhook_alerts else '禁用'}")
        print(f"   仪表板报警: {'启用' if enable_dashboard else '禁用'}")
    
    def _setup_logging(self) -> None:
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('zhulinsma_alerts.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ZhulinsmaAlerts')
    
    def send_alert(self, 
                   level: AlertLevel, 
                   title: str, 
                   message: str,
                   source: str = "unknown",
                   metadata: Optional[Dict] = None,
                   channels: Optional[List[AlertChannel]] = None) -> bool:
        """
        发送报警
        
        参数:
            level: 报警级别
            title: 报警标题
            message: 报警消息
            source: 报警来源
            metadata: 元数据
            channels: 报警渠道列表（默认使用所有启用的渠道）
        
        返回:
            是否成功发送
        """
        # 检查报警冷却
        alert_key = f"{source}:{title}"
        if self._is_in_cooldown(alert_key):
            return False
        
        # 创建报警记录
        alert_record = {
            'timestamp': datetime.now().isoformat(),
            'level': level.value,
            'title': title,
            'message': message,
            'source': source,
            'metadata': metadata or {}
        }
        
        # 确定报警渠道
        if channels is None:
            channels = self._get_default_channels(level)
        
        # 发送到各个渠道
        results = []
        
        for channel in channels:
            try:
                if channel == AlertChannel.LOG and self.enable_log_alerts:
                    results.append(self._send_log_alert(alert_record))
                
                elif channel == AlertChannel.EMAIL and self.enable_email_alerts:
                    results.append(self._send_email_alert(alert_record))
                
                elif channel == AlertChannel.WEBHOOK and self.enable_webhook_alerts:
                    results.append(self._send_webhook_alert(alert_record))
                
                elif channel == AlertChannel.DASHBOARD and self.enable_dashboard:
                    results.append(self._send_dashboard_alert(alert_record))
                
                elif channel == AlertChannel.CONSOLE and self.enable_console:
                    results.append(self._send_console_alert(alert_record))
            
            except Exception as e:
                print(f"❌ 报警发送失败 (渠道: {channel.value}): {e}")
                results.append(False)
        
        # 记录报警历史
        alert_record['channels'] = [c.value for c in channels]
        alert_record['success'] = any(results)
        
        self.alert_history.append(alert_record)
        
        # 限制历史记录大小
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
        
        # 设置报警冷却
        self._set_cooldown(alert_key)
        
        return any(results)
    
    def _get_default_channels(self, level: AlertLevel) -> List[AlertChannel]:
        """
        根据报警级别获取默认报警渠道
        
        参数:
            level: 报警级别
        
        返回:
            报警渠道列表
        """
        channels = [AlertChannel.LOG, AlertChannel.CONSOLE]
        
        if level in [AlertLevel.CRITICAL, AlertLevel.HIGH]:
            if self.enable_email_alerts:
                channels.append(AlertChannel.EMAIL)
            if self.enable_webhook_alerts:
                channels.append(AlertChannel.WEBHOOK)
        
        if self.enable_dashboard:
            channels.append(AlertChannel.DASHBOARD)
        
        return channels
    
    def _send_log_alert(self, alert_record: Dict) -> bool:
        """
        发送日志报警
        
        参数:
            alert_record: 报警记录
        
        返回:
            是否成功
        """
        try:
            level = alert_record['level']
            title = alert_record['title']
            message = alert_record['message']
            source = alert_record['source']
            
            log_message = f"[{source}] {title}: {message}"
            
            if level == AlertLevel.CRITICAL.value:
                self.logger.critical(log_message)
            elif level == AlertLevel.HIGH.value:
                self.logger.error(log_message)
            elif level == AlertLevel.MEDIUM.value:
                self.logger.warning(log_message)
            elif level == AlertLevel.LOW.value:
                self.logger.info(log_message)
            else:
                self.logger.info(log_message)
            
            return True
            
        except Exception as e:
            print(f"❌ 日志报警失败: {e}")
            return False
    
    def _send_email_alert(self, alert_record: Dict) -> bool:
        """
        发送邮件报警
        
        参数:
            alert_record: 报警记录
        
        返回:
            是否成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = ', '.join(self.email_config['to_emails'])
            msg['Subject'] = f"[Zhulinsma Alert] {alert_record['title']}"
            
            # 邮件正文
            body = f"""
            ===============================================
            竹林司马数据质量报警
            ===============================================
            
            报警级别: {alert_record['level'].upper()}
            报警来源: {alert_record['source']}
            报警时间: {alert_record['timestamp']}
            
            标题: {alert_record['title']}
            消息: {alert_record['message']}
            
            """
            
            if alert_record['metadata']:
                body += "\n元数据:\n"
                for key, value in alert_record['metadata'].items():
                    body += f"  {key}: {value}\n"
            
            msg.attach(MIMEText(body, 'plain'))
            
            # 发送邮件
            with smtplib.SMTP(self.email_config['smtp_server'], 
                             self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['username'], 
                           self.email_config['password'])
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"❌ 邮件报警失败: {e}")
            return False
    
    def _send_webhook_alert(self, alert_record: Dict) -> bool:
        """
        发送Webhook报警
        
        参数:
            alert_record: 报警记录
        
        返回:
            是否成功
        """
        try:
            if not self.webhook_url:
                return False
            
            payload = {
                'timestamp': alert_record['timestamp'],
                'level': alert_record['level'],
                'title': alert_record['title'],
                'message': alert_record['message'],
                'source': alert_record['source'],
                'metadata': alert_record['metadata']
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Webhook报警失败: {e}")
            return False
    
    def _send_dashboard_alert(self, alert_record: Dict) -> bool:
        """
        发送仪表板报警
        
        参数:
            alert_record: 报警记录
        
        返回:
            是否成功
        """
        try:
            # 这里可以集成到具体的仪表板系统
            # 例如：写入数据库、发送到消息队列等
            
            # 当前实现：保存到文件供仪表板读取
            dashboard_file = 'zhulinsma_dashboard_alerts.json'
            
            try:
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    existing_alerts = json.load(f)
            except FileNotFoundError:
                existing_alerts = []
            
            # 添加新报警
            existing_alerts.append(alert_record)
            
            # 只保留最近100条
            if len(existing_alerts) > 100:
                existing_alerts = existing_alerts[-100:]
            
            # 保存
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(existing_alerts, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"❌ 仪表板报警失败: {e}")
            return False
    
    def _send_console_alert(self, alert_record: Dict) -> bool:
        """
        发送控制台报警
        
        参数:
            alert_record: 报警记录
        
        返回:
            是否成功
        """
        try:
            level = alert_record['level']
            title = alert_record['title']
            message = alert_record['message']
            
            # 根据级别使用不同颜色（在终端中）
            if level == AlertLevel.CRITICAL.value:
                prefix = "🔴 CRITICAL"
            elif level == AlertLevel.HIGH.value:
                prefix = "🟠 HIGH"
            elif level == AlertLevel.MEDIUM.value:
                prefix = "🟡 MEDIUM"
            elif level == AlertLevel.LOW.value:
                prefix = "🔵 LOW"
            else:
                prefix = "ℹ️ INFO"
            
            print(f"{prefix}: [{alert_record['source']}] {title} - {message}")
            
            return True
            
        except Exception as e:
            print(f"❌ 控制台报警失败: {e}")
            return False
    
    def _is_in_cooldown(self, alert_key: str) -> bool:
        """
        检查报警是否在冷却时间内
        
        参数:
            alert_key: 报警键
        
        返回:
            是否在冷却时间内
        """
        if alert_key not in self.alert_cooldown:
            return False
        
        last_alert_time = self.alert_cooldown[alert_key]
        cooldown_end = last_alert_time + timedelta(minutes=self.default_cooldown_minutes)
        
        return datetime.now() < cooldown_end
    
    def _set_cooldown(self, alert_key: str) -> None:
        """
        设置报警冷却时间
        
        参数:
            alert_key: 报警键
        """
        self.alert_cooldown[alert_key] = datetime.now()
        
        # 清理过期的冷却记录
        cutoff_time = datetime.now() - timedelta(minutes=self.default_cooldown_minutes * 2)
        expired_keys = [
            key for key, time in self.alert_cooldown.items()
            if time < cutoff_time
        ]
        
        for key in expired_keys:
            del self.alert_cooldown[key]
    
    def get_alert_history(self, 
                          level: Optional[str] = None,
                          source: Optional[str] = None,
                          hours: Optional[int] = None) -> List[Dict]:
        """
        获取报警历史
        
        参数:
            level: 过滤报警级别
            source: 过滤报警来源
            hours: 过滤最近N小时的报警
        
        返回:
            报警历史列表
        """
        filtered_alerts = self.alert_history
        
        # 按时间过滤
        if hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            filtered_alerts = [
                alert for alert in filtered_alerts
                if datetime.fromisoformat(alert['timestamp']) >= cutoff_time
            ]
        
        # 按级别过滤
        if level is not None:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert['level'] == level
            ]
        
        # 按来源过滤
        if source is not None:
            filtered_alerts = [
                alert for alert in filtered_alerts
                if alert['source'] == source
            ]
        
        return filtered_alerts
    
    def get_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取报警统计信息
        
        参数:
            hours: 小时数
        
        返回:
            报警统计信息
        """
        recent_alerts = self.get_alert_history(hours=hours)
        
        if not recent_alerts:
            return {
                'total_alerts': 0,
                'by_level': {},
                'by_source': {},
                'success_rate': 0.0
            }
        
        # 按级别统计
        by_level = {}
        for alert in recent_alerts:
            level = alert['level']
            by_level[level] = by_level.get(level, 0) + 1
        
        # 按来源统计
        by_source = {}
        for alert in recent_alerts:
            source = alert['source']
            by_source[source] = by_source.get(source, 0) + 1
        
        # 计算成功率
        successful_alerts = sum(1 for alert in recent_alerts if alert.get('success', False))
        success_rate = (successful_alerts / len(recent_alerts)) * 100 if recent_alerts else 0.0
        
        return {
            'total_alerts': len(recent_alerts),
            'by_level': by_level,
            'by_source': by_source,
            'success_rate': success_rate,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_alert_history(self) -> None:
        """清空报警历史"""
        self.alert_history = []
    
    def export_alert_history(self, file_path: str) -> None:
        """
        导出报警历史
        
        参数:
            file_path: 导出文件路径
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.alert_history, f, ensure_ascii=False, indent=2)
            print(f"✅ 报警历史已导出到: {file_path}")
        except Exception as e:
            print(f"❌ 报警历史导出失败: {e}")
    
    def test_all_channels(self) -> Dict[str, bool]:
        """
        测试所有报警渠道
        
        返回:
            各渠道测试结果
        """
        test_results = {}
        
        # 测试日志报警
        if self.enable_log_alerts:
            test_record = {
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.INFO.value,
                'title': '报警渠道测试',
                'message': '测试日志报警功能',
                'source': 'alert_handler_test',
                'metadata': {'test': True}
            }
            test_results['log'] = self._send_log_alert(test_record)
        
        # 测试邮件报警
        if self.enable_email_alerts:
            test_record = {
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.INFO.value,
                'title': '报警渠道测试',
                'message': '测试邮件报警功能',
                'source': 'alert_handler_test',
                'metadata': {'test': True}
            }
            test_results['email'] = self._send_email_alert(test_record)
        
        # 测试Webhook报警
        if self.enable_webhook_alerts:
            test_record = {
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.INFO.value,
                'title': '报警渠道测试',
                'message': '测试Webhook报警功能',
                'source': 'alert_handler_test',
                'metadata': {'test': True}
            }
            test_results['webhook'] = self._send_webhook_alert(test_record)
        
        # 测试仪表板报警
        if self.enable_dashboard:
            test_record = {
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.INFO.value,
                'title': '报警渠道测试',
                'message': '测试仪表板报警功能',
                'source': 'alert_handler_test',
                'metadata': {'test': True}
            }
            test_results['dashboard'] = self._send_dashboard_alert(test_record)
        
        # 测试控制台报警
        if self.enable_console:
            test_record = {
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.INFO.value,
                'title': '报警渠道测试',
                'message': '测试控制台报警功能',
                'source': 'alert_handler_test',
                'metadata': {'test': True}
            }
            test_results['console'] = self._send_console_alert(test_record)
        
        return test_results


# 单例实例
_alert_handler = None

def get_alert_handler(**kwargs) -> AlertHandler:
    """
    获取报警处理器单例实例
    
    参数:
        **kwargs: 初始化参数
    
    返回:
        AlertHandler实例
    """
    global _alert_handler
    
    if _alert_handler is None:
        _alert_handler = AlertHandler(**kwargs)
    
    return _alert_handler


if __name__ == "__main__":
    # 测试代码
    print("=== 报警处理器测试 ===")
    
    # 创建报警处理器（仅启用日志和控制台）
    handler = AlertHandler(
        enable_log_alerts=True,
        enable_email_alerts=False,
        enable_webhook_alerts=False,
        enable_dashboard=True,
        enable_console=True
    )
    
    # 测试不同级别的报警
    print("\n📤 发送测试报警...")
    
    test_alerts = [
        (AlertLevel.INFO, "系统启动", "竹林司马监控系统已启动"),
        (AlertLevel.LOW, "数据检查", "数据质量检查完成，发现轻微问题"),
        (AlertLevel.MEDIUM, "验证警告", "数据验证通过率低于90%"),
        (AlertLevel.HIGH, "数据异常", "发现严重数据不一致"),
        (AlertLevel.CRITICAL, "系统故障", "数据源连接失败")
    ]
    
    for level, title, message in test_alerts:
        success = handler.send_alert(
            level=level,
            title=title,
            message=message,
            source="test_system"
        )
        print(f"  {level.value.upper():8s} {title}: {'✅成功' if success else '❌失败'}")
    
    # 获取报警统计
    print("\n📊 报警统计信息:")
    stats = handler.get_alert_statistics(hours=1)
    print(f"  总报警数: {stats['total_alerts']}")
    print(f"  按级别分布: {stats['by_level']}")
    print(f"  成功率: {stats['success_rate']:.1f}%")
    
    # 导出报警历史
    handler.export_alert_history('test_alert_history.json')
    
    print("\n✅ 报警处理器测试完成")