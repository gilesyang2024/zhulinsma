"""
存储系统基础模块
定义存储后端的抽象接口和基础配置
"""

import abc
import hashlib
import io
import os
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator

import logging
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class StorageType(str, Enum):
    """存储类型"""
    LOCAL = "local"          # 本地文件系统
    S3 = "s3"               # S3兼容对象存储
    AZURE = "azure"         # Azure Blob Storage
    GOOGLE = "google"       # Google Cloud Storage
    ALIYUN = "aliyun"       # 阿里云OSS
    TENCENT = "tencent"     # 腾讯云COS

class FileCategory(str, Enum):
    """文件分类"""
    IMAGE = "image"         # 图片
    VIDEO = "video"         # 视频
    AUDIO = "audio"         # 音频
    DOCUMENT = "document"   # 文档
    ARCHIVE = "archive"     # 压缩包
    OTHER = "other"         # 其他

class StorageConfig(BaseModel):
    """存储配置"""
    
    # 基础配置
    type: StorageType = Field(..., description="存储类型")
    name: str = Field(..., description="存储配置名称")
    enabled: bool = Field(True, description="是否启用")
    is_default: bool = Field(False, description="是否默认存储")
    
    # 连接配置
    endpoint: Optional[str] = Field(None, description="端点URL")
    region: Optional[str] = Field(None, description="区域")
    bucket: Optional[str] = Field(None, description="存储桶/容器名称")
    
    # 认证配置
    access_key: Optional[str] = Field(None, description="访问密钥")
    secret_key: Optional[str] = Field(None, description="秘密密钥")
    connection_string: Optional[str] = Field(None, description="连接字符串")
    
    # 路径配置
    base_path: Optional[str] = Field(None, description="基础路径")
    public_url_base: Optional[str] = Field(None, description="公开URL基础")
    
    # 性能配置
    max_file_size: int = Field(1024 * 1024 * 100, description="最大文件大小(字节)")
    chunk_size: int = Field(1024 * 1024 * 5, description="分块大小(字节)")
    timeout: int = Field(30, description="超时时间(秒)")
    retry_count: int = Field(3, description="重试次数")
    
    # 策略配置
    auto_create_bucket: bool = Field(True, description="自动创建存储桶")
    enable_versioning: bool = Field(False, description="启用版本控制")
    enable_encryption: bool = Field(False, description="启用加密")
    
    # 缓存配置
    cache_enabled: bool = Field(True, description="启用缓存")
    cache_ttl: int = Field(3600, description="缓存TTL(秒)")
    
    # 高级配置
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="自定义配置")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "s3",
                "name": "production-s3",
                "endpoint": "https://s3.amazonaws.com",
                "region": "us-east-1",
                "bucket": "my-app-files",
                "access_key": "AKIA...",
                "secret_key": "...",
                "public_url_base": "https://cdn.example.com"
            }
        }

class FileInfo(BaseModel):
    """文件信息"""
    
    key: str = Field(..., description="文件唯一标识/路径")
    size: int = Field(..., description="文件大小(字节)")
    content_type: Optional[str] = Field(None, description="内容类型")
    etag: Optional[str] = Field(None, description="ETag哈希值")
    last_modified: Optional[datetime] = Field(None, description="最后修改时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文件元数据")
    
    @property
    def is_image(self) -> bool:
        """是否为图片文件"""
        if not self.content_type:
            return False
        return self.content_type.startswith("image/")
    
    @property
    def is_video(self) -> bool:
        """是否为视频文件"""
        if not self.content_type:
            return False
        return self.content_type.startswith("video/")
    
    @property
    def is_audio(self) -> bool:
        """是否为音频文件"""
        if not self.content_type:
            return False
        return self.content_type.startswith("audio/")

class UploadResult(BaseModel):
    """上传结果"""
    
    success: bool = Field(..., description="是否成功")
    key: Optional[str] = Field(None, description="文件键/路径")
    url: Optional[str] = Field(None, description="访问URL")
    size: Optional[int] = Field(None, description="文件大小")
    etag: Optional[str] = Field(None, description="ETag哈希值")
    duration_ms: Optional[int] = Field(None, description="上传耗时(毫秒)")
    error: Optional[str] = Field(None, description="错误信息")

class DownloadResult(BaseModel):
    """下载结果"""
    
    success: bool = Field(..., description="是否成功")
    data: Optional[bytes] = Field(None, description="文件数据")
    size: Optional[int] = Field(None, description="文件大小")
    content_type: Optional[str] = Field(None, description="内容类型")
    duration_ms: Optional[int] = Field(None, description="下载耗时(毫秒)")
    error: Optional[str] = Field(None, description="错误信息")

