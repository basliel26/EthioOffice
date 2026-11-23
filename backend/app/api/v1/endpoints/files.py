"""
FastAPI Endpoints for Module 4: File Storage & Hierarchy Engine
Integrates StorageService, Breadcrumbs, Streamed Chunk Uploads, Cycle-Safe Moves,
and Cascading Soft-Delete / Purge lifecycles.
"""

import os
import uuid
import urllib.parse
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
    NewDocumentCreate,
    FileMoveRequest,
    FileRenameRequest,
    BreadcrumbItem,
    BatchMoveRequest,
    BatchMoveResponse,
    BatchDeleteRequest,
    BatchDeleteResponse,
    StorageAnalyticsResponse,
    FileVersionSummary,
    FileLockInfo,
    LockRequest,
    UnlockRequest,
    RevertVersionRequest,
    RecentFileItemResponse,
    EmptyTrashResponse,
)
from app.schemas.tag import TagResponse, FileTagAssignRequest, FileTagResponse
from app.services.tag_service import (
    TagService,
    TagDomainError,
    TagNotFoundError,
    TagConflictError,
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
    SecurityViolationError,
    FileLockedError,
)
from app.services.version_service import (
    VersionService,
    VersionDomainError,
    VersionNotFoundError,
    LockNotFoundError,
    LockPermissionDeniedError,
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


@router.get("/shared-with-me", response_model=List[FileItemResponse])
def list_files_shared_with_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all documents and folders shared with the user directly or via department branches.
    """
    from app.services.share_service import ShareService
    return ShareService.list_shared_with_me(db, current_user.organization_id, current_user)


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
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except SecurityViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SECURITY_VIOLATION", "message": str(e)})
    except FileItemConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/new-document", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
def create_new_document(
    payload: NewDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new native office document (.docx, .xlsx, .pptx, or .txt) ready for Euro-Office editing.
    """
    import io
    name = payload.name.strip() if payload.name and payload.name.strip() else "New Document"
    ext = payload.doc_type.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"
    if not name.lower().endswith(ext):
        filename = f"{name}{ext}"
    else:
        filename = name

    # Auto-resolve duplicates like Windows (e.g. "New Document (1).docx")
    existing_names = set(
        row[0] for row in db.query(FileItem.name).filter(
            FileItem.organization_id == current_user.organization_id,
            FileItem.parent_id == payload.parent_id,
            FileItem.is_deleted == False,
        ).all()
    )
    if filename in existing_names:
        base_stem = filename[:-len(ext)]
        counter = 1
        while f"{base_stem} ({counter}){ext}" in existing_names:
            counter += 1
        filename = f"{base_stem} ({counter}){ext}"

    content_bytes = b""
    content_type = "text/plain"

    try:
        if ext == ".docx":
            import docx
            doc = docx.Document()
            buf = io.BytesIO()
            doc.save(buf)
            content_bytes = buf.getvalue()
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == ".xlsx":
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            buf = io.BytesIO()
            wb.save(buf)
            content_bytes = buf.getvalue()
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation()
            blank_slide_layout = prs.slide_layouts[6]  # Blank slide template
            prs.slides.add_slide(blank_slide_layout)
            buf = io.BytesIO()
            prs.save(buf)
            content_bytes = buf.getvalue()
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            content_bytes = b""
            content_type = "text/plain"

        return StorageService.upload_file_stream(
            db=db,
            org_id=current_user.organization_id,
            user=current_user,
            stream=io.BytesIO(content_bytes),
            filename=filename,
            content_type=content_type,
            parent_id=payload.parent_id,
            drive_type=payload.drive_type,
            department_id=payload.department_id,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except FileItemConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
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
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except SecurityViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SECURITY_VIOLATION", "message": str(e)})
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analytics/summary", response_model=StorageAnalyticsResponse)
def get_storage_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns organization storage quota analytics, drive partitioning breakdown, and top files.
    """
    return StorageService.get_storage_analytics(db, current_user.organization_id)


@router.patch("/batch/move", response_model=BatchMoveResponse)
def batch_move_items(
    payload: BatchMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move multiple files or folders to a target parent directory in an atomic batch.
    """
    try:
        return StorageService.batch_move(
            db=db,
            org_id=current_user.organization_id,
            item_ids=payload.item_ids,
            new_parent_id=payload.new_parent_id,
            actor=current_user,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})


@router.delete("/batch/delete", response_model=BatchDeleteResponse)
def batch_delete_items(
    payload: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk soft-delete or permanently purge selected files and folders.
    """
    try:
        return StorageService.batch_delete(
            db=db,
            org_id=current_user.organization_id,
            item_ids=payload.item_ids,
            permanent=payload.permanent,
            actor=current_user,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})


@router.get("/starred", response_model=List[FileItemResponse])
def list_starred_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all documents and folders marked as favorite / starred by the user.
    """
    return StorageService.list_starred_items(db, current_user.organization_id, current_user)


@router.get("/recent", response_model=List[RecentFileItemResponse])
def get_recent_files(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enterprise Recent Documents Feed showing the latest documents opened, edited, or interacted with.
    """
    return StorageService.get_recent_items(db, current_user.organization_id, current_user, limit=limit)


@router.post("/trash/empty", response_model=EmptyTrashResponse)
def empty_trash(
    drive_type: Optional[str] = Query(None, description="Optional filter: PERSONAL or COMPANY"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently empties the recycle bin, freeing storage quota atomically.
    Admins can purge tenant-wide trash; regular staff purge their personal trash.
    """
    try:
        return StorageService.empty_trash(
            db=db,
            org_id=current_user.organization_id,
            actor=current_user,
            drive_type=drive_type,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})


@router.get("/{file_id}", response_model=FileItemResponse)
def get_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get file or folder metadata by ID.
    """
    try:
        item = StorageService.get_item(db, current_user.organization_id, file_id, current_user)
        return StorageService.to_file_response(db, item, current_user)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


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

        # RFC 5987 Amharic/UTF-8 filename encoding and ETag integrity header
        ascii_fallback = "".join(c for c in file_item.name if c.isascii() and (c.isalnum() or c in "._- ")).strip()
        if not ascii_fallback or ascii_fallback.startswith("."):
            ext = os.path.splitext(file_item.name)[1]
            ascii_fallback = f"document{ext}" if ext.isascii() else "document.bin"

        encoded_name = urllib.parse.quote(file_item.name, encoding="utf-8")
        content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_name}'

        response_headers = {
            "ETag": f'"{version.checksum_sha256}"',
            "Content-Disposition": content_disposition,
            "Accept-Ranges": "bytes",
        }

        return FileResponse(
            path=full_path,
            media_type=file_item.mime_type or "application/octet-stream",
            headers=response_headers,
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
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
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
        new_name = payload.name or payload.new_name
        return StorageService.rename_item(
            db=db,
            org_id=current_user.organization_id,
            item_id=item_id,
            new_name=new_name,
            actor=current_user
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except SecurityViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SECURITY_VIOLATION", "message": str(e)})
    except FileItemConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{item_id}")
def delete_item(
    item_id: uuid.UUID,
    permanent: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move item to Recycle Bin with Cascading Soft-Delete, or permanently purge if permanent=True.
    """
    try:
        if permanent:
            freed_bytes = StorageService.purge_item(db, current_user.organization_id, item_id, actor=current_user)
            return {"message": f"Item permanently deleted. Freed {freed_bytes} bytes", "freed_bytes": freed_bytes}
        affected = StorageService.soft_delete_item(db, current_user.organization_id, item_id, actor=current_user)
        return {"message": f"Successfully moved {affected} item(s) to Recycle Bin", "affected_count": affected}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
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
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# =====================================================================
# Module 5: Versioning & Concurrency Control (File Locking) Endpoints
# =====================================================================

@router.post("/{file_id}/versions", response_model=FileItemResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_version(
    file_id: uuid.UUID,
    file: UploadFile = File(...),
    change_summary: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a new version (vN+1) of an existing document.
    Enforces check-out lock ownership, 64KB chunk streaming, CAS deduplication, and quota budgeting.
    """
    try:
        return VersionService.upload_new_version(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            stream=file.file,
            filename=file.filename or "updated_file.bin",
            actor=current_user,
            change_summary=change_summary,
            content_type=file.content_type,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except SecurityViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "SECURITY_VIOLATION", "message": str(e)})
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except (FileItemNotFoundError, VersionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (StorageDomainError, VersionDomainError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{file_id}/versions", response_model=List[FileVersionSummary])
def list_versions(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all historical versions of a document, ordered newest first.
    """
    try:
        return VersionService.list_versions(db, current_user.organization_id, file_id, current_user)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except VersionDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{file_id}/versions/{version_number}/download")
def download_historical_version(
    file_id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a specific historical version payload with ETag and RFC 5987 Amharic encoding.
    """
    try:
        file_item, version, full_path = VersionService.get_version_file_info(
            db, current_user.organization_id, file_id, version_number, current_user
        )

        base_name, ext = os.path.splitext(file_item.name)
        v_filename = f"{base_name}_v{version.version_number}{ext}"

        ascii_fallback = "".join(c for c in v_filename if c.isascii() and (c.isalnum() or c in "._- ")).strip()
        if not ascii_fallback or ascii_fallback.startswith("."):
            ascii_fallback = f"document_v{version.version_number}{ext}" if ext.isascii() else f"document_v{version.version_number}.bin"

        encoded_name = urllib.parse.quote(v_filename, encoding="utf-8")
        content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded_name}'

        headers = {
            "ETag": f'"{version.checksum_sha256}"',
            "Content-Disposition": content_disposition,
            "Accept-Ranges": "bytes",
        }

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
            media_type=file_item.mime_type or "application/octet-stream",
            headers=headers,
        )
    except (FileItemNotFoundError, VersionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except VersionDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{file_id}/versions/{version_number}/revert", response_model=FileItemResponse)
def revert_to_version(
    file_id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rollback document to historical version N. Creates version (latest+1) reusing the historical payload (zero storage copy).
    """
    try:
        return VersionService.revert_to_version(
            db, current_user.organization_id, file_id, version_number, current_user
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except (FileItemNotFoundError, VersionNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except VersionDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{file_id}/lock", response_model=FileLockInfo)
def acquire_file_lock(
    file_id: uuid.UUID,
    payload: LockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Acquire exclusive check-out lock on a document.
    """
    try:
        return VersionService.acquire_lock(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
            reason=payload.reason,
            duration_minutes=payload.duration_minutes,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileLockedError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail={"code": "FILE_LOCKED", "message": str(e), "locked_by": getattr(e, 'locked_by_name', None)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (StorageDomainError, VersionDomainError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{file_id}/unlock")
def release_file_lock(
    file_id: uuid.UUID,
    payload: Optional[UnlockRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Release check-out lock. Supports Admin force-unlock.
    """
    try:
        force = payload.force if payload else False
        VersionService.release_lock(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
            force=force,
        )
        return {"message": "Lock released successfully"}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except LockPermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{file_id}/lock", response_model=Optional[FileLockInfo])
def get_file_lock(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Inspect active lock status and holder details on a file.
    """
    try:
        return VersionService.get_lock_info(db, current_user.organization_id, file_id, current_user)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{file_id}/star")
def star_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Star / favorite a file or folder for quick access.
    """
    try:
        StorageService.star_item(db, current_user.organization_id, file_id, current_user)
        return {"message": "Item starred successfully"}
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{file_id}/star")
def unstar_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unstar / remove a file or folder from favorites.
    """
    try:
        StorageService.unstar_item(db, current_user.organization_id, file_id, current_user)
        return {"message": "Item unstarred successfully"}
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{file_id}/tags", response_model=FileTagResponse)
def assign_tags_to_file(
    file_id: uuid.UUID,
    payload: FileTagAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign color-coded classification tags to a document (requires Editor permission).
    """
    try:
        return TagService.assign_tags_to_file(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            tag_ids=payload.tag_ids,
            actor=current_user,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except TagNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (TagDomainError, StorageDomainError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{file_id}/tags/{tag_id}")
def remove_tag_from_file(
    file_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a classification tag from a document.
    """
    try:
        TagService.remove_tag_from_file(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            tag_id=tag_id,
            actor=current_user,
        )
        return {"message": "Tag removed from file successfully"}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (TagDomainError, StorageDomainError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{file_id}/tags", response_model=List[TagResponse])
def get_file_tags(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all classification tags assigned to a file.
    """
    try:
        return TagService.get_file_tags(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
        )
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
