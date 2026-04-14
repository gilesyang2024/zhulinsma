"""
数据分析模块 - 事件收集器

负责接收、验证、存储前端发送的分析事件数据。
支持同步和批量写入模式。
"""
import json
import time
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from .models import PageView, EventTrack, EventType, DeviceType
from src.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()


@dataclass
class PageViewData:
    """页面浏览数据结构"""
    page_path: str
    page_title: Optional[str] = None
    referrer: Optional[str] = None
    device_type: str = "unknown"
    device_info: Dict[str, Any] = field(default_factory=dict)
    browser: Optional[str] = None
    os: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None


@dataclass
class EventData:
    """事件追踪数据结构"""
    event_type: str
    event_name: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    value: Optional[float] = None
    page_url: Optional[str] = None
    user_agent: Optional[str] = None


class EventCollector:
    """事件收集器
    
    负责收集和处理用户行为数据，包括：
    - 页面浏览记录（PV统计）
    - 用户交互事件（点击、点赞等）
    - 批量事件处理
    - 会话管理
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._batch_buffer: List[Any] = []
        self.batch_size = getattr(settings, 'ANALYTICS_BATCH_SIZE', 100)

    def generate_session_id(
        self,
        user_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> str:
        """生成会话ID
        
        基于用户信息生成唯一会话标识。
        """
        raw = f"{user_id or 'anonymous'}:{ip_address or ''}:{user_agent or ''}:{datetime.now().strftime('%Y%m%d')}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def track_page_view(
        self,
        user_id: Optional[str],
        session_id: str,
        page_data: PageViewData
    ) -> PageView:
        """记录页面浏览
        
        Args:
            user_id: 用户ID(可为空表示匿名)
            session_id: 会话ID
            page_data: 页面浏览数据
            
        Returns:
            创建的PageView记录
        """
        # 验证设备类型
        try:
            DeviceType(page_data.device_type)
        except ValueError:
            page_data.device_type = "unknown"

        page_view = PageView(
            user_id=user_id,
            session_id=session_id,
            page_path=page_data.page_path,
            page_title=page_data.page_title,
            referrer=page_data.referrer,
            device_type=page_data.device_type,
            device_info=page_data.device_info,
            browser=page_data.browser,
            os=page_data.os,
            ip_address=page_data.ip_address,
            country=page_data.country,
            city=page_data.city,
        )
        
        self.db.add(page_view)
        
        # 如果开启了自动提交，立即写入
        if not getattr(settings, 'ANALYTICS_BATCH_MODE', False):
            await self.db.commit()
            await self.db.refresh(page_view)
        
        logger.debug(f"记录页面浏览: {page_data.page_path} (session={session_id[:8]}...)")
        return page_view

    async def track_event(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        event_data: EventData,
        ip_address: Optional[str] = None
    ) -> EventTrack:
        """记录自定义事件
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            event_data: 事件数据
            ip_address: 客户端IP
            
        Returns:
            创建的EventTrack记录
        """
        # 验证事件类型
        try:
            EventType(event_data.event_type)
        except ValueError:
            pass  # 允许自定义事件类型

        event = EventTrack(
            event_type=event_data.event_type,
            event_name=event_data.event_name,
            user_id=user_id,
            session_id=session_id,
            target_type=event_data.target_type,
            target_id=event_data.target_id,
            properties=event_data.properties,
            value=event_data.value,
            page_url=event_data.page_url,
            ip_address=ip_address,
            user_agent=event_data.user_agent,
        )
        
        self.db.add(event)
        
        if not getattr(settings, 'ANALYTICS_BATCH_MODE', False):
            await self.db.commit()
            await self.db.refresh(event)
        
        logger.debug(f"记录事件: {event_data.event_type}/{event_data.event_name}")
        return event

    async def batch_track_events(
        self,
        events: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """批量记录事件
        
        用于高并发场景下的批量事件写入，提升吞吐量。
        
        Args:
            events: 事件字典列表
            user_id: 默认用户ID
            session_id: 默认会话ID
            
        Returns:
            成功记录的事件数量
        """
        count = 0
        
        for event_dict in events:
            event_type = event_dict.get("event_type", "custom")
            
            if event_type == "page_view":
                page_view = PageView(
                    user_id=user_id or event_dict.get("user_id"),
                    session_id=session_id or event_dict.get("session_id", ""),
                    page_path=event_dict.get("page_path", "/"),
                    page_title=event_dict.get("page_title"),
                    referrer=event_dict.get("referrer"),
                    device_type=event_dict.get("device_type", "unknown"),
                    browser=event_dict.get("browser"),
                    os=event_dict.get("os"),
                    ip_address=event_dict.get("ip_address"),
                )
                self.db.add(page_view)
                
            else:
                event = EventTrack(
                    event_type=event_type,
                    event_name=event_dict.get("event_name", "unnamed"),
                    user_id=user_id or event_dict.get("user_id"),
                    session_id=session_id or event_dict.get("session_id"),
                    target_type=event_dict.get("target_type"),
                    target_id=event_dict.get("target_id"),
                    properties=event_dict.get("properties", {}),
                    value=event_dict.get("value"),
                    page_url=event_dict.get("page_url"),
                    ip_address=event_dict.get("ip_address"),
                    user_agent=event_dict.get("user_agent"),
                )
                self.db.add(event)
            
            count += 1
        
        await self.db.commit()
        logger.info(f"批量记录了 {count} 个事件")
        return count

    async def update_page_view_duration(
        self,
        view_id: int,
        duration_seconds: int
    ) -> bool:
        """更新页面停留时长
        
        当用户离开页面时调用，记录实际停留时间用于跳出率计算。
        """
        result = await self.db.execute(
            select(PageView).where(PageView.id == view_id)
        )
        view = result.scalar_one_or_none()
        
        if not view:
            return False
        
        view.duration_seconds = duration_seconds
        view.is_bounce = duration_seconds < getattr(settings, 'BOUNCE_THRESHOLD_SECONDS', 5)
        
        await self.db.commit()
        logger.debug(f"更新页面停留时长: view_id={view_id}, duration={duration_seconds}s")
        return True

    # ========== 查询方法 ==========

    async def get_page_views(
        self,
        start_time: datetime,
        end_time: datetime,
        page_path: Optional[str] = None,
        user_id: Optional[str] = None,
        group_by: Optional[str] = None  # hour, day
    ) -> List[Dict[str, Any]]:
        """查询页面浏览统计数据
        
        支持按时间范围、页面路径、用户过滤，
        可选按小时或天聚合结果。
        """
        query = select(PageView).where(
            and_(
                PageView.created_at >= start_time,
                PageView.created_at <= end_time
            )
        )
        
        if page_path:
            query = query.where(PageView.page_path == page_path)
        if user_id:
            query = query.where(PageView.user_id == user_id)

        result = await self.db.execute(query.order_by(PageView.created_at.desc()))
        views = result.scalars().all()

        # 简单聚合逻辑
        if group_by == "day":
            from collections import defaultdict
            daily = defaultdict(lambda: {"views": 0, "unique_sessions": set(), "users": set()})
            for v in views:
                day_key = v.created_at.strftime("%Y-%m-%d")
                daily[day_key]["views"] += 1
                daily[day_key]["unique_sessions"].add(v.session_id)
                if v.user_id:
                    daily[day_key]["users"].add(v.user_id)
            
            return [
                {
                    "date": day,
                    "pv": data["views"],
                    "uv": len(data["unique_sessions"]),
                    "unique_users": len(data["users"])
                }
                for day, data in sorted(daily.items())
            ]
        
        return [self._page_view_to_dict(v) for v in views]

    async def get_events(
        self,
        start_time: datetime,
        end_time: datetime,
        event_type: Optional[str] = None,
        event_name: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询事件列表
        
        支持按类型、名称、用户和时间范围过滤。
        """
        conditions = [
            EventTrack.created_at >= start_time,
            EventTrack.created_at <= end_time
        ]
        
        if event_type:
            conditions.append(EventTrack.event_type == event_type)
        if event_name:
            conditions.append(EventTrack.event_name == event_name)
        if user_id:
            conditions.append(EventTrack.user_id == user_id)

        result = await self.db.execute(
            select(EventTrack)
            .where(and_(*conditions))
            .order_by(EventTrack.created_at.desc())
            .limit(limit)
        )
        events = result.scalars().all()
        
        return [self._event_to_dict(e) for e in events]

    async def count_events_by_type(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, int]:
        """按事件类型聚合计数
        
        返回各类型事件在指定时间范围内的数量分布。
        """
        result = await self.db.execute(
            select(
                EventTrack.event_type,
                func.count(EventTrack.id).label('count')
            )
            .where(
                and_(
                    EventTrack.created_at >= start_time,
                    EventTrack.created_at <= end_time
                )
            )
            .group_by(EventTrack.event_type)
            .order_by(func.count(EventTrack.id).desc())
        )
        
        return {row.event_type: row.count for row in result}

    async def get_unique_visitors(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """获取独立访客统计
        
        返回UV、PV等核心指标。
        """
        # PV
        pv_result = await self.db.execute(
            select(func.count(PageView.id)).where(
                and_(
                    PageView.created_at >= start_time,
                    PageView.created_at <= end_time
                )
            )
        )
        pv = pv_result.scalar() or 0

        # UV (按session去重)
        uv_result = await self.db.execute(
            select(func.count(func.distinct(PageView.session_id))).where(
                and_(
                    PageView.created_at >= start_time,
                    PageView.created_at <= end_time
                )
            )
        )
        uv = uv_result.scalar() or 0

        # 独立用户数
        users_result = await self.db.execute(
            select(func.count(func.distinct(PageView.user_id))).where(
                and_(
                    PageView.created_at >= start_time,
                    PageView.created_at <= end_time,
                    PageView.user_id.isnot(None)
                )
            )
        )
        unique_users = users_result.scalar() or 0

        # 跳出率
        bounce_result = await self.db.execute(
            select(func.count(PageView.id)).where(
                and_(
                    PageView.created_at >= start_time,
                    PageView.created_at <= end_time,
                    PageView.is_bounce == True
                )
            )
        )
        bounces = bounce_result.scalar() or 0
        bounce_rate = round(bounces / pv * 100, 2) if pv > 0 else 0

        return {
            "pv": pv,
            "uv": uv,
            "unique_users": unique_users,
            "bounces": bounces,
            "bounce_rate": bounce_rate,
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }

    @staticmethod
    def _page_view_to_dict(view: PageView) -> Dict[str, Any]:
        return {
            "id": view.id,
            "user_id": view.user_id,
            "session_id": view.session_id[:16],
            "page_path": view.page_path,
            "page_title": view.page_title,
            "device_type": view.device_type,
            "created_at": view.created_at.isoformat() if view.created_at else None,
            "duration_seconds": view.duration_seconds,
            "is_bounce": view.is_bounce,
        }

    @staticmethod
    def _event_to_dict(event: EventTrack) -> Dict[str, Any]:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "event_name": event.event_name,
            "user_id": event.user_id,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "properties": event.properties,
            "value": event.value,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
