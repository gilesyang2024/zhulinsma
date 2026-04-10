"""
速率限制中间件

基于用户和端点的请求速率限制。
"""

import time
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.cache import cache
from src.core.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


class RateLimiter:
    """速率限制器"""
    
    def __init__(self):
        """初始化速率限制器"""
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.limits = self._parse_limit_config()
        
    def _parse_limit_config(self) -> Dict[str, Dict[str, Any]]:
        """解析速率限制配置
        
        Returns:
            速率限制配置字典
        """
        limits = {}
        
        # 解析默认限制
        if settings.RATE_LIMIT_DEFAULT:
            limits["default"] = self._parse_limit_string(settings.RATE_LIMIT_DEFAULT)
        
        # 解析认证限制
        if settings.RATE_LIMIT_AUTH:
            limits["auth"] = self._parse_limit_string(settings.RATE_LIMIT_AUTH)
        
        # 解析上传限制
        if settings.RATE_LIMIT_UPLOAD:
            limits["upload"] = self._parse_limit_string(settings.RATE_LIMIT_UPLOAD)
        
        return limits
    
    def _parse_limit_string(self, limit_str: str) -> Dict[str, Any]:
        """解析限制字符串
        
        Args:
            limit_str: 限制字符串，格式如 "100/minute" 或 "20/5minutes"
            
        Returns:
            限制配置字典
        """
        try:
            parts = limit_str.split("/")
            if len(parts) != 2:
                raise ValueError(f"无效的限制格式: {limit_str}")
            
            count = int(parts[0].strip())
            period_str = parts[1].strip().lower()
            
            # 解析时间周期
            if period_str == "second":
                period_seconds = 1
            elif period_str == "minute":
                period_seconds = 60
            elif period_str == "hour":
                period_seconds = 3600
            elif period_str == "day":
                period_seconds = 86400
            else:
                # 尝试解析类似 "5minutes" 的格式
                if period_str.endswith("seconds"):
                    period_seconds = int(period_str[:-7])
                elif period_str.endswith("minutes"):
                    period_seconds = int(period_str[:-7]) * 60
                elif period_str.endswith("hours"):
                    period_seconds = int(period_str[:-5]) * 3600
                elif period_str.endswith("days"):
                    period_seconds = int(period_str[:-4]) * 86400
                else:
                    raise ValueError(f"未知的时间周期: {period_str}")
            
            return {
                "count": count,
                "period_seconds": period_seconds,
                "original": limit_str,
            }
            
        except ValueError as e:
            logger.error(f"解析速率限制配置失败: {limit_str}, 错误: {e}")
            return {
                "count": 100,
                "period_seconds": 60,
                "original": "100/minute",
                "error": str(e),
            }
    
    def get_limit_for_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """获取端点的速率限制配置
        
        Args:
            endpoint: API端点路径
            
        Returns:
            速率限制配置
        """
        # 特殊端点处理
        if "/auth/" in endpoint:
            return self.limits.get("auth", self.limits.get("default"))
        
        if "/upload" in endpoint or "/media/upload" in endpoint:
            return self.limits.get("upload", self.limits.get("default"))
        
        # 默认限制
        return self.limits.get("default", {
            "count": 100,
            "period_seconds": 60,
            "original": "100/minute",
        })
    
    async def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[str] = None,
    ) -> bool:
        """检查速率限制
        
        Args:
            request: 请求对象
            user_id: 用户ID（可选）
            
        Returns:
            bool: 是否允许请求
            
        Raises:
            RateLimitExceededError: 速率限制超出
        """
        if not self.enabled:
            return True
        
        try:
            # 获取端点限制
            endpoint = request.url.path
            limit_config = self.get_limit_for_endpoint(endpoint)
            
            if not limit_config:
                return True
            
            # 构建限制键
            limit_key = self._build_limit_key(request, user_id, limit_config)
            
            # 检查限制
            current_count = await self._get_current_count(limit_key)
            
            if current_count >= limit_config["count"]:
                # 计算重试时间
                retry_after = await self._get_retry_after(limit_key, limit_config)
                
                raise RateLimitExceededError(
                    retry_after=retry_after,
                    details={
                        "limit": limit_config["count"],
                        "period": limit_config["period_seconds"],
                        "endpoint": endpoint,
                        "user_id": user_id,
                    },
                )
            
            # 增加计数
            await self._increment_count(limit_key, limit_config)
            
            return True
            
        except RateLimitExceededError:
            raise
        except Exception as e:
            logger.error(f"速率限制检查失败: {e}")
            # 在错误情况下允许请求通过
            return True
    
    def _build_limit_key(
        self,
        request: Request,
        user_id: Optional[str],
        limit_config: Dict[str, Any],
    ) -> str:
        """构建速率限制键
        
        Args:
            request: 请求对象
            user_id: 用户ID
            limit_config: 限制配置
            
        Returns:
            限制键
        """
        # 基础键：端点 + 方法
        base_key = f"rate_limit:{request.url.path}:{request.method}"
        
        # 添加用户标识
        if user_id:
            identifier = f"user:{user_id}"
        else:
            # 使用IP地址作为匿名用户标识
            client_ip = request.client.host if request.client else "unknown"
            identifier = f"ip:{client_ip}"
        
        # 添加时间窗口
        current_window = int(time.time() / limit_config["period_seconds"])
        
        return f"{base_key}:{identifier}:{current_window}"
    
    async def _get_current_count(self, limit_key: str) -> int:
        """获取当前计数
        
        Args:
            limit_key: 限制键
            
        Returns:
            当前计数
        """
        try:
            count = await cache.get(limit_key)
            return int(count) if count else 0
        except Exception as e:
            logger.warning(f"获取速率限制计数失败: {limit_key}, 错误: {e}")
            return 0
    
    async def _increment_count(self, limit_key: str, limit_config: Dict[str, Any]):
        """增加计数
        
        Args:
            limit_key: 限制键
            limit_config: 限制配置
        """
        try:
            # 使用Redis的INCR命令
            current = await cache._redis_client.incr(limit_key)
            
            # 如果是第一次设置，设置过期时间
            if current == 1:
                await cache._redis_client.expire(
                    limit_key, 
                    limit_config["period_seconds"],
                )
                
        except Exception as e:
            logger.warning(f"增加速率限制计数失败: {limit_key}, 错误: {e}")
    
    async def _get_retry_after(self, limit_key: str, limit_config: Dict[str, Any]) -> int:
        """获取重试等待时间
        
        Args:
            limit_key: 限制键
            limit_config: 限制配置
            
        Returns:
            重试等待时间（秒）
        """
        try:
            # 获取键的剩余生存时间
            ttl = await cache._redis_client.ttl(limit_key)
            
            if ttl > 0:
                return ttl
            else:
                return limit_config["period_seconds"]
                
        except Exception as e:
            logger.warning(f"获取重试时间失败: {limit_key}, 错误: {e}")
            return limit_config["period_seconds"]
    
    async def get_rate_limit_info(
        self,
        request: Request,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取速率限制信息
        
        Args:
            request: 请求对象
            user_id: 用户ID
            
        Returns:
            速率限制信息
        """
        if not self.enabled:
            return {"enabled": False}
        
        try:
            endpoint = request.url.path
            limit_config = self.get_limit_for_endpoint(endpoint)
            
            if not limit_config:
                return {"enabled": True, "limit": None}
            
            limit_key = self._build_limit_key(request, user_id, limit_config)
            current_count = await self._get_current_count(limit_key)
            
            return {
                "enabled": True,
                "limit": limit_config["original"],
                "current": current_count,
                "remaining": max(0, limit_config["count"] - current_count),
                "endpoint": endpoint,
                "user_id": user_id,
            }
            
        except Exception as e:
            logger.error(f"获取速率限制信息失败: {e}")
            return {"enabled": True, "error": str(e)}


# 全局速率限制器实例
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """速率限制中间件
    
    Args:
        request: 请求对象
        call_next: 下一个中间件或路由处理函数
        
    Returns:
        响应对象
    """
    try:
        # 获取用户ID（如果已认证）
        user_id = None
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = security.extract_user_id_from_token(token)
        
        # 检查速率限制
        await rate_limiter.check_rate_limit(request, user_id)
        
        # 处理请求
        response = await call_next(request)
        
        # 添加速率限制头信息
        if rate_limiter.enabled:
            limit_info = await rate_limiter.get_rate_limit_info(request, user_id)
            
            if limit_info.get("limit"):
                response.headers["X-RateLimit-Limit"] = str(limit_info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(
                    int(time.time() + limit_info.get("reset_after", 60))
                )
        
        return response
        
    except RateLimitExceededError as e:
        # 速率限制超出
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": e.message,
                    "details": e.details,
                },
            },
        )
        
        # 添加重试头信息
        if e.details and "retry_after" in e.details:
            response.headers["Retry-After"] = str(e.details["retry_after"])
        
        return response
        
    except Exception as e:
        # 其他异常，继续传递
        logger.error(f"速率限制中间件异常: {e}")
        return await call_next(request)


# 依赖注入函数
async def check_rate_limit_dependency(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """检查速率限制的依赖注入函数
    
    Args:
        request: 请求对象
        current_user: 当前用户（可选）
        
    Raises:
        RateLimitExceededError: 速率限制超出
    """
    user_id = current_user["id"] if current_user else None
    
    if not rate_limiter.enabled:
        return
    
    try:
        await rate_limiter.check_rate_limit(request, user_id)
    except RateLimitExceededError as e:
        # 添加更多上下文信息
        e.details = e.details or {}
        e.details.update({
            "user_id": user_id,
            "endpoint": request.url.path,
            "method": request.method,
        })
        raise


# 测试端点
if settings.is_development:
    
    @router.get("/rate-limit/test")
    async def test_rate_limit(
        request: Request,
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    ):
        """测试速率限制（仅开发环境）"""
        user_id = current_user["id"] if current_user else None
        
        info = await rate_limiter.get_rate_limit_info(request, user_id)
        
        return {
            "rate_limit": info,
            "note": "仅用于开发测试",
            "current_user": current_user,
        }