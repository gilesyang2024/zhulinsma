"""
监控仪表板管理模块
提供监控数据的可视化仪表板配置和管理功能
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy import Column, String, JSON, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.core.config import Settings

import logging
logger = logging.getLogger(__name__)

# ====== 数据模型 ======

class DashboardLayout(str, Enum):
    """仪表板布局类型"""
    GRID = "grid"           # 网格布局
    FLEX = "flex"           # 弹性布局
    FIXED = "fixed"         # 固定布局
    
class WidgetType(str, Enum):
    """仪表板小组件类型"""
    CHART = "chart"         # 图表
    METRIC = "metric"       # 指标卡片
    TABLE = "table"         # 数据表格
    LOG = "log"            # 日志展示
    ALERT = "alert"         # 告警列表
    STATUS = "status"       # 状态面板

class ChartType(str, Enum):
    """图表类型"""
    LINE = "line"          # 折线图
    BAR = "bar"            # 柱状图
    PIE = "pie"            # 饼图
    GAUGE = "gauge"        # 仪表盘
    HEATMAP = "heatmap"    # 热力图
    SCATTER = "scatter"    # 散点图

class Dashboard(Base):
    """仪表板数据模型"""
    __tablename__ = "dashboards"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, comment="仪表板名称")
    description = Column(Text, nullable=True, comment="仪表板描述")
    
    # 布局配置
    layout = Column(String(50), default=DashboardLayout.GRID, comment="布局类型")
    columns = Column(Integer, default=12, comment="列数")
    row_height = Column(Integer, default=100, comment="行高(像素)")
    margin = Column(Integer, default=10, comment="边距(像素)")
    
    # 样式配置
    theme = Column(String(50), default="light", comment="主题")
    background_color = Column(String(50), default="#ffffff", comment="背景颜色")
    card_shadow = Column(String(50), default="sm", comment="卡片阴影")
    
    # 数据源和过滤器
    data_sources = Column(JSON, default=list, comment="数据源列表")
    filters = Column(JSON, default=dict, comment="过滤器配置")
    refresh_interval = Column(Integer, default=60, comment="刷新间隔(秒)")
    
    # 访问控制
    owner_id = Column(String(36), nullable=False, comment="拥有者ID")
    is_public = Column(Boolean, default=False, comment="是否公开")
    allowed_users = Column(JSON, default=list, comment="允许访问的用户ID列表")
    allowed_roles = Column(JSON, default=list, comment="允许访问的角色列表")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    widgets = relationship("DashboardWidget", back_populates="dashboard", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["id"] = self.id
        result["created_at"] = self.created_at.isoformat() if self.created_at else None
        result["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return result

class DashboardWidget(Base):
    """仪表板小组件数据模型"""
    __tablename__ = "dashboard_widgets"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dashboard_id = Column(String(36), nullable=False, comment="所属仪表板ID")
    widget_type = Column(String(50), nullable=False, comment="小组件类型")
    
    # 位置和大小
    x = Column(Integer, default=0, comment="X坐标")
    y = Column(Integer, default=0, comment="Y坐标")
    w = Column(Integer, default=4, comment="宽度")
    h = Column(Integer, default=4, comment="高度")
    min_w = Column(Integer, default=2, comment="最小宽度")
    min_h = Column(Integer, default=2, comment="最小高度")
    static = Column(Boolean, default=False, comment="是否固定位置")
    
    # 配置
    title = Column(String(255), nullable=False, comment="组件标题")
    config = Column(JSON, default=dict, comment="组件配置")
    data_source = Column(JSON, default=dict, comment="数据源配置")
    
    # 样式
    style = Column(JSON, default=dict, comment="样式配置")
    
    # 排序
    sort_order = Column(Integer, default=0, comment="排序顺序")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    dashboard = relationship("Dashboard", back_populates="widgets")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["id"] = self.id
        result["created_at"] = self.created_at.isoformat() if self.created_at else None
        result["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return result

# ====== 数据类 ======

@dataclass
class WidgetConfig:
    """小组件配置"""
    type: WidgetType
    title: str
    config: Dict[str, Any]
    data_source: Dict[str, Any]
    style: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        if self.position:
            result.update(self.position)
        return result

@dataclass
class DashboardCreateRequest:
    """创建仪表板请求"""
    name: str
    description: Optional[str] = None
    layout: DashboardLayout = DashboardLayout.GRID
    columns: int = 12
    theme: str = "light"
    widgets: List[WidgetConfig] = None
    
    def __post_init__(self):
        if self.widgets is None:
            self.widgets = []

@dataclass
class DashboardUpdateRequest:
    """更新仪表板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    layout: Optional[DashboardLayout] = None
    theme: Optional[str] = None
    widgets: Optional[List[WidgetConfig]] = None

