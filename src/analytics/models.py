"""
数据分析模块 - 数据模型

定义页面浏览、事件追踪、用户活动等分析相关的数据结构。
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Float, Boolean,
    DateTime, JSON, Index, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class EventType(str, Enum):
    """事件类型枚举"""
    PAGE_VIEW = "page_view"          # 页面浏览
    CLICK = "click"                   # 点击事件
    SUBMIT = "submit"                 # 提交事件
    DOWNLOAD = "download"            # 下载事件
    SHARE = "share"                  # 分享事件
    LIKE = "like"                    # 点赞事件
    FAVORITE = "favorite"            # 收藏事件
    COMMENT = "comment"              # 评论事件
    FOLLOW = "follow"                # 关注事件
    LOGIN = "login"                  # 登录事件
    LOGOUT = "logout"                # 登出事件
    SEARCH = "search"                # 搜索事件
    SIGNUP = "signup"                # 注册事件
    PURCHASE = "purchase"            # 购买事件
    CUSTOM = "custom"                # 自定义事件


class DeviceType(str, Enum):
    """设备类型枚举"""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    UNKNOWN = "unknown"


class PageView(Base):
    """页面浏览记录模型
    
    记录每次页面访问的详细信息，用于PV/UV统计和用户行为分析。
    """
    __tablename__ = "analytics_page_views"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 用户信息（允许匿名访问）
    user_id = Column(String(36), nullable=True, index=True, comment="用户ID")
    session_id = Column(String(128), nullable=False, index=True, comment="会话ID")
    
    # 页面信息
    page_path = Column(Text, nullable=False, comment="页面路径")
    page_title = Column(String(500), nullable=True, comment="页面标题")
    referrer = Column(Text, nullable=True, comment="来源URL")
    
    # 设备信息
    device_type = Column(String(20), default="unknown", comment="设备类型")
    device_info = Column(JSON, nullable=True, comment="详细设备信息")
    browser = Column(String(100), nullable=True, comment="浏览器")
    os = Column(String(100), nullable=True, comment="操作系统")
    
    # 位置信息
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    country = Column(String(100), nullable=True, comment="国家")
    city = Column(String(100), nullable=True, comment="城市")
    
    # 时间信息
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="访问时间")
    duration_seconds = Column(Integer, nullable=True, comment="停留时长(秒)")
    
    # 状态
    is_bounce = Column(Boolean, default=False, comment="是否跳出")

    __table_args__ = (
        Index('ix_page_views_session_time', 'session_id', 'created_at'),
        Index('ix_page_views_page_date', 'page_path', 'created_at'),
    )


class EventTrack(Base):
    """事件追踪模型
    
    记录用户在系统中的各种交互行为事件。
    """
    __tablename__ = "analytics_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 基本信息
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型")
    event_name = Column(String(200), nullable=False, comment="事件名称")
    
    # 用户信息
    user_id = Column(String(36), nullable=True, index=True, comment="用户ID")
    session_id = Column(String(128), nullable=True, index=True, comment="会话ID")
    
    # 目标对象
    target_type = Column(String(50), nullable=True, comment="目标对象类型(content/user/media等)")
    target_id = Column(String(36), nullable=True, comment="目标对象ID")
    
    # 事件属性
    properties = Column(JSON, nullable=True, default=dict, comment="事件属性")
    value = Column(Float, nullable=True, comment="事件数值(如购买金额)")
    
    # 环境信息
    page_url = Column(Text, nullable=True, comment="触发页面")
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    user_agent = Column(String(500), nullable=True, comment="User-Agent")
    
    # 时间
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="事件时间")

    __table_args__ = (
        Index('ix_events_user_type', 'user_id', 'event_type'),
        Index('ix_events_target', 'target_type', 'target_id'),
        Index('ix_events_time_type', 'created_at', 'event_type'),
    )


class UserActivity(Base):
    """用户活动聚合模型
    
    按天聚合的用户活动统计数据，用于快速查询用户活跃度。
    """
    __tablename__ = "analytics_user_activity"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 用户标识
    user_id = Column(String(36), nullable=False, index=True, comment="用户ID")
    
    # 统计日期
    date = Column(DateTime, nullable=False, comment="统计日期(精确到天)")

    # 页面浏览统计
    page_views = Column(Integer, default=0, comment="页面浏览数")
    unique_pages_visited = Column(Integer, default=0, comment="独立页面数")
    
    # 互动统计
    likes_given = Column(Integer, default=0, comment="点赞数")
    comments_made = Column(Integer, default=0, comment="评论数")
    shares_count = Column(Integer, default=0, comment="分享数")
    favorites_added = Column(Integer, default=0, comment="收藏数")
    follows_count = Column(Integer, default=0, comment="关注数")
    
    # 内容统计
    content_created = Column(Integer, default=0, comment="创建内容数")
    content_viewed = Column(Integer, default=0, comment="查看内容数")
    downloads_count = Column(Integer, default=0, comment="下载数")
    
    # 搜索统计
    searches_performed = Column(Integer, default=0, comment="搜索次数")
    
    # 时间统计
    total_session_duration = Column(Integer, default=0, comment="总会话时长(秒)")
    active_minutes = Column(Integer, default=0, comment="活跃分钟数")
    
    # 更新时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_activity_date'),
        Index('ix_user_activity_date', 'date'),
    )


class AnalyticsSummary(Base):
    """全局分析摘要模型
    
    预计算的全局统计数据，用于仪表板快速展示。
    """
    __tablename__ = "analytics_summaries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 统计维度
    metric_name = Column(String(100), nullable=False, unique=True, comment="指标名称")
    metric_value = Column(Float, nullable=False, default=0, comment="指标值")
    
    # 分组信息
    dimension = Column(String(50), nullable=True, comment="维度名称(daily/weekly/monthly)")
    dimension_value = Column(String(50), nullable=True, comment="维度值")
    
    # 元信息
    extra_meta = Column(JSON, nullable=True, default=dict, comment="附加元数据")
    
    # 时间
    calculated_at = Column(DateTime, server_default=func.now(), comment="计算时间")
    period_start = Column(DateTime, nullable=True, comment="统计周期开始")
    period_end = Column(DateTime, nullable=True, comment="统计周期结束")


class AnalyticsReport(Base):
    """分析报表模型
    
    存储生成的分析报表，支持定时报表和历史查询。
    """
    __tablename__ = "analytics_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    
    # 报表基本信息
    name = Column(String(255), nullable=False, comment="报表名称")
    report_type = Column(String(50), nullable=False, index=True, comment="报表类型")
    description = Column(Text, nullable=True, comment="报表描述")
    
    # 报表配置
    config = Column(JSON, nullable=False, comment="报表配置(包含查询条件、图表类型等)")
    
    # 报表数据
    data = Column(JSON, nullable=True, comment="报表数据")
    
    # 执行状态
    status = Column(String(20), default="pending", comment="状态: pending/running/completed/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 调度信息
    is_scheduled = Column(Boolean, default=False, comment="是否定时生成")
    schedule_cron = Column(String(100), nullable=True, comment="Cron表达式")
    last_run_at = Column(DateTime, nullable=True, comment="上次运行时间")
    next_run_at = Column(DateTime, nullable=True, comment="下次运行时间")
    
    # 创建者
    created_by = Column(String(36), nullable=True, comment="创建者ID")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
