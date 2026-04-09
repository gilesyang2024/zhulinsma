"""
预警触发器 - 实时监控技术指标并触发预警
"""
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json

from ..processor import IndicatorResult
from ..protocol import AlertType, AlertData, MessageParser

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TriggerState(Enum):
    """触发状态"""
    IDLE = "idle"           # 未触发
    TRIGGERED = "triggered" # 已触发
    COOLDOWN = "cooldown"  # 冷却中


@dataclass
class AlertRule:
    """预警规则"""
    stock_code: str
    alert_type: AlertType
    threshold: float
    enabled: bool = True
    cooldown_seconds: int = 300  # 冷却时间（秒）
    message_template: str = ""   # 自定义消息模板
    
    def get_message(self, value: float, indicators: dict = None) -> str:
        """生成预警消息"""
        if self.message_template:
            return self.message_template.format(
                stock_code=self.stock_code,
                value=value,
                threshold=self.threshold
            )
        
        # 默认消息模板
        templates = {
            AlertType.RSI_OVERBOUGHT: f"{self.stock_code} RSI指标达到{value:.1f}，已超买，注意回调风险",
            AlertType.RSI_OVERSOLD: f"{self.stock_code} RSI指标达到{value:.1f}，已超卖，关注反弹机会",
            AlertType.GOLDEN_CROSS: f"{self.stock_code} 出现金叉信号（5日均线上穿10日均线）",
            AlertType.DEATH_CROSS: f"{self.stock_code} 出现死叉信号（5日均线下穿10日均线）",
            AlertType.VOLUME_SPIKE: f"{self.stock_code} 成交量异动，量能放大至{value:.1f}倍",
            AlertType.DEVIATION_ALERT: f"{self.stock_code} 股价偏离5日均线{value:.2f}%，注意风险",
            AlertType.PRICE_BREAK: f"{self.stock_code} 价格突破{self.threshold}阻力位"
        }
        
        return templates.get(self.alert_type, f"{self.stock_code} 触发{self.alert_type.value}预警")


@dataclass
class TriggeredAlert:
    """已触发的预警"""
    rule: AlertRule
    value: float
    timestamp: str
    indicators: dict
    
    def to_alert_data(self) -> AlertData:
        """转换为AlertData"""
        return AlertData(
            alert_type=self.rule.alert_type.value,
            stock_code=self.rule.stock_code,
            message=self.rule.get_message(self.value, self.indicators),
            value=self.value,
            threshold=self.rule.threshold,
            timestamp=self.timestamp
        )


