"""
数据分析模块 - API接口

提供数据采集、查询、报表等RESTful API。
支持前端埋点、管理后台数据分析、定时报表等功能。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    Query, Body, BackgroundTasks
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import get_current_user, require_admin
from .models import EventType, DeviceType
from .collector import EventCollector, PageViewData, EventData
from .aggregator import DataAggregator
from .report import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["数据分析"])


# ========== 依赖注入 ==========

async def get_collector(db: AsyncSession = Depends(get_db)) -> EventCollector:
    return EventCollector(db)

async def get_aggregator(db: AsyncSession = Depends(get_db)) -> DataAggregator:
    return DataAggregator(db)

async def get_report_gen(db: AsyncSession = Depends(get_db)) -> ReportGenerator:
    return ReportGenerator(db)


# ==================== 事件采集接口 ====================

@router.post("/track/pageview", summary="记录页面浏览")
async def track_page_view(
    page_path: str = Query(..., description="页面路径"),
    session_id: str = Query(..., description="会话ID"),
    page_title: str = Query(None),
    referrer: str = Query(None),
    device_type: str = Query("unknown"),
    browser: str = Query(None),
    os: str = Query(None),
    ip_address: str = Query(None),
    collector: EventCollector = Depends(get_collector),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """记录一次页面浏览（前端埋点调用）"""
    
    data = PageViewData(
        page_path=page_path,
        page_title=page_title,
        referrer=referrer,
        device_type=device_type,
        browser=browser,
        os=os,
        ip_address=ip_address,
    )
    
    view = await collector.track_page_view(
        user_id=current_user.get("user_id") if current_user else None,
        session_id=session_id,
        page_data=data
    )
    
    return {
        "success": True,
        "view_id": view.id,
        "session_id": session_id
    }


@router.post("/track/event", summary="记录自定义事件")
async def track_event(
    event_data: EventData = Body(...),
    collector: EventCollector = Depends(get_collector),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """记录一个用户交互事件（前端埋点调用）"""
    
    event = await collector.track_event(
        user_id=current_user.get("user_id") if current_user else None,
        session_id=event_data.properties.pop("session_id", None) if event_data.properties else None,
        event_data=event_data,
    )
    
    return {"success": True, "event_id": event.id}


@router.post("/track/batch", summary="批量上报事件")
async def track_batch_events(
    events: List[Dict[str, Any]] = Body(..., min_length=1, max_length=100),
    collector: EventCollector = Depends(get_collector),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """批量上报多个事件，适合离线/批量场景"""
    
    count = await collector.batch_track_events(
        events=events,
        user_id=current_user.get("user_id") if current_user else None,
    )
    
    return {"success": True, "recorded_count": count}


@router.put("/track/pageview/{view_id}/duration", summary="更新页面停留时长")
async def update_page_duration(
    view_id: int,
    duration_seconds: int = Query(..., ge=0, le=86400),
    collector: EventCollector = Depends(get_collector),
):
    """更新页面浏览的停留时长（用户离开时调用）"""
    
    success = await collector.update_page_view_duration(view_id, duration_seconds)
    
    if not success:
        raise HTTPException(status_code=404, detail="页面浏览记录不存在")
    
    return {"success": True}


# ==================== 数据查询接口 ====================

@router.get("/overview", summary="获取概览指标")
async def get_overview(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取系统概览指标：PV、UV、活跃用户、热门页面等"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    result = await aggregator.get_overview_metrics(start_date, end_date)
    return result


@router.get("/engagement", summary="获取用户活跃度(DAU/WAU/MAU)")
async def get_engagement_metrics(
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取DAU(日活)、WAU(周活)、MAU(月活)及粘性指数"""
    return await aggregator.get_dau_wau_mau()


