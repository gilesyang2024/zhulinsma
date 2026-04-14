"""
竹林司马存储系统
提供多云存储支持，包括本地存储、对象存储（S3兼容）、云存储等
"""

from .base import StorageBackend, StorageConfig
from .local import LocalStorage
from .s3 import S3Storage
from .azure import AzureBlobStorage
from .google import GoogleCloudStorage
from .manager import StorageManager, FileMetadata, StorageProvider

__all__ = [
    "StorageBackend",
    "StorageConfig",
    "LocalStorage",
    "S3Storage",
    "AzureBlobStorage",
    "GoogleCloudStorage",
    "StorageManager",
    "FileMetadata",
    "StorageProvider"
]