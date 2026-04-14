"""
存储管理器
统一管理多个存储后端，提供统一的接口和策略
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from sqlalchemy import Column, String, JSON, DateTime, Boolean, Integer, Text, BigInteger, Float, Index, Enum as SQLEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.core.config import Settings
import logging
logger = logging.getLogger(__name__)

from .base import (
    StorageBackend, StorageConfig, StorageType,
    FileInfo, UploadResult, DownloadResult, FileCategory
)
from .local import LocalStorage
from .s3 import S3Storage
from .azure import AzureBlobStorage
from .google import GoogleCloudStorage

logger = logging.getLogger(__name__)

# ====== 数据模型 ======

class StorageProvider(Base):
    """存储提供商配置数据模型"""
    __tablename__ = "storage_providers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True, comment="提供商名称")
    type = Column(SQLEnum(StorageType), nullable=False, comment="存储类型")
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
            "type": self.type.value,
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
    file_category = Column(SQLEnum(FileCategory), default=FileCategory.OTHER, comment="文件分类")
    md5_hash = Column(String(32), nullable=True, comment="MD5哈希")
    sha256_hash = Column(String(64), nullable=True, comment="SHA256哈希")
    
    # 元数据
    extra_data = Column(JSON, default=dict, comment="文件元数据")
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
            "file_category": self.file_category.value,
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

# ====== 策略类 ======

class StoragePolicy(str, Enum):
    """存储策略"""
    DEFAULT = "default"          # 默认策略
    PERFORMANCE = "performance"  # 性能优先
    COST = "cost"               # 成本优先
    DURABILITY = "durability"   # 持久性优先
    GEO = "geo"                 # 地理分布优先

class StorageStrategy:
    """存储策略管理"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = Settings()
        
    async def select_provider(
        self,
        file_size: int,
        content_type: str,
        policy: StoragePolicy = StoragePolicy.DEFAULT,
        region_preference: Optional[str] = None
    ) -> Optional[StorageProvider]:
        """根据策略选择存储提供商"""
        from sqlalchemy import select
        
        # 获取所有启用的存储提供商
        stmt = select(StorageProvider).where(StorageProvider.enabled == True)
        result = await self.db.execute(stmt)
        providers = result.scalars().all()
        
        if not providers:
            return None
        
        # 根据策略选择
        if policy == StoragePolicy.DEFAULT:
            # 选择默认提供商
            for provider in providers:
                if provider.is_default:
                    return provider
            # 如果没有默认，选择第一个
            return providers[0]
        
        elif policy == StoragePolicy.PERFORMANCE:
            # 性能优先：选择延迟最低的
            # 这里简化处理，选择本地存储或最近的区域
            for provider in providers:
                if provider.type == StorageType.LOCAL:
                    return provider
            
            # 如果没有本地存储，根据区域偏好选择
            if region_preference:
                for provider in providers:
                    config = provider.config
                    if config.get('region') == region_preference:
                        return provider
            
            return providers[0]
        
        elif policy == StoragePolicy.COST:
            # 成本优先：选择成本最低的
            # 这里简化处理，选择本地存储
            for provider in providers:
                if provider.type == StorageType.LOCAL:
                    return provider
            
            # 按类型优先级：LOCAL < S3 < AZURE < GOOGLE
            type_priority = {
                StorageType.LOCAL: 1,
                StorageType.S3: 2,
                StorageType.AZURE: 3,
                StorageType.GOOGLE: 4
            }
            
            providers_sorted = sorted(providers, key=lambda p: type_priority.get(p.type, 99))
            return providers_sorted[0]
        
        elif policy == StoragePolicy.DURABILITY:
            # 持久性优先：选择可靠性最高的
            # 这里简化处理，选择云存储
            for provider in providers:
                if provider.type != StorageType.LOCAL:
                    return provider
            
            return providers[0]
        
        elif policy == StoragePolicy.GEO:
            # 地理分布优先：根据区域选择
            if region_preference:
                for provider in providers:
                    config = provider.config
                    if config.get('region') == region_preference:
                        return provider
            
            return providers[0]
        
        else:
            # 默认策略
            for provider in providers:
                if provider.is_default:
                    return provider
            return providers[0]

# ====== 存储管理器 ======

