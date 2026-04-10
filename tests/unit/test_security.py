"""测试安全模块"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from src.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    verify_token,
    get_current_user,
    get_current_active_user,
    get_current_superuser,
)
from src.schemas.v1.user import UserInDB
from src.core.exceptions import CredentialsException


class TestPasswordSecurity:
    """测试密码安全函数"""
    
    def test_password_hashing_and_verification(self):
        """测试密码哈希和验证"""
        plain_password = "TestPassword123!"
        
        # 哈希密码
        hashed_password = get_password_hash(plain_password)
        
        # 验证哈希密码应该成功
        assert verify_password(plain_password, hashed_password) is True
        
        # 错误的密码应该失败
        assert verify_password("WrongPassword", hashed_password) is False
        
    def test_different_passwords_generate_different_hashes(self):
        """测试不同密码生成不同哈希"""
        password1 = "Password1"
        password2 = "Password2"
        
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)
        
        assert hash1 != hash2
        
    def test_same_password_different_salts(self):
        """测试相同密码但不同盐值生成不同哈希"""
        password = "SamePassword"
        
        # 理论上相同密码每次哈希应该不同（因为随机盐值）
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # 虽然哈希值不同，但应该都能验证
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenSecurity:
    """测试令牌安全函数"""
    
    def test_create_access_token(self):
        """测试创建访问令牌"""
        data = {"sub": "testuser@example.com"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        
    def test_create_token_with_expires_delta(self):
        """测试带过期时间的令牌创建"""
        data = {"sub": "testuser@example.com"}
        expires_delta = timedelta(minutes=15)
        
        token = create_access_token(data, expires_delta=expires_delta)
        
        assert token is not None
        
    def test_verify_valid_token(self):
        """测试验证有效令牌"""
        data = {"sub": "testuser@example.com", "scopes": ["user"]}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload.get("sub") == "testuser@example.com"
        assert payload.get("scopes") == ["user"]
        
    def test_verify_invalid_token(self):
        """测试验证无效令牌"""
        invalid_token = "invalid.token.here"
        
        payload = verify_token(invalid_token)
        
        # 无效令牌应该返回None
        assert payload is None
        
    def test_verify_expired_token(self):
        """测试验证过期令牌"""
        data = {"sub": "testuser@example.com"}
        
        # 创建过期令牌（过期时间为过去）
        with patch('src.core.security.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime.utcnow() - timedelta(hours=1)
            token = create_access_token(data)
        
        # 现在时间恢复正常
        payload = verify_token(token)
        
        # 过期令牌应该返回None
        assert payload is None
        
    def test_token_with_additional_data(self):
        """测试包含额外数据的令牌"""
        data = {
            "sub": "testuser@example.com",
            "user_id": 123,
            "username": "testuser",
            "role": "admin"
        }
        
        token = create_access_token(data)
        payload = verify_token(token)
        
        assert payload.get("user_id") == 123
        assert payload.get("username") == "testuser"
        assert payload.get("role") == "admin"


class TestAuthentication:
    """测试认证函数"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """测试使用有效令牌获取当前用户"""
        test_user_data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": get_password_hash("password"),
            "is_active": True,
            "is_superuser": False,
        }
        
        # 创建测试用户
        test_user = UserInDB(**test_user_data)
        
        # 创建令牌
        token = create_access_token({"sub": "test@example.com"})
        
        # Mock数据库查询
        with patch('src.core.security.get_db') as mock_get_db:
            mock_session = AsyncMock()
            mock_query = AsyncMock()
            mock_query.filter = MagicMock(return_value=mock_query)
            mock_query.first = AsyncMock(return_value=test_user)
            
            mock_session.query = MagicMock(return_value=mock_query)
            mock_get_db.return_value = mock_session
            
            # 获取当前用户
            user = await get_current_user(token)
            
            assert user is not None
            assert user.id == 1
            assert user.username == "testuser"
            assert user.email == "test@example.com"
            
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """测试使用无效令牌获取当前用户"""
        invalid_token = "invalid.token"
        
        with pytest.raises(CredentialsException):
            await get_current_user(invalid_token)
            
    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self):
        """测试用户不存在的情况"""
        token = create_access_token({"sub": "nonexistent@example.com"})
        
        # Mock数据库查询返回None
        with patch('src.core.security.get_db') as mock_get_db:
            mock_session = AsyncMock()
            mock_query = AsyncMock()
            mock_query.filter = MagicMock(return_value=mock_query)
            mock_query.first = AsyncMock(return_value=None)
            
            mock_session.query = MagicMock(return_value=mock_query)
            mock_get_db.return_value = mock_session
            
            with pytest.raises(CredentialsException):
                await get_current_user(token)
                
    @pytest.mark.asyncio
    async def test_get_current_active_user(self):
        """测试获取当前活跃用户"""
        test_user_data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": get_password_hash("password"),
            "is_active": True,
            "is_superuser": False,
        }
        
        test_user = UserInDB(**test_user_data)
        
        # Mock get_current_user
        with patch('src.core.security.get_current_user', AsyncMock(return_value=test_user)):
            active_user = await get_current_active_user()
            
            assert active_user is not None
            assert active_user.is_active is True
            
    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """测试获取非活跃用户"""
        test_user_data = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": get_password_hash("password"),
            "is_active": False,  # 非活跃用户
            "is_superuser": False,
        }
        
        test_user = UserInDB(**test_user_data)
        
        # Mock get_current_user
        with patch('src.core.security.get_current_user', AsyncMock(return_value=test_user)):
            with pytest.raises(CredentialsException):
                await get_current_active_user()
                
    @pytest.mark.asyncio
    async def test_get_current_superuser(self):
        """测试获取超级用户"""
        test_user_data = {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "hashed_password": get_password_hash("password"),
            "is_active": True,
            "is_superuser": True,  # 超级用户
        }
        
        test_user = UserInDB(**test_user_data)
        
        # Mock get_current_active_user
        with patch('src.core.security.get_current_active_user', AsyncMock(return_value=test_user)):
            superuser = await get_current_superuser()
            
            assert superuser is not None
            assert superuser.is_superuser is True
            
    @pytest.mark.asyncio
    async def test_get_current_superuser_not_superuser(self):
        """测试获取非超级用户"""
        test_user_data = {
            "id": 1,
            "username": "regular",
            "email": "regular@example.com",
            "hashed_password": get_password_hash("password"),
            "is_active": True,
            "is_superuser": False,  # 非超级用户
        }
        
        test_user = UserInDB(**test_user_data)
        
        # Mock get_current_active_user
        with patch('src.core.security.get_current_active_user', AsyncMock(return_value=test_user)):
            with pytest.raises(CredentialsException):
                await get_current_superuser()