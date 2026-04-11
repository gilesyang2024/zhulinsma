"""
UUID兼容性模块
解决SQLite不支持PostgreSQL UUID类型的问题

提供：
1. 跨数据库的UUID类型定义
2. UUID与字符串的转换函数
3. 自动检测数据库类型并选择合适的UUID实现
"""

import uuid
from typing import Any, Optional, Union
from sqlalchemy import types, Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects import postgresql, sqlite
import logging

logger = logging.getLogger(__name__)


class GUID(TypeDecorator):
    """
    跨数据库的UUID类型实现
    
    支持：
    - PostgreSQL: 使用原生UUID类型
    - SQLite: 存储为16字节二进制或32字符十六进制字符串
    - 其他数据库: 存储为36字符字符串
    """
    
    impl = CHAR
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_postgres = False
        self._is_sqlite = False

    def load_dialect_impl(self, dialect):
        """根据数据库方言选择合适的类型实现"""
        if dialect.name == "postgresql":
            # PostgreSQL使用原生UUID类型
            self._is_postgres = True
            return dialect.type_descriptor(PG_UUID())
        elif dialect.name == "sqlite":
            # SQLite使用BLOB存储二进制UUID
            self._is_sqlite = True
            return dialect.type_descriptor(BLOB())
        else:
            # 其他数据库使用CHAR(32)存储十六进制字符串
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: Optional[Union[uuid.UUID, str, bytes]], dialect):
        """将Python值转换为数据库值"""
        if value is None:
            return None

        if isinstance(value, bytes):
            # 已经是二进制格式
            if self._is_sqlite:
                return value  # SQLite直接存储二进制
            elif self._is_postgres:
                return uuid.UUID(bytes=value)  # PostgreSQL转换为UUID对象
            else:
                return value.hex()  # 其他数据库转换为十六进制字符串

        if isinstance(value, str):
            # 字符串转换为UUID对象
            try:
                value = uuid.UUID(value)
            except ValueError:
                # 尝试去掉可能的前缀
                if value.startswith(('uuid:', 'urn:uuid:')):
                    value = uuid.UUID(value.split(':')[-1])
                else:
                    raise ValueError(f"无效的UUID字符串: {value}")

        if isinstance(value, uuid.UUID):
            if self._is_postgres:
                # PostgreSQL返回UUID对象
                return value
            elif self._is_sqlite:
                # SQLite返回二进制格式
                return value.bytes
            else:
                # 其他数据库返回十六进制字符串
                return value.hex

        raise TypeError(f"不支持的UUID类型: {type(value)}")

    def process_result_value(self, value, dialect):
        """将数据库值转换为Python UUID对象"""
        if value is None:
            return None

        if self._is_postgres:
            # PostgreSQL直接返回UUID对象
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        
        elif self._is_sqlite:
            # SQLite从二进制恢复UUID
            if isinstance(value, bytes):
                return uuid.UUID(bytes=value)
            elif isinstance(value, str):
                return uuid.UUID(value)
            else:
                raise ValueError(f"SQLite中的无效UUID值: {type(value)}")
        
        else:
            # 其他数据库从十六进制字符串恢复UUID
            if isinstance(value, str):
                if len(value) == 32:
                    # 无连字符的十六进制字符串
                    return uuid.UUID(hex=value)
                elif len(value) == 36:
                    # 有连字符的标准UUID字符串
                    return uuid.UUID(value)
                else:
                    raise ValueError(f"无效的UUID字符串长度: {len(value)}")
            elif isinstance(value, bytes):
                # 二进制格式
                return uuid.UUID(bytes=value)
            else:
                raise ValueError(f"不支持的UUID存储格式: {type(value)}")

    def __repr__(self):
        return "GUID()"


def create_uuid() -> uuid.UUID:
    """创建新的UUID"""
    return uuid.uuid4()


def uuid_to_str(uuid_obj: uuid.UUID) -> str:
    """将UUID对象转换为字符串"""
    return str(uuid_obj)


def str_to_uuid(uuid_str: str) -> uuid.UUID:
    """将字符串转换为UUID对象"""
    return uuid.UUID(uuid_str)


def bytes_to_uuid(uuid_bytes: bytes) -> uuid.UUID:
    """将字节转换为UUID对象"""
    return uuid.UUID(bytes=uuid_bytes)


def uuid_to_bytes(uuid_obj: uuid.UUID) -> bytes:
    """将UUID对象转换为字节"""
    return uuid_obj.bytes


