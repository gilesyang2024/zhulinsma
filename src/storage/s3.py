"""
S3兼容对象存储实现
支持Amazon S3、MinIO、阿里云OSS、腾讯云COS等S3兼容服务
"""

import asyncio
import hashlib
import io
import time
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .base import (
    StorageBackend, StorageConfig, StorageType,
    FileInfo, UploadResult, DownloadResult
)
import logging
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class S3Storage(StorageBackend):
    """S3兼容对象存储实现"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        
        # 验证必要配置
        if not config.endpoint and not config.region:
            raise ValueError("S3存储需要 endpoint 或 region 配置")
        
        if not config.bucket:
            raise ValueError("S3存储需要 bucket 配置")
        
        if not config.access_key or not config.secret_key:
            raise ValueError("S3存储需要 access_key 和 secret_key 配置")
        
        # 初始化S3客户端
        self._client = None
        self._resource = None
        self._bucket = None
        
    async def initialize(self) -> bool:
        """初始化S3存储"""
        try:
            # 创建S3客户端配置
            client_config = Config(
                s3={
                    'addressing_style': 'auto'
                },
                retries={
                    'max_attempts': self.config.retry_count,
                    'mode': 'standard'
                },
                connect_timeout=self.config.timeout,
                read_timeout=self.config.timeout
            )
            
            # 创建S3客户端
            self._client = boto3.client(
                's3',
                endpoint_url=self.config.endpoint,
                region_name=self.config.region,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                config=client_config
            )
            
            # 创建S3资源
            self._resource = boto3.resource(
                's3',
                endpoint_url=self.config.endpoint,
                region_name=self.config.region,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                config=client_config
            )
            
            # 获取存储桶
            self._bucket = self._resource.Bucket(self.config.bucket)
            
            # 检查存储桶是否存在，如果不存在且配置了自动创建则创建
            try:
                self._client.head_bucket(Bucket=self.config.bucket)
                logger.info(f"S3存储桶已存在: {self.config.bucket}")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                if error_code == '404' or error_code == 'NoSuchBucket':
                    if self.config.auto_create_bucket:
                        # 创建存储桶
                        create_kwargs = {'Bucket': self.config.bucket}
                        
                        # 如果指定了区域，添加区域配置
                        if self.config.region and self.config.region != 'us-east-1':
                            create_kwargs['CreateBucketConfiguration'] = {
                                'LocationConstraint': self.config.region
                            }
                        
                        self._client.create_bucket(**create_kwargs)
                        logger.info(f"S3存储桶创建成功: {self.config.bucket}")
                    else:
                        logger.error(f"S3存储桶不存在且未启用自动创建: {self.config.bucket}")
                        return False
                else:
                    logger.error(f"检查S3存储桶失败: {error_code}, {str(e)}")
                    return False
            
            # 测试连接
            try:
                # 尝试列出对象（限制为0）
                self._client.list_objects_v2(Bucket=self.config.bucket, MaxKeys=1)
                logger.info(f"S3存储初始化成功: {self.config.bucket}")
                self._initialized = True
                return True
            except ClientError as e:
                logger.error(f"S3存储连接测试失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"S3存储初始化失败: {str(e)}")
            return False
    
    def _clean_key(self, key: str) -> str:
        """清理S3对象键"""
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
        """上传文件到S3"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._client:
                return UploadResult(
                    success=False,
                    error="S3存储未初始化"
                )
            
            # 清理键
            clean_key = self._clean_key(key)
            
            # 检查文件是否已存在
            if not overwrite:
                try:
                    self._client.head_object(Bucket=self.config.bucket, Key=clean_key)
                    return UploadResult(
                        success=False,
                        error=f"文件已存在: {clean_key}"
                    )
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    if error_code != '404':
                        # 其他错误
                        return UploadResult(
                            success=False,
                            error=f"检查文件存在失败: {error_code}"
                        )
            
            # 准备上传参数
            upload_kwargs = {
                'Bucket': self.config.bucket,
                'Key': clean_key
            }
            
            # 处理数据
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
                body = io.BytesIO(data_bytes)
            elif isinstance(data, bytes):
                data_bytes = data
                body = io.BytesIO(data_bytes)
            elif hasattr(data, 'read'):
                # 如果是文件流
                if hasattr(data, 'seek') and data.tell() > 0:
                    data.seek(0)
                body = data
                # 尝试获取数据大小
                try:
                    if hasattr(data, 'getbuffer'):
                        data_bytes = data.getbuffer()
                    else:
                        # 对于流，我们可能需要读取来计算大小
                        current_pos = data.tell()
                        data.seek(0, 2)  # 移动到末尾
                        data_size = data.tell()
                        data.seek(current_pos)  # 恢复位置
                        data_bytes = b''
                except:
                    data_bytes = b''
            else:
                return UploadResult(
                    success=False,
                    error=f"不支持的数据类型: {type(data)}"
                )
            
            # 检查文件大小
            if isinstance(data_bytes, bytes) and len(data_bytes) > self.config.max_file_size:
                return UploadResult(
                    success=False,
                    error=f"文件大小超过限制: {len(data_bytes)} > {self.config.max_file_size}"
                )
            
            # 设置内容类型
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            else:
                # 自动检测
                content_type = self.get_content_type(clean_key)
                extra_args['ContentType'] = content_type
            
            # 设置元数据
            if metadata:
                # 转换元数据格式
                s3_metadata = {}
                for k, v in metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        s3_metadata[k] = str(v)
                extra_args['Metadata'] = s3_metadata
            
            # 如果需要加密
            if self.config.enable_encryption:
                extra_args['ServerSideEncryption'] = 'AES256'
            
            if extra_args:
                upload_kwargs['ExtraArgs'] = extra_args
            
            # 执行上传
            if isinstance(data_bytes, bytes) and len(data_bytes) > self.config.chunk_size:
                # 大文件使用分块上传
                upload_result = await self._multipart_upload(clean_key, body, len(data_bytes), extra_args)
            else:
                # 小文件直接上传
                body.seek(0)
                response = self._client.put_object(
                    Bucket=self.config.bucket,
                    Key=clean_key,
                    Body=body,
                    **extra_args
                )
                upload_result = UploadResult(
                    success=True,
                    key=clean_key,
                    etag=response.get('ETag', '').strip('"'),
                    size=len(data_bytes) if isinstance(data_bytes, bytes) else 0
                )
            
            # 生成访问URL
            url = self.get_public_url(clean_key)
            if not url:
                # 如果没有配置公开URL基础，生成S3 URL
                if self.config.endpoint:
                    url = f"{self.config.endpoint.rstrip('/')}/{self.config.bucket}/{clean_key}"
                else:
                    url = f"https://{self.config.bucket}.s3.{self.config.region}.amazonaws.com/{clean_key}"
            
            duration = int((time.time() - start_time) * 1000)
            upload_result.url = url
            upload_result.duration_ms = duration
            
            logger.info(f"S3文件上传成功: {clean_key}, 大小: {upload_result.size} bytes, 耗时: {duration}ms")
            
            return upload_result
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"S3上传文件失败: {key}, 错误: {error_code} - {error_msg}")
            
            return UploadResult(
                success=False,
                error=f"S3上传失败: {error_code} - {error_msg}"
            )
        except Exception as e:
            logger.error(f"S3上传文件失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传失败: {str(e)}"
            )
    
    async def _multipart_upload(
        self,
        key: str,
        body: io.BytesIO,
        total_size: int,
        extra_args: Dict[str, Any]
    ) -> UploadResult:
        """分块上传大文件"""
        try:
            # 创建分块上传
            response = self._client.create_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                **extra_args
            )
            upload_id = response['UploadId']
            
            # 分块上传
            part_number = 1
            parts = []
            chunk_size = self.config.chunk_size
            
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                
                # 上传分块
                response = self._client.upload_part(
                    Bucket=self.config.bucket,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )
                
                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })
                
                part_number += 1
            
            # 完成分块上传
            response = self._client.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            return UploadResult(
                success=True,
                key=key,
                etag=response.get('ETag', '').strip('"'),
                size=total_size
            )
            
        except Exception as e:
            logger.error(f"S3分块上传失败: {key}, 错误: {str(e)}")
            
            # 尝试取消上传
            try:
                if 'upload_id' in locals():
                    self._client.abort_multipart_upload(
                        Bucket=self.config.bucket,
                        Key=key,
                        UploadId=upload_id
                    )
            except:
                pass
            
            return UploadResult(
                success=False,
                error=f"分块上传失败: {str(e)}"
            )
    
    async def download(self, key: str) -> DownloadResult:
        """从S3下载文件"""
        start_time = time.time()
        
        try:
            if not self._initialized or not self._client:
                return DownloadResult(
                    success=False,
                    error="S3存储未初始化"
                )
            
            clean_key = self._clean_key(key)
            
            # 获取对象
            response = self._client.get_object(
                Bucket=self.config.bucket,
                Key=clean_key
            )
            
            # 读取数据
            data = response['Body'].read()
            
            # 获取元数据
            content_type = response.get('ContentType')
            etag = response.get('ETag', '').strip('"')
            size = len(data)
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"S3文件下载成功: {clean_key}, 大小: {size} bytes, 耗时: {duration}ms")
            
            return DownloadResult(
                success=True,
                data=data,
                size=size,
                content_type=content_type,
                duration_ms=duration
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey' or error_code == '404':
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            else:
                error_msg = e.response.get('Error', {}).get('Message', str(e))
                logger.error(f"S3下载文件失败: {key}, 错误: {error_code} - {error_msg}")
                
                return DownloadResult(
                    success=False,
                    error=f"S3下载失败: {error_code} - {error_msg}"
                )
        except Exception as e:
            logger.error(f"S3下载文件失败: {key}, 错误: {str(e)}")
            return DownloadResult(
                success=False,
                error=f"下载失败: {str(e)}"
            )
    
    async def delete(self, key: str) -> bool:
        """从S3删除文件"""
        try:
            if not self._initialized or not self._client:
                return False
            
            clean_key = self._clean_key(key)
            
            # 删除对象
            self._client.delete_object(
                Bucket=self.config.bucket,
                Key=clean_key
            )
            
            logger.info(f"S3文件删除成功: {clean_key}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey' or error_code == '404':
                logger.warning(f"尝试删除不存在的S3文件: {key}")
                return False
            else:
                error_msg = e.response.get('Error', {}).get('Message', str(e))
                logger.error(f"S3删除文件失败: {key}, 错误: {error_code} - {error_msg}")
                return False
        except Exception as e:
            logger.error(f"S3删除文件失败: {key}, 错误: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查S3文件是否存在"""
        try:
            if not self._initialized or not self._client:
                return False
            
            clean_key = self._clean_key(key)
            
            self._client.head_object(
                Bucket=self.config.bucket,
                Key=clean_key
            )
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            return error_code != 'NoSuchKey' and error_code != '404'
        except Exception as e:
            logger.error(f"检查S3文件存在失败: {key}, 错误: {str(e)}")
            return False
    
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取S3文件信息"""
        try:
            if not self._initialized or not self._client:
                return None
            
            clean_key = self._clean_key(key)
            
            response = self._client.head_object(
                Bucket=self.config.bucket,
                Key=clean_key
            )
            
            return FileInfo(
                key=key,
                size=response['ContentLength'],
                content_type=response.get('ContentType'),
                etag=response.get('ETag', '').strip('"'),
                last_modified=response['LastModified'],
                metadata=response.get('Metadata', {})
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey' or error_code == '404':
                return None
            else:
                logger.error(f"获取S3文件信息失败: {key}, 错误: {error_code}")
                return None
        except Exception as e:
            logger.error(f"获取S3文件信息失败: {key}, 错误: {str(e)}")
            return None
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出S3文件"""
        try:
            if not self._initialized or not self._client:
                return {
                    "files": [],
                    "has_more": False,
                    "continuation_token": None,
                    "error": "S3存储未初始化"
                }
            
            # 准备查询参数
            list_kwargs = {
                'Bucket': self.config.bucket,
                'MaxKeys': limit
            }
            
            if prefix:
                list_kwargs['Prefix'] = self._clean_key(prefix)
            
            if continuation_token:
                list_kwargs['ContinuationToken'] = continuation_token
            
            # 执行查询
            response = self._client.list_objects_v2(**list_kwargs)
            
            # 处理结果
            files = []
            for obj in response.get('Contents', []):
                file_info = FileInfo(
                    key=obj['Key'],
                    size=obj['Size'],
                    etag=obj.get('ETag', '').strip('"'),
                    last_modified=obj['LastModified'],
                    metadata={}
                )
                files.append(file_info)
            
            return {
                "files": [fi.dict() for fi in files],
                "has_more": response.get('IsTruncated', False),
                "continuation_token": response.get('NextContinuationToken'),
                "key_count": response.get('KeyCount', 0),
                "prefix": prefix
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"列出S3文件失败: 前缀={prefix}, 错误: {error_code} - {error_msg}")
            
            return {
                "files": [],
                "has_more": False,
                "continuation_token": None,
                "error": f"S3列出失败: {error_code} - {error_msg}"
            }
        except Exception as e:
            logger.error(f"列出S3文件失败: 前缀={prefix}, 错误: {str(e)}")
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
        """生成S3预签名URL"""
        try:
            if not self._initialized or not self._client:
                return None
            
            clean_key = self._clean_key(key)
            
            # 检查文件是否存在
            if not await self.exists(key):
                return None
            
            # 生成预签名URL
            url = self._client.generate_presigned_url(
                ClientMethod='get_object' if method.upper() == 'GET' else 'put_object',
                Params={
                    'Bucket': self.config.bucket,
                    'Key': clean_key
                },
                ExpiresIn=expires_in
            )
            
            return url
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"生成S3预签名URL失败: {key}, 错误: {error_code}")
            return None
        except Exception as e:
            logger.error(f"生成S3预签名URL失败: {key}, 错误: {str(e)}")
            return None
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """复制S3文件"""
        try:
            if not self._initialized or not self._client:
                return False
            
            clean_source_key = self._clean_key(source_key)
            clean_dest_key = self._clean_key(dest_key)
            
            # 如果是同一S3后端
            if dest_backend is None or dest_backend == self:
                # 在同一存储桶内复制
                copy_source = {
                    'Bucket': self.config.bucket,
                    'Key': clean_source_key
                }
                
                self._client.copy_object(
                    CopySource=copy_source,
                    Bucket=self.config.bucket,
                    Key=clean_dest_key
                )
                
                logger.info(f"S3文件复制成功: {clean_source_key} -> {clean_dest_key}")
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
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"S3复制文件失败: {source_key} -> {dest_key}, 错误: {error_code} - {error_msg}")
            return False
        except Exception as e:
            logger.error(f"S3复制文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    async def move(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """移动S3文件"""
        try:
            # 如果是同一S3后端
            if dest_backend is None or dest_backend == self:
                clean_source_key = self._clean_key(source_key)
                clean_dest_key = self._clean_key(dest_key)
                
                # 在同一存储桶内复制
                copy_source = {
                    'Bucket': self.config.bucket,
                    'Key': clean_source_key
                }
                
                self._client.copy_object(
                    CopySource=copy_source,
                    Bucket=self.config.bucket,
                    Key=clean_dest_key
                )
                
                # 删除源文件
                await self.delete(source_key)
                
                logger.info(f"S3文件移动成功: {clean_source_key} -> {clean_dest_key}")
                return True
            
            # 如果是不同后端，使用复制再删除的方式
            else:
                # 复制到目标后端
                copy_success = await self.copy(source_key, dest_key, dest_backend)
                if not copy_success:
                    return False
                
                # 删除源文件
                return await self.delete(source_key)
            
        except Exception as e:
            logger.error(f"S3移动文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    # ====== S3特有方法 ======
    
    async def get_bucket_info(self) -> Dict[str, Any]:
        """获取存储桶信息"""
        try:
            if not self._initialized or not self._client:
                return {"error": "S3存储未初始化"}
            
            # 获取存储桶位置
            location = self._client.get_bucket_location(Bucket=self.config.bucket)
            
            # 获取存储桶策略
            try:
                policy = self._client.get_bucket_policy(Bucket=self.config.bucket)
            except:
                policy = None
            
            # 获取存储桶版本控制状态
            try:
                versioning = self._client.get_bucket_versioning(Bucket=self.config.bucket)
            except:
                versioning = {}
            
            # 获取存储桶生命周期配置
            try:
                lifecycle = self._client.get_bucket_lifecycle_configuration(Bucket=self.config.bucket)
            except:
                lifecycle = None
            
            return {
                "bucket": self.config.bucket,
                "location": location.get('LocationConstraint', 'us-east-1'),
                "creation_date": None,  # S3 API不直接提供创建日期
                "has_policy": policy is not None,
                "versioning_status": versioning.get('Status', 'Disabled'),
                "has_lifecycle": lifecycle is not None,
                "endpoint": self.config.endpoint,
                "region": self.config.region
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"获取S3存储桶信息失败: {self.config.bucket}, 错误: {error_code} - {error_msg}")
            
            return {
                "bucket": self.config.bucket,
                "error": f"{error_code} - {error_msg}"
            }
        except Exception as e:
            logger.error(f"获取S3存储桶信息失败: {self.config.bucket}, 错误: {str(e)}")
            return {
                "bucket": self.config.bucket,
                "error": str(e)
            }
    
    async def set_object_acl(
        self,
        key: str,
        acl: str = "private"
    ) -> bool:
        """设置对象ACL"""
        try:
            if not self._initialized or not self._client:
                return False
            
            clean_key = self._clean_key(key)
            
            valid_acls = ["private", "public-read", "public-read-write", "authenticated-read"]
            if acl not in valid_acls:
                raise ValueError(f"无效的ACL: {acl}, 有效值: {valid_acls}")
            
            self._client.put_object_acl(
                Bucket=self.config.bucket,
                Key=clean_key,
                ACL=acl
            )
            
            logger.info(f"S3对象ACL设置成功: {clean_key} -> {acl}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"设置S3对象ACL失败: {key}, 错误: {error_code} - {error_msg}")
            return False
        except Exception as e:
            logger.error(f"设置S3对象ACL失败: {key}, 错误: {str(e)}")
            return False
    
    async def enable_versioning(self) -> bool:
        """启用存储桶版本控制"""
        try:
            if not self._initialized or not self._client:
                return False
            
            self._client.put_bucket_versioning(
                Bucket=self.config.bucket,
                VersioningConfiguration={
                    'Status': 'Enabled'
                }
            )
            
            logger.info(f"S3存储桶版本控制已启用: {self.config.bucket}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"启用S3存储桶版本控制失败: {self.config.bucket}, 错误: {error_code} - {error_msg}")
            return False
        except Exception as e:
            logger.error(f"启用S3存储桶版本控制失败: {self.config.bucket}, 错误: {str(e)}")
            return False
    
    async def get_object_versions(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """获取对象版本列表"""
        try:
            if not self._initialized or not self._client:
                return {"error": "S3存储未初始化"}
            
            list_kwargs = {
                'Bucket': self.config.bucket,
                'MaxKeys': limit
            }
            
            if prefix:
                list_kwargs['Prefix'] = self._clean_key(prefix)
            
            response = self._client.list_object_versions(**list_kwargs)
            
            versions = []
            delete_markers = []
            
            # 处理版本
            for version in response.get('Versions', []):
                versions.append({
                    'key': version['Key'],
                    'version_id': version['VersionId'],
                    'is_latest': version.get('IsLatest', False),
                    'last_modified': version['LastModified'].isoformat() if 'LastModified' in version else None,
                    'size': version['Size'],
                    'etag': version.get('ETag', '').strip('"')
                })
            
            # 处理删除标记
            for marker in response.get('DeleteMarkers', []):
                delete_markers.append({
                    'key': marker['Key'],
                    'version_id': marker['VersionId'],
                    'is_latest': marker.get('IsLatest', False),
                    'last_modified': marker['LastModified'].isoformat() if 'LastModified' in marker else None
                })
            
            return {
                "versions": versions,
                "delete_markers": delete_markers,
                "has_more": response.get('IsTruncated', False),
                "key_marker": response.get('NextKeyMarker'),
                "version_id_marker": response.get('NextVersionIdMarker')
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"获取S3对象版本失败: 前缀={prefix}, 错误: {error_code} - {error_msg}")
            
            return {
                "versions": [],
                "delete_markers": [],
                "error": f"{error_code} - {error_msg}"
            }
        except Exception as e:
            logger.error(f"获取S3对象版本失败: 前缀={prefix}, 错误: {str(e)}")
            return {
                "versions": [],
                "delete_markers": [],
                "error": str(e)
            }