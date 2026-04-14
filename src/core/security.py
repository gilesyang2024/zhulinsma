"""
安全模块

提供用户认证、授权、密码哈希和JWT令牌管理功能。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from .config import settings

logger = logging.getLogger(__name__)


# 密码哈希上下文
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # 适当增加轮数以增强安全性
)

# OAuth2密码流
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,  # 允许可选认证
)


class SecurityError(Exception):
    """安全相关异常"""
    pass


class TokenPayload:
    """JWT令牌载荷"""
    
    def __init__(
        self,
        sub: str,
        exp: datetime,
        iat: datetime,
        type: str = "access",
        **kwargs,
    ):
        self.sub = sub  # 主题（用户ID）
        self.exp = exp  # 过期时间
        self.iat = iat  # 签发时间
        self.type = type  # 令牌类型
        self.extra = kwargs  # 额外数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "sub": self.sub,
            "exp": self.exp,
            "iat": self.iat,
            "type": self.type,
        }
        data.update(self.extra)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        """从字典创建"""
        return cls(
            sub=data["sub"],
            exp=data["exp"],
            iat=data["iat"],
            type=data.get("type", "access"),
            **{k: v for k, v in data.items() if k not in ["sub", "exp", "iat", "type"]},
        )


class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        """初始化安全管理器"""
        self._jwt_secret_key = settings.JWT_SECRET_KEY
        self._jwt_algorithm = settings.JWT_ALGORITHM
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码
        
        Args:
            plain_password: 明文密码
            hashed_password: 哈希密码
            
        Returns:
            bool: 密码是否匹配
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """生成密码哈希
        
        Args:
            password: 明文密码
            
        Returns:
            str: 密码哈希值
        """
        try:
            return pwd_context.hash(password)
        except Exception as e:
            logger.error(f"密码哈希生成失败: {e}")
            raise SecurityError(f"密码处理失败: {e}")
    
    def create_access_token(
        self,
        user_id: Union[str, UUID],
        expires_delta: Optional[timedelta] = None,
        **extra_data,
    ) -> str:
        """创建访问令牌
        
        Args:
            user_id: 用户ID
            expires_delta: 过期时间偏移量
            **extra_data: 额外数据
            
        Returns:
            str: JWT访问令牌
        """
        try:
            # 计算过期时间
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(
                    minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
                )
            
            # 创建载荷
            payload = TokenPayload(
                sub=str(user_id),
                exp=expire,
                iat=datetime.utcnow(),
                type="access",
                **extra_data,
            )
            
            # 编码JWT
            encoded_jwt = jwt.encode(
                payload.to_dict(),
                self._jwt_secret_key,
                algorithm=self._jwt_algorithm,
            )
            
            logger.debug(f"创建访问令牌: user_id={user_id}")
            return encoded_jwt
            
        except Exception as e:
            logger.error(f"创建访问令牌失败: {e}")
            raise SecurityError(f"令牌创建失败: {e}")
    
    def create_refresh_token(
        self,
        user_id: Union[str, UUID],
        expires_delta: Optional[timedelta] = None,
        **extra_data,
    ) -> str:
        """创建刷新令牌
        
        Args:
            user_id: 用户ID
            expires_delta: 过期时间偏移量
            **extra_data: 额外数据
            
        Returns:
            str: JWT刷新令牌
        """
        try:
            # 计算过期时间
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            else:
                expire = datetime.utcnow() + timedelta(
                    days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
                )
            
            # 创建载荷
            payload = TokenPayload(
                sub=str(user_id),
                exp=expire,
                iat=datetime.utcnow(),
                type="refresh",
                **extra_data,
            )
            
            # 编码JWT
            encoded_jwt = jwt.encode(
                payload.to_dict(),
                self._jwt_secret_key,
                algorithm=self._jwt_algorithm,
            )
            
            logger.debug(f"创建刷新令牌: user_id={user_id}")
            return encoded_jwt
            
        except Exception as e:
            logger.error(f"创建刷新令牌失败: {e}")
            raise SecurityError(f"刷新令牌创建失败: {e}")
    
    def verify_token(self, token: str) -> TokenPayload:
        """验证JWT令牌
        
        Args:
            token: JWT令牌
            
        Returns:
            TokenPayload: 令牌载荷
            
        Raises:
            HTTPException: 令牌无效或过期
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭证无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # 解码JWT
            payload_dict = jwt.decode(
                token,
                self._jwt_secret_key,
                algorithms=[self._jwt_algorithm],
            )
            
            # 验证令牌类型
            token_type = payload_dict.get("type")
            if token_type not in ["access", "refresh"]:
                logger.warning(f"无效令牌类型: {token_type}")
                raise credentials_exception
            
            # 验证过期时间
            exp_timestamp = payload_dict.get("exp")
            if exp_timestamp is None:
                logger.warning("令牌缺少过期时间")
                raise credentials_exception
            
            # 转换为TokenPayload对象
            payload = TokenPayload.from_dict(payload_dict)
            
            # 验证主题（用户ID）
            if payload.sub is None:
                logger.warning("令牌缺少用户ID")
                raise credentials_exception
            
            logger.debug(f"验证令牌成功: user_id={payload.sub}, type={token_type}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("令牌已过期")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已过期",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError as e:
            logger.warning(f"令牌验证失败: {e}")
            raise credentials_exception
        except Exception as e:
            logger.error(f"令牌处理异常: {e}")
            raise credentials_exception
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """使用刷新令牌获取新的访问令牌
        
        Args:
            refresh_token: 刷新令牌
            
        Returns:
            str: 新的访问令牌
            
        Raises:
            HTTPException: 刷新令牌无效
        """
        try:
            # 验证刷新令牌
            payload = self.verify_token(refresh_token)
            
            # 确保是刷新令牌
            if payload.type != "refresh":
                logger.warning(f"非刷新令牌: type={payload.type}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的刷新令牌",
                )
            
            # 创建新的访问令牌
            new_access_token = self.create_access_token(
                user_id=payload.sub,
                **payload.extra,
            )
            
            logger.debug(f"刷新访问令牌: user_id={payload.sub}")
            return new_access_token
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"刷新令牌失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌失败",
            )
    
    def extract_user_id_from_token(self, token: str) -> Optional[str]:
        """从令牌中提取用户ID（不验证令牌）
        
        Args:
            token: JWT令牌
            
        Returns:
            用户ID或None
        """
        try:
            # 解码但不验证（用于日志等场景）
            payload_dict = jwt.decode(
                token,
                self._jwt_secret_key,
                algorithms=[self._jwt_algorithm],
                options={"verify_signature": False},
            )
            
            return payload_dict.get("sub")
        except Exception as e:
            logger.debug(f"提取用户ID失败: {e}")
            return None
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """验证密码强度
        
        Args:
            password: 密码
            
        Returns:
            包含验证结果和信息的字典
        """
        errors = []
        warnings = []
        
        # 长度检查
        if len(password) < 8:
            errors.append("密码至少需要8个字符")
        elif len(password) < 12:
            warnings.append("建议使用12个字符以上的密码")
        
        # 复杂度检查
        if not any(c.isupper() for c in password):
            errors.append("密码必须包含至少一个大写字母")
        
        if not any(c.islower() for c in password):
            errors.append("密码必须包含至少一个小写字母")
        
        if not any(c.isdigit() for c in password):
            errors.append("密码必须包含至少一个数字")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?`~" for c in password):
            warnings.append("建议包含特殊字符以提高安全性")
        
        # 常见密码检查
        common_passwords = [
            "password", "123456", "qwerty", "admin", "welcome",
            "123456789", "12345678", "12345", "1234567",
        ]
        
        if password.lower() in common_passwords:
            errors.append("密码过于常见，请使用更复杂的密码")
        
        # 结果
        is_valid = len(errors) == 0
        score = max(0, min(100, 
            20 * (len(password) >= 8) +
            20 * (any(c.isupper() for c in password)) +
            20 * (any(c.islower() for c in password)) +
            20 * (any(c.isdigit() for c in password)) +
            20 * (any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?`~" for c in password))
        ))
        
        return {
            "is_valid": is_valid,
            "score": score,
            "errors": errors,
            "warnings": warnings,
            "strength": self._get_strength_label(score),
        }
    
    def _get_strength_label(self, score: int) -> str:
        """获取密码强度标签"""
        if score >= 80:
            return "非常强"
        elif score >= 60:
            return "强"
        elif score >= 40:
            return "中等"
        elif score >= 20:
            return "弱"
        else:
            return "非常弱"


