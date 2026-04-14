"""
结构化日志模块
基于structlog实现结构化日志记录
"""
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog
from structlog import get_logger
from structlog.processors import JSONRenderer, TimeStamper
from structlog.stdlib import BoundLogger, add_log_level, filter_by_level
from structlog.contextvars import merge_contextvars, clear_contextvars, bind_contextvars

from src.core.config import Settings

settings = Settings()


class StructuredLogger:
    """结构化日志管理器"""
    
    def __init__(self, service_name: str = "zhulinsma-api"):
        self.service_name = service_name
        self.logger: Optional[BoundLogger] = None
        self._setup_logging()
    
    def _setup_logging(self):
        """设置结构化日志"""
        
        # 基础日志配置
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG
        )
        
        # structlog处理器链
        processors = [
            # 添加日志级别
            add_log_level,
            # 过滤日志级别
            filter_by_level,
            # 合并上下文变量
            merge_contextvars,
            # 添加时间戳
            TimeStamper(fmt="iso", utc=True),
            # 添加服务名称
            self._add_service_name,
            # 添加环境信息
            self._add_environment,
            # 添加请求ID（如果有）
            self._add_request_id,
            # JSON格式输出
            JSONRenderer()
        ]
        
        # 配置structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # 获取logger实例
        self.logger = get_logger(self.service_name)
        
        logging.info(f"结构化日志已初始化 - 服务: {self.service_name}, 环境: {settings.ENVIRONMENT}")
    
    def _add_service_name(self, _, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """添加服务名称"""
        event_dict["service"] = self.service_name
        return event_dict
    
    def _add_environment(self, _, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """添加环境信息"""
        event_dict["environment"] = settings.ENVIRONMENT
        return event_dict
    
    def _add_request_id(self, _, __, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """添加请求ID（从上下文变量中获取）"""
        return event_dict
    
    def bind(self, **kwargs):
        """绑定上下文变量"""
        bind_contextvars(**kwargs)
        return self
    
    def clear_context(self):
        """清理上下文变量"""
        clear_contextvars()
    
    def debug(self, event: str, **kwargs):
        """DEBUG级别日志"""
        if self.logger:
            self.logger.debug(event, **kwargs)
    
    def info(self, event: str, **kwargs):
        """INFO级别日志"""
        if self.logger:
            self.logger.info(event, **kwargs)
    
    def warning(self, event: str, **kwargs):
        """WARNING级别日志"""
        if self.logger:
            self.logger.warning(event, **kwargs)
    
    def error(self, event: str, **kwargs):
        """ERROR级别日志"""
        if self.logger:
            self.logger.error(event, **kwargs)
    
    def critical(self, event: str, **kwargs):
        """CRITICAL级别日志"""
        if self.logger:
            self.logger.critical(event, **kwargs)
    
    def exception(self, event: str, exc_info: Exception = None, **kwargs):
        """异常日志，自动包含堆栈跟踪"""
        if self.logger:
            kwargs["exc_info"] = exc_info
            self.logger.error(event, **kwargs)


class RequestLogger:
    """HTTP请求日志记录器"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    async def log_request(self, request, response=None, duration=None, error=None):
        """记录HTTP请求日志"""
        log_data = {
            "type": "http_request",
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        
        if response:
            log_data.update({
                "status_code": response.status_code,
                "response_size": getattr(response, "content_length", None),
            })
        
        if duration is not None:
            log_data["duration_ms"] = duration * 1000
        
        if error:
            log_data.update({
                "error": str(error),
                "error_type": type(error).__name__,
            })
        
        # 从上下文变量中获取额外信息
        context_data = self._get_context_data()
        log_data.update(context_data)
        
        # 根据状态码选择日志级别
        if error or (response and response.status_code >= 500):
            self.logger.error("http_request_error", **log_data)
        elif response and response.status_code >= 400:
            self.logger.warning("http_request_client_error", **log_data)
        else:
            self.logger.info("http_request", **log_data)
    
    def _get_context_data(self) -> Dict[str, Any]:
        """从上下文变量中获取数据"""
        # 这里可以获取请求ID、用户ID等上下文信息
        return {}


class DatabaseLogger:
    """数据库操作日志记录器"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def log_query(self, operation: str, table: str, duration: float, success: bool = True, error: str = None):
        """记录数据库查询日志"""
        log_data = {
            "type": "database_query",
            "operation": operation,
            "table": table,
            "duration_ms": duration * 1000,
            "success": success,
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            self.logger.info("database_query", **log_data)
        else:
            self.logger.error("database_query_error", **log_data)
    
    def log_transaction(self, action: str, duration: float, success: bool = True):
        """记录数据库事务日志"""
        log_data = {
            "type": "database_transaction",
            "action": action,
            "duration_ms": duration * 1000,
            "success": success,
        }
        
        if success:
            self.logger.info("database_transaction", **log_data)
        else:
            self.logger.error("database_transaction_error", **log_data)


class BusinessLogger:
    """业务日志记录器"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def log_user_action(self, user_id: str, action: str, **kwargs):
        """记录用户行为日志"""
        log_data = {
            "type": "user_action",
            "user_id": user_id,
            "action": action,
            **kwargs
        }
        
        self.logger.info("user_action", **log_data)
    
    def log_content_action(self, content_id: str, action: str, user_id: str = None, **kwargs):
        """记录内容操作日志"""
        log_data = {
            "type": "content_action",
            "content_id": content_id,
            "action": action,
            **kwargs
        }
        
        if user_id:
            log_data["user_id"] = user_id
        
        self.logger.info("content_action", **log_data)
    
    def log_payment(self, payment_id: str, amount: float, currency: str, status: str, **kwargs):
        """记录支付日志"""
        log_data = {
            "type": "payment",
            "payment_id": payment_id,
            "amount": amount,
            "currency": currency,
            "status": status,
            **kwargs
        }
        
        if status == "success":
            self.logger.info("payment_success", **log_data)
        else:
            self.logger.warning("payment_failed", **log_data)


# 全局日志实例
_structured_logger: Optional[StructuredLogger] = None
_request_logger: Optional[RequestLogger] = None
_database_logger: Optional[DatabaseLogger] = None
_business_logger: Optional[BusinessLogger] = None


def setup_logging(service_name: str = "zhulinsma-api"):
    """设置日志系统"""
    global _structured_logger, _request_logger, _database_logger, _business_logger
    
    if _structured_logger is None:
        _structured_logger = StructuredLogger(service_name)
        _request_logger = RequestLogger(_structured_logger)
        _database_logger = DatabaseLogger(_structured_logger)
        _business_logger = BusinessLogger(_structured_logger)
    
    return _structured_logger


def get_logger() -> StructuredLogger:
    """获取日志记录器"""
    global _structured_logger
    if _structured_logger is None:
        _structured_logger = setup_logging()
    return _structured_logger


def get_request_logger() -> RequestLogger:
    """获取请求日志记录器"""
    global _request_logger
    if _request_logger is None:
        setup_logging()
    return _request_logger


def get_database_logger() -> DatabaseLogger:
    """获取数据库日志记录器"""
    global _database_logger
    if _database_logger is None:
        setup_logging()
    return _database_logger


def get_business_logger() -> BusinessLogger:
    """获取业务日志记录器"""
    global _business_logger
    if _business_logger is None:
        setup_logging()
    return _business_logger


# FastAPI中间件集成
def logging_middleware(app):
    """日志中间件"""
    
    @app.middleware("http")
    async def log_requests(request, call_next):
        """记录HTTP请求日志"""
        start_time = time.time()
        request_id = str(uuid4())
        
        # 绑定请求上下文
        get_logger().bind(request_id=request_id)
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # 记录请求日志
            await get_request_logger().log_request(request, response, duration)
            
            # 添加请求ID到响应头
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # 记录错误日志
            await get_request_logger().log_request(request, None, duration, error=e)
            
            # 清理上下文
            get_logger().clear_context()
            raise
        
        finally:
            # 清理上下文
            get_logger().clear_context()
    
    return app


# 日志格式示例
def log_examples():
    """日志格式示例"""
    logger = get_logger()
    
    # HTTP请求日志示例
    logger.info("http_request", 
                method="GET",
                path="/api/v1/users",
                status_code=200,
                duration_ms=125.5,
                user_id="user_123",
                request_id="req_123456")
    
    # 数据库查询日志示例
    logger.info("database_query",
                operation="SELECT",
                table="users",
                duration_ms=45.2,
                rows_returned=100)
    
    # 业务日志示例
    logger.info("user_registration",
                user_id="user_456",
                email="user@example.com",
                source="web")
    
    # 错误日志示例
    logger.error("database_connection_failed",
                 error="Connection timeout",
                 database="main",
                 retry_count=3)