# ====== 服务类 ======

class DashboardService:
    """仪表板服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = Settings()
        
    async def create_dashboard(self, request: DashboardCreateRequest, owner_id: str) -> Dashboard:
        """创建仪表板"""
        logger.info(f"创建仪表板: {request.name}, 拥有者: {owner_id}")
        
        # 检查名称是否已存在
        from sqlalchemy import select
        stmt = select(Dashboard).where(Dashboard.name == request.name)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(f"仪表板名称 '{request.name}' 已存在")
        
        # 创建仪表板
        dashboard = Dashboard(
            name=request.name,
            description=request.description,
            layout=request.layout,
            columns=request.columns,
            theme=request.theme,
            owner_id=owner_id
        )
        
        self.db.add(dashboard)
        await self.db.flush()
        
        # 添加小组件
        if request.widgets:
            for idx, widget_config in enumerate(request.widgets):
                widget = DashboardWidget(
                    dashboard_id=dashboard.id,
                    widget_type=widget_config.type.value,
                    title=widget_config.title,
                    config=widget_config.config,
                    data_source=widget_config.data_source,
                    style=widget_config.style or {},
                    x=0,
                    y=idx * 4,
                    w=widget_config.config.get("width", 4),
                    h=widget_config.config.get("height", 4),
                    sort_order=idx
                )
                self.db.add(widget)
        
        await self.db.commit()
        await self.db.refresh(dashboard)
        
        logger.info(f"仪表板创建成功: {dashboard.id}")
        return dashboard
    
    async def get_dashboard(self, dashboard_id: str, user_id: str = None) -> Optional[Dashboard]:
        """获取仪表板"""
        logger.info(f"获取仪表板: {dashboard_id}")
        
        from sqlalchemy import select
        stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
        result = await self.db.execute(stmt)
        dashboard = result.scalar_one_or_none()
        
        if not dashboard:
            return None
        
        # 检查访问权限
        if not self._can_access_dashboard(dashboard, user_id):
            return None
        
        return dashboard
    
    async def get_dashboards_by_owner(self, owner_id: str) -> List[Dashboard]:
        """获取用户的仪表板列表"""
        logger.info(f"获取用户仪表板列表: {owner_id}")
        
        from sqlalchemy import select
        stmt = select(Dashboard).where(Dashboard.owner_id == owner_id).order_by(Dashboard.updated_at.desc())
        result = await self.db.execute(stmt)
        dashboards = result.scalars().all()
        
        return list(dashboards)
    
    async def get_public_dashboards(self) -> List[Dashboard]:
        """获取公开仪表板列表"""
        logger.info("获取公开仪表板列表")
        
        from sqlalchemy import select
        stmt = select(Dashboard).where(Dashboard.is_public == True).order_by(Dashboard.updated_at.desc())
        result = await self.db.execute(stmt)
        dashboards = result.scalars().all()
        
        return list(dashboards)
    
    async def update_dashboard(self, dashboard_id: str, request: DashboardUpdateRequest, user_id: str) -> Optional[Dashboard]:
        """更新仪表板"""
        logger.info(f"更新仪表板: {dashboard_id}")
        
        dashboard = await self.get_dashboard(dashboard_id, user_id)
        if not dashboard or dashboard.owner_id != user_id:
            return None
        
        # 更新字段
        if request.name is not None:
            dashboard.name = request.name
        if request.description is not None:
            dashboard.description = request.description
        if request.layout is not None:
            dashboard.layout = request.layout
        if request.theme is not None:
            dashboard.theme = request.theme
        
        # 更新小组件（如果提供）
        if request.widgets is not None:
            # 删除现有小组件
            from sqlalchemy import delete
            stmt = delete(DashboardWidget).where(DashboardWidget.dashboard_id == dashboard_id)
            await self.db.execute(stmt)
            
            # 添加新小组件
            for idx, widget_config in enumerate(request.widgets):
                widget = DashboardWidget(
                    dashboard_id=dashboard_id,
                    widget_type=widget_config.type.value,
                    title=widget_config.title,
                    config=widget_config.config,
                    data_source=widget_config.data_source,
                    style=widget_config.style or {},
                    x=0,
                    y=idx * 4,
                    w=widget_config.config.get("width", 4),
                    h=widget_config.config.get("height", 4),
                    sort_order=idx
                )
                self.db.add(widget)
        
        dashboard.updated_at = func.now()
        await self.db.commit()
        await self.db.refresh(dashboard)
        
        logger.info(f"仪表板更新成功: {dashboard_id}")
        return dashboard
    
    async def delete_dashboard(self, dashboard_id: str, user_id: str) -> bool:
        """删除仪表板"""
        logger.info(f"删除仪表板: {dashboard_id}")
        
        dashboard = await self.get_dashboard(dashboard_id, user_id)
        if not dashboard or dashboard.owner_id != user_id:
            return False
        
        await self.db.delete(dashboard)
        await self.db.commit()
        
        logger.info(f"仪表板删除成功: {dashboard_id}")
        return True
    
    async def add_widget(self, dashboard_id: str, widget_config: WidgetConfig, user_id: str) -> Optional[DashboardWidget]:
        """添加小组件到仪表板"""
        logger.info(f"添加小组件到仪表板: {dashboard_id}")
        
        dashboard = await self.get_dashboard(dashboard_id, user_id)
        if not dashboard or dashboard.owner_id != user_id:
            return None
        
        # 获取当前最大Y坐标
        from sqlalchemy import select, func
        stmt = select(func.max(DashboardWidget.y)).where(DashboardWidget.dashboard_id == dashboard_id)
        result = await self.db.execute(stmt)
        max_y = result.scalar() or 0
        
        # 创建小组件
        widget = DashboardWidget(
            dashboard_id=dashboard_id,
            widget_type=widget_config.type.value,
            title=widget_config.title,
            config=widget_config.config,
            data_source=widget_config.data_source,
            style=widget_config.style or {},
            x=0,
            y=max_y + 4,
            w=widget_config.config.get("width", 4),
            h=widget_config.config.get("height", 4),
            sort_order=0
        )
        
        self.db.add(widget)
        await self.db.commit()
        await self.db.refresh(widget)
        
        logger.info(f"小组件添加成功: {widget.id}")
        return widget
    
    async def get_widget_data(self, widget_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取小组件数据"""
        logger.info(f"获取小组件数据: {widget_id}")
        
        from sqlalchemy import select
        stmt = select(DashboardWidget).where(DashboardWidget.id == widget_id)
        result = await self.db.execute(stmt)
        widget = result.scalar_one_or_none()
        
        if not widget:
            return None
        
        # 获取关联的仪表板
        dashboard = await self.get_dashboard(widget.dashboard_id, user_id)
        if not dashboard:
            return None
        
        # 根据小组件类型生成数据
        return await self._generate_widget_data(widget)
    
    async def clone_dashboard(self, dashboard_id: str, new_name: str, user_id: str) -> Optional[Dashboard]:
        """克隆仪表板"""
        logger.info(f"克隆仪表板: {dashboard_id} -> {new_name}")
        
        original = await self.get_dashboard(dashboard_id, user_id)
        if not original:
            return None
        
        # 创建新仪表板
        dashboard = Dashboard(
            name=new_name,
            description=f"{original.description} (克隆)",
            layout=original.layout,
            columns=original.columns,
            theme=original.theme,
            owner_id=user_id,
            is_public=False
        )
        
        self.db.add(dashboard)
        await self.db.flush()
        
        # 克隆小组件
        for original_widget in original.widgets:
            widget = DashboardWidget(
                dashboard_id=dashboard.id,
                widget_type=original_widget.widget_type,
                title=original_widget.title,
                config=original_widget.config.copy(),
                data_source=original_widget.data_source.copy(),
                style=original_widget.style.copy() if original_widget.style else {},
                x=original_widget.x,
                y=original_widget.y,
                w=original_widget.w,
                h=original_widget.h,
                sort_order=original_widget.sort_order
            )
            self.db.add(widget)
        
        await self.db.commit()
        await self.db.refresh(dashboard)
        
        logger.info(f"仪表板克隆成功: {dashboard.id}")
        return dashboard
    
    def _can_access_dashboard(self, dashboard: Dashboard, user_id: str = None) -> bool:
        """检查用户是否可以访问仪表板"""
        # 公开仪表板所有人都可以访问
        if dashboard.is_public:
            return True
        
        # 如果没有用户ID，只允许访问公开仪表板
        if not user_id:
            return False
        
        # 拥有者可以访问
        if dashboard.owner_id == user_id:
            return True
        
        # 检查允许的用户列表
        if user_id in dashboard.allowed_users:
            return True
        
        # TODO: 检查允许的角色列表
        # 这里需要实现角色检查逻辑
        
        return False
    
    async def _generate_widget_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成小组件数据"""
        widget_type = WidgetType(widget.widget_type)
        
        if widget_type == WidgetType.METRIC:
            # 生成指标数据
            return await self._generate_metric_data(widget)
        elif widget_type == WidgetType.CHART:
            # 生成图表数据
            return await self._generate_chart_data(widget)
        elif widget_type == WidgetType.TABLE:
            # 生成表格数据
            return await self._generate_table_data(widget)
        elif widget_type == WidgetType.LOG:
            # 生成日志数据
            return await self._generate_log_data(widget)
        elif widget_type == WidgetType.ALERT:
            # 生成告警数据
            return await self._generate_alert_data(widget)
        elif widget_type == WidgetType.STATUS:
            # 生成状态数据
            return await self._generate_status_data(widget)
        else:
            return {"error": f"不支持的小组件类型: {widget_type}"}
    
    async def _generate_metric_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成指标数据"""
        config = widget.config
        
        # 这里可以根据实际需求从数据库或监控系统获取数据
        # 示例：返回模拟数据
        return {
            "value": 12345,
            "label": config.get("label", "指标"),
            "unit": config.get("unit", ""),
            "trend": 12.5,  # 百分比变化
            "trend_label": "相比昨天",
            "icon": config.get("icon", "chart-line")
        }
    
    async def _generate_chart_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成图表数据"""
        config = widget.config
        chart_type = config.get("chart_type", ChartType.LINE)
        
        # 生成模拟数据
        import random
        data = []
        labels = []
        
        for i in range(10):
            labels.append(f"数据点 {i+1}")
            data.append(random.randint(10, 100))
        
        return {
            "type": chart_type,
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": config.get("label", "数据集"),
                    "data": data,
                    "backgroundColor": config.get("backgroundColor", "#3b82f6"),
                    "borderColor": config.get("borderColor", "#1d4ed8")
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {
                        "position": "top"
                    }
                }
            }
        }
    
    async def _generate_table_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成表格数据"""
        config = widget.config
        
        # 生成模拟数据
        columns = config.get("columns", ["ID", "名称", "状态", "时间"])
        data = []
        
        for i in range(10):
            data.append({
                "id": f"item_{i+1}",
                "name": f"项目 {i+1}",
                "status": "运行中" if i % 3 == 0 else "已停止" if i % 3 == 1 else "错误",
                "time": f"2024-01-{i+1:02d} 12:00:00"
            })
        
        return {
            "columns": columns,
            "data": data,
            "total": 10,
            "page": 1,
            "page_size": 10
        }
    
    async def _generate_log_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成日志数据"""
        config = widget.config
        
        # 生成模拟日志数据
        import random
        levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        logs = []
        
        for i in range(20):
            logs.append({
                "timestamp": f"2024-01-01 12:{i:02d}:00",
                "level": random.choice(levels),
                "message": f"这是第 {i+1} 条日志消息",
                "source": f"service_{random.randint(1, 5)}"
            })
        
        return {
            "logs": logs,
            "total": 20,
            "filter": config.get("filter", {})
        }
    
    async def _generate_alert_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成告警数据"""
        config = widget.config
        
        # 生成模拟告警数据
        alerts = [
            {
                "id": "alert_1",
                "title": "API响应时间过高",
                "severity": "high",
                "status": "active",
                "timestamp": "2024-01-01 12:00:00",
                "description": "API /users 的响应时间超过 500ms 阈值"
            },
            {
                "id": "alert_2",
                "title": "数据库连接数接近上限",
                "severity": "medium",
                "status": "active",
                "timestamp": "2024-01-01 11:30:00",
                "description": "数据库连接数达到 90% 容量"
            },
            {
                "id": "alert_3",
                "title": "内存使用率过高",
                "severity": "low",
                "status": "resolved",
                "timestamp": "2024-01-01 10:00:00",
                "description": "服务器内存使用率达到 85%"
            }
        ]
        
        return {
            "alerts": alerts,
            "total_active": sum(1 for a in alerts if a["status"] == "active"),
            "total_resolved": sum(1 for a in alerts if a["status"] == "resolved")
        }
    
    async def _generate_status_data(self, widget: DashboardWidget) -> Dict[str, Any]:
        """生成状态数据"""
        config = widget.config
        
        # 生成模拟状态数据
        services = [
            {"name": "API Gateway", "status": "healthy", "latency": "45ms", "uptime": "99.9%"},
            {"name": "Database", "status": "healthy", "latency": "12ms", "uptime": "99.8%"},
            {"name": "Cache", "status": "degraded", "latency": "120ms", "uptime": "98.5%"},
            {"name": "Queue", "status": "healthy", "latency": "5ms", "uptime": "99.7%"},
            {"name": "Storage", "status": "unhealthy", "latency": "timeout", "uptime": "95.2%"}
        ]
        
        return {
            "services": services,
            "overall_status": "degraded",
            "timestamp": datetime.now().isoformat()
        }

