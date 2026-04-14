"""
健康检查系统
提供应用和服务健康状态监控
"""
import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.config import Settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CheckResult(BaseModel):
    """检查结果"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: HealthStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    service: str
    environment: str
    checks: Dict[str, CheckResult]
    uptime_seconds: float


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.settings = Settings()
        self.start_time = time.time()
        self.checks: Dict[str, callable] = {}
        
        # 注册默认检查
        self._register_default_checks()
        
        logger.info("健康检查器已初始化")
    
    def _register_default_checks(self):
        """注册默认健康检查"""
        self.register_check("application", self.check_application)
        self.register_check("memory", self.check_memory)
        self.register_check("database", self.check_database)
        self.register_check("cache", self.check_cache)
        self.register_check("external_api", self.check_external_api)
    
    def register_check(self, name: str, check_func: callable):
        """注册健康检查"""
        self.checks[name] = check_func
        logger.info(f"健康检查已注册: {name}")
    
    async def check_application(self) -> CheckResult:
        """检查应用状态"""
        start_time = time.time()
        
        try:
            # 检查应用基本功能
            latency_ms = (time.time() - start_time) * 1000
            
            return CheckResult(
                name="application",
                status=HealthStatus.HEALTHY,
                message="应用运行正常",
                latency_ms=latency_ms,
                details={
                    "pid": None,  # 可以添加进程ID
                    "thread_count": None,  # 可以添加线程数
                }
            )
        except Exception as e:
            return CheckResult(
                name="application",
                status=HealthStatus.UNHEALTHY,
                message=f"应用检查失败: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def check_memory(self) -> CheckResult:
        """检查内存使用"""
        start_time = time.time()
        
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            memory_percent = process.memory_percent()
            is_healthy = memory_percent < 90  # 内存使用率低于90%为健康
            
            latency_ms = (time.time() - start_time) * 1000
            
            return CheckResult(
                name="memory",
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
                message=f"内存使用率: {memory_percent:.1f}%" if is_healthy else f"内存使用率过高: {memory_percent:.1f}%",
                latency_ms=latency_ms,
                details={
                    "memory_percent": memory_percent,
                    "memory_rss_mb": memory_info.rss / 1024 / 1024,
                    "memory_vms_mb": memory_info.vms / 1024 / 1024,
                }
            )
        except ImportError:
            # psutil未安装，返回未知状态
            return CheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil未安装，无法检查内存使用",
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return CheckResult(
                name="memory",
                status=HealthStatus.UNHEALTHY,
                message=f"内存检查失败: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def check_database(self) -> CheckResult:
        """检查数据库连接"""
        start_time = time.time()
        
        try:
            from sqlalchemy import text
            from src.core.database import async_session
            
            async with async_session() as session:
                # 执行简单的查询测试连接
                start_db_time = time.time()
                result = await session.execute(text("SELECT 1"))
                db_latency = (time.time() - start_db_time) * 1000
                
                # 检查结果
                row = result.fetchone()
                is_connected = row[0] == 1
            
            total_latency = (time.time() - start_time) * 1000
            
            if is_connected:
                return CheckResult(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="数据库连接正常",
                    latency_ms=total_latency,
                    details={
                        "query_latency_ms": db_latency,
                        "connection_pool": "active",  # 可以添加连接池信息
                    }
                )
            else:
                return CheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="数据库连接测试失败",
                    latency_ms=total_latency
                )
                
        except ImportError:
            return CheckResult(
                name="database",
                status=HealthStatus.UNKNOWN,
                message="数据库模块未导入",
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return CheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"数据库连接失败: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def check_cache(self) -> CheckResult:
        """检查缓存连接"""
        start_time = time.time()
        
        try:
            from src.core.cache import redis_client
            
            start_cache_time = time.time()
            is_connected = await redis_client.ping()
            cache_latency = (time.time() - start_cache_time) * 1000
            
            total_latency = (time.time() - start_time) * 1000
            
            if is_connected:
                return CheckResult(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    message="缓存连接正常",
                    latency_ms=total_latency,
                    details={
                        "cache_latency_ms": cache_latency,
                        "cache_type": "redis",
                    }
                )
            else:
                return CheckResult(
                    name="cache",
                    status=HealthStatus.UNHEALTHY,
                    message="缓存连接测试失败",
                    latency_ms=total_latency
                )
                
        except ImportError:
            return CheckResult(
                name="cache",
                status=HealthStatus.UNKNOWN,
                message="缓存模块未导入",
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return CheckResult(
                name="cache",
                status=HealthStatus.UNHEALTHY,
                message=f"缓存连接失败: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def check_external_api(self) -> CheckResult:
        """检查外部API连接"""
        start_time = time.time()
        
        try:
            import httpx
            
            # 测试连接到一个稳定的外部API
            test_url = "https://httpbin.org/get"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                start_api_time = time.time()
                response = await client.get(test_url)
                api_latency = (time.time() - start_api_time) * 1000
            
            total_latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return CheckResult(
                    name="external_api",
                    status=HealthStatus.HEALTHY,
                    message="外部API连接正常",
                    latency_ms=total_latency,
                    details={
                        "api_latency_ms": api_latency,
                        "status_code": response.status_code,
                        "test_url": test_url,
                    }
                )
            else:
                return CheckResult(
                    name="external_api",
                    status=HealthStatus.DEGRADED,
                    message=f"外部API响应异常: {response.status_code}",
                    latency_ms=total_latency,
                    details={
                        "status_code": response.status_code,
                        "test_url": test_url,
                    }
                )
                
        except ImportError:
            return CheckResult(
                name="external_api",
                status=HealthStatus.UNKNOWN,
                message="httpx未安装，无法测试外部API",
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return CheckResult(
                name="external_api",
                status=HealthStatus.DEGRADED,
                message=f"外部API连接失败: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def run_all_checks(self) -> HealthCheckResponse:
        """运行所有健康检查"""
        checks = {}
        overall_status = HealthStatus.HEALTHY
        
        # 并发运行所有检查
        check_tasks = []
        for name, check_func in self.checks.items():
            task = asyncio.create_task(check_func())
            check_tasks.append((name, task))
        
        # 收集结果
        for name, task in check_tasks:
            try:
                result = await task
                checks[name] = result
                
                # 更新整体状态
                if result.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                    
            except Exception as e:
                checks[name] = CheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"检查执行失败: {str(e)}"
                )
                overall_status = HealthStatus.UNHEALTHY
        
        # 构建响应
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=self.settings.APP_VERSION,
            service=self.settings.APP_NAME,
            environment=self.settings.ENVIRONMENT,
            checks=checks,
            uptime_seconds=time.time() - self.start_time
        )
    
    async def check_ready(self) -> Dict[str, Any]:
        """就绪检查（轻量级）"""
        try:
            # 只检查关键依赖
            db_check = await self.check_database()
            cache_check = await self.check_cache()
            
            is_ready = (
                db_check.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] and
                cache_check.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            )
            
            return {
                "status": "ready" if is_ready else "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": db_check.dict(),
                    "cache": cache_check.dict(),
                }
            }
            
        except Exception as e:
            return {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def check_live(self) -> Dict[str, Any]:
        """存活检查（最轻量级）"""
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - self.start_time
        }


# 全局健康检查器实例
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


# FastAPI路由
health_router = APIRouter(prefix="/health", tags=["健康检查"])


@health_router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """综合健康检查"""
    try:
        checker = get_health_checker()
        return await checker.run_all_checks()
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"健康检查失败: {str(e)}"
        )


@health_router.get("/ready", response_model=Dict[str, Any])
async def readiness_probe():
    """就绪探针 - 用于Kubernetes就绪检查"""
    try:
        checker = get_health_checker()
        result = await checker.check_ready()
        
        if result["status"] == "ready":
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )
            
    except Exception as e:
        logger.error(f"就绪检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"就绪检查失败: {str(e)}"
        )


@health_router.get("/live", response_model=Dict[str, Any])
async def liveness_probe():
    """存活探针 - 用于Kubernetes存活检查"""
    try:
        checker = get_health_checker()
        return await checker.check_live()
    except Exception as e:
        logger.error(f"存活检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"存活检查失败: {str(e)}"
        )


@health_router.get("/simple")
async def simple_health_check():
    """简单健康检查（最快速）"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "竹林司马",
        "version": get_health_checker().settings.APP_VERSION
    }


@health_router.get("/details/{check_name}", response_model=CheckResult)
async def check_detail(check_name: str):
    """获取特定检查的详细信息"""
    checker = get_health_checker()
    
    if check_name in checker.checks:
        try:
            return await checker.checks[check_name]()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"检查执行失败: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"检查 '{check_name}' 不存在"
        )


@health_router.post("/custom")
async def custom_health_check(check_data: Dict[str, Any]):
    """自定义健康检查"""
    # 这里可以实现自定义的健康检查逻辑
    return {
        "status": "custom_check_received",
        "data": check_data,
        "timestamp": datetime.utcnow().isoformat()
    }