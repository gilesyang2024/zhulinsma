"""
文件存储系统API模块
提供文件上传、下载、管理和存储提供商配置的REST API接口
"""
import json
import mimetypes
from typing import Dict, List, Any, Optional, BinaryIO, Annotated
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    status, 
    UploadFile, 
    File, 
    Form, 
    Query,
    BackgroundTasks,
    Body
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field, HttpUrl, validator

from src.core.database import get_db
from src.core.security import get_current_user, require_admin
from src.core.config import Settings
from .manager import StorageManager, StorageProvider, FileMetadata

# 初始化设置和路由器
settings = Settings()
router = APIRouter(prefix="/storage", tags=["文件存储"])

# 请求和响应模型
class StorageProviderCreate(BaseModel):
    """创建存储提供商的请求模型"""
    name: str = Field(..., min_length=1, max_length=255, description="提供商名称")
    type: str = Field(..., description="存储类型: local, s3, azure, google")
    config: Dict[str, Any] = Field(..., description="存储配置")
    is_default: bool = Field(False, description="是否设为默认存储提供商")
    
    @validator('type')
    def validate_type(cls, v):
        allowed_types = ['local', 's3', 'azure', 'google']
        if v not in allowed_types:
            raise ValueError(f"存储类型必须是: {', '.join(allowed_types)}")
        return v

class StorageProviderResponse(BaseModel):
    """存储提供商响应模型"""
    id: str
    name: str
    type: str
    config: Dict[str, Any]
    is_default: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class FileUploadRequest(BaseModel):
    """文件上传请求模型"""
    provider_name: Optional[str] = Field(None, description="指定存储提供商名称，不指定则使用默认")
    tags: List[str] = Field(default_factory=list, description="文件标签")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    expiration_days: Optional[int] = Field(None, ge=1, description="文件过期天数")
    make_public: bool = Field(False, description="是否设为公开访问")
    encrypt: bool = Field(False, description="是否加密存储")

class FileMetadataResponse(BaseModel):
    """文件元数据响应模型"""
    id: str
    filename: str
    original_filename: str
    content_type: str
    size: int
    provider_name: str
    storage_path: str
    url: Optional[str] = None
    is_public: bool
    tags: List[str]
    metadata: Dict[str, Any]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class FileListResponse(BaseModel):
    """文件列表响应模型"""
    total: int
    files: List[FileMetadataResponse]
    page: int
    page_size: int
    total_pages: int

class StorageStatsResponse(BaseModel):
    """存储统计响应模型"""
    total_files: int
    total_size: int
    by_provider: Dict[str, Dict[str, Any]]
    by_type: Dict[str, int]

class PresignedUrlRequest(BaseModel):
    """预签名URL请求模型"""
    expires_in: int = Field(3600, ge=60, le=604800, description="过期时间(秒)")

class PresignedUrlResponse(BaseModel):
    """预签名URL响应模型"""
    upload_url: str
    download_url: Optional[str] = None
    expires_at: datetime

# 依赖注入函数
async def get_storage_manager(db: AsyncSession = Depends(get_db)) -> StorageManager:
    """获取存储管理器实例"""
    return StorageManager(db)

async def get_provider_or_404(
    provider_name: str,
    db: AsyncSession = Depends(get_db)
) -> StorageProvider:
    """根据名称获取存储提供商或返回404"""
    result = await db.execute(
        select(StorageProvider).where(StorageProvider.name == provider_name)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"存储提供商 '{provider_name}' 不存在"
        )
    return provider

# API端点
@router.get("/providers", response_model=List[StorageProviderResponse], summary="获取存储提供商列表")
async def list_providers(
    db: AsyncSession = Depends(get_db)
) -> List[StorageProviderResponse]:
    """获取所有存储提供商配置"""
    result = await db.execute(select(StorageProvider).order_by(StorageProvider.created_at))
    providers = result.scalars().all()
    return providers

@router.get("/providers/{provider_name}", response_model=StorageProviderResponse, summary="获取存储提供商详情")
async def get_provider(
    provider: StorageProvider = Depends(get_provider_or_404)
) -> StorageProviderResponse:
    """获取指定存储提供商的详情"""
    return provider