# ====== 预设仪表板 ======

class DashboardPreset:
    """预设仪表板配置"""
    
    @staticmethod
    def get_system_monitoring() -> DashboardCreateRequest:
        """系统监控仪表板"""
        return DashboardCreateRequest(
            name="系统监控仪表板",
            description="系统整体监控仪表板，包含关键指标和图表",
            layout=DashboardLayout.GRID,
            theme="dark",
            widgets=[
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="API请求总数",
                    config={"width": 3, "height": 2, "icon": "api", "unit": "次"},
                    data_source={"type": "prometheus", "query": "sum(http_requests_total)"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="平均响应时间",
                    config={"width": 3, "height": 2, "icon": "clock", "unit": "ms"},
                    data_source={"type": "prometheus", "query": "avg(http_request_duration_seconds) * 1000"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="错误率",
                    config={"width": 3, "height": 2, "icon": "alert-circle", "unit": "%"},
                    data_source={"type": "prometheus", "query": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m]) * 100"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="活跃用户数",
                    config={"width": 3, "height": 2, "icon": "users", "unit": "人"},
                    data_source={"type": "database", "query": "SELECT COUNT(DISTINCT user_id) FROM sessions WHERE active = true"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="请求趋势图",
                    config={"width": 12, "height": 6, "chart_type": ChartType.LINE},
                    data_source={"type": "prometheus", "query": "rate(http_requests_total[5m])"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="响应时间分布",
                    config={"width": 6, "height": 6, "chart_type": ChartType.BAR},
                    data_source={"type": "prometheus", "query": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"}
                ),
                WidgetConfig(
                    type=WidgetType.TABLE,
                    title="最近告警",
                    config={"width": 6, "height": 6, "columns": ["时间", "级别", "服务", "描述"]},
                    data_source={"type": "alerts", "filter": {"limit": 10}}
                ),
                WidgetConfig(
                    type=WidgetType.STATUS,
                    title="服务状态",
                    config={"width": 12, "height": 4},
                    data_source={"type": "health", "services": ["api", "db", "cache", "queue", "storage"]}
                )
            ]
        )
    
    @staticmethod
    def get_business_analytics() -> DashboardCreateRequest:
        """业务分析仪表板"""
        return DashboardCreateRequest(
            name="业务分析仪表板",
            description="业务指标和用户行为分析仪表板",
            layout=DashboardLayout.FLEX,
            theme="light",
            widgets=[
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="今日新增用户",
                    config={"width": 4, "height": 2, "icon": "user-plus", "unit": "人"},
                    data_source={"type": "database", "query": "SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURDATE()"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="活跃会话数",
                    config={"width": 4, "height": 2, "icon": "activity", "unit": "个"},
                    data_source={"type": "database", "query": "SELECT COUNT(*) FROM sessions WHERE active = true"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="订单转化率",
                    config={"width": 4, "height": 2, "icon": "shopping-cart", "unit": "%"},
                    data_source={"type": "analytics", "metric": "conversion_rate"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="用户增长趋势",
                    config={"width": 8, "height": 6, "chart_type": ChartType.LINE},
                    data_source={"type": "analytics", "metric": "user_growth"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="用户分布",
                    config={"width": 4, "height": 6, "chart_type": ChartType.PIE},
                    data_source={"type": "analytics", "metric": "user_distribution"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="热门功能使用",
                    config={"width": 12, "height": 6, "chart_type": ChartType.BAR},
                    data_source={"type": "analytics", "metric": "feature_usage"}
                ),
                WidgetConfig(
                    type=WidgetType.TABLE,
                    title="用户行为日志",
                    config={"width": 12, "height": 8, "columns": ["用户", "行为", "时间", "详情"]},
                    data_source={"type": "logs", "filter": {"type": "user_activity", "limit": 20}}
                )
            ]
        )
    
    @staticmethod
    def get_error_monitoring() -> DashboardCreateRequest:
        """错误监控仪表板"""
        return DashboardCreateRequest(
            name="错误监控仪表板",
            description="系统错误和异常监控仪表板",
            layout=DashboardLayout.GRID,
            theme="dark",
            widgets=[
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="今日错误数",
                    config={"width": 3, "height": 2, "icon": "alert-triangle", "unit": "个"},
                    data_source={"type": "logs", "filter": {"level": "ERROR", "time_range": "today"}}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="错误率趋势",
                    config={"width": 3, "height": 2, "icon": "trending-down", "unit": "%"},
                    data_source={"type": "metrics", "query": "error_rate"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="影响用户数",
                    config={"width": 3, "height": 2, "icon": "users", "unit": "人"},
                    data_source={"type": "analytics", "metric": "affected_users"}
                ),
                WidgetConfig(
                    type=WidgetType.METRIC,
                    title="平均修复时间",
                    config={"width": 3, "height": 2, "icon": "clock", "unit": "小时"},
                    data_source={"type": "incidents", "metric": "mttr"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="错误类型分布",
                    config={"width": 6, "height": 6, "chart_type": ChartType.PIE},
                    data_source={"type": "logs", "aggregation": "error_types"}
                ),
                WidgetConfig(
                    type=WidgetType.CHART,
                    title="错误时间趋势",
                    config={"width": 6, "height": 6, "chart_type": ChartType.LINE},
                    data_source={"type": "logs", "filter": {"level": "ERROR"}, "time_series": True}
                ),
                WidgetConfig(
                    type=WidgetType.LOG,
                    title="最新错误日志",
                    config={"width": 12, "height": 8},
                    data_source={"type": "logs", "filter": {"level": "ERROR", "limit": 50}}
                ),
                WidgetConfig(
                    type=WidgetType.TABLE,
                    title="待处理错误",
                    config={"width": 12, "height": 6, "columns": ["ID", "错误类型", "首次出现", "影响范围", "状态"]},
                    data_source={"type": "incidents", "filter": {"status": "open"}}
                )
            ]
        )

# ====== 工具函数 ======

def create_default_dashboards(db: AsyncSession, owner_id: str) -> Dict[str, Dashboard]:
    """创建默认仪表板"""
    logger.info(f"为用户创建默认仪表板: {owner_id}")
    
    service = DashboardService(db)
    dashboards = {}
    
    try:
        # 系统监控仪表板
        system_request = DashboardPreset.get_system_monitoring()
        system_request.name = f"{owner_id}_system_monitoring"
        system_dashboard = service.create_dashboard(system_request, owner_id)
        dashboards["system"] = system_dashboard
        
        # 业务分析仪表板
        business_request = DashboardPreset.get_business_analytics()
        business_request.name = f"{owner_id}_business_analytics"
        business_dashboard = service.create_dashboard(business_request, owner_id)
        dashboards["business"] = business_dashboard
        
        # 错误监控仪表板
        error_request = DashboardPreset.get_error_monitoring()
        error_request.name = f"{owner_id}_error_monitoring"
        error_dashboard = service.create_dashboard(error_request, owner_id)
        dashboards["error"] = error_dashboard
        
        logger.info(f"默认仪表板创建成功: {list(dashboards.keys())}")
        return dashboards
        
    except Exception as e:
        logger.error(f"创建默认仪表板失败: {str(e)}")
        return {}