class AlertTrigger:
    """预警触发器"""
    
    def __init__(self):
        self._rules: Dict[str, List[AlertRule]] = {}  # stock_code -> rules
        self._callbacks: List[Callable] = []
        self._triggered_history: Dict[str, TriggeredAlert] = {}  # rule_id -> triggered alert
        self._cooldown_end: Dict[str, datetime] = {}  # rule_id -> cooldown end time
    
    def add_rule(self, rule: AlertRule):
        """添加预警规则"""
        stock_code = rule.stock_code
        
        if stock_code not in self._rules:
            self._rules[stock_code] = []
        
        # 检查是否已存在相同规则
        for existing_rule in self._rules[stock_code]:
            if (existing_rule.alert_type == rule.alert_type and 
                existing_rule.threshold == rule.threshold):
                logger.warning(f"规则已存在: {stock_code} {rule.alert_type.value}")
                return
        
        self._rules[stock_code].append(rule)
        logger.info(f"添加预警规则: {stock_code} {rule.alert_type.value} 阈值={rule.threshold}")
    
    def remove_rule(self, stock_code: str, alert_type: AlertType):
        """移除预警规则"""
        if stock_code in self._rules:
            self._rules[stock_code] = [
                r for r in self._rules[stock_code] 
                if r.alert_type != alert_type
            ]
            logger.info(f"移除预警规则: {stock_code} {alert_type.value}")
    
    def clear_rules(self, stock_code: str = None):
        """清空预警规则"""
        if stock_code:
            self._rules.pop(stock_code, None)
        else:
            self._rules.clear()
        logger.info(f"清空预警规则: {stock_code or '全部'}")
    
    def register_callback(self, callback: Callable):
        """注册回调函数"""
        self._callbacks.append(callback)
    
    def check(self, stock_code: str, indicators: IndicatorResult) -> List[TriggeredAlert]:
        """检查是否触发预警"""
        triggered_alerts = []
        
        rules = self._rules.get(stock_code, [])
        
        for rule in rules:
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            rule_id = f"{stock_code}_{rule.alert_type.value}"
            if rule_id in self._cooldown_end:
                if datetime.now() < self._cooldown_end[rule_id]:
                    continue  # 还在冷却中
            
            # 检查各项指标
            alert_triggered = False
            trigger_value = 0.0
            
            if rule.alert_type == AlertType.RSI_OVERBOUGHT:
                if indicators.rsi and indicators.rsi > rule.threshold:
                    alert_triggered = True
                    trigger_value = indicators.rsi
                    
            elif rule.alert_type == AlertType.RSI_OVERSOLD:
                if indicators.rsi and indicators.rsi < rule.threshold:
                    alert_triggered = True
                    trigger_value = indicators.rsi
                    
            elif rule.alert_type == AlertType.GOLDEN_CROSS:
                if indicators.golden_cross:
                    alert_triggered = True
                    trigger_value = 1.0
                    
            elif rule.alert_type == AlertType.DEATH_CROSS:
                if indicators.death_cross:
                    alert_triggered = True
                    trigger_value = 1.0
                    
            elif rule.alert_type == AlertType.DEVIATION_ALERT:
                deviation = abs(indicators.deviation_5 or 0)
                if deviation > rule.threshold:
                    alert_triggered = True
                    trigger_value = deviation
                    
            elif rule.alert_type == AlertType.VOLUME_SPIKE:
                # TODO: 需要成交量数据
                pass
                
            elif rule.alert_type == AlertType.PRICE_BREAK:
                # TODO: 需要支撑阻力位数据
                pass
            
            # 触发预警
            if alert_triggered:
                # 安全转换indicators为字典
                if hasattr(indicators, 'to_dict'):
                    indicators_dict = indicators.to_dict()
                elif isinstance(indicators, dict):
                    indicators_dict = indicators
                else:
                    indicators_dict = {}
                triggered = TriggeredAlert(
                    rule=rule,
                    value=trigger_value,
                    timestamp=datetime.now().isoformat(),
                    indicators=indicators_dict
                )
                triggered_alerts.append(triggered)
                
                # 设置冷却时间
                self._cooldown_end[rule_id] = (
                    datetime.now().timestamp() + rule.cooldown_seconds
                )
                
                logger.info(f"触发预警: {rule.stock_code} {rule.alert_type.value} "
                          f"值={trigger_value:.2f} 阈值={rule.threshold}")
        
        # 触发回调
        for alert in triggered_alerts:
            for callback in self._callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"执行回调失败: {e}")
        
        return triggered_alerts
    
    def get_rules(self, stock_code: str = None) -> List[AlertRule]:
        """获取预警规则"""
        if stock_code:
            return self._rules.get(stock_code, [])
        else:
            all_rules = []
            for rules in self._rules.values():
                all_rules.extend(rules)
            return all_rules
    
    def get_status(self) -> dict:
        """获取预警状态"""
        return {
            "total_rules": sum(len(rules) for rules in self._rules.values()),
            "stocks_tracked": len(self._rules),
            "triggered_count": len(self._triggered_history)
        }


class AlertManager:
    """预警管理器 - 整合触发器和消息发送"""
    
    def __init__(self, gateway=None):
        self.trigger = AlertTrigger()
        self.gateway = gateway
        self._alert_history: List[TriggeredAlert] = []
        
        # 注册回调
        self.trigger.register_callback(self._on_alert_triggered)
    
    def _on_alert_triggered(self, alert: TriggeredAlert):
        """预警触发回调"""
        # 保存到历史
        self._alert_history.append(alert)
        
        # 限制历史记录数量
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-500:]
        
        # 推送到WebSocket
        if self.gateway:
            alert_data = alert.to_alert_data()
            # 转换AlertData为字典
            alert_dict = alert_data.to_dict() if hasattr(alert_data, 'to_dict') else alert_data
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 创建异步任务
                    import nest_asyncio
                    try:
                        nest_asyncio.apply()
                    except:
                        pass
                    loop.run_until_complete(
                        self.gateway.push_alert(alert.rule.stock_code, alert_dict)
                    )
            except Exception as e:
                logger.error(f"推送预警失败: {e}")
        
        logger.info(f"预警触发: {alert.rule.stock_code} {alert.rule.alert_type.value}")
    
    async def check_and_notify(self, stock_code: str, indicators: IndicatorResult):
        """检查并通知"""
        triggered = self.trigger.check(stock_code, indicators)
        return triggered
    
    def add_rule(self, stock_code: str, alert_type: AlertType, threshold: float, **kwargs):
        """添加规则（简化接口）"""
        rule = AlertRule(
            stock_code=stock_code,
            alert_type=alert_type,
            threshold=threshold,
            **kwargs
        )
        self.trigger.add_rule(rule)
    
    def get_alert_history(self, stock_code: str = None, limit: int = 50) -> List[TriggeredAlert]:
        """获取预警历史"""
        if stock_code:
            return [a for a in self._alert_history if a.rule.stock_code == stock_code][-limit:]
        return self._alert_history[-limit:]


# 添加 asyncio 导入
import asyncio

# 导出
__all__ = ['AlertTrigger', 'AlertRule', 'TriggeredAlert', 'AlertManager', 'AlertType']