@router.post("/providers", response_model=StorageProviderResponse, status_code=status.HTTP_201_CREATED, summary="创建存储提供商")
async def create_provider(
    provider_data: StorageProviderCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin)
) -> StorageProviderResponse:
    """创建新的存储提供商配置"""
    
    # 检查名称是否已存在
    result = await db.execute(
        select(StorageProvider).where(StorageProvider.name == provider_data.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"存储提供商 '{provider_data.name}' 已存在"
        )
    
    # 如果是默认提供商，取消现有的默认设置
    if provider_data.is_default:
        await db.execute(
            select(StorageProvider)
            .where(StorageProvider.is_default == True)
            .update({"is_default": False})
        )
    
    # 创建新的存储提供商
    provider = StorageProvider(
        name=provider_data.name,
        type=provider_data.type,
        config=provider_data.config,
        is_default=provider_data.is_default
    )
    
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    
    return provider

@router.put("/providers/{provider_name}", response_model=StorageProviderResponse, summary="更新存储提供商")
async def update_provider(
    provider_name: str,
    provider_data: StorageProviderCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin)
) -> StorageProviderResponse:
    """更新存储提供商配置"""
    
    # 获取现有提供商
    result = await db.execute(
        select(StorageProvider).where(StorageProvider.name == provider_name)
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"存储提供商 '{provider_name}' 不存在"
        )
    
    # 检查新名称是否与其他提供商冲突
    if provider_data.name != provider_name:
        result = await db.execute(
            select(StorageProvider).where(StorageProvider.name == provider_data.name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"存储提供商 '{provider_data.name}' 已存在"
            )
    
    # 如果是默认提供商，取消现有的默认设置
    if provider_data.is_default and not provider.is_default:
        await db.execute(
            select(StorageProvider)
            .where(StorageProvider.is_default == True)
            .update({"is_default": False})
        )
    
    # 更新提供商信息
    provider.name = provider_data.name
    provider.type = provider_data.type
    provider.config = provider_data.config
    provider.is_default = provider_data.is_default
    
    await db.commit()
    await db.refresh(provider)
    
    return provider

@router.delete("/providers/{provider_name}", status_code=status.HTTP_204_NO_CONTENT, summary="删除存储提供商")
async def delete_provider(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin)
):
    """删除存储提供商配置"""
    
    # 检查是否还有文件使用该提供商
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.provider_name == provider_name)
    )
    files = result.scalars().all()
    if files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法删除存储提供商 '{provider_name}'，仍有 {len(files)} 个文件使用该提供商"
        )
    
    # 删除提供商
    await db.execute(
        delete(StorageProvider).where(StorageProvider.name == provider_name)
    )
    await db.commit()

@router.post("/upload", response_model=FileMetadataResponse, status_code=status.HTTP_201_CREATED, summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    provider_name: Optional[str] = Form(None),
    tags: str = Form("", description="以逗号分隔的标签"),
    metadata_json: str = Form("{}", description="JSON格式的元数据"),
    expiration_days: Optional[int] = Form(None),
    make_public: bool = Form(False),
    encrypt: bool = Form(False),
    storage_manager: StorageManager = Depends(get_storage_manager),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> FileMetadataResponse:
    """上传文件到指定的存储提供商"""
    
    try:
        # 解析标签和元数据
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        try:
            custom_metadata = json.loads(metadata_json) if metadata_json else {}
        except json.JSONDecodeError:
            custom_metadata = {}
        
        # 获取文件内容
        content = await file.read()
        
        # 上传文件
        upload_result = await storage_manager.upload_file(
            filename=file.filename,
            content=content,
            content_type=file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
            provider_name=provider_name,
            tags=tag_list,
            metadata=custom_metadata,
            expires_in_days=expiration_days,
            make_public=make_public,
            encrypt=encrypt,
            user_id=current_user.get("user_id")
        )
        
        return upload_result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )

@router.post("/upload-multiple", response_model=List[FileMetadataResponse], summary="批量上传文件")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    provider_name: Optional[str] = Form(None),
    tags: str = Form("", description="以逗号分隔的标签"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    storage_manager: StorageManager = Depends(get_storage_manager),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[FileMetadataResponse]:
    """批量上传多个文件"""
    
    async def upload_single(file: UploadFile) -> FileMetadataResponse:
        """单个文件上传函数"""
        try:
            content = await file.read()
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
            
            upload_result = await storage_manager.upload_file(
                filename=file.filename,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                provider_name=provider_name,
                tags=tag_list,
                user_id=current_user.get("user_id")
            )
            return upload_result
        except Exception as e:
            # 在后台任务中记录错误
            print(f"文件上传失败: {file.filename} - {str(e)}")
            raise
    
    # 异步处理所有上传
    results = []
    for file in files:
        try:
            result = await upload_single(file)
            results.append(result)
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
                "success": False
            })
    
    return results

@router.get("/files", response_model=FileListResponse, summary="获取文件列表")
async def list_files(
    provider_name: Optional[str] = Query(None, description="按存储提供商过滤"),
    tag: Optional[str] = Query(None, description="按标签过滤"),
    content_type: Optional[str] = Query(None, description="按内容类型过滤"),
    is_public: Optional[bool] = Query(None, description="按公开状态过滤"),
    user_id: Optional[str] = Query(None, description="按用户ID过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> FileListResponse:
    """获取文件列表，支持分页和过滤"""
    
    from sqlalchemy import func
    
    # 构建查询条件
    query = select(FileMetadata)
    
    if provider_name:
        query = query.where(FileMetadata.provider_name == provider_name)
    
    if tag:
        query = query.where(FileMetadata.tags.contains([tag]))
    
    if content_type:
        query = query.where(FileMetadata.content_type.like(f"%{content_type}%"))
    
    if is_public is not None:
        query = query.where(FileMetadata.is_public == is_public)
    
    if user_id:
        query = query.where(FileMetadata.user_id == user_id)
    else:
        # 非管理员只能查看自己的文件
        if not current_user.get("is_admin", False):
            query = query.where(FileMetadata.user_id == current_user.get("user_id"))
    
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 计算分页
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # 应用分页
    query = query.order_by(FileMetadata.created_at.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    files = result.scalars().all()
    
    return FileListResponse(
        total=total,
        files=files,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/files/{file_id}", response_model=FileMetadataResponse, summary="获取文件详情")
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> FileMetadataResponse:
    """获取指定文件的元数据"""
    
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file_metadata = result.scalar_one_or_none()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限：非公开文件只能由所有者或管理员访问
    if not file_metadata.is_public:
        if not current_user.get("is_admin", False) and file_metadata.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此文件"
            )
    
    return file_metadata

@router.get("/files/{file_id}/download", summary="下载文件")
async def download_file(
    file_id: str,
    inline: bool = Query(True, description="是否内联显示（true）还是作为附件下载（false）"),
    storage_manager: StorageManager = Depends(get_storage_manager),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """下载指定文件"""
    
    # 获取文件元数据
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file_metadata = result.scalar_one_or_none()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限
    if not file_metadata.is_public:
        if not current_user.get("is_admin", False) and file_metadata.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限下载此文件"
            )
    
    try:
        # 从存储后端获取文件
        file_data = await storage_manager.download_file(file_id)
        
        if file_data.get("stream"):
            # 流式响应
            response = StreamingResponse(
                file_data["stream"],
                media_type=file_metadata.content_type,
                headers={
                    "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename=\"{file_metadata.original_filename}\"",
                    "Content-Length": str(file_metadata.size)
                }
            )
        elif file_data.get("local_path"):
            # 本地文件响应
            response = FileResponse(
                path=file_data["local_path"],
                filename=file_metadata.original_filename,
                media_type=file_metadata.content_type
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取文件内容"
            )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件下载失败: {str(e)}"
        )

@router.get("/files/{file_id}/url", summary="获取文件访问URL")
async def get_file_url(
    file_id: str,
    expires_in: int = Query(3600, ge=60, le=604800, description="URL过期时间(秒)"),
    storage_manager: StorageManager = Depends(get_storage_manager),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取文件的访问URL（包括预签名URL）"""
    
    # 获取文件元数据
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file_metadata = result.scalar_one_or_none()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限
    if not file_metadata.is_public:
        if not current_user.get("is_admin", False) and file_metadata.user_id != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此文件"
            )
    
    try:
        # 获取文件URL
        url_data = await storage_manager.get_file_url(
            file_id,
            expires_in=expires_in
        )
        
        return url_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件URL失败: {str(e)}"
        )

@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除文件")
async def delete_file(
    file_id: str,
    storage_manager: StorageManager = Depends(get_storage_manager),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """删除指定文件"""
    
    # 获取文件元数据
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file_metadata = result.scalar_one_or_none()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限：只有所有者或管理员可以删除
    if not current_user.get("is_admin", False) and file_metadata.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此文件"
        )
    
    try:
        # 从存储后端删除文件
        success = await storage_manager.delete_file(file_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件删除失败"
            )
        
        # 从数据库删除元数据
        await db.execute(
            delete(FileMetadata).where(FileMetadata.id == file_id)
        )
        await db.commit()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件删除失败: {str(e)}"
        )

@router.get("/stats", response_model=StorageStatsResponse, summary="获取存储统计信息")
async def get_storage_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin)
) -> StorageStatsResponse:
    """获取存储系统的统计信息"""
    
    from sqlalchemy import func
    
    # 获取总文件数和总大小
    result = await db.execute(
        select(func.count(FileMetadata.id), func.coalesce(func.sum(FileMetadata.size), 0))
        .select_from(FileMetadata)
    )
    total_files, total_size = result.first()
    
    # 按提供商统计
    result = await db.execute(
        select(
            FileMetadata.provider_name,
            func.count(FileMetadata.id).label("file_count"),
            func.coalesce(func.sum(FileMetadata.size), 0).label("total_size")
        )
        .group_by(FileMetadata.provider_name)
    )
    by_provider = {}
    for row in result:
        provider_name = row.provider_name
        by_provider[provider_name] = {
            "file_count": row.file_count,
            "total_size": row.total_size
        }
    
    # 按内容类型统计
    result = await db.execute(
        select(
            func.split_part(FileMetadata.content_type, '/', 1).label("type_prefix"),
            func.count(FileMetadata.id).label("file_count")
        )
        .group_by("type_prefix")
    )
    by_type = {}
    for row in result:
        by_type[row.type_prefix] = row.file_count
    
    return StorageStatsResponse(
        total_files=total_files or 0,
        total_size=total_size or 0,
        by_provider=by_provider,
        by_type=by_type
    )

@router.post("/files/{file_id}/toggle-public", response_model=FileMetadataResponse, summary="切换文件公开状态")
async def toggle_file_public(
    file_id: str,
    storage_manager: StorageManager = Depends(get_storage_manager),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> FileMetadataResponse:
    """切换文件的公开/私有状态"""
    
    # 获取文件元数据
    result = await db.execute(
        select(FileMetadata).where(FileMetadata.id == file_id)
    )
    file_metadata = result.scalar_one_or_none()
    
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # 检查权限：只有所有者或管理员可以修改
    if not current_user.get("is_admin", False) and file_metadata.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此文件"
        )
    
    try:
        # 切换公开状态
        new_is_public = not file_metadata.is_public
        
        # 如果设为公开，生成公共访问URL
        if new_is_public:
            await storage_manager.make_file_public(file_id)
        
        # 更新数据库
        file_metadata.is_public = new_is_public
        await db.commit()
        await db.refresh(file_metadata)
        
        return file_metadata
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"切换文件公开状态失败: {str(e)}"
        )

@router.post("/providers/{provider_name}/sync", summary="同步存储提供商的文件列表")
async def sync_provider(
    provider_name: str,
    background_tasks: BackgroundTasks,
    storage_manager: StorageManager = Depends(get_storage_manager),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_admin)
) -> Dict[str, Any]:
    """同步存储提供商的文件列表到数据库"""
    
    # 检查提供商是否存在
    result = await db.execute(
        select(StorageProvider).where(StorageProvider.name == provider_name)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"存储提供商 '{provider_name}' 不存在"
        )
    
    # 在后台任务中执行同步
    async def sync_task():
        try:
            await storage_manager.sync_provider_files(provider_name)
        except Exception as e:
            print(f"同步提供商 {provider_name} 失败: {str(e)}")
    
    background_tasks.add_task(sync_task)
    
    return {
        "message": f"已开始同步存储提供商 '{provider_name}' 的文件列表",
        "status": "syncing"
    }