# 全局安全管理器实例
security = SecurityManager()


# 依赖注入函数
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """获取当前认证用户
    
    Args:
        token: JWT令牌
        
    Returns:
        用户信息字典
        
    Raises:
        HTTPException: 认证失败
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # 验证令牌
        payload = security.verify_token(token)
        
        # 确保是访问令牌
        if payload.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌类型",
            )
        
        # 返回用户信息（这里需要从数据库获取完整用户信息）
        # 实际应用中，这里应该从数据库或缓存获取用户信息
        user_info = {
            "id": payload.sub,
            "token_payload": payload.to_dict(),
        }
        
        return user_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户认证失败",
        )


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[Dict[str, Any]]:
    """获取当前认证用户（可选）
    
    Args:
        token: JWT令牌
        
    Returns:
        用户信息字典或None
    """
    if token is None:
        return None
    
    try:
        return await get_current_user(token)
    except HTTPException:
        return None


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """要求管理员权限
    
    Args:
        user: 当前用户
        
    Returns:
        用户信息
        
    Raises:
        HTTPException: 非管理员用户
    """
    # 这里需要检查用户角色
    # 实际应用中，应该从用户信息中检查角色
    is_admin = False  # 暂时硬编码，实际应从数据库获取
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    
    return user


# 密码验证函数
def validate_password_complexity(password: str) -> None:
    """验证密码复杂度
    
    Args:
        password: 密码
        
    Raises:
        HTTPException: 密码不符合要求
    """
    validation = security.validate_password_strength(password)
    
    if not validation["is_valid"]:
        errors = ", ".join(validation["errors"])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"密码不符合要求: {errors}",
        )


# 健康检查函数
async def check_security_health() -> Dict[str, Any]:
    """检查安全模块健康状态
    
    Returns:
        健康状态信息
    """
    try:
        # 测试密码哈希
        test_password = "test_password_123"
        hashed = security.get_password_hash(test_password)
        is_valid = security.verify_password(test_password, hashed)
        
        # 测试JWT令牌
        test_user_id = "test-user-id"
        access_token = security.create_access_token(test_user_id)
        refresh_token = security.create_refresh_token(test_user_id)
        
        # 验证令牌
        access_payload = security.verify_token(access_token)
        refresh_payload = security.verify_token(refresh_token)
        
        return {
            "status": "healthy",
            "message": "安全模块运行正常",
            "password_hashing": is_valid,
            "jwt_tokens": {
                "access_token_valid": access_payload.sub == test_user_id,
                "refresh_token_valid": refresh_payload.sub == test_user_id,
            },
        }
        
    except Exception as e:
        logger.error(f"安全模块健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "message": f"安全模块异常: {str(e)}",
        }


async def get_current_superuser(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    获取当前超级管理员用户
    
    Args:
        user: 当前用户
        
    Returns:
        超级管理员用户信息
        
    Raises:
        HTTPException: 不是超级管理员
    """
    if not user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return user