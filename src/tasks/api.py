"""
任务API接口
"""
import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status

from .models import TaskCreateRequest, TaskResponse, TaskStats
from .service import TaskService, get_task_service

router = APIRouter(prefix="/tasks", tags=["任务"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def create_task(
    request: TaskCreateRequest,
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, str]:
    """创建新任务"""
    try:
        task_id = await task_service.enqueue_task(
            name=request.name,
            args=request.args,
            kwargs=request.kwargs,
            priority=request.priority
        )
        return {"task_id": task_id, "message": "任务已加入队列"}
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    task_service: TaskService = Depends(get_task_service)
) -> List[TaskResponse]:
    """获取任务列表"""
    try:
        tasks = await task_service.get_tasks(
            status=status,
            limit=limit,
            offset=offset
        )
        return tasks
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务列表失败: {str(e)}"
        )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
) -> TaskResponse:
    """获取任务详情"""
    try:
        task = await task_service.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务详情失败: {str(e)}"
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: str,
    task_service: TaskService = Depends(get_task_service)
):
    """取消任务"""
    try:
        success = await task_service.cancel_task(task_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无法取消"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消任务失败: {str(e)}"
        )


@router.get("/stats/queue", response_model=Dict[str, Any])
async def get_queue_stats(
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """获取队列统计信息"""
    try:
        stats = await task_service.get_queue_stats()
        return stats
    except Exception as e:
        logger.error(f"获取队列统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取队列统计失败: {str(e)}"
        )


@router.get("/stats/worker", response_model=Dict[str, Any])
async def get_worker_stats(
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """获取工作器统计信息"""
    try:
        stats = await task_service.get_worker_stats()
        return stats
    except Exception as e:
        logger.error(f"获取工作器统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工作器统计失败: {str(e)}"
        )


@router.post("/cleanup", response_model=Dict[str, str])
async def cleanup_tasks(
    days_old: int = 30,
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, str]:
    """清理旧任务"""
    try:
        count = await task_service.cleanup_old_tasks(days_old)
        return {"message": f"已清理 {count} 个旧任务"}
    except Exception as e:
        logger.error(f"清理任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理任务失败: {str(e)}"
        )


@router.post("/retry-failed", response_model=Dict[str, str])
async def retry_failed_tasks(
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, str]:
    """重试失败的任务"""
    try:
        count = await task_service.retry_failed_tasks()
        return {"message": f"已重新排队 {count} 个失败任务"}
    except Exception as e:
        logger.error(f"重试失败任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重试失败任务失败: {str(e)}"
        )


@router.post("/worker/start", response_model=Dict[str, str])
async def start_worker(
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, str]:
    """启动任务工作器"""
    try:
        await task_service.start_worker()
        return {"message": "任务工作器已启动"}
    except Exception as e:
        logger.error(f"启动工作器失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动工作器失败: {str(e)}"
        )


@router.post("/worker/stop", response_model=Dict[str, str])
async def stop_worker(
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, str]:
    """停止任务工作器"""
    try:
        await task_service.stop_worker()
        return {"message": "任务工作器已停止"}
    except Exception as e:
        logger.error(f"停止工作器失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止工作器失败: {str(e)}"
        )