"""
数据分析模块 - 数据聚合器

负责将原始事件数据聚合成有意义的统计指标，
支持用户活跃度分析、内容热度分析、漏斗分析等。
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case, desc, text
from sqlalchemy.sql import label

from .models import (
    PageView, EventTrack, UserActivity,
    AnalyticsSummary, EventType
)

logger = logging.getLogger(__name__)


class DataAggregator:
    """数据聚合器
    
    提供多种数据聚合能力：
    - 用户行为聚合（DAU/WAU/MAU、留存率、活跃度）
    - 内容数据聚合（热门内容、互动率）
    - 转化漏斗分析
    - 时间序列趋势分析
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ========== 核心指标 ==========

    async def get_overview_metrics(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取概览指标
        
        返回指定时间范围内的核心业务指标。
        """
        if end_date is None:
            end_date = datetime.now()
        
        # 并行查询各指标
        metrics = {}
        
        # 1. 页面浏览总量
        pv = await self._count_page_views(start_date, end_date)
        metrics["page_views"] = pv
        
        # 2. 独立访客数(UV)
        uv = await self._count_unique_visitors(start_date, end_date)
        metrics["unique_visitors"] = uv
        
        # 3. 独立用户数(注册用户)
        users = await self._count_unique_users(start_date, end_date)
        metrics["active_users"] = users
        
        # 4. 总事件数
        events = await self._count_events(start_date, end_date)
        metrics["total_events"] = events
        
        # 5. 各类型事件分布
        event_distribution = await self._get_event_distribution(start_date, end_date)
        metrics["event_distribution"] = event_distribution
        
        # 6. 热门页面TOP10
        top_pages = await self._get_top_pages(start_date, end_date, limit=10)
        metrics["top_pages"] = top_pages
        
        # 7. 设备分布
        device_dist = await self._get_device_distribution(start_date, end_date)
        metrics["device_distribution"] = device_dist
        
        # 8. 日均PV/UV对比昨日
        days_diff = (end_date - start_date).days or 1
        metrics["avg_daily_pv"] = round(pv / days_diff, 2)
        metrics["avg_daily_uv"] = round(uv / days_diff, 2)
        
        # 同比增长
        prev_start = start_date - (end_date - start_date)
        prev_end = start_date
        prev_pv = await self._count_page_views(prev_start, prev_end)
        prev_uv = await self._count_unique_visitors(prev_start, prev_end)
        
        if prev_pv > 0:
            metrics["pv_growth_rate"] = round((pv - prev_pv) / prev_pv * 100, 2)
        else:
            metrics["pv_growth_rate"] = None
            
        if prev_uv > 0:
            metrics["uv_growth_rate"] = round((uv - prev_uv) / prev_uv * 100, 2)
        else:
            metrics["uv_growth_rate"] = None
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "metrics": metrics
        }

    async def get_dau_wau_mau(
        self,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取DAU/WAU/MAU指标（日活/周活/月活）
        
        基于注册用户的活跃度统计。
        """
        today = (date or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        
        dau = await self._count_active_users(today, today + timedelta(days=1))
        wau = await self._count_active_users(today - timedelta(days=6), today + timedelta(days=1))
        mau = await self._count_active_users(today - timedelta(days=29), today + timedelta(days=1))
        
        # 粘性指数 (DAU/MAU，越高表示用户粘性越强)
        stickiness = round(dau / mau * 100, 2) if mau > 0 else 0
        
        # 每日DAU趋势(最近30天)
        daily_trend = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_dau = await self._count_active_users(day, day + timedelta(days=1))
            daily_trend.append({
                "date": day.strftime("%Y-%m-%d"),
                "dau": day_dau
            })
        
        return {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "stickiness_percent": stickiness,
            "daily_trend_30d": daily_trend,
            "calculated_at": datetime.now().isoformat()
        }

    async def calculate_retention(
        self,
        cohort_date: datetime,
        periods: int = 7
    ) -> List[Dict[str, Any]]:
        """计算用户留存率
        
        Args:
            cohort_date: 用户首次访问日期（队列日期）
            periods: 计算留存的天数
            
        Returns:
            每日留存率列表，如 [Day1: 60%, Day2: 45%, ...]
        """
        # 获取该日期的新用户（首次访问）
        new_users_result = await self.db.execute(
            select(func.distinct(PageView.user_id))
            .where(
                and_(
                    PageView.user_id.isnot(None),
                    func.date(PageView.created_at) == cohort_date.date()
                )
            )
        )
        new_user_ids = [row[0] for row in new_users_result.fetchall()]
        
        if not new_user_ids:
            return [{"cohort_date": cohort_date.strftime("%Y-%m-%d"), "cohort_size": 0}]
        
        cohort_size = len(new_user_ids)
        retention_data = [
            {"cohort_date": cohort_date.strftime("%Y-%m-%d"), 
             "cohort_size": cohort_size}
        ]
        
        # 计算每日留存
        for day in range(1, periods + 1):
            target_date = cohort_date + timedelta(days=day)
            
            retained_result = await self.db.execute(
                select(func.count(func.distinct(PageView.user_id)))
                .where(
                    and_(
                        PageView.user_id.in_(new_user_ids),
                        func.date(PageView.created_at) == target_date.date()
                    )
                )
            )
            retained_count = retained_result.scalar() or 0
            retention_rate = round(retained_count / cohort_size * 100, 2) if cohort_size > 0 else 0
            
            retention_data.append({
                f"day_{day}_retained": retained_count,
                f"day_{day}_rate": f"{retention_rate}%"
            })
        
        return retention_data

    async def get_content_popularity(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取内容热度排行
        
        基于事件追踪数据统计内容的浏览量、点赞数、分享数等。
        """
        if end_date is None:
            end_date = datetime.now()
        
        result = await self.db.execute(
            select(
                EventTrack.target_type,
                EventTrack.target_id,
                func.count(EventTrack.id).label('total_events'),
                func.sum(case((EventTrack.event_type == 'like', 1), else_=0)).label('likes'),
                func.sum(case((EventTrack.event_type == 'favorite', 1), else_=0)).label('favorites'),
                func.sum(case((EventTrack.event_type == 'share', 1), else_=0)).label('shares'),
                func.sum(case((EventTrack.event_type == 'comment', 1), else_=0)).label('comments'),
            )
            .where(
                and_(
                    EventTrack.target_id.isnot(None),
                    EventTrack.target_type == 'content',
                    EventTrack.created_at >= start_date,
                    EventTrack.created_at <= end_date
                )
            )
            .group_by(EventTrack.target_type, EventTrack.target_id)
            .order_by(desc('total_events'))
            .limit(limit)
        )
        
        rows = result.all()
        
        popularity = []
        rank = 1
        for row in rows:
            total_interactions = int(row.likes or 0) + int(row.favorites or 0) + \
                                int(row.shares or 0) + int(row.comments or 0)
            
            popularity.append({
                "rank": rank,
                "target_id": row.target_id,
                "total_events": int(row.total_events),
                "likes": int(row.likes or 0),
                "favorites": int(row.favorites or 0),
                "shares": int(row.shares or 0),
                "comments": int(row.comments or 0),
                "engagement_score": total_interactions * 10 + int(row.total_events)
            })
            rank += 1
        
        return popularity

    async def get_conversion_funnel(
        self,
        funnel_name: str,
        steps: List[Tuple[str, str]],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """转化漏斗分析
        
        Args:
            funnel_name: 漏斗名称
            steps: 漏斗步骤列表 [(event_type, event_name), ...]
            start_date: 开始时间
            end_date: 结束时间
            
        Returns:
            包含每步人数和转化率的漏斗数据
        """
        funnel_data = {
            "name": funnel_name,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "steps": []
        }
        
        prev_count = None
        
        for event_type, event_name in steps:
            result = await self.db.execute(
                select(func.count(func.distinct(EventTrack.session_id)))
                .where(
                    and_(
                        EventTrack.event_type == event_type,
                        EventTrack.event_name == event_name,
                        EventTrack.created_at >= start_date,
                        EventTrack.created_at <= end_date
                    )
                )
            )
            count = result.scalar() or 0
            
            step_data = {
                "step_name": event_name,
                "event_type": event_type,
                "count": count,
            }
            
            if prev_count is not None and prev_count > 0:
                step_data["conversion_rate"] = round(count / prev_count * 100, 2)
                step_data["drop_off"] = round((prev_count - count) / prev_count * 100, 2)
            else:
                step_data["conversion_rate"] = 100.0
                step_data["drop_off"] = 0.0
            
            funnel_data["steps"].append(step_data)
            prev_count = count
        
        # 整体转化率
        if len(funnel_data["steps"]) >= 2:
            first_step = funnel_data["steps"][0]["count"]
            last_step = funnel_data["steps"][-1]["count"]
            if first_step > 0:
                funnel_data["overall_conversion"] = round(last_step / first_step * 100, 2)
            else:
                funnel_data["overall_conversion"] = 0.0
        
        return funnel_data

    async def get_time_series_trend(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "day"  # hour, day, week, month
    ) -> List[Dict[str, Any]]:
        """时间序列趋势分析
        
        返回指定指标在时间范围内的变化趋势。
        """
        # 根据interval选择SQL trunc函数
        interval_map = {
            'hour': 'hour',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }
        trunc_unit = interval_map.get(interval, 'day')
        
        if metric == "page_views":
            base_query = select(
                label('period', func.date_trunc(trunc_unit, PageView.created_at)),
                label('value', func.count(PageView.id))
            ).where(
                and_(
                    PageView.created_at >= start_date,
                    PageView.created_at <= end_date
                )
            ).group_by(text('period')).order_by(text('period'))
            
        elif metric == "events":
            base_query = select(
                label('period', func.date_trunc(trunc_unit, EventTrack.created_at)),
                label('value', func.count(EventTrack.id))
            ).where(
                and_(
                    EventTrack.created_at >= start_date,
                    EventTrack.created_at <= end_date
                )
            ).group_by(text('period')).order_by(text('period'))
        else:
            return []
        
        result = await self.db.execute(base_query)
        rows = result.all()
        
        return [
            {
                "period": str(row.period),
                "value": row.value
            }
            for row in rows
        ]

    async def aggregate_user_activity(self, user_id: str, date: datetime) -> UserActivity:
        """聚合单个用户的日活动数据
        
        将当天的原始事件汇总到UserActivity表。
        """
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # 页面浏览
        pv_result = await self.db.execute(
            select(func.count(PageView.id), 
                   func.count(func.distinct(PageView.page_path)),
                   func.coalesce(func.sum(PageView.duration_seconds), 0))
            .where(and_(PageView.user_id == user_id,
                       PageView.created_at >= day_start,
                       PageView.created_at < day_end))
        )
        pv_row = pv_result.first()
        
        # 事件统计
        likes = await self._count_user_event(user_id, "like", day_start, day_end)
        comments = await self._count_user_event(user_id, "comment", day_start, day_end)
        shares = await self._count_user_event(user_id, "share", day_start, day_end)
        favorites = await self._count_user_event(user_id, "favorite", day_start, day_end)
        follows = await self._count_user_event(user_id, "follow", day_start, day_end)
        searches = await self._count_user_event(user_id, "search", day_start, day_end)
        downloads = await self._count_user_event(user_id, "download", day_start, day_end)
        
        # 创建或更新UserActivity
        result = await self.db.execute(
            select(UserActivity).where(
                and_(UserActivity.user_id == user_id,
                     UserActivity.date == day_start)
            )
        )
        activity = result.scalar_one_or_none()
        
        if not activity:
            activity = UserActivity(
                user_id=user_id,
                date=day_start,
                page_views=pv_row[0] or 0,
                unique_pages_visited=pv_row[1] or 0,
                likes_given=likes,
                comments_made=comments,
                shares_count=shares,
                favorites_added=favorites,
                follows_count=follows,
                downloads_count=downloads,
                searches_performed=searches,
                total_session_duration=int(pv_row[2] or 0),
            )
            self.db.add(activity)
        else:
            activity.page_views = pv_row[0] or 0
            activity.unique_pages_visited = pv_row[1] or 0
            activity.likes_given = likes
            activity.comments_made = comments
            activity.shares_count = shares
            activity.favorites_added = favorites
            activity.follows_count = follows
            activity.downloads_count = downloads
            activity.searches_performed = searches
            activity.total_session_duration = int(pv_row[2] or 0)
        
        await self.db.commit()
        return activity

    # ========== 内部辅助方法 ==========

    async def _count_page_views(self, start: datetime, end: datetime) -> int:
        result = await self.db.execute(
            select(func.count(PageView.id)).where(
                and_(PageView.created_at >= start, PageView.created_at <= end)
            )
        )
        return result.scalar() or 0

    async def _count_unique_visitors(self, start: datetime, end: datetime) -> int:
        result = await self.db.execute(
            select(func.count(func.distinct(PageView.session_id))).where(
                and_(PageView.created_at >= start, PageView.created_at <= end)
            )
        )
        return result.scalar() or 0

    async def _count_unique_users(self, start: datetime, end: datetime) -> int:
        result = await self.db.execute(
            select(func.count(func.distinct(PageView.user_id))).where(
                and_(PageView.created_at >= start,
                     PageView.created_at <= end,
                     PageView.user_id.isnot(None))
            )
        )
        return result.scalar() or 0

    async def _count_events(self, start: datetime, end: datetime) -> int:
        result = await self.db.execute(
            select(func.count(EventTrack.id)).where(
                and_(EventTrack.created_at >= start, EventTrack.created_at <= end)
            )
        )
        return result.scalar() or 0

    async def _get_event_distribution(self, start: datetime, end: datetime) -> Dict[str, int]:
        result = await self.db.execute(
            select(EventTrack.event_type, func.count(EventTrack.id))
            .where(and_(EventTrack.created_at >= start, EventTrack.created_at <= end))
            .group_by(EventTrack.event_type)
            .order_by(desc(func.count(EventTrack.id)))
        )
        return {row[0]: row[1] for row in result}

    async def _get_top_pages(self, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
        result = await self.db.execute(
            select(PageView.page_path, func.count(PageView.id).label('cnt'),
                   func.count(func.distinct(PageView.session_id)).label('unique_sessions'))
            .where(and_(PageView.created_at >= start, PageView.created_at <= end))
            .group_by(PageView.page_path)
            .order_by(desc('cnt'))
            .limit(limit)
        )
        return [
            {"path": row.page_path, "views": int(row.cnt), "unique_visits": int(row.unique_sessions)}
            for row in result
        ]

    async def _get_device_distribution(self, start: datetime, end: datetime) -> Dict[str, int]:
        result = await self.db.execute(
            select(PageView.device_type, func.count(PageView.id))
            .where(and_(PageView.created_at >= start, PageView.created_at <= end))
            .group_by(PageView.device_type)
        )
        return {row[0]: row[1] for row in result}

    async def _count_active_users(self, start: datetime, end: datetime) -> int:
        result = await self.db.execute(
            select(func.count(func.distinct(PageView.user_id)))
            .where(
                and_(
                    PageView.user_id.isnot(None),
                    PageView.created_at >= start,
                    PageView.created_at <= end
                )
            )
        )
        return result.scalar() or 0

    async def _count_user_event(
        self, user_id: str, event_type: str, start: datetime, end: datetime
    ) -> int:
        result = await self.db.execute(
            select(func.count(EventTrack.id))
            .where(and_(
                EventTrack.user_id == user_id,
                EventTrack.event_type == event_type,
                EventTrack.created_at >= start,
                EventTrack.created_at < end
            ))
        )
        return result.scalar() or 0
