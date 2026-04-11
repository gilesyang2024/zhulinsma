"""
媒体和审计系统模型
包含 Media, MediaProcessTask, AuditLog 等模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, JSON, CheckConstraint, Text, BigInteger, ARRAY
from src.core.uuid_compat import GUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from src.core.database import Base


class Media(Base):
    """
    媒体文件模型
    支持图片、视频、音频、文档等多种文件类型
    """
    __tablename__ = "media"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255))
    mime_type = Column(String(100))
    size_bytes = Column(BigInteger)
    storage_path = Column(Text, nullable=False)
    storage_provider = Column(String(50), default="local")
    storage_bucket = Column(String(100), default="default")
    
    # 文件属性
    file_hash = Column(String(64))  # SHA256哈希
    width = Column(Integer)
    height = Column(Integer)
    duration_seconds = Column(Integer)  # 视频/音频时长
    bitrate = Column(Integer)  # 比特率
    format = Column(String(50))
    
    # 元数据
    title = Column(String(255))
    description = Column(Text)
    alt_text = Column(Text)
    caption = Column(Text)
    media_metadata = Column(JSONB, default=dict)  # EXIF, IPTC等
    tags = Column(ARRAY(String))
    
    # 所有权
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content_id = Column(GUID(), ForeignKey("content.id", ondelete="SET NULL"), nullable=True)
    
    # 状态
    is_public = Column(Boolean, default=True)
    is_processed = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # 关系
    uploader = relationship("User", back_populates="media_items")
    content = relationship("Content", back_populates="media_items")
    process_tasks = relationship("MediaProcessTask", back_populates="media", cascade="all, delete-orphan")
    message_attachments = relationship("MessageAttachment", back_populates="media", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("storage_provider IN ('local', 's3', 'minio', 'cloudinary')", name="storage_provider_enum"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10737418240", name="chk_file_size"),  # 最大10GB
    )
    
    @hybrid_property
    def is_image(self) -> bool:
        """检查是否为图片"""
        return self.mime_type and self.mime_type.startswith("image/")
    
    @hybrid_property
    def is_video(self) -> bool:
        """检查是否为视频"""
        return self.mime_type and self.mime_type.startswith("video/")
    
    @hybrid_property
    def is_audio(self) -> bool:
        """检查是否为音频"""
        return self.mime_type and self.mime_type.startswith("audio/")
    
    @hybrid_property
    def is_document(self) -> bool:
        """检查是否为文档"""
        return self.mime_type and (
            self.mime_type.startswith("application/") or 
            self.mime_type in ["text/plain", "text/html", "text/markdown"]
        )
    
    @hybrid_property
    def file_size_human(self) -> str:
        """获取人类可读的文件大小"""
        if not self.size_bytes:
            return "0 B"
        
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    @hybrid_property
    def duration_human(self) -> str:
        """获取人类可读的时长"""
        if not self.duration_seconds:
            return ""
        
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "file_size_human": self.file_size_human,
            "storage_provider": self.storage_provider,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "duration_human": self.duration_human,
            "format": self.format,
            "title": self.title,
            "description": self.description,
            "alt_text": self.alt_text,
            "caption": self.caption,
            "is_public": self.is_public,
            "is_processed": self.is_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_private:
            data.update({
                "storage_path": self.storage_path,
                "storage_bucket": self.storage_bucket,
                "file_hash": self.file_hash,
                "bitrate": self.bitrate,
                "tags": self.tags,
                "metadata": self.media_metadata,
                "user_id": str(self.user_id) if self.user_id else None,
                "content_id": str(self.content_id) if self.content_id else None,
            })
        
        if self.uploader and self.is_public:
            data["uploader"] = {
                "id": str(self.uploader.id),
                "username": self.uploader.username,
                "avatar_url": self.uploader.avatar_url,
            }
        
        return data
    
    def get_url(self) -> str:
        """获取媒体文件的访问URL"""
        if self.storage_provider == "local":
            # 本地存储的相对URL
            return f"/media/{self.storage_path}"
        elif self.storage_provider == "s3":
            # S3存储的URL
            return f"https://{self.storage_bucket}.s3.amazonaws.com/{self.storage_path}"
        elif self.storage_provider == "cloudinary":
            # Cloudinary的URL
            return f"https://res.cloudinary.com/{self.storage_bucket}/{self.storage_path}"
        else:
            # 其他存储提供商的URL
            return f"/media/{self.id}/download"
    
    def __repr__(self):
        return f"<Media(id={self.id}, filename='{self.filename}', mime_type='{self.mime_type}')>"


class MediaProcessTask(Base):
    """
    媒体处理任务模型
    用于异步处理媒体文件
    """
    __tablename__ = "media_process_tasks"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    media_id = Column(GUID(), ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    parameters = Column(JSONB, default=dict)
    result = Column(JSONB)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    media = relationship("Media", back_populates="process_tasks")
    
    __table_args__ = (
        CheckConstraint("task_type IN ('thumbnail', 'transcode', 'optimize', 'watermark', 'extract_metadata')", 
                       name="task_type_enum"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="task_status_enum"),
    )
    
    @hybrid_property
    def is_completed(self) -> bool:
        """检查任务是否完成"""
        return self.status == "completed"
    
    @hybrid_property
    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == "failed"
    
    @hybrid_property
    def duration_ms(self) -> Optional[int]:
        """获取任务持续时间（毫秒）"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None
    
    def start(self):
        """开始处理任务"""
        self.status = "processing"
        self.started_at = datetime.now()
    
    def complete(self, result: Dict[str, Any] = None):
        """完成任务"""
        self.status = "completed"
        self.completed_at = datetime.now()
        if result:
            self.result = result
    
    def fail(self, error_message: str):
        """任务失败"""
        self.status = "failed"
        self.completed_at = datetime.now()
        self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "media_id": str(self.media_id),
            "task_type": self.task_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f"<MediaProcessTask(id={self.id}, media_id={self.media_id}, task_type='{self.task_type}', status='{self.status}')>"


class AuditLog(Base):
    """
    审计日志模型
    记录系统操作和用户行为
    """
    __tablename__ = "audit_logs"
    
    id = Column(GUID(), primary_key=True, default=uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), index=True)
    resource_id = Column(GUID(), index=True)
    
    # 请求信息
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_path = Column(Text)
    request_method = Column(String(10))
    request_headers = Column(JSONB)
    request_body = Column(JSONB)
    response_status = Column(Integer)
    response_body = Column(JSONB)
    error_message = Column(Text)
    error_stack = Column(Text)
    
    # 性能指标
    duration_ms = Column(Integer)
    memory_usage_mb = Column(Integer)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User")
    
    __table_args__ = (
        CheckConstraint("request_method IN ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS')", 
                       name="request_method_enum"),
    )
    
    @classmethod
    def create_from_request(
        cls,
        user_id: Optional[UUID] = None,
        action: str = "",
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        request_headers: Optional[Dict] = None,
        request_body: Optional[Dict] = None,
        response_status: Optional[int] = None,
        response_body: Optional[Dict] = None,
        error_message: Optional[str] = None,
        error_stack: Optional[str] = None,
        duration_ms: Optional[int] = None,
        memory_usage_mb: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> "AuditLog":
        """从请求信息创建审计日志"""
        return cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_path=request_path,
            request_method=request_method,
            request_headers=request_headers,
            request_body=request_body,
            response_status=response_status,
            response_body=response_body,
            error_message=error_message,
            error_stack=error_stack,
            duration_ms=duration_ms,
            memory_usage_mb=memory_usage_mb,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "id": str(self.id),
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "request_method": self.request_method,
            "response_status": self.response_status,
            "duration_ms": self.duration_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if self.user_id:
            data["user_id"] = str(self.user_id)
        
        if include_sensitive:
            data.update({
                "ip_address": self.ip_address,
                "user_agent": self.user_agent,
                "request_path": self.request_path,
                "request_headers": self.request_headers,
                "request_body": self.request_body,
                "response_body": self.response_body,
                "error_message": self.error_message,
                "error_stack": self.error_stack,
            })
        
        if self.user:
            data["user"] = {
                "id": str(self.user.id),
                "username": self.user.username,
                "email": self.user.email,
            }
        
        return data
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"