"""
Google Cloud Storage 实现
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

class GoogleCloudStorage(StorageBackend):
    """Google Cloud Storage 实现"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        
        # 验证必要配置
        if not config.bucket:  # 在GCS中bucket对应存储桶名称
            raise ValueError("Google Cloud Storage 需要 bucket 配置")
        
        # 初始化GCS客户端
        self._client = None
        self._bucket = None
        
    async def initialize(self) -> bool:
        """初始化Google Cloud Storage"""
        try:
            # 尝试导入Google Cloud SDK
            try:
                from google.cloud import storage
                from google.auth.exceptions import DefaultCredentialsError
            except ImportError:
                logger.error("Google Cloud SDK未安装，请运行: pip install google-cloud-storage")
                return False
            
            # 创建存储客户端
            try:
                self._client = storage.Client()
            except DefaultCredentialsError:
                logger.error("Google Cloud身份验证失败，请设置GOOGLE_APPLICATION_CREDENTIALS环境变量")
                return False
            
            # 获取存储桶
            try:
                self._bucket = self._client.get_bucket(self.config.bucket)
                logger.info(f"Google Cloud Storage桶已存在: {self.config.bucket}")
            except Exception as e:
                if "Not found" in str(e) or "404" in str(e):
                    if self.config.auto_create_bucket:
                        # 创建存储桶
                        self._bucket = self._client.create_bucket(self.config.bucket)
                        logger.info(f"Google Cloud Storage桶创建成功: {self.config.bucket}")
                    else:
                        logger.error(f"Google Cloud Storage桶不存在且未启用自动创建: {self.config.bucket}")
                        return False
                else:
                    logger.error(f"检查Google Cloud Storage桶失败: {str(e)}")
                    return False
            
            # 测试连接
            try:
                # 尝试列出blob（限制为1）
                blobs = list(self._bucket.list_blobs(max_results=1))
                logger.info(f"Google Cloud Storage初始化成功: {self.config.bucket}")
                self._initialized = True
                return True
            except Exception as e:
                logger.error(f"Google Cloud Storage连接测试失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Google Cloud Storage初始化失败: {str(e)}")
            return False
    
    def _clean_key(self, key: str) -> str:
        """清理GCS对象键"""
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
        """上传文件到Google Cloud Storage"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._bucket:
                return UploadResult(
                    success=False,
                    error="Google Cloud Storage未初始化"
                )
            
            clean_key = self._clean_key(key)
            
            # 获取blob
            blob = self._bucket.blob(clean_key)
            
            # 检查blob是否已存在
            if not overwrite:
                try:
                    if blob.exists():
                        return UploadResult(
                            success=False,
                            error=f"文件已存在: {clean_key}"
                        )
                except Exception as e:
                    return UploadResult(
                        success=False,
                        error=f"检查文件存在失败: {str(e)}"
                    )
            
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
            
            # 设置元数据
            blob.content_type = content_type
            if metadata:
                blob.metadata = metadata
            
            # 上传blob
            blob.upload_from_string(data_bytes, content_type=content_type)
            
            # 重新加载blob以获取最新属性
            blob.reload()
            
            # 生成访问URL
            url = self.get_public_url(clean_key)
            if not url:
                url = blob.public_url
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"Google Cloud文件上传成功: {clean_key}, 大小: {len(data_bytes)} bytes, 耗时: {duration}ms")
            
            return UploadResult(
                success=True,
                key=clean_key,
                url=url,
                size=len(data_bytes),
                etag=blob.etag.strip('"') if blob.etag else None,
                duration_ms=duration
            )
            
        except Exception as e:
            logger.error(f"Google Cloud上传文件失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传失败: {str(e)}"
            )
    
    async def download(self, key: str) -> DownloadResult:
        """从Google Cloud Storage下载文件"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._bucket:
                return DownloadResult(
                    success=False,
                    error="Google Cloud Storage未初始化"
                )
            
            clean_key = self._clean_key(key)
            
            # 获取blob
            blob = self._bucket.blob(clean_key)
            
            # 检查blob是否存在
            if not blob.exists():
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            
            # 下载blob
            data = blob.download_as_bytes()
            
            # 重新加载blob以获取属性
            blob.reload()
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"Google Cloud文件下载成功: {clean_key}, 大小: {len(data)} bytes, 耗时: {duration}ms")
            
            return DownloadResult(
                success=True,
                data=data,
                size=len(data),
                content_type=blob.content_type,
                duration_ms=duration
            )
            
        except Exception as e:
            if "Not found" in str(e) or "404" in str(e):
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            else:
                logger.error(f"Google Cloud下载文件失败: {key}, 错误: {str(e)}")
                return DownloadResult(
                    success=False,
                    error=f"下载失败: {str(e)}"
                )
    
    async def delete(self, key: str) -> bool:
        """从Google Cloud Storage删除文件"""
        try:
            if not self._initialized or not self._bucket:
                return False
            
            clean_key = self._clean_key(key)
            
            # 获取blob
            blob = self._bucket.blob(clean_key)
            
            # 删除blob
            blob.delete()
            
            logger.info(f"Google Cloud文件删除成功: {clean_key}")
            return True
            
        except Exception as e:
            if "Not found" in str(e) or "404" in str(e):
                logger.warning(f"尝试删除不存在的Google Cloud文件: {key}")
                return False
            else:
                logger.error(f"Google Cloud删除文件失败: {key}, 错误: {str(e)}")
                return False
    
    async def exists(self, key: str) -> bool:
        """检查Google Cloud文件是否存在"""
        try:
            if not self._initialized or not self._bucket:
                return False
            
            clean_key = self._clean_key(key)
            
            blob = self._bucket.blob(clean_key)
            return blob.exists()
            
        except Exception as e:
            logger.error(f"检查Google Cloud文件存在失败: {key}, 错误: {str(e)}")
            return False
    
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取Google Cloud文件信息"""
        try:
            if not self._initialized or not self._bucket:
                return None
            
            clean_key = self._clean_key(key)
            
            blob = self._bucket.blob(clean_key)
            
            # 检查是否存在
            if not blob.exists():
                return None
            
            # 获取属性
            blob.reload()
            
            return FileInfo(
                key=key,
                size=blob.size,
                content_type=blob.content_type,
                etag=blob.etag.strip('"') if blob.etag else None,
                last_modified=blob.updated,
                metadata=blob.metadata or {}
            )
            
        except Exception as e:
            logger.error(f"获取Google Cloud文件信息失败: {key}, 错误: {str(e)}")
            return None
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出Google Cloud文件"""
        try:
            if not self._initialized or not self._bucket:
                return {"error": "Google Cloud Storage未初始化"}
            
            # 准备查询参数
            list_kwargs = {
                'max_results': limit
            }
            
            if prefix:
                list_kwargs['prefix'] = self._clean_key(prefix)
            
            # 执行查询
            blobs = self._bucket.list_blobs(**list_kwargs)
            
            # 处理结果
            files = []
            count = 0
            
            for blob in blobs:
                file_info = FileInfo(
                    key=blob.name,
                    size=blob.size,
                    etag=blob.etag.strip('"') if blob.etag else None,
                    last_modified=blob.updated,
                    metadata=blob.metadata or {}
                )
                files.append(file_info)
                count += 1
            
            # GCS SDK自动处理分页
            has_more = count >= limit
            
            return {
                "files": [fi.dict() for fi in files],
                "has_more": has_more,
                "continuation_token": None,  # GCS SDK自动处理分页
                "count": count
            }
            
        except Exception as e:
            logger.error(f"列出Google Cloud文件失败: 前缀={prefix}, 错误: {str(e)}")
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
        """生成Google Cloud预签名URL"""
        try:
            if not self._initialized or not self._bucket:
                return None
            
            clean_key = self._clean_key(key)
            
            # 获取blob
            blob = self._bucket.blob(clean_key)
            
            # 检查blob是否存在
            if not blob.exists():
                return None
            
            # 生成签名URL
            from datetime import datetime, timedelta
            
            url = blob.generate_signed_url(
                expiration=timedelta(seconds=expires_in),
                method=method.upper()
            )
            
            return url
            
        except Exception as e:
            logger.error(f"生成Google Cloud预签名URL失败: {key}, 错误: {str(e)}")
            return None
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """复制Google Cloud文件"""
        try:
            if not self._initialized or not self._bucket:
                return False
            
            clean_source_key = self._clean_key(source_key)
            clean_dest_key = self._clean_key(dest_key)
            
            # 如果是同一GCS后端
            if dest_backend is None or dest_backend == self:
                # 获取源blob
                source_blob = self._bucket.blob(clean_source_key)
                
                # 检查源blob是否存在
                if not source_blob.exists():
                    return False
                
                # 复制blob
                self._bucket.copy_blob(source_blob, self._bucket, clean_dest_key)
                
                logger.info(f"Google Cloud文件复制成功: {clean_source_key} -> {clean_dest_key}")
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
            logger.error(f"Google Cloud复制文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    async def move(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """移动Google Cloud文件"""
        try:
            # 如果是同一GCS后端
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
            logger.error(f"Google Cloud移动文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False