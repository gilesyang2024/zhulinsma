#!/usr/bin/env python3
"""
竹林司马 FastAPI 后端入口

启动方式:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    python main.py
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.database import db
from src.core.exceptions import register_exception_handlers
from src.api.v1 import api_router

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 生命周期管理
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用启动/关闭生命周期"""
    # ── 启动 ──
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"  环境: {settings.APP_ENV}")
    logger.info("=" * 60)

    # 数据库连接
    try:
        await db.connect()
        await db.create_all()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化跳过（可选）: {e}")

    # 选股战法引擎预热
    try:
        from src.api.v1.stock import get_engine, get_stock_fetcher, get_indicator
        engine = get_engine()
        logger.info(f"选股战法引擎就绪，已注册 {len(engine.list_strategies())} 个战法")
    except Exception as e:
        logger.warning(f"选股战法引擎初始化跳过: {e}")

    logger.info("服务启动完成，开始接受请求")

    yield

    # ── 关闭 ──
    logger.info("正在关闭服务...")
    try:
        await db.disconnect()
        logger.info("数据库连接已关闭")
    except Exception:
        pass
    logger.info("服务已关闭")


# ─────────────────────────────────────────────
# 创建应用
# ─────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    ## 竹林司马 (Zhulinsma) 后端 API

    ### 核心模块
    - **用户系统**: 注册/登录/JWT认证
    - **选股战法**: 技术指标/策略分析/AI评分
    - **内容管理**: CRUD/审核
    - **推荐引擎**: 多策略融合推荐
    - **监控系统**: 健康检查/Prometheus指标
    - **数据分析**: 事件采集/留存/漏斗

    ### 选股战法模块
    - `GET  /api/v1/stock/strategies` — 查询可用战法
    - `POST /api/v1/stock/analyze` — 个股战法分析
    - `GET  /api/v1/stock/realtime/{code}` — 实时行情
    - `GET  /api/v1/stock/daily/{code}` — 日K数据
    - `GET  /api/v1/stock/indicators/{code}` — 技术指标
    - `GET  /api/v1/stock/limit-up` — 涨停板列表
    - `POST /api/v1/stock/ai-score` — AI智能评分
    - `POST /api/v1/stock/ai-recommend` — AI选股推荐
    - `GET  /api/v1/stock/trend/{code}` — 趋势分析
    - `GET  /api/v1/stock/risk/{code}` — 风险评估
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# 中间件
# ─────────────────────────────────────────────

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.APP_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常 {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.APP_DEBUG else "请稍后重试",
        },
    )


# 注册自定义异常处理器
try:
    register_exception_handlers(app)
except Exception:
    pass


# ─────────────────────────────────────────────
# 路由注册
# ─────────────────────────────────────────────

app.include_router(api_router, prefix=settings.API_V1_STR)


# ─────────────────────────────────────────────
# 根路由
# ─────────────────────────────────────────────

@app.get("/", tags=["根"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "docs": "/docs",
        "total_routes": len(app.routes),
    }


# ─────────────────────────────────────────────
# 直接启动
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.APP_DEBUG,
    )
