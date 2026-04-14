"""
指标收集模块
基于Prometheus的指标收集和暴露
"""
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Callable
import logging

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)
from prometheus_client.exposition import make_wsgi_app
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # HTTP请求指标
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry,
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        )
        
        # 数据库指标
        self.database_queries_total = Counter(
            'database_queries_total',
            'Total database queries',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.database_query_duration_seconds = Histogram(
            'database_query_duration_seconds',
            'Database query duration in seconds',
            ['operation', 'table'],
            registry=self.registry,
            buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1)
        )
        
        # 缓存指标
        self.cache_hits_total = Counter(
            'cache_hits_total',
            'Total cache hits',
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            'cache_misses_total',
            'Total cache misses',
            registry=self.registry
        )
        
        self.cache_operations_duration_seconds = Histogram(
            'cache_operations_duration_seconds',
            'Cache operation duration in seconds',
            registry=self.registry,
            buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1)
        )
        
        # 业务指标
        self.user_registrations_total = Counter(
            'user_registrations_total',
            'Total user registrations',
            registry=self.registry
        )
        
        self.user_logins_total = Counter(
            'user_logins_total',
            'Total user logins',
            registry=self.registry
        )
        
        self.user_sessions_active = Gauge(
            'user_sessions_active',
            'Active user sessions',
            registry=self.registry
        )
        
        self.content_published_total = Counter(
            'content_published_total',
            'Total content published',
            registry=self.registry
        )
        
        self.content_views_total = Counter(
            'content_views_total',
            'Total content views',
            registry=self.registry
        )
        
        self.content_interactions_total = Counter(
            'content_interactions_total',
            'Total content interactions',
            ['type'],  # like, comment, share, bookmark
            registry=self.registry
        )
        
        # 系统指标
        self.application_info = Info(
            'application_info',
            'Application information',
            registry=self.registry
        )
        
        # 初始化应用信息
        self.application_info.info({
            'version': '1.0.0',
            'name': '竹林司马',
            'environment': 'development'
        })
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """记录HTTP请求指标"""
        status = f"{status_code // 100}xx"
        
        # 记录请求总数
        self.http_requests_total.labels(
            method=method.upper(),
            endpoint=endpoint,
            status=status
        ).inc()
        
        # 记录请求持续时间
        self.http_request_duration_seconds.labels(
            method=method.upper(),
            endpoint=endpoint
        ).observe(duration)
    
    def record_database_query(self, operation: str, table: str, duration: float):
        """记录数据库查询指标"""
        self.database_queries_total.labels(
            operation=operation,
            table=table
        ).inc()
        
        self.database_query_duration_seconds.labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def record_cache_operation(self, hit: bool, duration: float):
        """记录缓存操作指标"""
        if hit:
            self.cache_hits_total.inc()
        else:
            self.cache_misses_total.inc()
        
        self.cache_operations_duration_seconds.observe(duration)
    
    def record_user_registration(self):
        """记录用户注册"""
        self.user_registrations_total.inc()
    
    def record_user_login(self):
        """记录用户登录"""
        self.user_logins_total.inc()
    
    def update_active_sessions(self, count: int):
        """更新活跃会话数"""
        self.user_sessions_active.set(count)
    
    def record_content_published(self):
        """记录内容发布"""
        self.content_published_total.inc()
    
    def record_content_view(self):
        """记录内容浏览"""
        self.content_views_total.inc()
    
    def record_content_interaction(self, interaction_type: str):
        """记录内容互动"""
        self.content_interactions_total.labels(type=interaction_type).inc()
    
    def get_metrics(self) -> bytes:
        """获取指标数据"""
        return generate_latest(self.registry)
    
    def setup_middleware(self, app: FastAPI):
        """设置FastAPI中间件自动收集HTTP指标"""
        
        @app.middleware("http")
        async def metrics_middleware(request: Request, call_next):
            """HTTP指标收集中间件"""
            start_time = time.time()
            
            try:
                response = await call_next(request)
                duration = time.time() - start_time
                
                # 记录HTTP请求指标
                self.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=response.status_code,
                    duration=duration
                )
                
                return response
                
            except Exception as e:
                # 如果发生异常，记录500错误
                duration = time.time() - start_time
                self.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=500,
                    duration=duration
                )
                raise
        
        @app.get("/metrics", response_class=PlainTextResponse)
        async def metrics_endpoint():
            """Prometheus指标端点"""
            metrics_data = self.get_metrics()
            return Response(
                content=metrics_data,
                media_type=CONTENT_TYPE_LATEST
            )
        
        logger.info("指标中间件已设置")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        # 这里可以添加自定义的指标摘要逻辑
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "http_requests": "已启用",
                "database_queries": "已启用", 
                "cache_operations": "已启用",
                "business_metrics": "已启用"
            }
        }


# 全局指标收集器实例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器实例"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# 上下文管理器用于测量代码块执行时间
@asynccontextmanager
async def measure_duration(metric_func: Callable, *labels):
    """测量代码块执行时间的上下文管理器"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metric_func(*labels, duration)


# 数据库查询测量装饰器
def measure_database_query(operation: str, table: str):
    """测量数据库查询的装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metrics = get_metrics_collector()
                metrics.record_database_query(operation, table, duration)
        return wrapper
    return decorator