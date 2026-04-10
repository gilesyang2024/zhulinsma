"""
媒体相关的Pydantic模型
用于API请求和响应验证
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator, HttpUrl


class MediaBase(BaseModel):
    """媒体基础模型"""
    filename: str = Field(..., description="文件名", max_length=255)
    original_filename: str = Field(..., description="原始文件名", max_length=255)
    file_size: int = Field(..., description="文件大小（字节）", ge=0)
    file_type: str = Field(..., description="文件类型", max_length=100)
    mime_type: str = Field(..., description="MIME类型", max_length=100)


class MediaCreate(MediaBase):
    """媒体创建模型"""
    storage_type: str = Field(default="local", description="存储类型", max_length=20)
    storage_bucket: Optional[str] = Field(None, description="存储桶", max_length=100)
    is_public: bool = Field(default=True, description="是否公开")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class MediaUpdate(BaseModel):
    """媒体更新模型"""
    filename: Optional[str] = Field(None, description="文件名", max_length=255)
    is_public: Optional[bool] = Field(None, description="是否公开")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class MediaProcessTaskCreate(BaseModel):
    """媒体处理任务创建模型"""
    task_type: str = Field(..., description="任务类型", max_length=50)
    priority: int = Field(default=1, description="优先级", ge=1, le=10)
    parameters: Dict[str, Any] = Field(default_factory=dict, description="处理参数")


class MediaProcessTaskUpdate(BaseModel):
    """媒体处理任务更新模型"""
    status: Optional[str] = Field(None, description="状态", max_length=20)
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    error_message: Optional[str] = Field(None, description="错误信息")


class MediaResponse(MediaBase):
    """媒体响应模型"""
    id: UUID
    file_path: str = Field(..., description="文件路径", max_length=500)
    storage_type: str = Field(..., description="存储类型", max_length=20)
    storage_bucket: Optional[str] = Field(None, description="存储桶", max_length=100)
    width: Optional[int] = Field(None, description="宽度（像素）")
    height: Optional[int] = Field(None, description="高度（像素）")
    duration: Optional[int] = Field(None, description="时长（秒）")
    bitrate: Optional[int] = Field(None, description="比特率")
    encoding: Optional[str] = Field(None, description="编码格式", max_length=50)
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL", max_length=500)
    preview_url: Optional[str] = Field(None, description="预览图URL", max_length=500)
    is_public: bool = Field(..., description="是否公开")
    is_processed: bool = Field(..., description="是否已处理")
    process_status: Optional[str] = Field(None, description="处理状态", max_length=20)
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    uploaded_by: UUID = Field(..., description="上传用户ID")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaDetailResponse(MediaResponse):
    """媒体详情响应模型"""
    uploaded_by_username: str = Field(..., description="上传用户名")
    uploaded_by_email: str = Field(..., description="上传用户邮箱")
    
    class Config:
        from_attributes = True


class MediaProcessTaskResponse(BaseModel):
    """媒体处理任务响应模型"""
    id: UUID
    media_id: UUID
    task_type: str = Field(..., description="任务类型", max_length=50)
    status: str = Field(..., description="状态", max_length=20)
    priority: int = Field(..., description="优先级", ge=1, le=10)
    parameters: Dict[str, Any] = Field(..., description="处理参数")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(..., description="重试次数")
    max_retries: int = Field(..., description="最大重试次数")
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaListResponse(BaseModel):
    """媒体列表响应模型"""
    items: List[MediaResponse] = Field(..., description="媒体列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class MediaProcessTaskListResponse(BaseModel):
    """媒体处理任务列表响应模型"""
    items: List[MediaProcessTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class MediaUploadRequest(BaseModel):
    """媒体上传请求模型"""
    is_public: bool = Field(default=True, description="是否公开")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class MediaUploadResponse(BaseModel):
    """媒体上传响应模型"""
    id: UUID
    filename: str = Field(..., description="文件名")
    original_filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小")
    file_type: str = Field(..., description="文件类型")
    mime_type: str = Field(..., description="MIME类型")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    preview_url: Optional[str] = Field(None, description="预览图URL")
    upload_url: str = Field(..., description="上传URL")
    expires_at: datetime = Field(..., description="上传链接过期时间")


class MediaQueryParams(BaseModel):
    """媒体查询参数模型"""
    file_type: Optional[str] = Field(None, description="文件类型")
    is_public: Optional[bool] = Field(None, description="是否公开")
    is_processed: Optional[bool] = Field(None, description="是否已处理")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    uploaded_by: Optional[UUID] = Field(None, description="上传用户ID")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    search: Optional[str] = Field(None, description="搜索关键词")
    page: int = Field(default=1, description="页码", ge=1)
    page_size: int = Field(default=20, description="每页大小", ge=1, le=100)
    order_by: str = Field(default="created_at", description="排序字段")
    order: str = Field(default="desc", description="排序方向")


class MediaProcessTaskQueryParams(BaseModel):
    """媒体处理任务查询参数模型"""
    media_id: Optional[UUID] = Field(None, description="媒体ID")
    task_type: Optional[str] = Field(None, description="任务类型")
    status: Optional[str] = Field(None, description="状态")
    priority: Optional[int] = Field(None, description="优先级")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    page: int = Field(default=1, description="页码", ge=1)
    page_size: int = Field(default=20, description="每页大小", ge=1, le=100)
    order_by: str = Field(default="created_at", description="排序字段")
    order: str = Field(default="desc", description="排序方向")


# 文件上传相关模型
class FileUploadPart(BaseModel):
    """分片上传部分信息"""
    part_number: int = Field(..., description="分片编号", ge=1)
    size: int = Field(..., description="分片大小")
    etag: Optional[str] = Field(None, description="ETag")


class MultipartUploadInit(BaseModel):
    """分片上传初始化请求"""
    filename: str = Field(..., description="文件名", max_length=255)
    file_size: int = Field(..., description="文件大小", ge=0)
    mime_type: str = Field(..., description="MIME类型", max_length=100)
    is_public: bool = Field(default=True, description="是否公开")


class MultipartUploadInitResponse(BaseModel):
    """分片上传初始化响应"""
    upload_id: UUID = Field(..., description="上传ID")
    upload_urls: List[str] = Field(..., description="分片上传URL列表")
    expires_at: datetime = Field(..., description="上传链接过期时间")


class MultipartUploadComplete(BaseModel):
    """分片上传完成请求"""
    parts: List[FileUploadPart] = Field(..., description="已上传的分片列表")