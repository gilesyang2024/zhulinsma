"""
Azure Blob Storage 实现
"""

import time
from typing import Any, BinaryIO, Dict, Optional, Union

from .base import (
    StorageBackend, StorageConfig, StorageType,
    FileInfo, UploadResult, DownloadResult
)
import logging
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class AzureBlobStorage(StorageBackend):
    """Azure Blob Storage 实现"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        
        # 验证必要配置
        if not config.connection_string:
            raise ValueError("Azure Blob Storage 需要 connection_string 配置")
        
        if not config.bucket:  # 在Azure中bucket对应容器名称
            raise ValueError("Azure Blob Storage 需要 bucket/container 配置")
        
        # 初始化Azure客户端
        self._client = None
        self._container_client = None
        self._container_name = config.bucket
        
    async def initialize(self) -> bool:
        """初始化Azure Blob Storage"""
        try:
            # 尝试导入Azure SDK
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError:
                logger.error("Azure SDK未安装，请运行: pip install azure-storage-blob")
                return False
            
            # 创建Blob服务客户端
            self._client = BlobServiceClient.from_connection_string(
                self.config.connection_string
            )
            
            # 获取容器客户端
            self._container_client = self._client.get_container_client(self._container_name)
            
            # 检查容器是否存在，如果不存在且配置了自动创建则创建
            try:
                properties = self._container_client.get_container_properties()
                logger.info(f"Azure容器已存在: {self._container_name}")
            except Exception as e:
                if "ContainerNotFound" in str(e):
                    if self.config.auto_create_bucket:
                        # 创建容器
                        self._container_client.create_container()
                        logger.info(f"Azure容器创建成功: {self._container_name}")
                    else:
                        logger.error(f"Azure容器不存在且未启用自动创建: {self._container_name}")
                        return False
                else:
                    logger.error(f"检查Azure容器失败: {str(e)}")
                    return False
            
            # 测试连接
            try:
                # 尝试列出blob（限制为0）
                blobs = self._container_client.list_blobs(max_results=1)
                list(blobs)  # 触发查询
                logger.info(f"Azure Blob Storage初始化成功: {self._container_name}")
                self._initialized = True
                return True
            except Exception as e:
                logger.error(f"Azure Blob Storage连接测试失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Azure Blob Storage初始化失败: {str(e)}")
            return False
    
    def _clean_key(self, key: str) -> str:
        """清理Azure Blob键"""
        # 移除开头的斜杠
        key = key.lstrip('/')
        
        # 确保键不为空
        if not key:
            key = 'default'
            
        return key
    
    async def upload(
        self,
        key: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False
    ) -> UploadResult:
        """上传文件到Azure Blob Storage"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._container_client:
                return UploadResult(
                    success=False,
                    error="Azure Blob Storage未初始化"
                )
            
            clean_key = self._clean_key(key)
            
            # 检查blob是否已存在
            if not overwrite:
                try:
                    blob_client = self._container_client.get_blob_client(clean_key)
                    blob_client.get_blob_properties()
                    return UploadResult(
                        success=False,
                        error=f"文件已存在: {clean_key}"
                    )
                except Exception as e:
                    if "BlobNotFound" not in str(e):
                        return UploadResult(
                            success=False,
                            error=f"检查文件存在失败: {str(e)}"
                        )
            
            # 获取blob客户端
            blob_client = self._container_client.get_blob_client(clean_key)
            
            # 处理数据
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            elif isinstance(data, bytes):
                data_bytes = data
            elif hasattr(data, 'read'):
                # 如果是文件流
                if hasattr(data, 'seek') and data.tell() > 0:
                    data.seek(0)
                data_bytes = data.read()
                if hasattr(data, 'seek'):
                    data.seek(0)
            else:
                return UploadResult(
                    success=False,
                    error=f"不支持的数据类型: {type(data)}"
                )
            
            # 检查文件大小
            if len(data_bytes) > self.config.max_file_size:
                return UploadResult(
                    success=False,
                    error=f"文件大小超过限制: {len(data_bytes)} > {self.config.max_file_size}"
                )
            
            # 设置内容类型
            if not content_type:
                content_type = self.get_content_type(clean_key)
            
            # 上传blob
            blob_client.upload_blob(
                data=data_bytes,
                overwrite=overwrite,
                content_type=content_type,
                metadata=metadata or {}
            )
            
            # 获取blob属性
            properties = blob_client.get_blob_properties()
            
            # 生成访问URL
            url = self.get_public_url(clean_key)
            if not url:
                url = blob_client.url
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"Azure文件上传成功: {clean_key}, 大小: {len(data_bytes)} bytes, 耗时: {duration}ms")
            
            return UploadResult(
                success=True,
                key=clean_key,
                url=url,
                size=len(data_bytes),
                etag=properties.etag.strip('"') if properties.etag else None,
                duration_ms=duration
            )
            
        except Exception as e:
            logger.error(f"Azure上传文件失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传失败: {str(e)}"
            )
    
    async def download(self, key: str) -> DownloadResult:
        """从Azure Blob Storage下载文件"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._container_client:
                return DownloadResult(
                    success=False,
                    error="Azure Blob Storage未初始化"
                )
            
            clean_key = self._clean_key(key)
            
            # 获取blob客户端
            blob_client = self._container_client.get_blob_client(clean_key)
            
            # 下载blob
            download_stream = blob_client.download_blob()
            data = download_stream.readall()
            
            # 获取blob属性
            properties = blob_client.get_blob_properties()
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"Azure文件下载成功: {clean_key}, 大小: {len(data)} bytes, 耗时: {duration}ms")
            
            return DownloadResult(
                success=True,
                data=data,
                size=len(data),
                content_type=properties.content_type,
                duration_ms=duration
            )
            
        except Exception as e:
            if "BlobNotFound" in str(e):
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            else:
                logger.error(f"Azure下载文件失败: {key}, 错误: {str(e)}")
                return DownloadResult(
                    success=False,
                    error=f"下载失败: {str(e)}"
                )
    
    async def delete(self, key: str) -> bool:
        """从Azure Blob Storage删除文件"""
        try:
            if not self._initialized or not self._container_client:
                return False
            
            clean_key = self._clean_key(key)
            
            # 获取blob客户端
            blob_client = self._container_client.get_blob_client(clean_key)
            
            # 删除blob
            blob_client.delete_blob()
            
            logger.info(f"Azure文件删除成功: {clean_key}")
            return True
            
        except Exception as e:
            if "BlobNotFound" in str(e):
                logger.warning(f"尝试删除不存在的Azure文件: {key}")
                return False
            else:
                logger.error(f"Azure删除文件失败: {key}, 错误: {str(e)}")
                return False
    
    async def exists(self, key: str) -> bool:
        """检查Azure文件是否存在"""
        try:
            if not self._initialized or not self._container_client:
                return False
            
            clean_key = self._clean_key(key)
            
            blob_client = self._container_client.get_blob_client(clean_key)
            blob_client.get_blob_properties()
            return True
            
        except Exception as e:
            return "BlobNotFound" not in str(e)
    
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取Azure文件信息"""
        try:
            if not self._initialized or not self._container_client:
                return None
            
            clean_key = self._clean_key(key)
            
            blob_client = self._container_client.get_blob_client(clean_key)
            properties = blob_client.get_blob_properties()
            
            return FileInfo(
                key=key,
                size=properties.size,
                content_type=properties.content_type,
                etag=properties.etag.strip('"') if properties.etag else None,
                last_modified=properties.last_modified,
                metadata=properties.metadata
            )
            
        except Exception as e:
            if "BlobNotFound" in str(e):
                return None
            else:
                logger.error(f"获取Azure文件信息失败: {key}, 错误: {str(e)}")
                return None
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出Azure文件"""
        try:
            if not self._initialized or not self._container_client:
                return {"error": "Azure Blob Storage未初始化"}
            
            # 准备查询参数
            list_kwargs = {}
            
            if prefix:
                list_kwargs['name_starts_with'] = self._clean_key(prefix)
            
            # 执行查询
            blobs = self._container_client.list_blobs(**list_kwargs)
            
            # 处理结果
            files = []
            count = 0
            
            for blob in blobs:
                if count >= limit:
                    break
                
                file_info = FileInfo(
                    key=blob.name,
                    size=blob.size,
                    etag=blob.etag.strip('"') if blob.etag else None,
                    last_modified=blob.last_modified,
                    metadata={}
                )
                files.append(file_info)
                count += 1
            
            # Azure SDK没有直接的分页支持，这里简化处理
            has_more = count >= limit
            
            return {
                "files": [fi.dict() for fi in files],
                "has_more": has_more,
                "continuation_token": None,  # Azure SDK的分页需要手动处理
                "count": count
            }
            
        except Exception as e:
            logger.error(f"列出Azure文件失败: 前缀={prefix}, 错误: {str(e)}")
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
        method: str = "GET"
    ) -> Optional[str]:
        """生成Azure预签名URL"""
        try:
            if not self._initialized or not self._container_client:
                return None
            
            clean_key = self._clean_key(key)
            
            # 检查blob是否存在
            if not await self.exists(key):
                return None
            
            # 获取blob客户端
            blob_client = self._container_client.get_blob_client(clean_key)
            
            # 生成SAS URL
            from datetime import datetime, timedelta
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            # 设置权限
            permissions = BlobSasPermissions(read=True)
            if method.upper() == "PUT":
                permissions = BlobSasPermissions(write=True)
            
            # 生成SAS令牌
            sas_token = generate_blob_sas(
                account_name=self._client.account_name,
                container_name=self._container_name,
                blob_name=clean_key,
                account_key=self._client.credential.account_key,
                permission=permissions,
                expiry=datetime.utcnow() + timedelta(seconds=expires_in)
            )
            
            # 构建完整URL
            url = f"{blob_client.url}?{sas_token}"
            
            return url
            
        except Exception as e:
            logger.error(f"生成Azure预签名URL失败: {key}, 错误: {str(e)}")
            return None
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """复制Azure文件"""
        try:
            if not self._initialized or not self._container_client:
                return False
            
            clean_source_key = self._clean_key(source_key)
            clean_dest_key = self._clean_key(dest_key)
            
            # 如果是同一Azure后端
            if dest_backend is None or dest_backend == self:
                # 获取源blob客户端
                source_blob_client = self._container_client.get_blob_client(clean_source_key)
                
                # 获取目标blob客户端
                dest_blob_client = self._container_client.get_blob_client(clean_dest_key)
                
                # 开始复制操作
                dest_blob_client.start_copy_from_url(source_blob_client.url)
                
                logger.info(f"Azure文件复制成功: {clean_source_key} -> {clean_dest_key}")
                return True
            
            # 如果是不同后端，使用下载再上传的方式
            else:
                # 下载源文件
                download_result = await self.download(source_key)
                if not download_result.success or not download_result.data:
                    return False
                
                # 上传到目标后端
                upload_result = await dest_backend.upload(
                    dest_key,
                    download_result.data,
                    download_result.content_type
                )
                
                return upload_result.success
            
        except Exception as e:
            logger.error(f"Azure复制文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    async def move(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """移动Azure文件"""
        try:
            # 如果是同一Azure后端
            if dest_backend is None or dest_backend == self:
                # 先复制
                copy_success = await self.copy(source_key, dest_key, None)
                if not copy_success:
                    return False
                
                # 再删除源文件
                return await self.delete(source_key)
            
            # 如果是不同后端，使用复制再删除的方式
            else:
                # 复制到目标后端
                copy_success = await self.copy(source_key, dest_key, dest_backend)
                if not copy_success:
                    return False
                
                # 删除源文件
                return await self.delete(source_key)
            
        except Exception as e:
            logger.error(f"Azure移动文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False