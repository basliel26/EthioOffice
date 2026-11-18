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


class NewDocumentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    doc_type: str = Field(..., pattern="^(docx|xlsx|pptx|txt)$")
    parent_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    drive_type: str = "PERSONAL"


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
    change_summary: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    ec_created_at: Optional[str] = None

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
    is_starred: Optional[bool] = False
    tags: Optional[List[str]] = []
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
    duration_minutes: int = Field(120, ge=1, le=1440)  # Max 24 hours


class UnlockRequest(BaseModel):
    force: bool = False


class RevertVersionRequest(BaseModel):
    target_version_number: int = Field(..., ge=1)


class BatchMoveRequest(BaseModel):
    item_ids: List[uuid.UUID] = Field(..., min_length=1)
    new_parent_id: Optional[uuid.UUID] = None


class BatchMoveResponse(BaseModel):
    moved_count: int
    failed_count: int
    details: List[dict]


class BatchDeleteRequest(BaseModel):
    item_ids: List[uuid.UUID] = Field(..., min_length=1)
    permanent: bool = False


class BatchDeleteResponse(BaseModel):
    affected_count: int
    freed_bytes: int


class LargestFileSummary(BaseModel):
    id: uuid.UUID
    name: str
    size_bytes: int
    drive_type: str
    owner_name: Optional[str] = None
    created_at: datetime
    ec_created_at: Optional[str] = None


class StorageAnalyticsResponse(BaseModel):
    total_used_bytes: int
    storage_limit_bytes: int
    percentage_used: float
    personal_drive_bytes: int
    company_drive_bytes: int
    trash_bytes: int
    total_files: int
    total_folders: int
    top_largest_files: List[LargestFileSummary]


class RecentFileItemResponse(BaseModel):
    file: FileItemResponse
    last_action: str
    last_action_amharic: str
    last_action_at: datetime
    last_action_at_ec: Optional[str] = None


class EmptyTrashResponse(BaseModel):
    purged_count: int
    freed_bytes: int
    freed_mb: float


