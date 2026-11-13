import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class BreadcrumbItem(BaseModel):
    id: uuid.UUID
    name: str
    is_folder: bool

    model_config = ConfigDict(from_attributes=True)


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    drive_type: str = "PERSONAL"  # 'PERSONAL' or 'COMPANY'


class FileMoveRequest(BaseModel):
    new_parent_id: Optional[uuid.UUID] = None


class FileRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class FileLockInfo(BaseModel):
    locked_by_name: str
    locked_by_id: uuid.UUID
    reason: Optional[str]
    expires_at: datetime


class FileVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    size_bytes: int
    checksum_sha256: str
    created_at: datetime
    ec_created_at: str

    model_config = ConfigDict(from_attributes=True)


class FileItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_folder: bool
    parent_id: Optional[uuid.UUID]
    drive_type: str
    mime_type: Optional[str]
    size_bytes: int
    owner_id: uuid.UUID
    owner_name: Optional[str] = None
    department_id: Optional[uuid.UUID]
    is_deleted: bool
    is_locked: bool = False
    lock_info: Optional[FileLockInfo] = None
    subfolder_count: Optional[int] = 0
    file_count: Optional[int] = 0
    breadcrumbs: Optional[List[BreadcrumbItem]] = None
    created_at: datetime
    updated_at: datetime
    ec_created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ShareCreateRequest(BaseModel):
    target_user_id: Optional[uuid.UUID] = None
    target_department_id: Optional[uuid.UUID] = None
    permission: str = "VIEWER"  # 'VIEWER' or 'EDITOR'


class LockRequest(BaseModel):
    reason: Optional[str] = "Editing document"
    duration_minutes: int = 120  # Default 2 hours
