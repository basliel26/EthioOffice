"""
FastAPI Endpoints for Module 4: File Storage & Hierarchy Engine
Integrates StorageService, Breadcrumbs, Streamed Chunk Uploads, Cycle-Safe Moves,
and Cascading Soft-Delete / Purge lifecycles.
"""

import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.file import FileItem, FileVersion
from app.models.audit import AuditLog, AuditAction
from app.schemas.file import (
    FileItemResponse,
    FolderCreate,
    FileMoveRequest,
    FileRenameRequest,
    BreadcrumbItem,
)
from app.services.storage_service import (
    StorageService,
    storage_provider,
    StorageDomainError,
    FileItemNotFoundError,
    FolderCycleError,
    FileItemConflictError,
    DriveAccessDeniedError,
    FilePayloadMissingError,
)
from app.services.tenant_service import StorageQuotaExceededError
from app.services.capability_service import LicenseReadOnlyLockdownError

router = APIRouter()


@router.get("", response_model=List[FileItemResponse])
def list_files(
    drive_type: str = Query("PERSONAL", pattern="^(PERSONAL|COMPANY|TRASH)$"),
    parent_id: Optional[uuid.UUID] = Query(None),
    department_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List files and folders within the specified drive partition (PERSONAL, COMPANY, TRASH).
    """
    return StorageService.list_items(
        db=db,
        org_id=current_user.organization_id,
        user=current_user,
        drive_type=drive_type,
        parent_id=parent_id,
        department_id=department_id,
        search=search,
    )


@router.post("/folder", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new directory in Personal or Company Drive.
    Enforces write lockdown and unique naming within the folder.
    """
    try:
        return StorageService.create_folder(
            db=db,
            org_id=current_user.organization_id,
            user=current_user,
            name=payload.name,
            parent_id=payload.parent_id,
            drive_type=payload.drive_type,
            department_id=payload.department_id,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/upload", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    parent_id: Optional[uuid.UUID] = Form(None),
    department_id: Optional[uuid.UUID] = Form(None),
    drive_type: str = Form("PERSONAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document using memory-capped 64KB chunk streaming.
    Calculates SHA-256 on the fly, enforces CAS deduplication, and manages quotas.
    """
    try:
        return StorageService.upload_file_stream(
            db=db,
            org_id=current_user.organization_id,
            user=current_user,
            stream=file.file,
            filename=file.filename or "uploaded_file.bin",
            content_type=file.content_type,
            parent_id=parent_id,
            drive_type=drive_type,
            department_id=department_id,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{file_id}/download")
def download_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream download the current version of the specified file.
    """
    try:
        file_item = StorageService.get_item(db, current_user.organization_id, file_id, current_user)
        if file_item.is_folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folders cannot be downloaded directly")

        version = db.query(FileVersion).filter(FileVersion.id == file_item.current_version_id).first()
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File version not found")

        full_path = storage_provider.get_full_path(version.storage_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical file payload missing on disk")

        # Audit log download
        audit = AuditLog(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            action=AuditAction.DOWNLOAD,
            target_type="FILE",
            target_id=file_item.id,
            target_name=file_item.name,
            details={"version": version.version_number, "size_bytes": version.size_bytes}
        )
        db.add(audit)
        db.commit()

        return FileResponse(
            path=full_path,
            filename=file_item.name,
            media_type=file_item.mime_type or "application/octet-stream"
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{item_id}/breadcrumbs", response_model=List[BreadcrumbItem])
def get_breadcrumbs(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full hierarchical path from root to target folder or file.
    """
    try:
        # Check access
        StorageService.get_item(db, current_user.organization_id, item_id, current_user)
        return StorageService.get_breadcrumbs(db, current_user.organization_id, item_id)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{item_id}/move", response_model=FileItemResponse)
def move_item(
    item_id: uuid.UUID,
    payload: FileMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move a folder or file to another parent directory.
    Enforces cycle detection to prevent moving a folder into its own descendants.
    """
    try:
        return StorageService.move_item(
            db=db,
            org_id=current_user.organization_id,
            item_id=item_id,
            new_parent_id=payload.new_parent_id,
            actor=current_user
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FolderCycleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "CYCLE_DETECTED", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{item_id}/rename", response_model=FileItemResponse)
def rename_item(
    item_id: uuid.UUID,
    payload: FileRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rename a folder or file within its current parent.
    """
    try:
        return StorageService.rename_item(
            db=db,
            org_id=current_user.organization_id,
            item_id=item_id,
            new_name=payload.name,
            actor=current_user
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{item_id}")
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move item to Recycle Bin with Cascading Soft-Delete:
    If a folder is deleted, all its descendant files and subfolders are also marked deleted.
    """
    try:
        affected = StorageService.soft_delete_item(db, current_user.organization_id, item_id, actor=current_user)
        return {"message": f"Successfully moved {affected} item(s) to Recycle Bin", "affected_count": affected}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{item_id}/restore")
def restore_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restore an item from Recycle Bin with Cascading Restore:
    Restores the folder and all descendant files and subfolders.
    """
    try:
        restored = StorageService.restore_item(db, current_user.organization_id, item_id, actor=current_user)
        return {"message": f"Successfully restored {restored} item(s)", "restored_count": restored}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{item_id}/purge")
def purge_item_permanently(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently purge an item from disk and database.
    Reclaims storage quota from organization and department.
    """
    try:
        freed_bytes = StorageService.purge_item(db, current_user.organization_id, item_id, actor=current_user)
        return {"message": f"Item permanently deleted. Freed {freed_bytes} bytes", "freed_bytes": freed_bytes}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
