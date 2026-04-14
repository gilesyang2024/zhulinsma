"""
存储系统数据模型
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, 
    Index, Integer, JSON, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

from src.core.database import Base
from .base import FileCategory, StorageType

# ====== 数据模型 ======

class StorageProvider(Base):
    """存储提供商配置数据模型"""
    __tablename__ = "storage_providers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, comment="提供商名称")
    type = Column(String(50), nullable=False, comment="存储类型")
    config = Column(JSON, nullable=False, comment="存储配置")
    
    # 状态信息
    enabled = Column(Boolean, default=True, comment="是否启用")
    is_default = Column(Boolean, default=False, comment="是否默认存储")
    health_status = Column(String(50), default="unknown", comment="健康状态")
    last_health_check = Column(DateTime, nullable=True, comment="最后健康检查时间")
    
    # 统计信息
    total_files = Column(Integer, default=0, comment="总文件数")
    total_size = Column(BigInteger, default=0, comment="总文件大小(字节)")
    used_percent = Column(Float, default=0.0, comment="使用百分比")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "health_status": self.health_status,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "used_percent": self.used_percent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class FileMetadata(Base):
    """文件元数据数据模型"""
    __tablename__ = "file_metadata"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_key = Column(String(1024), nullable=False, comment="文件键")
    storage_provider_id = Column(String(36), nullable=False, comment="存储提供商ID")
    
    # 文件信息
    filename = Column(String(255), nullable=False, comment="文件名")
    size = Column(BigInteger, nullable=False, comment="文件大小(字节)")
    content_type = Column(String(255), nullable=True, comment="内容类型")
    file_category = Column(String(50), default=FileCategory.OTHER.value, comment="文件分类")
    md5_hash = Column(String(32), nullable=True, comment="MD5哈希")
    sha256_hash = Column(String(64), nullable=True, comment="SHA256哈希")
    
    # 元数据
    metadata = Column(JSON, default=dict, comment="文件元数据")
    tags = Column(JSON, default=list, comment="文件标签")
    
    # 访问信息
    uploader_id = Column(String(36), nullable=True, comment="上传者ID")
    upload_ip = Column(String(45), nullable=True, comment="上传IP地址")
    access_count = Column(Integer, default=0, comment="访问次数")
    last_access = Column(DateTime, nullable=True, comment="最后访问时间")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 索引
    __table_args__ = (
        Index('idx_file_key', 'file_key'),
        Index('idx_storage_provider', 'storage_provider_id'),
        Index('idx_file_category', 'file_category'),
        Index('idx_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "file_key": self.file_key,
            "storage_provider_id": self.storage_provider_id,
            "filename": self.filename,
            "size": self.size,
            "content_type": self.content_type,
            "file_category": self.file_category,
            "md5_hash": self.md5_hash,
            "sha256_hash": self.sha256_hash,
            "metadata": self.metadata,
            "tags": self.tags,
            "uploader_id": self.uploader_id,
            "upload_ip": self.upload_ip,
            "access_count": self.access_count,
            "last_access": self.last_access.isoformat() if self.last_access else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# ====== 响应模型 ======

class StorageProviderResponse:
    """存储提供商响应模型"""
    
    def __init__(self, provider: StorageProvider):
        self.id = provider.id
        self.name = provider.name
        self.type = provider.type
        self.enabled = provider.enabled
        self.is_default = provider.is_default
        self.health_status = provider.health_status
        self.total_files = provider.total_files
        self.total_size = provider.total_size
        self.used_percent = provider.used_percent
        self.created_at = provider.created_at
        self.updated_at = provider.updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "health_status": self.health_status,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "used_percent": self.used_percent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class FileMetadataResponse:
    """文件元数据响应模型"""
    
    def __init__(self, metadata: FileMetadata):
        self.id = metadata.id
        self.file_key = metadata.file_key
        self.storage_provider_id = metadata.storage_provider_id
        self.filename = metadata.filename
        self.size = metadata.size
        self.content_type = metadata.content_type
        self.file_category = metadata.file_category
        self.md5_hash = metadata.md5_hash
        self.sha256_hash = metadata.sha256_hash
        self.metadata = metadata.metadata
        self.tags = metadata.tags
        self.uploader_id = metadata.uploader_id
        self.upload_ip = metadata.upload_ip
        self.access_count = metadata.access_count
        self.last_access = metadata.last_access
        self.created_at = metadata.created_at
        self.updated_at = metadata.updated_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "file_key": self.file_key,
            "storage_provider_id": self.storage_provider_id,
            "filename": self.filename,
            "size": self.size,
            "content_type": self.content_type,
            "file_category": self.file_category,
            "md5_hash": self.md5_hash,
            "sha256_hash": self.sha256_hash,
            "metadata": self.metadata,
            "tags": self.tags,
            "uploader_id": self.uploader_id,
            "upload_ip": self.upload_ip,
            "access_count": self.access_count,
            "last_access": self.last_access.isoformat() if self.last_access else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# ====== 工具函数 ======

async def create_default_storage_provider(db: AsyncSession) -> Optional[StorageProvider]:
    """创建默认存储提供商"""
    try:
        from .base import StorageConfig, StorageType
        
        # 检查是否已存在默认提供商
        from sqlalchemy import select
        stmt = select(StorageProvider).where(StorageProvider.is_default == True)
        result = await db.execute(stmt)
        existing_default = result.scalar_one_or_none()
        
        if existing_default:
            return existing_default
        
        # 创建默认本地存储配置
        default_config = StorageConfig(
            type=StorageType.LOCAL,
            name="default-local-storage",
            base_path="./storage",
            is_default=True,
            enabled=True
        )
        
        provider = StorageProvider(
            id=str(uuid.uuid4()),
            name=default_config.name,
            type=default_config.type.value,
            config=default_config.dict(),
            enabled=True,
            is_default=True,
            health_status="unknown"
        )
        
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        
        return provider
        
    except Exception as e:
        print(f"创建默认存储提供商失败: {str(e)}")
        await db.rollback()
        return None

async def migrate_files(
    db: AsyncSession,
    source_provider_id: str,
    dest_provider_id: str,
    batch_size: int = 100
) -> Dict[str, Any]:
    """迁移文件从一个提供商到另一个提供商"""
    try:
        from sqlalchemy import select
        from .manager import StorageManager
        
        # 获取文件列表
        stmt = select(FileMetadata).where(
            FileMetadata.storage_provider_id == source_provider_id
        ).limit(batch_size)
        
        result = await db.execute(stmt)
        files = result.scalars().all()
        
        if not files:
            return {
                "success": True,
                "message": "没有需要迁移的文件",
                "migrated_count": 0,
                "failed_count": 0
            }
        
        # 初始化存储管理器
        manager = StorageManager(db)
        await manager.initialize()
        
        # 迁移文件
        migrated_count = 0
        failed_count = 0
        failed_files = []
        
        for file_meta in files:
            try:
                # 下载源文件
                download_result = await manager.download(
                    file_meta.file_key,
                    source_provider_id
                )
                
                if not download_result.success:
                    failed_count += 1
                    failed_files.append({
                        "file_key": file_meta.file_key,
                        "error": f"下载失败: {download_result.error}"
                    })
                    continue
                
                # 上传到目标提供商
                upload_result = await manager.upload(
                    key=file_meta.file_key,
                    data=download_result.data,
                    content_type=download_result.content_type,
                    provider_id=dest_provider_id,
                    metadata=file_meta.metadata
                )
                
                if upload_result.success:
                    # 更新文件元数据
                    file_meta.storage_provider_id = dest_provider_id
                    migrated_count += 1
                else:
                    failed_count += 1
                    failed_files.append({
                        "file_key": file_meta.file_key,
                        "error": f"上传失败: {upload_result.error}"
                    })
                    
            except Exception as e:
                failed_count += 1
                failed_files.append({
                    "file_key": file_meta.file_key,
                    "error": str(e)
                })
        
        # 提交更改
        await db.commit()
        
        return {
            "success": True,
            "message": f"文件迁移完成: {migrated_count} 成功, {failed_count} 失败",
            "migrated_count": migrated_count,
            "failed_count": failed_count,
            "failed_files": failed_files,
            "has_more": len(files) >= batch_size
        }
        
    except Exception as e:
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "migrated_count": 0,
            "failed_count": 0
        }