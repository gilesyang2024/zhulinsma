import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

# 全局测试配置
TEST_CONFIG = {
    "DATABASE_URL": "sqlite+aiosqlite:///./test.db",
    "TEST_MODE": True,
    "DEBUG": True,
}

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """为异步测试创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境"""
    import os
    os.environ.update({
        key: str(value) for key, value in TEST_CONFIG.items()
    })
    yield
    # 测试后清理

@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    
    # 模拟查询链式调用
    query_mock = MagicMock()
    query_mock.filter = MagicMock(return_value=query_mock)
    query_mock.first = AsyncMock()
    query_mock.all = AsyncMock()
    query_mock.offset = MagicMock(return_value=query_mock)
    query_mock.limit = MagicMock(return_value=query_mock)
    query_mock.order_by = MagicMock(return_value=query_mock)
    
    session.query = MagicMock(return_value=query_mock)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    
    return session

@pytest.fixture
def mock_fastapi_request():
    """模拟FastAPI请求"""
    request = MagicMock()
    request.headers = {}
    request.cookies = {}
    request.query_params = {}
    request.path_params = {}
    request.client = MagicMock(host="test.example.com")
    return request

@pytest.fixture
def sample_user_data():
    """提供示例用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "phone": "+861234567890",
        "is_active": True,
        "is_superuser": False,
    }

@pytest.fixture
def sample_content_data():
    """提供示例内容数据"""
    return {
        "title": "测试内容标题",
        "content": "这是测试内容正文，用于单元测试。",
        "content_type": "article",
        "status": "published",
        "tags": ["测试", "文章"],
        "category": "技术",
    }

@pytest.fixture
def mock_redis_client():
    """模拟Redis客户端"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=False)
    return redis_mock

def pytest_configure(config):
    """pytest配置钩子"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "database: Tests requiring database")
    config.addinivalue_line("markers", "auth: Authentication related tests")