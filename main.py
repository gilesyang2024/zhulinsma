"""
竹林司马后端应用主入口

FastAPI应用实例和启动配置。
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from src.core.config import settings
from src.core.exceptions import register_exception_handlers
from src.core.database import db, check_database_health
from src.core.cache import cache, check_cache_health
from src.core.security import check_security_health
from src.api.v1 import api_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器
    
    Args:
        app: FastAPI应用实例
    """
    # 启动时
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"环境: {settings.APP_ENV}, 调试: {settings.APP_DEBUG}")
    
    # 连接数据库
    try:
        await db.connect()
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise
    
    # 连接缓存
    try:
        await cache.connect()
        logger.info("缓存连接成功")
    except Exception as e:
        logger.error(f"缓存连接失败: {e}")
        # 缓存连接失败不阻止应用启动
    
    yield
    
    # 关闭时
    logger.info("正在关闭应用...")
    
    # 断开缓存连接
    try:
        await cache.disconnect()
        logger.info("缓存连接已断开")
    except Exception as e:
        logger.error(f"缓存断开失败: {e}")
    
    # 断开数据库连接
    try:
        await db.disconnect()
        logger.info("数据库连接已断开")
    except Exception as e:
        logger.error(f"数据库断开失败: {e}")
    
    logger.info("应用已关闭")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="竹林司马内容管理系统的后端API",
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    openapi_url="/api/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

# 注册异常处理器
register_exception_handlers(app)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.APP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加Prometheus指标应用
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 注册API路由
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["根路径"])
async def root():
    """根路径，返回应用信息"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/api/docs" if settings.is_development else None,
        "health": "/health",
        "metrics": "/metrics",
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """系统健康检查"""
    # 并行检查各个组件
    db_health = await check_database_health()
    cache_health = await check_cache_health()
    security_health = await check_security_health()
    
    # 确定总体状态
    all_healthy = all([
        db_health["status"] == "healthy",
        cache_health["status"] == "healthy",
        security_health["status"] == "healthy",
    ])
    
    status_code = (
        status.HTTP_200_OK if all_healthy 
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    
    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": db_health,
            "cache": cache_health,
            "security": security_health,
        },
    }
    
    return JSONResponse(
        status_code=status_code,
        content=response,
    )


@app.get("/info", tags=["系统信息"])
async def system_info():
    """系统信息"""
    import platform
    import sys
    
    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        },
        "python": {
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "system": {
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "api": {
            "version": "v1",
            "prefix": settings.API_PREFIX,
            "docs": "/api/docs" if settings.is_development else None,
        },
    }


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    # 记录请求开始
    logger.info(
        f"请求开始: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent"),
        },
    )
    
    # 处理请求
    response = await call_next(request)
    
    # 记录请求结束
    logger.info(
        f"请求结束: {request.method} {request.url.path} - {response.status_code}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "response_time_ms": 0,  # 实际应用中需要计算响应时间
        },
    )
    
    return response


# 开发环境下的调试路由
if settings.is_development:
    
    @app.get("/debug/config", tags=["调试"])
    async def debug_config():
        """调试配置信息（仅开发环境）"""
        # 注意：不要暴露敏感信息如密码、密钥等
        return {
            "app": {
                "name": settings.APP_NAME,
                "env": settings.APP_ENV,
                "debug": settings.APP_DEBUG,
                "allowed_hosts": settings.APP_ALLOWED_HOSTS,
            },
            "api": {
                "prefix": settings.API_PREFIX,
                "v1_str": settings.API_V1_STR,
            },
            "database": {
                "url": str(settings.DATABASE_URL).split("@")[0] + "@***",  # 隐藏密码
                "pool_size": settings.DATABASE_POOL_SIZE,
            },
            "cache": {
                "url": settings.REDIS_URL,
                "pool_size": settings.REDIS_POOL_SIZE,
            },
            "jwt": {
                "algorithm": settings.JWT_ALGORITHM,
                "access_token_expire_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            },
        }


if __name__ == "__main__":
    # 本地运行
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )