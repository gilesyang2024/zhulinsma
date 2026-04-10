"""
异常处理模块

定义应用级别的异常类和全局异常处理器。
"""

import logging
from typing import Any, Dict, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用基础异常类"""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


# ==================== 认证相关异常 ====================

class AuthenticationError(AppException):
    """认证异常"""
    
    def __init__(
        self,
        message: str = "认证失败",
        code: str = "AUTHENTICATION_FAILED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(AppException):
    """授权异常"""
    
    def __init__(
        self,
        message: str = "权限不足",
        code: str = "PERMISSION_DENIED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class TokenExpiredError(AuthenticationError):
    """令牌过期异常"""
    
    def __init__(
        self,
        message: str = "令牌已过期",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="TOKEN_EXPIRED",
            details=details,
        )


class InvalidTokenError(AuthenticationError):
    """无效令牌异常"""
    
    def __init__(
        self,
        message: str = "无效的令牌",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
            details=details,
        )


# ==================== 资源相关异常 ====================

class NotFoundError(AppException):
    """资源未找到异常"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Union[str, UUID, int],
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"{resource_type} {resource_id} 未找到"
        
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                **(details or {}),
            },
        )


class AlreadyExistsError(AppException):
    """资源已存在异常"""
    
    def __init__(
        self,
        resource_type: str,
        resource_identifier: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"{resource_type} {resource_identifier} 已存在"
        
        super().__init__(
            message=message,
            code="RESOURCE_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "resource_type": resource_type,
                "resource_identifier": resource_identifier,
                **(details or {}),
            },
        )


class ValidationError(AppException):
    """数据验证异常"""
    
    def __init__(
        self,
        message: str = "数据验证失败",
        field_errors: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={
                "field_errors": field_errors or {},
                **(details or {}),
            },
        )


# ==================== 业务逻辑异常 ====================

class BusinessLogicError(AppException):
    """业务逻辑异常"""
    
    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_LOGIC_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class RateLimitExceededError(AppException):
    """速率限制异常"""
    
    def __init__(
        self,
        message: str = "请求过于频繁，请稍后重试",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ExternalServiceError(AppException):
    """外部服务异常"""
    
    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"{service_name} 服务异常"
        
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={
                "service_name": service_name,
                **(details or {}),
            },
        )


# ==================== 数据库相关异常 ====================

class DatabaseError(AppException):
    """数据库异常"""
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ConstraintViolationError(DatabaseError):
    """约束违反异常"""
    
    def __init__(
        self,
        constraint_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"违反约束: {constraint_name}"
        
        super().__init__(
            message=message,
            details={
                "constraint_name": constraint_name,
                **(details or {}),
            },
        )


class DeadlockError(DatabaseError):
    """死锁异常"""
    
    def __init__(
        self,
        message: str = "数据库死锁",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="DEADLOCK_ERROR",
            details=details,
        )


# ==================== 文件处理异常 ====================

class FileProcessingError(AppException):
    """文件处理异常"""
    
    def __init__(
        self,
        message: str = "文件处理失败",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="FILE_PROCESSING_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FileSizeExceededError(FileProcessingError):
    """文件大小超限异常"""
    
    def __init__(
        self,
        max_size: int,
        actual_size: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"文件大小超过限制: {actual_size} > {max_size}"
        
        super().__init__(
            message=message,
            details={
                "max_size": max_size,
                "actual_size": actual_size,
                **(details or {}),
            },
        )


class InvalidFileTypeError(FileProcessingError):
    """无效文件类型异常"""
    
    def __init__(
        self,
        allowed_types: list[str],
        actual_type: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"不支持的文件类型: {actual_type}，允许的类型: {', '.join(allowed_types)}"
        
        super().__init__(
            message=message,
            details={
                "allowed_types": allowed_types,
                "actual_type": actual_type,
                **(details or {}),
            },
        )


# ==================== 异常处理器 ====================

async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    """应用异常处理器
    
    Args:
        request: 请求对象
        exc: 异常实例
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.warning(
        f"应用异常: {exc.code} - {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )
    
    error_response = {
        "success": False,
        "error": {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
        "meta": {
            "path": request.url.path,
            "method": request.method,
        },
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理器
    
    Args:
        request: 请求对象
        exc: HTTP异常实例
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.warning(
        f"HTTP异常: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    
    error_response = {
        "success": False,
        "error": {
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
        },
        "meta": {
            "path": request.url.path,
            "method": request.method,
        },
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )


async def validation_exception_handler(request, exc: ValidationError) -> JSONResponse:
    """验证异常处理器
    
    Args:
        request: 请求对象
        exc: 验证异常实例
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.warning(
        f"验证异常: {exc}",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
        },
    )
    
    # 提取字段错误
    field_errors = {}
    for error in exc.errors():
        loc = error.get("loc", [])
        if len(loc) >= 2:
            field = ".".join(str(x) for x in loc[1:])
        else:
            field = ".".join(str(x) for x in loc)
        
        field_errors[field] = {
            "message": error.get("msg"),
            "type": error.get("type"),
        }
    
    error_response = {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "数据验证失败",
            "details": {
                "field_errors": field_errors,
            },
        },
        "meta": {
            "path": request.url.path,
            "method": request.method,
        },
    }
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response,
    )


async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
    """通用异常处理器
    
    Args:
        request: 请求对象
        exc: 异常实例
        
    Returns:
        JSONResponse: 错误响应
    """
    logger.error(
        f"未处理异常: {type(exc).__name__} - {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "exception_args": exc.args,
        },
        exc_info=True,
    )
    
    # 生产环境隐藏详细错误信息
    if hasattr(request.app.state, "settings") and request.app.state.settings.is_production:
        message = "服务器内部错误"
        details = None
    else:
        message = f"{type(exc).__name__}: {str(exc)}"
        details = {"traceback": str(exc.__traceback__) if hasattr(exc, "__traceback__") else None}
    
    error_response = {
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": message,
            "details": details,
        },
        "meta": {
            "path": request.url.path,
            "method": request.method,
        },
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


# ==================== 异常工具函数 ====================

def not_found(resource_type: str, resource_id: Union[str, UUID, int]) -> NotFoundError:
    """快速创建资源未找到异常
    
    Args:
        resource_type: 资源类型
        resource_id: 资源ID
        
    Returns:
        NotFoundError: 资源未找到异常
    """
    return NotFoundError(resource_type=resource_type, resource_id=resource_id)


def already_exists(resource_type: str, resource_identifier: str) -> AlreadyExistsError:
    """快速创建资源已存在异常
    
    Args:
        resource_type: 资源类型
        resource_identifier: 资源标识符
        
    Returns:
        AlreadyExistsError: 资源已存在异常
    """
    return AlreadyExistsError(
        resource_type=resource_type,
        resource_identifier=resource_identifier,
    )


def validation_failed(field_errors: Dict[str, str]) -> ValidationError:
    """快速创建验证失败异常
    
    Args:
        field_errors: 字段错误字典
        
    Returns:
        ValidationError: 验证失败异常
    """
    return ValidationError(field_errors=field_errors)


def business_error(message: str, code: Optional[str] = None) -> BusinessLogicError:
    """快速创建业务逻辑异常
    
    Args:
        message: 错误消息
        code: 错误代码（可选）
        
    Returns:
        BusinessLogicError: 业务逻辑异常
    """
    return BusinessLogicError(message=message, code=code or "BUSINESS_LOGIC_ERROR")


# ==================== 异常注册 ====================

def register_exception_handlers(app):
    """注册异常处理器到FastAPI应用
    
    Args:
        app: FastAPI应用实例
    """
    # 注册应用异常处理器
    app.add_exception_handler(AppException, app_exception_handler)
    
    # 注册HTTP异常处理器
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    # 注册验证异常处理器
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # 注册通用异常处理器
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("异常处理器已注册")