def is_valid_uuid(value: Union[str, uuid.UUID, bytes]) -> bool:
    """检查是否为有效的UUID"""
    try:
        if isinstance(value, str):
            uuid.UUID(value)
        elif isinstance(value, bytes):
            uuid.UUID(bytes=value)
        elif isinstance(value, uuid.UUID):
            return True
        else:
            return False
        return True
    except (ValueError, TypeError):
        return False


class UUIDModelMixin:
    """UUID模型混入类，为模型提供UUID相关功能"""
    
    @property
    def uuid_str(self) -> str:
        """获取UUID字符串表示"""
        if hasattr(self, 'id'):
            return str(self.id)
        raise AttributeError("模型没有id属性")

    @classmethod
    def generate_id(cls) -> uuid.UUID:
        """生成新的UUID ID"""
        return create_uuid()


# 全局UUID兼容性配置
UUID_COMPAT = {
    "type": GUID,  # 默认使用GUID类型
    "postgresql": PG_UUID,  # PostgreSQL专用类型
    "sqlite": GUID,  # SQLite使用GUID
    "default": GUID,  # 默认使用GUID
}


def get_uuid_type(dialect_name: str = None) -> Any:
    """
    根据数据库方言获取合适的UUID类型
    
    Args:
        dialect_name: 数据库方言名称（postgresql, sqlite, mysql等）
        
    Returns:
        合适的UUID类型类
    """
    if dialect_name:
        return UUID_COMPAT.get(dialect_name, UUID_COMPAT["default"])
    return UUID_COMPAT["type"]


def setup_uuid_compatibility(dialect_name: str = None):
    """
    设置UUID兼容性配置
    
    Args:
        dialect_name: 当前数据库方言
        
    Returns:
        dict: 配置字典
    """
    dialect = dialect_name or "default"
    uuid_type = get_uuid_type(dialect)
    
    config = {
        "dialect": dialect,
        "uuid_type": uuid_type,
        "supports_native_uuid": dialect == "postgresql",
        "storage_format": "native" if dialect == "postgresql" else ("binary" if dialect == "sqlite" else "hex")
    }
    
    logger.info(f"UUID兼容性配置: {config}")
    return config


# 测试函数
def test_uuid_compatibility():
    """测试UUID兼容性功能"""
    import tempfile
    import os
    from sqlalchemy import create_engine, MetaData, Table, Column
    from sqlalchemy.orm import Session
    
    # 测试UUID生成和转换
    test_uuid = create_uuid()
    print(f"生成的UUID: {test_uuid}")
    
    # 转换为字符串和字节
    uuid_str = uuid_to_str(test_uuid)
    uuid_bytes = uuid_to_bytes(test_uuid)
    
    print(f"UUID字符串: {uuid_str}")
    print(f"UUID字节长度: {len(uuid_bytes)}")
    
    # 验证转换
    assert str_to_uuid(uuid_str) == test_uuid
    assert bytes_to_uuid(uuid_bytes) == test_uuid
    
    # 测试有效性检查
    assert is_valid_uuid(test_uuid) == True
    assert is_valid_uuid(uuid_str) == True
    assert is_valid_uuid(uuid_bytes) == True
    assert is_valid_uuid("invalid-uuid") == False
    
    print("✓ UUID兼容性测试通过")
    
    # 测试SQLite兼容性
    temp_db = tempfile.mktemp(suffix=".db")
    try:
        # 创建SQLite引擎
        engine = create_engine(f"sqlite:///{temp_db}")
        
        # 创建测试表
        metadata = MetaData()
        test_table = Table(
            "test_uuid",
            metadata,
            Column("id", GUID(), primary_key=True),
            Column("name", String(50))
        )
        
        metadata.create_all(engine)
        
        # 插入数据
        with Session(engine) as session:
            session.execute(
                test_table.insert(),
                [
                    {"id": create_uuid(), "name": "Test 1"},
                    {"id": create_uuid(), "name": "Test 2"},
                ]
            )
            session.commit()
            
            # 查询数据
            result = session.execute(test_table.select()).fetchall()
            print(f"插入的记录数: {len(result)}")
            for row in result:
                print(f"  - ID: {row.id}, Name: {row.name}")
                assert isinstance(row.id, uuid.UUID)
        
        print("✓ SQLite UUID存储测试通过")
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_db):
            os.unlink(temp_db)


if __name__ == "__main__":
    # 运行测试
    test_uuid_compatibility()