class StorageBackend(abc.ABC):
    """存储后端抽象基类"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self._initialized = False
        self.name = config.name
        self.type = config.type
        logger.info(f"初始化存储后端: {self.name} ({self.type.value})")
    
    @abc.abstractmethod
    async def initialize(self) -> bool:
        """初始化存储后端"""
        pass
    
    @abc.abstractmethod
    async def upload(
        self,
        key: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False
    ) -> UploadResult:
        """
        上传文件
        
        Args:
            key: 文件唯一标识/路径
            data: 文件数据
            content_type: 内容类型
            metadata: 文件元数据
            overwrite: 是否覆盖已存在文件
            
        Returns:
            UploadResult: 上传结果
        """
        pass
    
    @abc.abstractmethod
    async def download(self, key: str) -> DownloadResult:
        """
        下载文件
        
        Args:
            key: 文件唯一标识/路径
            
        Returns:
            DownloadResult: 下载结果
        """
        pass
    
    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """
        删除文件
        
        Args:
            key: 文件唯一标识/路径
            
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            key: 文件唯一标识/路径
            
        Returns:
            bool: 文件是否存在
        """
        pass
    
    @abc.abstractmethod
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """
        获取文件信息
        
        Args:
            key: 文件唯一标识/路径
            
        Returns:
            Optional[FileInfo]: 文件信息，不存在返回None
        """
        pass
    
    @abc.abstractmethod
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出文件
        
        Args:
            prefix: 前缀过滤
            limit: 返回数量限制
            continuation_token: 继续令牌（用于分页）
            
        Returns:
            Dict[str, Any]: 包含文件和分页信息的结果
        """
        pass
    
    @abc.abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "GET"
    ) -> Optional[str]:
        """
        生成预签名URL
        
        Args:
            key: 文件唯一标识/路径
            expires_in: 过期时间(秒)
            method: HTTP方法
            
        Returns:
            Optional[str]: 预签名URL，失败返回None
        """
        pass
    
    @abc.abstractmethod
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional['StorageBackend'] = None
    ) -> bool:
        """
        复制文件
        
        Args:
            source_key: 源文件键
            dest_key: 目标文件键
            dest_backend: 目标存储后端，None表示同一后端
            
        Returns:
            bool: 是否复制成功
        """
        pass
    
    @abc.abstractmethod
    async def move(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional['StorageBackend'] = None
    ) -> bool:
        """
        移动文件
        
        Args:
            source_key: 源文件键
            dest_key: 目标文件键
            dest_backend: 目标存储后端，None表示同一后端
            
        Returns:
            bool: 是否移动成功
        """
        pass
    
    # ====== 公共方法 ======
    
    def get_public_url(self, key: str) -> Optional[str]:
        """获取公开URL"""
        if not self.config.public_url_base:
            return None
        
        # 清理路径
        if key.startswith("/"):
            key = key[1:]
        
        return f"{self.config.public_url_base.rstrip('/')}/{key}"
    
    async def upload_stream(
        self,
        key: str,
        stream: BinaryIO,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None
    ) -> UploadResult:
        """
        流式上传文件
        
        Args:
            key: 文件唯一标识/路径
            stream: 文件流
            content_type: 内容类型
            metadata: 文件元数据
            chunk_size: 分块大小
            
        Returns:
            UploadResult: 上传结果
        """
        chunk_size = chunk_size or self.config.chunk_size
        
        try:
            # 读取整个流到内存（对于大文件可能需要分块上传）
            data = stream.read()
            return await self.upload(key, data, content_type, metadata)
        except Exception as e:
            logger.error(f"流式上传失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"流式上传失败: {str(e)}"
            )
    
    async def upload_file(
        self,
        key: str,
        file_path: Union[str, Path],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False
    ) -> UploadResult:
        """
        上传本地文件
        
        Args:
            key: 文件唯一标识/路径
            file_path: 本地文件路径
            content_type: 内容类型
            metadata: 文件元数据
            overwrite: 是否覆盖已存在文件
            
        Returns:
            UploadResult: 上传结果
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return UploadResult(
                    success=False,
                    error=f"文件不存在: {file_path}"
                )
            
            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size > self.config.max_file_size:
                return UploadResult(
                    success=False,
                    error=f"文件大小超过限制: {file_size} > {self.config.max_file_size}"
                )
            
            # 读取文件
            with open(file_path, "rb") as f:
                data = f.read()
            
            # 自动检测内容类型
            if not content_type:
                import mimetypes
                content_type, _ = mimetypes.guess_type(str(file_path))
            
            return await self.upload(key, data, content_type, metadata, overwrite)
            
        except Exception as e:
            logger.error(f"上传文件失败: {file_path}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传文件失败: {str(e)}"
            )
    
    async def download_to_file(
        self,
        key: str,
        file_path: Union[str, Path]
    ) -> bool:
        """
        下载文件到本地
        
        Args:
            key: 文件唯一标识/路径
            file_path: 本地文件路径
            
        Returns:
            bool: 是否下载成功
        """
        try:
            result = await self.download(key)
            if not result.success or not result.data:
                logger.error(f"下载文件失败: {key}")
                return False
            
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "wb") as f:
                f.write(result.data)
            
            logger.info(f"文件下载成功: {key} -> {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"下载文件到本地失败: {key}, 错误: {str(e)}")
            return False
    
    async def batch_upload(
        self,
        files: List[Dict[str, Any]],
        concurrency: int = 3
    ) -> List[UploadResult]:
        """
        批量上传文件
        
        Args:
            files: 文件列表，每个元素包含 key, data/content_type/metadata
            concurrency: 并发数
            
        Returns:
            List[UploadResult]: 上传结果列表
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        results = []
        
        async def upload_one(file_info: Dict[str, Any]) -> UploadResult:
            """上传单个文件"""
            key = file_info.get("key")
            data = file_info.get("data")
            content_type = file_info.get("content_type")
            metadata = file_info.get("metadata", {})
            overwrite = file_info.get("overwrite", False)
            
            if not key or data is None:
                return UploadResult(
                    success=False,
                    error="缺少必要参数: key 或 data"
                )
            
            return await self.upload(key, data, content_type, metadata, overwrite)
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)
        
        async def upload_with_semaphore(file_info: Dict[str, Any]) -> UploadResult:
            """带信号量控制的文件上传"""
            async with semaphore:
                return await upload_one(file_info)
        
        # 创建并执行所有上传任务
        tasks = [upload_with_semaphore(file_info) for file_info in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(UploadResult(
                    success=False,
                    error=f"上传异常: {str(result)}"
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def batch_delete(
        self,
        keys: List[str],
        concurrency: int = 3
    ) -> List[Dict[str, Any]]:
        """
        批量删除文件
        
        Args:
            keys: 文件键列表
            concurrency: 并发数
            
        Returns:
            List[Dict[str, Any]]: 删除结果列表
        """
        import asyncio
        
        results = []
        
        async def delete_one(key: str) -> Dict[str, Any]:
            """删除单个文件"""
            try:
                success = await self.delete(key)
                return {
                    "key": key,
                    "success": success,
                    "error": None if success else "删除失败"
                }
            except Exception as e:
                return {
                    "key": key,
                    "success": False,
                    "error": str(e)
                }
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)
        
        async def delete_with_semaphore(key: str) -> Dict[str, Any]:
            """带信号量控制的文件删除"""
            async with semaphore:
                return await delete_one(key)
        
        # 创建并执行所有删除任务
        tasks = [delete_with_semaphore(key) for key in keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "key": keys[i] if i < len(keys) else "unknown",
                    "success": False,
                    "error": f"删除异常: {str(result)}"
                })
            else:
                final_results.append(result)
        
        return final_results
    
    # ====== 工具方法 ======
    
    @staticmethod
    def generate_key(
        prefix: Optional[str] = None,
        filename: Optional[str] = None,
        use_timestamp: bool = True,
        use_uuid: bool = True
    ) -> str:
        """
        生成文件键
        
        Args:
            prefix: 前缀（如目录路径）
            filename: 原始文件名
            use_timestamp: 是否使用时间戳
            use_uuid: 是否使用UUID
            
        Returns:
            str: 生成的文件键
        """
        import uuid
        import time
        
        parts = []
        
        # 添加前缀
        if prefix:
            parts.append(prefix.strip("/"))
        
        # 添加时间戳部分
        if use_timestamp:
            timestamp = int(time.time())
            parts.append(str(timestamp))
        
        # 添加UUID部分
        if use_uuid:
            unique_id = uuid.uuid4().hex[:8]
            parts.append(unique_id)
        
        # 添加文件名
        if filename:
            # 清理文件名中的特殊字符
            import re
            safe_filename = re.sub(r'[^\w\-\.]', '_', filename)
            parts.append(safe_filename)
        
        # 如果没有文件名，使用默认名称
        if not filename and not parts:
            parts.append("file")
        
        # 如果没有文件名但有其他部分，添加默认扩展名
        if not filename and parts:
            parts.append("data")
        
        return "/".join(parts)
    
    @staticmethod
    def calculate_md5(data: bytes) -> str:
        """计算MD5哈希"""
        return hashlib.md5(data).hexdigest()
    
    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """计算SHA256哈希"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def get_content_type(filename: str) -> str:
        """根据文件名获取内容类型"""
        import mimetypes
        
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            # 根据扩展名判断常见类型
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            content_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'mp4': 'video/mp4',
                'avi': 'video/x-msvideo',
                'mov': 'video/quicktime',
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav',
                'pdf': 'application/pdf',
                'doc': 'application/msword',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xls': 'application/vnd.ms-excel',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'ppt': 'application/vnd.ms-powerpoint',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'txt': 'text/plain',
                'json': 'application/json',
                'xml': 'application/xml',
                'zip': 'application/zip',
                'tar': 'application/x-tar',
                'gz': 'application/gzip'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
        
        return content_type
    
    @staticmethod
    def get_file_category(content_type: str) -> FileCategory:
        """根据内容类型获取文件分类"""
        if content_type.startswith('image/'):
            return FileCategory.IMAGE
        elif content_type.startswith('video/'):
            return FileCategory.VIDEO
        elif content_type.startswith('audio/'):
            return FileCategory.AUDIO
        elif content_type in [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/html',
            'application/json',
            'application/xml'
        ]:
            return FileCategory.DOCUMENT
        elif content_type in [
            'application/zip',
            'application/x-tar',
            'application/gzip',
            'application/x-rar-compressed'
        ]:
            return FileCategory.ARCHIVE
        else:
            return FileCategory.OTHER