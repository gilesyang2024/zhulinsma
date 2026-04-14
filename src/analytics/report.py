"""
数据分析模块 - 报表生成器

支持自定义报表配置、定时生成、多格式导出（JSON/CSV）。
"""

import json
import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import AnalyticsReport, AnalyticsSummary
from .aggregator import DataAggregator
from .collector import EventCollector

logger = logging.getLogger(__name__)


class ReportGenerator:
    """报表生成器
    
    功能：
    - 预定义报表模板
    - 自定义报表创建和执行
    - 定时报表调度
    - 多格式导出
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = DataAggregator(db)
        self.collector = EventCollector(db)
    
    # ========== 预定义报表模板 ==========

    REPORT_TEMPLATES = {
        "daily_overview": {
            "name": "每日概览报表",
            "type": "daily",
            "description": "每日核心指标汇总，包含PV/UV/DAU/事件分布等",
            "config": {
                "metrics": ["page_views", "unique_visitors", "active_users", 
                           "event_distribution", "top_pages", "device_distribution"],
                "period_days": 1,
                "compare_with_previous": True,
            },
            "chart_types": ["line", "pie", "bar"]
        },
        
        "weekly_performance": {
            "name": "周度运营报表",
            "type": "weekly",
            "description": "每周运营数据对比分析，包含趋势变化和周环比",
            "config": {
                "metrics": ["dau_wau_mau", "content_popularity", "retention"],
                "period_days": 7,
                "compare_with_previous": True,
            },
            "chart_types": ["line", "table", "heatmap"]
        },
        
        "user_retention": {
            "name": "用户留存报表",
            "type": "retention",
            "description": "用户留存率分析，按队列日期分组展示",
            "config": {
                "cohort_periods": 7,
                "days_to_analyze": 30,
            },
            "chart_types": ["heatmap", "line"]
        },
        
        "content_heatmap": {
            "name": "内容热度报表",
            "type": "content",
            "description": "内容互动热度排行和趋势分析",
            "config": {
                "limit_top": 50,
                "period_days": 7,
                "metrics": ["views", "likes", "shares", "comments"],
            },
            "chart_types": ["bar", "rank_table", "scatter"]
        },
        
        "conversion_funnel": {
            "name": "转化漏斗分析",
            "type": "funnel",
            "description": "用户转化路径分析和漏斗可视化",
            "config": {
                "funnels": [
                    {"name": "注册漏斗", "steps": [("page_view", "landing"), ("click", "signup_btn"), ("submit", "register"), ("custom", "email_verify")]},
                    {"name": "内容消费漏斗", "steps": [("page_view", "article"), ("click", "read_more"), ("like", "article_like"), ("share", "article_share")]},
                    {"name": "购买漏斗", "steps": [("click", "product_view"), ("click", "add_cart"), ("click", "checkout"), ("purchase", "complete")]},
                ],
                "period_days": 7,
            },
            "chart_types": ["funnel", "sankey"]
        }
    }

    async def generate_report(
        self,
        report_type: str,
        config_override: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成报表
        
        根据报表类型调用相应的聚合方法获取数据。
        
        Args:
            report_type: 报表类型 (daily_overview / weekly_performance 等)
            config_override: 覆盖模板配置
            start_date: 自定义开始时间
            end_date: 自定义结束时间
            
        Returns:
            包含完整报表数据的字典
        """
        template = self.REPORT_TEMPLATES.get(report_type)
        if not template:
            raise ValueError(f"未知的报表类型: {report_type}. 可选: {list(self.REPORT_TEMPLATES.keys())}")
        
        # 合并配置
        config = {**template["config"], **(config_override or {})}
        
        now = datetime.now()
        period_days = config.get("period_days", 1)
        report_end = end_date or now
        report_start = start_date or (report_end - timedelta(days=period_days))
        
        report_data = {
            "meta": {
                "report_name": template["name"],
                "report_type": report_type,
                "generated_at": now.isoformat(),
                "period_start": report_start.isoformat(),
                "period_end": report_end.isoformat(),
            },
            "data": {}
        }
        
        metrics = config.get("metrics", [])
        
        for metric in metrics:
            try:
                if metric == "overview":
                    report_data["data"]["overview"] = await self.aggregator.get_overview_metrics(
                        report_start, report_end
                    )
                
                elif metric == "page_views":
                    report_data["data"]["page_views"] = await self.collector.get_page_views(
                        report_start, report_end, group_by="day"
                    )
                
                elif metric == "unique_visitors":
                    report_data["data"]["visitors"] = await self.collector.get_unique_visitors(
                        report_start, report_end
                    )
                
                elif metric == "active_users":
                    pass  # 已包含在overview中
                
                elif metric == "event_distribution":
                    report_data["data"]["events"] = await self.aggregator._get_event_distribution(
                        report_start, report_end
                    )
                
                elif metric == "top_pages":
                    report_data["data"]["top_pages"] = await self.aggregator._get_top_pages(
                        report_start, report_end
                    )
                
                elif metric == "device_distribution":
                    report_data["data"]["devices"] = await self.aggregator._get_device_distribution(
                        report_start, report_end
                    )
                
                elif metric == "dau_wau_mau":
                    report_data["data"]["engagement"] = await self.aggregator.get_dau_wau_mau(now)
                
                elif metric == "retention":
                    cohorts = []
                    for days_ago in range(config.get("days_to_analyze", 7)):
                        cohort_date = report_start + timedelta(days=days_ago)
                        retention = await self.aggregator.calculate_retention(cohort_date)
                        cohorts.append(retention)
                    report_data["data"]["retention_cohorts"] = cohorts
                
                elif metric == "content_popularity":
                    report_data["data"]["popular_content"] = await self.aggregator.get_content_popularity(
                        report_start, report_end,
                        limit=config.get("limit_top", 20)
                    )
            
            except Exception as e:
                logger.error(f"生成指标 '{metric}' 失败: {str(e)}")
                report_data["data"][metric] = {"error": str(e)}
        
        return report_data

    async def create_and_save_report(
        self,
        name: str,
        report_type: str,
        config_override: Optional[Dict[str, Any]] = None,
        is_scheduled: bool = False,
        schedule_cron: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> AnalyticsReport:
        """创建报表记录并执行生成
        
        同时保存报表元数据和生成的数据。
        """
        # 创建报表记录
        report = AnalyticsReport(
            name=name,
            report_type=report_type,
            description=self.REPORT_TEMPLATES.get(report_type, {}).get("description"),
            config={**self.REPORT_TEMPLATES.get(report_type, {}).get("config", {}), **(config_override or {})},
            status="running",
            is_scheduled=is_scheduled,
            schedule_cron=schedule_cron,
            created_by=created_by,
        )
        
        self.db.add(report)
        await self.db.flush()
        
        # 生成数据
        try:
            data = await self.generate_report(
                report_type=report_type,
                config_override=config_override,
                created_by=created_by
            )
            
            report.data = data
            report.status = "completed"
            report.last_run_at = datetime.now()
            
        except Exception as e:
            report.status = "failed"
            report.error_message = str(e)
            logger.error(f"报表生成失败 [{report.id}]: {str(e)}")
        
        await self.db.commit()
        await self.db.refresh(report)
        
        return report

    async def get_report(self, report_id: str) -> Optional[AnalyticsReport]:
        """获取单个报表详情"""
        result = await self.db.execute(
            select(AnalyticsReport).where(AnalyticsReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        report_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[List[AnalyticsReport], int]:
        """列出报表"""
        query = select(AnalyticsReport)
        count_query = select(func.count(AnalyticsReport.id))
        
        if report_type:
            query = query.where(AnalyticsReport.report_type == report_type)
            count_query = count_query.where(AnalyticsReport.report_type == report_type)
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        result = await self.db.execute(
            query.order_by(AnalyticsReport.created_at.desc())
            .offset(offset).limit(limit)
        )
        reports = result.scalars().all()
        
        return reports, total

    async def delete_report(self, report_id: str) -> bool:
        """删除报表记录"""
        from sqlalchemy import delete as sql_delete
        result = await self.db.execute(
            sql_delete(AnalyticsReport).where(AnalyticsReport.id == report_id)
        )
        await db.commit() if hasattr(db, 'commit') else None
        return result.rowcount > 0

    # ========== 导出功能 ==========

    @staticmethod
    def export_to_json(data: Dict[str, Any], indent: int = 2) -> str:
        """导出为JSON格式"""
        return json.dumps(data, ensure_ascii=False, indent=indent, default=str)

    @staticmethod
    def export_to_csv(
        data: List[Dict[str, Any]],
        fieldnames: Optional[List[str]] = None
    ) -> str:
        """导出为CSV格式
        
        将列表型数据转换为CSV字符串。
        """
        output = io.StringIO()
        
        if not data:
            return ""
        
        if fieldnames is None:
            fieldnames = list(data[0].keys())
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()

    async def export_report(
        self,
        report_id: str,
        format: str = "json"
    ) -> str:
        """导出已生成的报表
        
        Args:
            report_id: 报表ID
            format: 导出格式 (json / csv)
            
        Returns:
            格式化的字符串
        """
        report = await self.get_report(report_id)
        
        if not report or not report.data:
            raise ValueError(f"报表不存在或尚未生成: {report_id}")
        
        if format.lower() == "json":
            return self.export_to_json(report.data)
        
        elif format.lower() == "csv":
            # 尝试将嵌套数据展平为列表
            flat_data = self._flatten_report_data(report.data)
            return self.export_to_csv(flat_data)
        
        else:
            raise ValueError(f"不支持的导出格式: {format}")

    @staticmethod
    def _flatten_report_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将报表数据展平为适合CSV的列表结构"""
        rows = []
        
        # 尝试从常见字段提取行数据
        for key, value in data.get("data", {}).items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        row = {"section": key}
                        row.update(item)
                        rows.append(row)
            elif isinstance(value, dict):
                row = {"section": key}
                row.update(value)
                rows.append(row)
        
        if not rows:
            rows.append({"raw_data": json.dumps(data, ensure_ascii=False)})
        
        return rows

    # ========== 定时报表管理 ==========

    async def get_due_scheduled_reports(self) -> List[AnalyticsReport]:
        """获取到期的定时报表"""
        from sqlalchemy import or_
        result = await self.db.execute(
            select(AnalyticsReport)
            .where(
                and_(
                    AnalyticsReport.is_scheduled == True,
                    AnalyticsReport.next_run_at <= datetime.now()
                )
            )
        )
        return result.scalars().all()

    async def update_next_run_time(self, report: AnalyticsReport):
        """更新下次运行时间（简单实现：基于周期推断）"""
        # 简单的调度逻辑：根据报表类型推算间隔
        type_intervals = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        
        interval = type_intervals.get(
            report.report_type,
            timedelta(days=1)
        )
        
        report.last_run_at = datetime.now()
        report.next_run_at = datetime.now() + interval
        
        await self.db.commit()