@router.get("/retention", summary="获取用户留存率")
async def get_retention(
    cohort_date: str = Query(..., description="队列日期 YYYY-MM-DD格式"),
    periods: int = Query(7, ge=1, le=30, description="计算天数"),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取指定日期新用户的留存率曲线"""
    
    try:
        date_obj = datetime.strptime(cohort_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用YYYY-MM-DD")
    
    return await aggregator.calculate_retention(date_obj, periods)


@router.get("/content/popular", summary="获取内容热度排行")
async def get_popular_content(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取最受欢迎的内容排行（基于互动数据）"""
    
    start_date = datetime.now() - timedelta(days=days)
    return await aggregator.get_content_popularity(start_date, limit=limit)


@router.get("/funnel", summary="转化漏斗分析")
async def analyze_funnel(
    funnel_name: str = Query("注册漏斗"),
    steps_json: str = Query(
        '[["click","landing"],["click","signup_btn"],["submit","register"]]',
        description='步骤JSON: [[event_type,event_name],...]'
    ),
    days: int = Query(7, ge=1, le=90),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """分析指定转化漏斗的数据"""
    
    import json
    
    try:
        steps = json.loads(steps_json)
        if not isinstance(steps, list) or len(steps) < 2:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="steps参数必须是有效的JSON数组")
    
    start_date = datetime.now() - timedelta(days=days)
    
    return await aggregator.get_conversion_funnel(
        funnel_name=funnel_name,
        steps=[tuple(s) for s in steps],
        start_date=start_date,
        end_date=datetime.now()
    )


@router.get("/trend", summary="时间序列趋势")
async def get_trend(
    metric: str = Query("page_views", description="指标: page_views / events"),
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("day", description="间隔: hour / day / week / month"),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取指定指标的时间趋势数据"""
    
    start_date = datetime.now() - timedelta(days=days)
    return await aggregator.get_time_series_trend(metric, start_date, datetime.now(), interval)


@router.get("/visitors", summary="访客统计")
async def get_visitor_stats(
    days: int = Query(7, ge=1, le=90),
    collector: EventCollector = Depends(get_collector),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取独立访客统计（PV/UV/跳出率等）"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return await collector.get_unique_visitors(start_date, end_date)


@router.get("/events/distribution", summary="事件类型分布")
async def get_event_distribution(
    days: int = Query(7, ge=1, le=90),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取各类型事件的分布情况"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return await aggregator._get_event_distribution(start_date, end_date)


# ==================== 报表接口 ====================

@router.get("/reports", summary="列出报表")
async def list_reports(
    report_type: str = Query(None, description="按类型过滤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    report_gen: ReportGenerator = Depends(get_report_gen),
    _: Dict[str, Any] = Depends(require_admin)
):
    """列出已生成的报表"""
    reports, total = await report_gen.list_reports(report_type, limit, offset)
    return {
        "total": total,
        "reports": reports,
        "limit": limit,
        "offset": offset,
    }


@router.post("/reports/generate", summary="生成新报表")
async def generate_new_report(
    name: str = Query(..., description="报表名称"),
    report_type: str = Query(..., description=f"报表类型"),
    is_scheduled: bool = Query(False, description="是否定时生成"),
    schedule_cron: str = Query(None, description="Cron表达式"),
    config_override: Optional[Dict[str, Any]] = Body(None),
    report_gen: ReportGenerator = Depends(get_report_gen),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """触发生成一个新的分析报表"""
    
    # 验证报表类型
    available_types = list(ReportGenerator.REPORT_TEMPLATES.keys())
    if report_type not in available_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的报表类型。可选: {available_types}"
        )
    
    report = await report_gen.create_and_save_report(
        name=name,
        report_type=report_type,
        config_override=config_override,
        is_scheduled=is_scheduled,
        schedule_cron=schedule_cron,
        created_by=current_user.get("user_id")
    )
    
    return report


@router.get("/reports/{report_id}", summary="获取报表详情")
async def get_report_detail(
    report_id: str,
    report_gen: ReportGenerator = Depends(get_report_gen),
    _: Dict[str, Any] = Depends(require_admin)
):
    """获取单个报表的详细数据"""
    
    report = await report_gen.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    
    return report


@router.delete("/reports/{report_id}", summary="删除报表")
async def delete_analytics_report(
    report_id: str,
    report_gen: ReportGenerator = Depends(get_report_gen),
    db: AsyncSession = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin)
):
    """删除报表记录"""
    
    from sqlalchemy import delete as sql_delete
    result = await db.execute(
        sql_delete(report_gen.__class__.__bases__[0].__subclasses__()[0] if False else None)  # placeholder
    ) if False else None
    
    report = await report_gen.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")
    
    await db.delete(report)
    await db.commit()
    
    return {"success": True}


@router.get("/reports/{report_id}/export", summary="导出报表")
async def export_report_endpoint(
    report_id: str,
    format: str = Query("json", description="导出格式: json 或 csv"),
    report_gen: ReportGenerator = Depends(get_report_gen),
    _: Dict[str, Any] = Depends(require_admin)
):
    """导出报表为指定格式"""
    
    if format.lower() not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="导出格式仅支持 json 和 csv")
    
    content = await report_gen.export_report(report_id, format.lower())
    
    media_type = "application/json" if format.lower() == "json" else "text/csv"
    filename = f"report_{report_id}.{format.lower()}"
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/templates", summary="获取可用报表模板")
async def get_report_templates():
    """列出所有可用的预定义报表模板"""
    return {
        "templates": [
            {"key": k, **v} for k, v in ReportGenerator.REPORT_TEMPLATES.items()
        ]
    }


# ==================== 用户活动聚合接口 ====================

@router.post("/aggregate/user/{user_id}", summary="聚合用户活动数据")
async def aggregate_single_user_activity(
    user_id: str,
    date: str = Query(None, description="聚合日期 YYYY-MM-DD，默认今天"),
    aggregator: DataAggregator = Depends(get_aggregator),
    _: Dict[str, Any] = Depends(require_admin)
):
    """手动触发单个用户的活动数据聚合"""
    
    target_date = (
        datetime.strptime(date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0
        ) if date else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    )
    
    activity = await aggregator.aggregate_user_activity(user_id, target_date)
    return activity
