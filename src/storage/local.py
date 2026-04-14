"""
本地文件系统存储实现
"""

import asyncio
import hashlib
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union
from urllib.parse import urljoin

from .base import (
    StorageBackend, StorageConfig, StorageType,
    FileInfo, UploadResult, DownloadResult
)
import logging
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class LocalStorage(StorageBackend):
    """本地文件系统存储实现"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = Path(config.base_path or "./storage")
        self._ensure_base_path()
    
    def _ensure_base_path(self) -> None:
        """确保基础路径存在"""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"本地存储基础路径已创建: {self.base_path}")
        except Exception as e:
            logger.error(f"创建本地存储基础路径失败: {self.base_path}, 错误: {str(e)}")
            raise
    
    async def initialize(self) -> bool:
        """初始化本地存储"""
        try:
            self._ensure_base_path()
            
            # 检查目录权限
            test_file = self.base_path / ".test_permission"
            try:
                test_file.touch()
                test_file.unlink()
                logger.info(f"本地存储初始化成功: {self.base_path}")
                self._initialized = True
                return True
            except PermissionError:
                logger.error(f"本地存储目录权限不足: {self.base_path}")
                return False
                
        except Exception as e:
            logger.error(f"本地存储初始化失败: {str(e)}")
            return False
    
    def _get_full_path(self, key: str) -> Path:
        """获取完整的本地文件路径"""
        # 清理路径，防止路径遍历攻击
        clean_key = key.lstrip("/")
        if ".." in clean_key or clean_key.startswith("/"):
            raise ValueError(f"无效的文件键: {key}")
        
        return self.base_path / clean_key
    
    async def upload(
        self,
        key: str,
        data: Union[bytes, BinaryIO, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        overwrite: bool = False
    ) -> UploadResult:
        """上传文件到本地存储"""
        start_time = time.time()
        
        try:
            # 获取完整路径
            full_path = self._get_full_path(key)
            
            # 检查文件是否已存在
            if full_path.exists() and not overwrite:
                return UploadResult(
                    success=False,
                    error=f"文件已存在: {key}"
                )
            
            # 确保目录存在
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 处理数据
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            elif isinstance(data, bytes):
                data_bytes = data
            elif hasattr(data, 'read'):
                # 如果是文件流
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
            
            # 写入文件
            with open(full_path, "wb") as f:
                f.write(data_bytes)
            
            # 计算ETag
            etag = hashlib.md5(data_bytes).hexdigest()
            
            # 获取文件信息
            file_size = len(data_bytes)
            last_modified = datetime.fromtimestamp(full_path.stat().st_mtime)
            
            # 生成访问URL
            url = self.get_public_url(key)
            if not url and self.config.public_url_base:
                url = urljoin(self.config.public_url_base, key.lstrip("/"))
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"文件上传成功: {key}, 大小: {file_size} bytes, 耗时: {duration}ms")
            
            return UploadResult(
                success=True,
                key=key,
                url=url,
                size=file_size,
                etag=etag,
                duration_ms=duration
            )
            
        except ValueError as e:
            return UploadResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"上传文件失败: {key}, 错误: {str(e)}")
            return UploadResult(
                success=False,
                error=f"上传失败: {str(e)}"
            )
    
    async def download(self, key: str) -> DownloadResult:
        """从本地存储下载文件"""
        start_time = time.time()
        
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                return DownloadResult(
                    success=False,
                    error=f"文件不存在: {key}"
                )
            
            # 读取文件
            with open(full_path, "rb") as f:
                data = f.read()
            
            # 获取文件信息
            file_size = len(data)
            stat_info = full_path.stat()
            
            # 自动检测内容类型
            import mimetypes
            content_type, _ = mimetypes.guess_type(str(full_path))
            if not content_type:
                content_type = self.get_content_type(key)
            
            duration = int((time.time() - start_time) * 1000)
            
            logger.info(f"文件下载成功: {key}, 大小: {file_size} bytes, 耗时: {duration}ms")
            
            return DownloadResult(
                success=True,
                data=data,
                size=file_size,
                content_type=content_type,
                duration_ms=duration
            )
            
        except ValueError as e:
            return DownloadResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"下载文件失败: {key}, 错误: {str(e)}")
            return DownloadResult(
                success=False,
                error=f"下载失败: {str(e)}"
            )
    
    async def delete(self, key: str) -> bool:
        """从本地存储删除文件"""
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                logger.warning(f"尝试删除不存在的文件: {key}")
                return False
            
            # 删除文件
            full_path.unlink()
            
            # 尝试删除空目录
            try:
                parent = full_path.parent
                if parent != self.base_path and parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except:
                pass
            
            logger.info(f"文件删除成功: {key}")
            return True
            
        except ValueError as e:
            logger.error(f"删除文件失败(无效键): {key}, 错误: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {key}, 错误: {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        try:
            full_path = self._get_full_path(key)
            return full_path.exists() and full_path.is_file()
        except ValueError:
            return False
        except Exception as e:
            logger.error(f"检查文件存在失败: {key}, 错误: {str(e)}")
            return False
    
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取文件信息"""
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists() or not full_path.is_file():
                return None
            
            # 获取文件属性
            stat_info = full_path.stat()
            
            # 读取文件计算ETag
            with open(full_path, "rb") as f:
                data = f.read(8192)  # 只读取前8KB计算ETag
                etag = hashlib.md5(data).hexdigest()
            
            # 自动检测内容类型
            import mimetypes
            content_type, _ = mimetypes.guess_type(str(full_path))
            if not content_type:
                content_type = self.get_content_type(key)
            
            return FileInfo(
                key=key,
                size=stat_info.st_size,
                content_type=content_type,
                etag=etag,
                last_modified=datetime.fromtimestamp(stat_info.st_mtime),
                metadata={}
            )
            
        except ValueError as e:
            logger.error(f"获取文件信息失败(无效键): {key}, 错误: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取文件信息失败: {key}, 错误: {str(e)}")
            return None
    
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """列出文件"""
        try:
            # 获取搜索路径
            if prefix:
                search_path = self._get_full_path(prefix)
                if not search_path.exists():
                    return {
                        "files": [],
                        "has_more": False,
                        "continuation_token": None
                    }
            else:
                search_path = self.base_path
            
            # 收集文件
            files: List[FileInfo] = []
            scanned_count = 0
            
            # 使用continuation_token实现分页
            start_after = None
            if continuation_token:
                # 简单的分页实现：基于文件路径
                start_after = continuation_token
            
            for root, dirs, file_names in os.walk(search_path):
                # 限制扫描数量
                if scanned_count >= limit * 2:  # 多扫描一些以防过滤
                    break
                
                for file_name in file_names:
                    # 构建相对路径
                    full_file_path = Path(root) / file_name
                    try:
                        rel_path = full_file_path.relative_to(self.base_path)
                        key = str(rel_path).replace("\\", "/")
                    except ValueError:
                        continue
                    
                    # 应用前缀过滤
                    if prefix and not key.startswith(prefix.lstrip("/")):
                        continue
                    
                    # 应用分页
                    if start_after and key <= start_after:
                        continue
                    
                    scanned_count += 1
                    
                    # 获取文件信息
                    file_info = await self.get_info(key)
                    if file_info:
                        files.append(file_info)
                    
                    # 达到限制
                    if len(files) >= limit:
                        break
                
                if len(files) >= limit:
                    break
            
            # 按路径排序
            files.sort(key=lambda x: x.key)
            
            # 生成下一个continuation_token
            next_token = None
            if len(files) >= limit and scanned_count >= limit:
                next_token = files[-1].key
            
            return {
                "files": [fi.dict() for fi in files],
                "has_more": next_token is not None,
                "continuation_token": next_token,
                "total_scanned": scanned_count
            }
            
        except Exception as e:
            logger.error(f"列出文件失败: 前缀={prefix}, 错误: {str(e)}")
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
        """
        生成预签名URL
        
        注意：本地存储不支持真正的预签名URL，
        这里返回公开URL或文件路径
        """
        try:
            if not await self.exists(key):
                return None
            
            # 如果有配置公开URL基础，使用之
            if self.config.public_url_base:
                url = self.get_public_url(key)
                if url:
                    return url
            
            # 否则返回文件路径（仅用于内部使用）
            full_path = self._get_full_path(key)
            return str(full_path.absolute())
            
        except Exception as e:
            logger.error(f"生成预签名URL失败: {key}, 错误: {str(e)}")
            return None
    
    async def copy(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """复制文件"""
        try:
            # 如果是同一后端
            if dest_backend is None or dest_backend == self:
                source_path = self._get_full_path(source_key)
                dest_path = self._get_full_path(dest_key)
                
                if not source_path.exists():
                    return False
                
                # 确保目标目录存在
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制文件
                shutil.copy2(source_path, dest_path)
                logger.info(f"文件复制成功: {source_key} -> {dest_key}")
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
            logger.error(f"复制文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    async def move(
        self,
        source_key: str,
        dest_key: str,
        dest_backend: Optional[StorageBackend] = None
    ) -> bool:
        """移动文件"""
        try:
            # 如果是同一后端
            if dest_backend is None or dest_backend == self:
                source_path = self._get_full_path(source_key)
                dest_path = self._get_full_path(dest_key)
                
                if not source_path.exists():
                    return False
                
                # 确保目标目录存在
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 移动文件
                shutil.move(str(source_path), str(dest_path))
                logger.info(f"文件移动成功: {source_key} -> {dest_key}")
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
            logger.error(f"移动文件失败: {source_key} -> {dest_key}, 错误: {str(e)}")
            return False
    
    # ====== 本地存储特有方法 ======
    
    async def get_disk_usage(self) -> Dict[str, Any]:
        """获取磁盘使用情况"""
        try:
            import psutil
            
            disk_usage = psutil.disk_usage(str(self.base_path))
            
            return {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": disk_usage.percent,
                "path": str(self.base_path)
            }
        except ImportError:
            logger.warning("psutil未安装，无法获取磁盘使用情况")
            return {
                "path": str(self.base_path),
                "error": "psutil未安装"
            }
        except Exception as e:
            logger.error(f"获取磁盘使用情况失败: {str(e)}")
            return {
                "path": str(self.base_path),
                "error": str(e)
            }
    
    async def cleanup_old_files(
        self,
        days_old: int = 30,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """清理旧文件"""
        try:
            import time
            from datetime import datetime, timedelta
            
            cutoff_time = time.time() - (days_old * 24 * 3600)
            deleted_count = 0
            total_size = 0
            errors = []
            
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    # 应用模式过滤
                    if pattern and pattern not in file:
                        continue
                    
                    file_path = Path(root) / file
                    
                    # 检查文件修改时间
                    try:
                        mtime = file_path.stat().st_mtime
                        if mtime < cutoff_time:
                            # 计算文件大小
                            file_size = file_path.stat().st_size
                            
                            # 删除文件
                            file_path.unlink()
                            
                            deleted_count += 1
                            total_size += file_size
                            
                            logger.debug(f"清理旧文件: {file_path}, 大小: {file_size} bytes")
                    except Exception as e:
                        errors.append(f"{file_path}: {str(e)}")
            
            # 清理空目录
            for root, dirs, files in os.walk(self.base_path, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                    except:
                        pass
            
            result = {
                "deleted_count": deleted_count,
                "total_size_freed": total_size,
                "errors": errors,
                "cutoff_date": datetime.fromtimestamp(cutoff_time).isoformat()
            }
            
            logger.info(f"文件清理完成: 删除 {deleted_count} 个文件, 释放 {total_size} bytes")
            return result
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {str(e)}")
            return {
                "deleted_count": 0,
                "total_size_freed": 0,
                "errors": [str(e)],
                "error": f"清理失败: {str(e)}"
            }
    
    async def backup(self, backup_path: Union[str, Path]) -> bool:
        """备份存储目录"""
        try:
            backup_path = Path(backup_path)
            
            # 确保备份目录存在
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # 生成备份文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"storage_backup_{timestamp}.tar.gz"
            
            # 使用tar命令创建压缩备份
            import subprocess
            import shlex
            
            # 切换到存储目录的父目录
            storage_parent = self.base_path.parent
            storage_name = self.base_path.name
            
            cmd = f"tar -czf {shlex.quote(str(backup_file))} -C {shlex.quote(str(storage_parent))} {shlex.quote(storage_name)}"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                backup_size = backup_file.stat().st_size if backup_file.exists() else 0
                logger.info(f"存储备份成功: {backup_file}, 大小: {backup_size} bytes")
                return True
            else:
                logger.error(f"存储备份失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"存储备份失败: {str(e)}")
            return False
    
    async def restore(self, backup_file: Union[str, Path]) -> bool:
        """从备份恢复存储目录"""
        try:
            backup_file = Path(backup_file)
            
            if not backup_file.exists():
                logger.error(f"备份文件不存在: {backup_file}")
                return False
            
            # 备份当前存储目录
            temp_backup = self.base_path.parent / f"storage_backup_temp_{int(time.time())}"
            if self.base_path.exists():
                shutil.move(str(self.base_path), str(temp_backup))
            
            try:
                # 恢复备份
                import subprocess
                import shlex
                
                storage_parent = self.base_path.parent
                
                cmd = f"tar -xzf {shlex.quote(str(backup_file))} -C {shlex.quote(str(storage_parent))}"
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # 删除临时备份
                    if temp_backup.exists():
                        shutil.rmtree(str(temp_backup))
                    
                    logger.info(f"存储恢复成功: {backup_file}")
                    return True
                else:
                    # 恢复失败，恢复原始目录
                    if temp_backup.exists():
                        if self.base_path.exists():
                            shutil.rmtree(str(self.base_path))
                        shutil.move(str(temp_backup), str(self.base_path))
                    
                    logger.error(f"存储恢复失败: {result.stderr}")
                    return False
                    
            except Exception as restore_error:
                # 恢复失败，尝试恢复原始目录
                if temp_backup.exists():
                    if self.base_path.exists():
                        shutil.rmtree(str(self.base_path))
                    shutil.move(str(temp_backup), str(self.base_path))
                
                logger.error(f"存储恢复失败: {str(restore_error)}")
                return False
                
        except Exception as e:
            logger.error(f"存储恢复失败: {str(e)}")
            return False