"""
推荐系统数据模型

定义用户行为、物品特征、推荐结果等核心数据结构。
支持SQLAlchemy ORM持久化和内存计算双模式。
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, BigInteger, Text, Float, Boolean,
    DateTime, JSON, Index, ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func

from src.core.database import Base


# ============================================================
# 枚举类型
# ============================================================

class InteractionType(str, Enum):
    """用户交互行为类型"""
    VIEW = "view"              # 浏览
    CLICK = "click"            # 点击
    LIKE = "like"              # 点赞
    FAVORITE = "favorite"      # 收藏
    SHARE = "share"            # 分享
    COMMENT = "comment"        # 评论
    FOLLOW = "follow"          # 关注
    SUBSCRIBE = "subscribe"    # 订阅/追更
    DOWNLOAD = "download"      # 下载
    COMPLETE = "complete"      # 完整观看/完成
    RATING = "rating"          # 评分


class RecommendationReason(str, Enum):
    """推荐原因（可解释性）"""
    COLLABORATIVE_ITEM = "collaborative_item"       # 基于物品协同过滤
    COLLABORATIVE_USER = "collaborative_user"       # 基于用户协同过滤
    CONTENT_SIMILARITY = "content_similarity"       # 内容相似度
    TAG_MATCH = "tag_match"                         # 标签匹配
    TRENDING = "trending"                           # 热门趋势
    POPULAR = "popular"                             # 全局热门
    NEW_RELEASE = "new_release"                     # 新发布
    USER_PREFERENCE = "user_preference"             # 用户偏好匹配
    SOCIAL_GRAPH = "social_graph"                   # 社交关系
    CONTEXTUAL = "contextual"                       # 场景化推荐
    COLD_START = "cold_start"                       # 冷启动推荐
    BOOSTED = "boosted"                             # 运营强推


class ItemContentType(str, Enum):
    """内容类型枚举"""
    VIDEO = "video"
    ARTICLE = "article"
    AUDIO = "audio"
    IMAGE = "image"
    LIVE = "live"
    COURSE = "course"
    SERIES = "series"


class RecommendationScene(str, Enum):
    """推荐场景"""
    HOME_FEED = "home_feed"           # 首页信息流
    DETAIL_RELATED = "detail_related" # 详情页相关推荐
    DISCOVERY = "discovery"           # 发现页/探索
    SEARCH = "search_result"          # 搜索结果页推荐
    USER_PROFILE = "user_profile"     # 个人主页推荐
    CATEGORY = "category"             # 分类频道
    HOT_LIST = "hot_list"             # 热榜/榜单
    FOLLOWING_FEED = "following_feed" # 关注动态流


# ============================================================
# SQLAlchemy ORM 模型
# ============================================================

class UserInteraction(Base):
    """用户行为记录模型
    
    记录用户与内容的所有交互行为，是协同过滤算法的数据基础。
    支持显式反馈（评分）和隐式反馈（浏览/点赞等）。
    """
    __tablename__ = "rec_user_interactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 用户和物品
    user_id = Column(String(36), nullable=False, index=True, comment="用户ID")
    item_id = Column(String(36), nullable=False, index=True, comment="内容ID")
    
    # 交互信息
    interaction_type = Column(String(30), nullable=False, index=True, comment="交互类型")
    score = Column(Float, default=1.0, comment="交互权重分(隐式反馈自动计算)")
    rating_value = Column(Float, nullable=True, comment="显式评分值(1-5)")
    
    # 上下文信息
    scene = Column(String(30), nullable=True, comment="发生场景")
    source = Column(String(50), nullable=True, comment="来源渠道")
    device_type = Column(String(20), nullable=True, comment="设备类型")
    
    # 元数据
    properties = Column(JSON, nullable=True, default=dict, comment="扩展属性")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="交互时间")

    __table_args__ = (
        UniqueConstraint('user_id', 'item_id', 'interaction_type', 'created_at',
                         name='uq_user_item_interaction'),
        Index('ix_interactions_user_time', 'user_id', 'created_at'),
        Index('ix_interactions_item_time', 'item_id', 'created_at'),
        Index('ix_interactions_type_time', 'interaction_type', 'created_at'),
    )


class ItemFeature(Base):
    """内容特征向量模型
    
    存储内容的结构化特征，用于content-based推荐。
    包括标签、分类、TF-IDF特征、嵌入向量等。
    """
    __tablename__ = "rec_item_features"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 物品标识
    item_id = Column(String(36), nullable=False, unique=True, index=True, comment="内容ID")
    content_type = Column(String(20), nullable=True, comment="内容类型")
    
    # 分类特征
    category = Column(String(100), nullable=True, index=True, comment="一级分类")
    sub_category = Column(String(100), nullable=True, comment="二级分类")
    tags = Column(JSON, nullable=True, default=list, comment="标签列表")
    
    # 文本特征
    title_vector = Column(JSON, nullable=True, comment="标题TF-IDF向量")
    content_vector = Column(JSON, nullable=True, comment="正文TF-IDF向量")
    embedding = Column(JSON, nullable=True, comment="语义嵌入向量(如BERT)")
    
    # 统计特征
    view_count = Column(Integer, default=0, comment="总浏览量")
    like_count = Column(Integer, default=0, comment="总点赞数")
    share_count = Column(Integer, default=0, comment="总分享数")
    comment_count = Column(Integer, default=0, comment="总评论数")
    favorite_count = Column(Integer, default=0, comment="总收藏数")
    avg_duration = Column(Float, nullable=True, comment="平均观看时长(秒)")
    completion_rate = Column(Float, default=0, comment="平均完播率")
    
    # 质量分数
    quality_score = Column(Float, default=0, comment="综合质量分(0-1)")
    popularity_score = Column(Float, default=0, comment="热度分数")
    
    # 作者信息
    author_id = Column(String(36), nullable=True, index=True, comment="作者ID")
    
    # 时间
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserProfile(Base):
    """用户画像模型
    
    存储用户的长期兴趣偏好，用于个性化推荐。
    包括偏好标签、兴趣向量、统计摘要等。
    """
    __tablename__ = "rec_user_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 用户标识
    user_id = Column(String(36), nullable=False, unique=True, index=True, comment="用户ID")
    
    # 兴趣标签（带权重）
    preference_tags = Column(JSON, nullable=True, default=dict, comment="偏好标签 {tag: weight}")
    
    # 偏好分类
    preferred_categories = Column(JSON, nullable=True, default=list, comment="偏好的分类列表")
    
    # 兴趣向量（降维后的用户表示）
    interest_vector = Column(JSON, nullable=True, comment="兴趣向量(100-300维)")
    
    # 统计摘要
    total_interactions = Column(Integer, default=0, comment="总交互次数")
    active_days = Column(Integer, default=0, comment="活跃天数")
    avg_session_duration = Column(Float, nullable=True, comment="平均会话时长(秒)")
    
    # 用户分段
    user_segment = Column(String(30), nullable=True, comment="用户群组(new/active/churned/power)")
    power_score = Column(Float, default=0, comment="用户价值分")
    
    # 时间窗口内的活跃度
    recent_activity_score = Column(Float, default=0, comment="近期活跃度(7天)")
    
    # 更新时间
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RecommendationResult(Base):
    """推荐结果缓存模型
    
    缓存已计算的推荐结果，减少实时计算压力。
    支持按场景和用户维度的缓存。
    """
    __tablename__ = "rec_recommendation_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    
    # 推荐请求标识
    user_id = Column(String(36), nullable=True, index=True, comment="目标用户ID(null=全局推荐)")
    scene = Column(String(30), nullable=False, index=True, comment="推荐场景")
    
    # 推荐结果
    items = Column(JSON, nullable=False, comment="推荐列表 [{item_id, score, reason, rank}]")
    
    # 元信息
    algorithm_version = Column(String(20), nullable=True, comment="算法版本")
    strategies_used = Column(JSON, nullable=True, default=list, comment="使用的策略列表")
    generation_time_ms = Column(Integer, nullable=True, comment="生成耗时(ms)")
    
    # 有效期
    expires_at =Column(DateTime, nullable=True, index=True, comment="过期时间")
    
    # 统计
    impression_count = Column(Integer, default=0, comment="曝光次数")
    click_count = Column(Integer, default=0, comment="点击次数")
    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_rec_cache_user_scene', 'user_id', 'scene'),
        Index('ix_rec_cache_expires', 'expires_at'),
    )


class TrendingItem(Base):
    """热门内容排行榜模型
    
    实时更新的热门内容排行，支持多维度榜单。
    """
    __tablename__ = "rec_trending_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 物品
    item_id = Column(String(36), nullable=False, index=True, comment="内容ID")
    
    # 榜单维度
    ranking_type = Column(String(30), nullable=False, index=True, comment="榜单类型(hourly/daily/weekly/monthly)")
    category = Column(String(100), nullable=True, index=True, comment="分类筛选")
    
    # 排名数据
    rank_position = Column(Integer, nullable=True, comment="当前排名")
    raw_score = Column(Float, nullable=False, comment="原始得分")
    normalized_score = Column(Float, nullable=True, comment="归一化得分(0-1)")
    
    # 趋势信息
    prev_rank = Column(Integer, nullable=True, comment="上一周期排名")
    trend = Column(String(10), nullable=True, comment="趋势(up/down/same/new/hot)")
    streak_days = Column(Integer, default=0, comment="连续上榜天数")
    
    # 统计快照
    stat_snapshot = Column(JSON, nullable=True, comment="统计快照{views, likes, ...}")
    
    # 时间窗口
    period_start = Column(DateTime, nullable=False, comment="统计周期开始")
    period_end = Column(DateTime, nullable=False, comment="统计周期结束")
    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('item_id', 'ranking_type', 'category', 'period_start',
                         name='uq_trending_unique'),
        Index('ix_trending_rank', 'ranking_type', 'rank_position'),
    )


class SimilarItemPair(Base):
    """物品相似度矩阵（预计算）
    
    预计算的物品间相似度，用于ItemCF快速查询。
    采用稀疏存储策略，只保留Top-K相似对。
    """
    __tablename__ = "rec_similar_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 物品对
    item_id_a = Column(String(36), nullable=False, index=True, comment="源物品ID")
    item_id_b = Column(String(36), nullable=False, index=True, comment="目标物品ID")
    
    # 相似度
    similarity_score = Column(Float, nullable=False, comment="余弦相似度/Jaccard系数")
    similarity_method = Column(String(30), nullable=True, comment="计算方法(cosine/jaccard/hybrid)")
    
    # 共现统计
    co_occur_count = Column(Integer, default=0, comment="共同被交互的用户数")
    support_count = Column(Integer, default=0, comment="至少一方被交互的用户数")
    
    # 更新时间
    computed_at = Column(DateTime, server_default=func.now(), comment="计算时间")

    __table_args__ = (
        UniqueConstraint('item_id_a', 'item_id_b', name='uq_similar_pair'),
        Index('ix_similar_score', 'item_id_a', 'similarity_score'),
    )
