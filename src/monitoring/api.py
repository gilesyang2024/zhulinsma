"""
监控系统API模块
提供监控相关的API端点
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import get_current_user
import logging; get_logger = logging.getLogger
from src.monitoring.metrics import get_metrics_collector
from src.monitoring.alerts import AlertManager, AlertConfig
from src.monitoring.health import HealthChecker
from src.monitoring.dashboard import (
    DashboardService, DashboardCreateRequest, DashboardUpdateRequest,
    WidgetConfig, DashboardPreset
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/monitoring",
    tags=["监控"],
    responses={
        404: {"description": "未找到"},
        500: {"description": "服务器内部错误"}
    }
)

# ====== 指标API ======

@router.get("/metrics", summary="获取系统指标")
async def get_metrics(
    format: str = Query("json", description="返回格式: json 或 prometheus"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取系统监控指标
    
    支持的格式:
    - json: 返回JSON格式的指标数据
    - prometheus: 返回Prometheus格式的指标数据
    """
    try:
        collector = get_metrics_collector()
        
        if format.lower() == "prometheus":
            # 返回Prometheus格式
            from prometheus_client import generate_latest
            content = generate_latest(collector.registry)
            return JSONResponse(
                content=content.decode('utf-8'),
                media_type="text/plain; version=0.0.4"
            )
        else:
            # 返回JSON格式
            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "metrics": collector.get_metrics_summary()
            }
            return metrics_data
            
    except Exception as e:
        logger.error(f"获取指标失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取指标失败: {str(e)}"
        )