class StorageManager:
    """存储管理器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = Settings()
        self._backends: Dict[str, StorageBackend] = {}
        self._default_backend: Optional[StorageBackend] = None
        self._strategy = StorageStrategy(db)
        
    async def initialize(self) -> bool:
        """初始化存储管理器"""
        try:
            logger.info("开始初始化存储管理器")
            
            # 从数据库加载存储提供商配置
            from sqlalchemy import select
            stmt = select(StorageProvider).where(StorageProvider.enabled == True)
            result = await self.db.execute(stmt)
            providers = result.scalars().all()
            
            if not providers:
                logger.warning("没有找到启用的存储提供商")
                # 创建默认本地存储
                await self._create_default_provider()
                # 重新加载
                result = await self.db.execute(stmt)
                providers = result.scalars().all()
            
            # 初始化所有存储后端
            success_count = 0
            for provider in providers:
                try:
                    backend = await self._create_backend(provider)
                    if backend:
                        self._backends[provider.id] = backend
                        
                        # 设置默认后端
                        if provider.is_default:
                            self._default_backend = backend
                        
                        success_count += 1
                        logger.info(f"存储后端初始化成功: {provider.name} ({provider.type.value})")
                    else:
                        logger.error(f"存储后端初始化失败: {provider.name}")
                except Exception as e:
                    logger.error(f"初始化存储后端异常: {provider.name}, 错误: {str(e)}")
            
            # 如果没有默认后端，设置第一个为默认
            if not self._default_backend and self._backends:
                first_key = next(iter(self._backends))
                self._default_backend = self._backends[first_key]
                
                # 更新数据库
                provider_id = first_key
                stmt = select(StorageProvider).where(StorageProvider.id == provider_id)
                result = await self.db.execute(stmt)
                provider = result.scalar_one_or_none()
                if provider:
                    provider.is_default = True
                    await self.db.commit()
            
            logger.info(f"存储管理器初始化完成: {success_count}/{len(providers)} 个后端成功")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"存储管理器初始化失败: {str(e)}")
            return False
    
    async def _create_default_provider(self) -> None:
        """创建默认存储提供商"""
        try:
            import uuid
            
            # 创建默认本地存储配置
            default_config = StorageConfig(
                type=StorageType.LOCAL,
                name="default-local-storage",
                base_path="./storage",
                is_default=True
            )
            
            provider = StorageProvider(
                id=str(uuid.uuid4()),
                name=default_config.name,
                type=default_config.type,
                config=default_config.dict(),
                enabled=True,
                is_default=True,
                health_status="unknown"
            )
            
            self.db.add(provider)
            await self.db.commit()
            
            logger.info(f"默认存储提供商创建成功: {default_config.name}")
            
        except Exception as e:
            logger.error(f"创建默认存储提供商失败: {str(e)}")
            await self.db.rollback()
    
    async def _create_backend(self, provider: StorageProvider) -> Optional[StorageBackend]:
        """创建存储后端实例"""
        try:
            config_dict = provider.config
            if isinstance(config_dict, str):
                config_dict = json.loads(config_dict)
            
            config = StorageConfig(**config_dict)
            
            # 根据类型创建对应的后端
            if config.type == StorageType.LOCAL:
                backend = LocalStorage(config)
            elif config.type == StorageType.S3:
                backend = S3Storage(config)
            elif config.type == StorageType.AZURE:
                backend = AzureBlobStorage(config)
            elif config.type == StorageType.GOOGLE:
                backend = GoogleCloudStorage(config)
            else:
                logger.error(f"不支持的存储类型: {config.type}")
                return None
            
            # 初始化后端
            if await backend.initialize():
                return backend
            else:
                return None
            
        except Exception as e:
            logger.error(f"创建存储后端失败: {provider.name}, 错误: {str(e)}")
            return None
    
    # ====== 统一操作接口 ======
    
    async def upload(
        self,
        key: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        policy: StoragePolicy = StoragePolicy.DEFAULT,
        region_preference: Optional[str] = None,
        user_id: Optional[str] = None,
        user_ip: Optional[str] = None
    ) -> UploadResult:
        """上传文件"""
        start_time = time.time()
        
        try:
            # 选择存储提供商
            backend = None
            selected_provider_id = None
            
            if provider_id:
                # 使用指定的提供商
                backend = self._backends.get(provider_id)
                selected_provider_id = provider_id
            else:
                # 根据策略选择
                file_size = len(data) if isinstance(data, bytes) else 0
                if hasattr(data, 'getbuffer'):
                    file_size = len(data.getbuffer())
                
                provider = await self._strategy.select_provider(
                    file_size=file_size,
                    content_type=content_type or '',
                    policy=policy,
                    region_preference=region_preference
                )
                
                if provider:
                    backend = self._backends.get(provider.id)
                    selected_provider_id = provider.id
            
            # 如果没有后端，使用默认后端
            if not backend and self._default_backend:
                backend = self._default_backend
                # 查找对应的提供商ID
                for pid, b in self._backends.items():
                    if b == backend:
                        selected_provider_id = pid
                        break
            
            if not backend:
                return UploadResult(
                    success=False,
                    error="没有可用的存储后端"
                )
            
            # 计算文件哈希
            md5_hash = None
            sha256_hash = None
            
            if isinstance(data, bytes):
                md5_hash = hashlib.md5(data).hexdigest()
                sha256_hash = hashlib.sha256(data).hexdigest()
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
                md5_hash = hashlib.md5(data_bytes).hexdigest()
                sha256_hash = hashlib.sha256(data_bytes).hexdigest()
            
            # 执行上传
            upload_result = await backend.upload(
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata
            )
            
            if upload_result.success:
                # 保存文件元数据到数据库
                await self._save_file_metadata(
                    file_key=key,
                    provider_id=selected_provider_id,
                    filename=Path(key).name if '/' in key else key,
                    size=upload_result.size or 0,
                    content_type=content_type,
                    md5_hash=md5_hash,
                    sha256_hash=sha256_hash,
                    metadata=metadata or {},
                    uploader_id=user_id,
                    upload_ip=user_ip
                )
                
                # 更新提供商统计信息
                await self._update_provider_stats(selected_provider_id)
            
            duration = int((time.time() - start_time) * 1000)
            upload_result.duration_ms = duration
            
            return upload_result
            
        except Exception as e:
            logger.error(f"存储管理器上传文件失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传失败: {str(e)}"
            )
    
    async def download(
        self,
        key: str,
        provider_id: Optional[str] = None
    ) -> DownloadResult:
        """下载文件"""
        start_time = time.time()
        
        try:
            # 查找文件所在的存储提供商
            backend = None
            if provider_id:
                # 使用指定的提供商
                backend = self._backends.get(provider_id)
            else:
                # 从数据库查找文件元数据
                from sqlalchemy import select
                stmt = select(FileMetadata).where(FileMetadata.file_key == key)
                result = await self.db.execute(stmt)
                file_meta = result.scalar_one_or_none()
                
                if file_meta:
                    backend = self._backends.get(file_meta.storage_provider_id)
            
            if not backend:
                # 尝试在所有后端中查找
                for b in self._backends.values():
                    if await b.exists(key):
                        backend = b
                        break
            
            if not backend:
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            
            # 执行下载
            download_result = await backend.download(key)
            
            if download_result.success:
                # 更新文件访问统计
                await self._update_file_access(key)
            
            duration = int((time.time() - start_time) * 1000)
            download_result.duration_ms = duration
            
            return download_result
            
        except Exception as e:
            logger.error(f"存储管理器下载文件失败: {key}, 错误: {str(e)}")
            return DownloadResult(
                success=False,
                error=f"下载失败: {str(e)}"
            )
    
    async def delete(
        self,
        key: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """删除文件"""
        try:
            # 查找文件所在的存储提供商
            backend = None
            file_meta = None
            
            if provider_id:
                # 使用指定的提供商
                backend = self._backends.get(provider_id)
            else:
                # 从数据库查找文件元数据
                from sqlalchemy import select
                stmt = select(FileMetadata).where(FileMetadata.file_key == key)
                result = await self.db.execute(stmt)
                file_meta = result.scalar_one_or_none()
                
                if file_meta:
                    backend = self._backends.get(file_meta.storage_provider_id)
            
            if not backend:
                # 尝试在所有后端中查找并删除
                deleted = False
                for b in self._backends.values():
                    if await b.exists(key):
                        if await b.delete(key):
                            deleted = True
                
                if deleted:
                    # 删除文件元数据
                    if file_meta:
                        await self.db.delete(file_meta)
                        await self.db.commit()
                    
                    return True
                else:
                    return False
            
            # 执行删除
            success = await backend.delete(key)
            
            if success:
                # 删除文件元数据
                if file_meta:
                    await self.db.delete(file_meta)
                    await self.db.commit()
                else:
                    # 如果没有元数据，尝试查找并删除
                    stmt = select(FileMetadata).where(FileMetadata.file_key == key)
                    result = await self.db.execute(stmt)
                    file_meta = result.scalar_one_or_none()
                    if file_meta:
                        await self.db.delete(file_meta)
                        await self.db.commit()
                
                # 更新提供商统计信息
                if file_meta:
                    await self._update_provider_stats(file_meta.storage_provider_id)
            
            return success
            
        except Exception as e:
            logger.error(f"存储管理器删除文件失败: {key}, 错误: {str(e)}")
            return False
    
    async def exists(
        self,
        key: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """检查文件是否存在"""
        try:
            if provider_id:
                backend = self._backends.get(provider_id)
                if backend:
                    return await backend.exists(key)
                return False
            else:
                # 检查所有后端
                for backend in self._backends.values():
                    if await backend.exists(key):
                        return True
                return False
            
        except Exception as e:
            logger.error(f"存储管理器检查文件存在失败: {key}, 错误: {str(e)}")
            return False
    
    async def get_info(
        self,
        key: str,
        provider_id: Optional[str] = None
    ) -> Optional[FileInfo]:
        """获取文件信息"""
        try:
            # 首先从数据库获取元数据
            from sqlalchemy import select
            stmt = select(FileMetadata).where(FileMetadata.file_key == key)
            result = await self.db.execute(stmt)
            file_meta = result.scalar_one_or_none()
            
            # 查找存储后端
            backend = None
            if provider_id:
                backend = self._backends.get(provider_id)
            elif file_meta:
                backend = self._backends.get(file_meta.storage_provider_id)
            
            if not backend:
                # 尝试在所有后端中查找
                for b in self._backends.values():
                    if await b.exists(key):
                        backend = b
                        break
            
            if not backend:
                return None
            
            # 获取存储后端的信息
            storage_info = await backend.get_info(key)
            if not storage_info:
                return None
            
            # 合并数据库元数据
            if file_meta:
                storage_info.metadata.update(file_meta.metadata or {})
                storage_info.metadata['db_id'] = file_meta.id
                storage_info.metadata['access_count'] = file_meta.access_count
                storage_info.metadata['uploader_id'] = file_meta.uploader_id
            
            return storage_info
            
        except Exception as e:
            logger.error(f"存储管理器获取文件信息失败: {key}, 错误: {str(e)}")
            return None
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出文件"""
        try:
            if provider_id:
                # 从特定提供商列出
                backend = self._backends.get(provider_id)
                if backend:
                    return await backend.list_files(prefix, limit, continuation_token)
                else:
                    return {
                        "files": [],
                        "has_more": False,
                        "continuation_token": None,
                        "error": f"存储提供商不存在: {provider_id}"
                    }
            else:
                # 从所有提供商列出（从数据库）
                from sqlalchemy import select
                
                query = select(FileMetadata)
                
                if prefix:
                    query = query.where(FileMetadata.file_key.startswith(prefix))
                
                query = query.order_by(FileMetadata.created_at.desc()).limit(limit)
                
                result = await self.db.execute(query)
                files = result.scalars().all()
                
                # 转换为FileInfo
                file_infos = []
                for file_meta in files:
                    # 获取存储后端信息
                    backend = self._backends.get(file_meta.storage_provider_id)
                    storage_info = None
                    if backend:
                        storage_info = await backend.get_info(file_meta.file_key)
                    
                    if storage_info:
                        # 合并元数据
                        storage_info.metadata.update(file_meta.metadata or {})
                        storage_info.metadata['db_id'] = file_meta.id
                        storage_info.metadata['access_count'] = file_meta.access_count
                        file_infos.append(storage_info)
                    else:
                        # 只有数据库记录
                        file_info = FileInfo(
                            key=file_meta.file_key,
                            size=file_meta.size,
                            content_type=file_meta.content_type,
                            last_modified=file_meta.updated_at,
                            metadata={
                                'db_id': file_meta.id,
                                'access_count': file_meta.access_count,
                                'uploader_id': file_meta.uploader_id
                            }
                        )
                        file_infos.append(file_info)
                
                return {
                    "files": [fi.dict() for fi in file_infos],
                    "has_more": len(files) >= limit,
                    "continuation_token": None,
                    "total": len(file_infos)
                }
            
        except Exception as e:
            logger.error(f"存储管理器列出文件失败: 前缀={prefix}, 错误: {str(e)}")
            return {
                "files": [],
                "has_more": False,
                "continuation_token": None,
                "error": str(e)
            }
    
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET",
        provider_id: Optional[str] = None
    ) -> Optional[str]:
        """生成预签名URL"""
        try:
            # 查找文件所在的存储提供商
            backend = None
            if provider_id:
                backend = self._backends.get(provider_id)
            else:
                # 从数据库查找文件元数据
                from sqlalchemy import select
                stmt = select(FileMetadata).where(FileMetadata.file_key == key)
                result = await self.db.execute(stmt)
                file_meta = result.scalar_one_or_none()
                
                if file_meta:
                    backend = self._backends.get(file_meta.storage_provider_id)
            
            if not backend:
                # 尝试在所有后端中查找
                for b in self._backends.values():
                    if await b.exists(key):
                        backend = b
                        break
            
            if not backend:
                return None
            
            return await backend.generate_presigned_url(key, expires_in, method)
            
        except Exception as e:
            logger.error(f"存储管理器生成预签名URL失败: {key}, 错误: {str(e)}")
            return None
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        source_provider_id: Optional[str] = None,
        dest_provider_id: Optional[str] = None
    ) -> bool:
        """复制文件"""
        try:
            # 查找源文件存储提供商
            source_backend = None
            source_file_meta = None
            
            if source_provider_id:
                source_backend = self._backends.get(source_provider_id)
            else:
                # 从数据库查找源文件元数据
                from sqlalchemy import select
                stmt = select(FileMetadata).where(FileMetadata.file_key == source_key)
                result = await self.db.execute(stmt)
                source_file_meta = result.scalar_one_or_none()
                
                if source_file_meta:
                    source_backend = self._backends.get(source_file_meta.storage_provider_id)
            
            if not source_backend:
                # 尝试在所有后端中查找源文件
                for b in self._backends.values():
                    if await b.exists(source_key):
                        source_backend = b
                        break
            
            if not source_backend:
                return False
            
            # 查找目标存储提供商
            dest_backend = None
            if dest_provider_id:
                dest_backend = self._backends.get(dest_provider_id)
            else:
                # 使用源文件提供商作为目标（同一提供商内复制）
                dest_backend = source_backend
            
            # 执行复制
            success = await source_backend.copy(source_key, dest_key, dest_backend)
            
            if success and source_file_meta:
                # 复制文件元数据
                new_file_meta = FileMetadata(
                    file_key=dest_key,
                    storage_provider_id=dest_provider_id or source_file_meta.storage_provider_id,
                    filename=Path(dest_key).name if '/' in dest_key else dest_key,
                    size=source_file_meta.size,
                    content_type=source_file_meta.content_type,
                    file_category=source_file_meta.file_category,
                    md5_hash=source_file_meta.md5_hash,
                    sha256_hash=source_file_meta.sha256_hash,
                    metadata=source_file_meta.metadata.copy() if source_file_meta.metadata else {},
                    tags=source_file_meta.tags.copy() if source_file_meta.tags else []
                )
                
                self.db.add(new_file_meta)
                await self.db.commit()
                
                # 更新目标提供商统计信息
                await self._update_provider_stats(new_file_meta.storage_provider_id)
            
            return success
            
        except Exception as e:
            logger.error(f"存储管理器复制文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    async def move(
        self,
        source_key: str,
        dest_key: str,
        source_provider_id: Optional[str] = None,
        dest_provider_id: Optional[str] = None
    ) -> bool:
        """移动文件"""
        try:
            # 先复制
            copy_success = await self.copy(
                source_key, dest_key,
                source_provider_id, dest_provider_id
            )
            
            if not copy_success:
                return False
            
            # 再删除源文件
            return await self.delete(source_key, source_provider_id)
            
        except Exception as e:
            logger.error(f"存储管理器移动文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    # ====== 管理功能 ======
    
    async def get_providers(self) -> List[Dict[str, Any]]:
        """获取所有存储提供商"""
        try:
            from sqlalchemy import select
            stmt = select(StorageProvider).order_by(StorageProvider.is_default.desc(), StorageProvider.created_at)
            result = await self.db.execute(stmt)
            providers = result.scalars().all()
            
            return [p.to_dict() for p in providers]
            
        except Exception as e:
            logger.error(f"获取存储提供商失败: {str(e)}")
            return []
    
    async def add_provider(self, config: StorageConfig) -> Optional[str]:
        """添加存储提供商"""
        try:
            import uuid
            
            # 检查名称是否已存在
            from sqlalchemy import select
            stmt = select(StorageProvider).where(StorageProvider.name == config.name)
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                raise ValueError(f"存储提供商名称已存在: {config.name}")
            
            # 创建提供商记录
            provider = StorageProvider(
                id=str(uuid.uuid4()),
                name=config.name,
                type=config.type,
                config=config.dict(),
                enabled=config.enabled,
                is_default=config.is_default,
                health_status="unknown"
            )
            
            self.db.add(provider)
            await self.db.commit()
            
            # 如果这是默认提供商，取消其他提供商的默认状态
            if config.is_default:
                await self._set_default_provider(provider.id)
            
            # 初始化存储后端
            backend = await self._create_backend(provider)
            if backend:
                self._backends[provider.id] = backend
                
                if config.is_default:
                    self._default_backend = backend
                
                logger.info(f"存储提供商添加成功: {config.name}")
                return provider.id
            else:
                logger.error(f"存储提供商后端初始化失败: {config.name}")
                # 删除数据库记录
                await self.db.delete(provider)
                await self.db.commit()
                return None
            
        except Exception as e:
            logger.error(f"添加存储提供商失败: {str(e)}")
            await self.db.rollback()
            return None
    
    async def update_provider(self, provider_id: str, config: StorageConfig) -> bool:
        """更新存储提供商"""
        try:
            from sqlalchemy import select
            stmt = select(StorageProvider).where(StorageProvider.id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider:
                raise ValueError(f"存储提供商不存在: {provider_id}")
            
            # 检查名称冲突
            if config.name != provider.name:
                stmt = select(StorageProvider).where(StorageProvider.name == config.name)
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing and existing.id != provider_id:
                    raise ValueError(f"存储提供商名称已存在: {config.name}")
            
            # 更新配置
            provider.name = config.name
            provider.type = config.type
            provider.config = config.dict()
            provider.enabled = config.enabled
            
            # 处理默认状态
            if config.is_default and not provider.is_default:
                provider.is_default = True
                await self._set_default_provider(provider_id)
            elif not config.is_default and provider.is_default:
                # 不能取消唯一的默认提供商
                stmt = select(StorageProvider).where(
                    StorageProvider.is_default == True,
                    StorageProvider.id != provider_id
                )
                result = await self.db.execute(stmt)
                other_default = result.scalar_one_or_none()
                if not other_default:
                    raise ValueError("至少需要一个默认存储提供商")
                provider.is_default = False
            
            await self.db.commit()
            
            # 重新初始化存储后端
            backend = await self._create_backend(provider)
            if backend:
                self._backends[provider_id] = backend
                
                if config.is_default:
                    self._default_backend = backend
                
                logger.info(f"存储提供商更新成功: {config.name}")
                return True
            else:
                logger.error(f"存储提供商后端重新初始化失败: {config.name}")
                return False
            
        except Exception as e:
            logger.error(f"更新存储提供商失败: {str(e)}")
            await self.db.rollback()
            return False
    
    async def delete_provider(self, provider_id: str, force: bool = False) -> bool:
        """删除存储提供商"""
        try:
            from sqlalchemy import select
            
            # 检查提供商是否存在
            stmt = select(StorageProvider).where(StorageProvider.id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider:
                return False
            
            # 检查是否有文件使用该提供商
            stmt = select(FileMetadata).where(FileMetadata.storage_provider_id == provider_id)
            result = await self.db.execute(stmt)
            files = result.scalars().all()
            
            if files and not force:
                raise ValueError(f"存储提供商有 {len(files)} 个关联文件，请先迁移或删除这些文件")
            
            # 如果是默认提供商，需要先设置其他提供商为默认
            if provider.is_default:
                # 查找其他启用的提供商
                stmt = select(StorageProvider).where(
                    StorageProvider.id != provider_id,
                    StorageProvider.enabled == True
                )
                result = await self.db.execute(stmt)
                other_providers = result.scalars().all()
                
                if other_providers:
                    # 设置第一个为默认
                    new_default = other_providers[0]
                    new_default.is_default = True
                else:
                    raise ValueError("不能删除唯一的存储提供商")
            
            # 删除关联的文件元数据
            if files:
                for file_meta in files:
                    await self.db.delete(file_meta)
            
            # 删除提供商
            await self.db.delete(provider)
            await self.db.commit()
            
            # 从内存中移除后端
            if provider_id in self._backends:
                del self._backends[provider_id]
                
                # 如果删除的是默认后端，重新设置
                if self._default_backend and self._default_backend == self._backends.get(provider_id):
                    if self._backends:
                        first_key = next(iter(self._backends))
                        self._default_backend = self._backends[first_key]
                    else:
                        self._default_backend = None
            
            logger.info(f"存储提供商删除成功: {provider.name}")
            return True
            
        except Exception as e:
            logger.error(f"删除存储提供商失败: {str(e)}")
            await self.db.rollback()
            return False
    
    async def check_health(self, provider_id: Optional[str] = None) -> Dict[str, Any]:
        """检查存储提供商健康状态"""
        try:
            results = {}
            
            if provider_id:
                # 检查特定提供商
                backend = self._backends.get(provider_id)
                if backend:
                    # 简单测试：检查是否能列出文件
                    start_time = time.time()
                    try:
                        list_result = await backend.list_files(limit=1)
                        latency = int((time.time() - start_time) * 1000)
                        
                        results[provider_id] = {
                            "status": "healthy",
                            "latency_ms": latency,
                            "has_files": len(list_result.get("files", [])) > 0,
                            "timestamp": datetime.now().isoformat()
                        }
                    except Exception as e:
                        results[provider_id] = {
                            "status": "unhealthy",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                
                # 更新数据库状态
                from sqlalchemy import select
                stmt = select(StorageProvider).where(StorageProvider.id == provider_id)
                result = await self.db.execute(stmt)
                provider = result.scalar_one_or_none()
                
                if provider:
                    health_info = results.get(provider_id, {})
                    provider.health_status = health_info.get("status", "unknown")
                    provider.last_health_check = datetime.now()
                    await self.db.commit()
            
            else:
                # 检查所有提供商
                for pid, backend in self._backends.items():
                    start_time = time.time()
                    try:
                        list_result = await backend.list_files(limit=1)
                        latency = int((time.time() - start_time) * 1000)
                        
                        results[pid] = {
                            "status": "healthy",
                            "latency_ms": latency,
                            "has_files": len(list_result.get("files", [])) > 0,
                            "timestamp": datetime.now().isoformat()
                        }
                    except Exception as e:
                        results[pid] = {
                            "status": "unhealthy",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                
                # 批量更新数据库状态
                from sqlalchemy import select
                stmt = select(StorageProvider)
                result = await self.db.execute(stmt)
                providers = result.scalars().all()
                
                for provider in providers:
                    health_info = results.get(provider.id, {})
                    provider.health_status = health_info.get("status", "unknown")
                    provider.last_health_check = datetime.now()
                
                await self.db.commit()
            
            return results
            
        except Exception as e:
            logger.error(f"检查存储健康状态失败: {str(e)}")
            return {"error": str(e)}
    
    async def get_stats(self, provider_id: Optional[str] = None) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            if provider_id:
                # 获取特定提供商的统计
                from sqlalchemy import select, func
                stmt = select(
                    func.count(FileMetadata.id).label("file_count"),
                    func.sum(FileMetadata.size).label("total_size")
                ).where(FileMetadata.storage_provider_id == provider_id)
                
                result = await self.db.execute(stmt)
                stats = result.first()
                
                return {
                    "provider_id": provider_id,
                    "file_count": stats.file_count or 0,
                    "total_size": stats.total_size or 0,
                    "average_file_size": stats.total_size / stats.file_count if stats.file_count else 0
                }
            else:
                # 获取所有提供商的统计
                from sqlalchemy import select, func
                stmt = select(
                    FileMetadata.storage_provider_id,
                    func.count(FileMetadata.id).label("file_count"),
                    func.sum(FileMetadata.size).label("total_size")
                ).group_by(FileMetadata.storage_provider_id)
                
                result = await self.db.execute(stmt)
                rows = result.all()
                
                # 获取提供商信息
                providers = await self.get_providers()
                provider_map = {p["id"]: p for p in providers}
                
                stats = {}
                for row in rows:
                    provider_info = provider_map.get(row.storage_provider_id, {})
                    stats[row.storage_provider_id] = {
                        "name": provider_info.get("name", "Unknown"),
                        "type": provider_info.get("type", "unknown"),
                        "file_count": row.file_count or 0,
                        "total_size": row.total_size or 0,
                        "average_file_size": row.total_size / row.file_count if row.file_count else 0
                    }
                
                # 计算总计
                total_files = sum(s["file_count"] for s in stats.values())
                total_size = sum(s["total_size"] for s in stats.values())
                
                return {
                    "providers": stats,
                    "total_files": total_files,
                    "total_size": total_size,
                    "provider_count": len(stats)
                }
            
        except Exception as e:
            logger.error(f"获取存储统计信息失败: {str(e)}")
            return {"error": str(e)}
    
    # ====== 内部方法 ======
    
    async def _save_file_metadata(
        self,
        file_key: str,
        provider_id: str,
        filename: str,
        size: int,
        content_type: Optional[str] = None,
        md5_hash: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        uploader_id: Optional[str] = None,
        upload_ip: Optional[str] = None
    ) -> None:
        """保存文件元数据到数据库"""
        try:
            import uuid
            
            # 确定文件分类
            file_category = FileCategory.OTHER
            if content_type:
                file_category = self.get_file_category(content_type)
            
            file_meta = FileMetadata(
                id=str(uuid.uuid4()),
                file_key=file_key,
                storage_provider_id=provider_id,
                filename=filename,
                size=size,
                content_type=content_type,
                file_category=file_category,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash,
                metadata=metadata or {},
                tags=tags or [],
                uploader_id=uploader_id,
                upload_ip=upload_ip
            )
            
            self.db.add(file_meta)
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"保存文件元数据失败: {file_key}, 错误: {str(e)}")
            await self.db.rollback()
    
    async def _update_file_access(self, file_key: str) -> None:
        """更新文件访问统计"""
        try:
            from sqlalchemy import select
            stmt = select(FileMetadata).where(FileMetadata.file_key == file_key)
            result = await self.db.execute(stmt)
            file_meta = result.scalar_one_or_none()
            
            if file_meta:
                file_meta.access_count += 1
                file_meta.last_access = datetime.now()
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"更新文件访问统计失败: {file_key}, 错误: {str(e)}")
    
    async def _update_provider_stats(self, provider_id: str) -> None:
        """更新存储提供商统计信息"""
        try:
            from sqlalchemy import select, func
            stmt = select(
                func.count(FileMetadata.id).label("file_count"),
                func.sum(FileMetadata.size).label("total_size")
            ).where(FileMetadata.storage_provider_id == provider_id)
            
            result = await self.db.execute(stmt)
            stats = result.first()
            
            # 更新提供商记录
            stmt = select(StorageProvider).where(StorageProvider.id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if provider:
                provider.total_files = stats.file_count or 0
                provider.total_size = stats.total_size or 0
                
                # 这里可以添加使用百分比计算（需要知道提供商容量）
                # provider.used_percent = ...
                
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"更新提供商统计信息失败: {provider_id}, 错误: {str(e)}")
    
    async def _set_default_provider(self, provider_id: str) -> None:
        """设置默认存储提供商"""
        try:
            from sqlalchemy import select
            stmt = select(StorageProvider).where(StorageProvider.is_default == True)
            result = await self.db.execute(stmt)
            current_defaults = result.scalars().all()
            
            for provider in current_defaults:
                if provider.id != provider_id:
                    provider.is_default = False
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"设置默认存储提供商失败: {str(e)}")
            await self.db.rollback()