@router.get("/metrics/summary", summary="获取指标摘要")
async def get_metrics_summary(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取系统指标摘要"""
    try:
        collector = get_metrics_collector()
        summary = collector.get_metrics_summary()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"获取指标摘要失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取指标摘要失败: {str(e)}"
        )

@router.get("/metrics/historical", summary="获取历史指标")
async def get_historical_metrics(
    metric_name: str = Query(..., description="指标名称"),
    start_time: str = Query(None, description="开始时间(ISO格式)"),
    end_time: str = Query(None, description="结束时间(ISO格式)"),
    interval: str = Query("1h", description="时间间隔"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取历史指标数据
    
    注意: 需要配置时间序列数据库支持
    """
    try:
        # 这里可以集成Prometheus、InfluxDB等时间序列数据库
        # 目前返回模拟数据
        
        if not start_time:
            start_time = (datetime.now() - timedelta(hours=24)).isoformat()
        if not end_time:
            end_time = datetime.now().isoformat()
        
        # 模拟历史数据
        import random
        data_points = []
        current_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_time_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        while current_time < end_time_dt:
            data_points.append({
                "timestamp": current_time.isoformat(),
                "value": random.uniform(10, 100)
            })
            current_time += timedelta(minutes=5)
        
        return {
            "metric": metric_name,
            "data": data_points,
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "count": len(data_points)
        }
        
    except Exception as e:
        logger.error(f"获取历史指标失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史指标失败: {str(e)}"
        )

# ====== 告警API ======

@router.get("/alerts", summary="获取告警列表")
async def get_alerts(
    status: str = Query(None, description="告警状态: active, resolved, silenced"),
    severity: str = Query(None, description="严重级别: critical, warning, info"),
    limit: int = Query(100, description="返回数量限制"),
    offset: int = Query(0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取告警列表"""
    try:
        alert_manager = AlertManager()
        alerts = alert_manager.get_alerts(
            status=status,
            severity=severity,
            limit=limit,
            offset=offset
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total": len(alerts),
            "active_count": sum(1 for a in alerts if a["status"] == "active"),
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"获取告警列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取告警列表失败: {str(e)}"
        )

@router.post("/alerts", summary="创建告警")
async def create_alert(
    alert_config: AlertConfig,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """创建新的告警配置"""
    try:
        alert_manager = AlertManager()
        alert_id = alert_manager.create_alert(alert_config)
        
        logger.info(f"告警配置创建成功: {alert_id}, 创建者: {current_user.get('id')}")
        
        return {
            "id": alert_id,
            "message": "告警配置创建成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"创建告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建告警失败: {str(e)}"
        )

@router.put("/alerts/{alert_id}", summary="更新告警")
async def update_alert(
    alert_id: str,
    alert_config: AlertConfig,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """更新告警配置"""
    try:
        alert_manager = AlertManager()
        
        if not alert_manager.update_alert(alert_id, alert_config):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"告警 {alert_id} 不存在"
            )
        
        logger.info(f"告警配置更新成功: {alert_id}, 更新者: {current_user.get('id')}")
        
        return {
            "id": alert_id,
            "message": "告警配置更新成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新告警失败: {str(e)}"
        )

@router.delete("/alerts/{alert_id}", summary="删除告警")
async def delete_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """删除告警配置"""
    try:
        alert_manager = AlertManager()
        
        if not alert_manager.delete_alert(alert_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"告警 {alert_id} 不存在"
            )
        
        logger.info(f"告警配置删除成功: {alert_id}, 删除者: {current_user.get('id')}")
        
        return {
            "id": alert_id,
            "message": "告警配置删除成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除告警失败: {str(e)}"
        )

@router.post("/alerts/{alert_id}/silence", summary="静默告警")
async def silence_alert(
    alert_id: str,
    duration_minutes: int = Query(60, description="静默持续时间(分钟)"),
    reason: str = Query("", description="静默原因"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """静默告警"""
    try:
        alert_manager = AlertManager()
        
        if not alert_manager.silence_alert(alert_id, duration_minutes, reason):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"告警 {alert_id} 不存在"
            )
        
        logger.info(f"告警静默成功: {alert_id}, 静默者: {current_user.get('id')}")
        
        return {
            "id": alert_id,
            "message": "告警静默成功",
            "silenced_until": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"静默告警失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"静默告警失败: {str(e)}"
        )

# ====== 仪表板API ======

@router.get("/dashboards", summary="获取仪表板列表")
async def get_dashboards(
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取用户可访问的仪表板列表"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        service = DashboardService(db)
        
        # 获取用户拥有的仪表板
        owned = await service.get_dashboards_by_owner(user_id)
        
        # 获取公开仪表板
        public = await service.get_public_dashboards()
        
        # 去重
        owned_ids = {d.id for d in owned}
        public_filtered = [d for d in public if d.id not in owned_ids]
        
        dashboards = owned + public_filtered
        
        return {
            "timestamp": datetime.now().isoformat(),
            "owned_count": len(owned),
            "public_count": len(public_filtered),
            "total": len(dashboards),
            "dashboards": [d.to_dict() for d in dashboards]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取仪表板列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取仪表板列表失败: {str(e)}"
        )

@router.post("/dashboards", summary="创建仪表板")
async def create_dashboard(
    request: DashboardCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """创建新的仪表板"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        service = DashboardService(db)
        dashboard = await service.create_dashboard(request, user_id)
        
        return {
            "id": dashboard.id,
            "message": "仪表板创建成功",
            "dashboard": dashboard.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建仪表板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建仪表板失败: {str(e)}"
        )

@router.get("/dashboards/{dashboard_id}", summary="获取仪表板详情")
async def get_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取仪表板详情"""
    try:
        user_id = current_user.get("id")
        service = DashboardService(db)
        
        dashboard = await service.get_dashboard(dashboard_id, user_id)
        if not dashboard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"仪表板 {dashboard_id} 不存在或无权访问"
            )
        
        return {
            "dashboard": dashboard.to_dict(),
            "widgets": [w.to_dict() for w in dashboard.widgets],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取仪表板详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取仪表板详情失败: {str(e)}"
        )

@router.put("/dashboards/{dashboard_id}", summary="更新仪表板")
async def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """更新仪表板"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        service = DashboardService(db)
        dashboard = await service.update_dashboard(dashboard_id, request, user_id)
        
        if not dashboard:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"仪表板 {dashboard_id} 不存在或无权修改"
            )
        
        return {
            "id": dashboard.id,
            "message": "仪表板更新成功",
            "dashboard": dashboard.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新仪表板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新仪表板失败: {str(e)}"
        )

@router.delete("/dashboards/{dashboard_id}", summary="删除仪表板")
async def delete_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """删除仪表板"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        service = DashboardService(db)
        success = await service.delete_dashboard(dashboard_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"仪表板 {dashboard_id} 不存在或无权删除"
            )
        
        return {
            "id": dashboard_id,
            "message": "仪表板删除成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除仪表板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除仪表板失败: {str(e)}"
        )

@router.post("/dashboards/preset/{preset_name}", summary="创建预设仪表板")
async def create_preset_dashboard(
    preset_name: str,
    custom_name: str = Query(None, description="自定义仪表板名称"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """创建预设的仪表板"""
    try:
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        # 获取预设配置
        preset_methods = {
            "system_monitoring": DashboardPreset.get_system_monitoring,
            "business_analytics": DashboardPreset.get_business_analytics,
            "error_monitoring": DashboardPreset.get_error_monitoring
        }
        
        if preset_name not in preset_methods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的预设名称: {preset_name}"
            )
        
        preset_request = preset_methods[preset_name]()
        
        # 使用自定义名称
        if custom_name:
            preset_request.name = custom_name
        
        service = DashboardService(db)
        dashboard = await service.create_dashboard(preset_request, user_id)
        
        return {
            "id": dashboard.id,
            "message": "预设仪表板创建成功",
            "preset": preset_name,
            "dashboard": dashboard.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建预设仪表板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建预设仪表板失败: {str(e)}"
        )

@router.get("/dashboards/{dashboard_id}/widgets/{widget_id}/data", summary="获取小组件数据")
async def get_widget_data(
    dashboard_id: str,
    widget_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取仪表板小组件的数据"""
    try:
        user_id = current_user.get("id")
        service = DashboardService(db)
        
        data = await service.get_widget_data(widget_id, user_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"小组件 {widget_id} 不存在或无权访问"
            )
        
        return {
            "widget_id": widget_id,
            "dashboard_id": dashboard_id,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取小组件数据失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取小组件数据失败: {str(e)}"
        )

# ====== 系统状态API ======

@router.get("/status", summary="获取系统状态")
async def get_system_status(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取系统整体状态"""
    try:
        health_checker = HealthChecker()
        metrics_collector = get_metrics_collector()
        
        # 执行健康检查
        health_result = await health_checker.check_all()
        
        # 获取指标摘要
        metrics_summary = metrics_collector.get_metrics_summary()
        
        # 获取告警状态
        alert_manager = AlertManager()
        active_alerts = alert_manager.get_alerts(status="active", limit=10)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy" if health_result["overall"]["status"] == "healthy" else "degraded",
            "health": health_result,
            "metrics": metrics_summary,
            "alerts": {
                "active_count": len(active_alerts),
                "recent_alerts": active_alerts[:5]
            },
            "system_info": {
                "uptime": health_checker.get_uptime(),
                "version": "1.0.0",  # 可以从配置中获取
                "environment": "development"  # 可以从配置中获取
            }
        }
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )

@router.get("/logs", summary="获取系统日志")
async def get_system_logs(
    level: str = Query(None, description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    service: str = Query(None, description="服务名称"),
    start_time: str = Query(None, description="开始时间(ISO格式)"),
    end_time: str = Query(None, description="结束时间(ISO格式)"),
    limit: int = Query(100, description="返回数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取系统日志"""
    try:
        # 这里需要集成实际的日志存储系统
        # 目前返回模拟数据
        
        import random
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        services = ["api", "database", "cache", "queue", "monitoring"]
        
        if level and level not in levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的日志级别: {level}"
            )
        
        logs = []
        for i in range(min(limit, 50)):
            log_level = level if level else random.choice(levels)
            log_service = service if service else random.choice(services)
            
            logs.append({
                "id": f"log_{i+1}",
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                "level": log_level,
                "service": log_service,
                "message": f"这是来自 {log_service} 服务的 {log_level} 级别日志消息 #{i+1}",
                "context": {
                    "request_id": f"req_{random.randint(1000, 9999)}",
                    "user_id": current_user.get("id") if random.random() > 0.7 else None
                }
            })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total": len(logs),
            "logs": logs,
            "filter": {
                "level": level,
                "service": service,
                "start_time": start_time,
                "end_time": end_time
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统日志失败: {str(e)}"
        )

# ====== 管理API ======

@router.post("/reset", summary="重置监控数据")
async def reset_monitoring_data(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """重置监控数据（需要管理员权限）"""
    try:
        # 检查管理员权限
        user_roles = current_user.get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限"
            )
        
        # 在后台任务中重置
        def reset_in_background():
            try:
                metrics_collector = get_metrics_collector()
                metrics_collector.reset_metrics()
                logger.info("监控数据重置成功")
            except Exception as e:
                logger.error(f"重置监控数据失败: {str(e)}")
        
        background_tasks.add_task(reset_in_background)
        
        return {
            "message": "监控数据重置任务已启动",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置监控数据失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置监控数据失败: {str(e)}"
        )

@router.post("/export", summary="导出监控数据")
async def export_monitoring_data(
    export_format: str = Query("json", description="导出格式: json 或 csv"),
    include_metrics: bool = Query(True, description="是否包含指标数据"),
    include_logs: bool = Query(False, description="是否包含日志数据"),
    include_alerts: bool = Query(True, description="是否包含告警数据"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """导出监控数据"""
    try:
        # 这里可以实现实际的数据导出逻辑
        # 目前返回模拟数据
        
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "exported_by": current_user.get("id"),
            "format": export_format,
            "metadata": {
                "include_metrics": include_metrics,
                "include_logs": include_logs,
                "include_alerts": include_alerts
            }
        }
        
        if include_metrics:
            collector = get_metrics_collector()
            export_data["metrics"] = collector.get_metrics_summary()
        
        if include_alerts:
            alert_manager = AlertManager()
            export_data["alerts"] = alert_manager.get_alerts(limit=100)
        
        return export_data
        
    except Exception as e:
        logger.error(f"导出监控数据失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出监控数据失败: {str(e)}"
        )