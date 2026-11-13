import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.ethiopian_calendar import format_ethiopian_date
from app.models.user import User
from app.models.file import FileItem, FileVersion, DriveType
from app.models.share import FileShare, SharePermission
from app.models.lock import FileLock
from app.models.audit import AuditLog, AuditAction
from app.schemas.file import (
    FileItemResponse,
    FolderCreate,
    ShareCreateRequest,
    LockRequest,
    FileLockInfo,
)

router = APIRouter()


def build_file_response(item: FileItem) -> FileItemResponse:
    # Check lock status
    is_locked = False
    lock_info = None
    if item.lock and item.lock.expires_at > datetime.now(timezone.utc):
        is_locked = True
        lock_info = FileLockInfo(
            locked_by_name=item.lock.locked_by.full_name if item.lock.locked_by else "Colleague",
            locked_by_id=item.lock.locked_by_id,
            reason=item.lock.reason,
            expires_at=item.lock.expires_at,
        )

    # Ethiopian date
    ec_date = format_ethiopian_date(item.created_at.date()) if item.created_at else None

    return FileItemResponse(
        id=item.id,
        name=item.name,
        is_folder=item.is_folder,
        parent_id=item.parent_id,
        drive_type=item.drive_type.value if hasattr(item.drive_type, "value") else str(item.drive_type),
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
        owner_id=item.owner_id,
        owner_name=item.owner.full_name if item.owner else None,
        department_id=item.department_id,
        is_deleted=item.is_deleted,
        is_locked=is_locked,
        lock_info=lock_info,
        created_at=item.created_at,
        updated_at=item.updated_at,
        ec_created_at=ec_date,
    )


@router.get("", response_model=List[FileItemResponse])
def list_files(
    drive_type: str = Query("PERSONAL", pattern="^(PERSONAL|COMPANY|TRASH)$"),
    parent_id: Optional[uuid.UUID] = Query(None),
    department_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List files and folders within the specified drive scope and parent folder.
    """
    query = db.query(FileItem).filter(FileItem.organization_id == current_user.organization_id)

    if drive_type == "TRASH":
        query = query.filter(FileItem.is_deleted == True)
        if current_user.role.value == "STAFF":
            query = query.filter(FileItem.deleted_by_id == current_user.id)
    else:
        query = query.filter(FileItem.is_deleted == False)
        
        if drive_type == "PERSONAL":
            query = query.filter(
                FileItem.drive_type == DriveType.PERSONAL,
                FileItem.owner_id == current_user.id
            )
        elif drive_type == "COMPANY":
            query = query.filter(FileItem.drive_type == DriveType.COMPANY)
            if department_id:
                query = query.filter(FileItem.department_id == department_id)
        
        # Navigate specific directory
        if parent_id:
            query = query.filter(FileItem.parent_id == parent_id)
        else:
            query = query.filter(FileItem.parent_id == None)

    items = query.order_by(FileItem.is_folder.desc(), FileItem.name.asc()).all()
    return [build_file_response(i) for i in items]


@router.post("/folder", response_model=FileItemResponse)
def create_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new directory in Personal or Company Drive.
    """
    drive_enum = DriveType.COMPANY if payload.drive_type.upper() == "COMPANY" else DriveType.PERSONAL
    
    folder = FileItem(
        organization_id=current_user.organization_id,
        name=payload.name.strip(),
        is_folder=True,
        parent_id=payload.parent_id,
        drive_type=drive_enum,
        owner_id=current_user.id,
        department_id=payload.department_id,
    )
    db.add(folder)
    db.flush()

    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=AuditAction.UPLOAD,
        target_type="FOLDER",
        target_id=folder.id,
        target_name=folder.name,
        details={"drive_type": payload.drive_type}
    )
    db.add(audit)
    db.commit()
    db.refresh(folder)

    return build_file_response(folder)


@router.post("/upload", response_model=FileItemResponse)
async def upload_file(
    file: UploadFile = File(...),
    parent_id: Optional[uuid.UUID] = Form(None),
    department_id: Optional[uuid.UUID] = Form(None),
    drive_type: str = Form("PERSONAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document/file, compute SHA-256 integrity hash, store on disk, and create FileVersion #1.
    """
    content = await file.read()
    size_bytes = len(content)

    # Check file size limit
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Calculate SHA-256 checksum
    sha256_hash = hashlib.sha256(content).hexdigest()

    # Prepare storage directory
    org_storage_dir = os.path.join(settings.STORAGE_ROOT, str(current_user.organization_id))
    os.makedirs(org_storage_dir, exist_ok=True)

    # Content-addressed filename
    ext = os.path.splitext(file.filename)[1]
    storage_filename = f"{uuid.uuid4()}{ext}"
    full_path = os.path.join(org_storage_dir, storage_filename)

    with open(full_path, "wb") as f:
        f.write(content)

    drive_enum = DriveType.COMPANY if drive_type.upper() == "COMPANY" else DriveType.PERSONAL

    # Create file record
    file_item = FileItem(
        organization_id=current_user.organization_id,
        name=file.filename,
        is_folder=False,
        parent_id=parent_id,
        drive_type=drive_enum,
        owner_id=current_user.id,
        department_id=department_id,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
    )
    db.add(file_item)
    db.flush()

    # Create version #1
    version_1 = FileVersion(
        file_id=file_item.id,
        version_number=1,
        storage_path=os.path.relpath(full_path, settings.STORAGE_ROOT),
        checksum_sha256=sha256_hash,
        size_bytes=size_bytes,
        created_by_id=current_user.id,
        change_summary="Initial upload",
    )
    db.add(version_1)
    db.flush()

    file_item.current_version_id = version_1.id

    # Audit log
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=AuditAction.UPLOAD,
        target_type="FILE",
        target_id=file_item.id,
        target_name=file_item.name,
        details={"size_bytes": size_bytes, "sha256": sha256_hash}
    )
    db.add(audit)
    db.commit()
    db.refresh(file_item)

    return build_file_response(file_item)


@router.get("/{file_id}/download")
def download_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the current version of the specified file.
    """
    file_item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == current_user.organization_id,
        FileItem.is_deleted == False
    ).first()

    if not file_item or file_item.is_folder:
        raise HTTPException(status_code=404, detail="File not found")

    version = db.query(FileVersion).filter(FileVersion.id == file_item.current_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="File version not found")

    full_path = os.path.join(settings.STORAGE_ROOT, version.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Physical file payload missing on server disk")

    # Audit download
    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=AuditAction.DOWNLOAD,
        target_type="FILE",
        target_id=file_item.id,
        target_name=file_item.name,
        details={"version": version.version_number}
    )
    db.add(audit)
    db.commit()

    return FileResponse(
        path=full_path,
        filename=file_item.name,
        media_type=file_item.mime_type or "application/octet-stream"
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete a file or folder into the Recycle Bin.
    """
    item = db.query(FileItem).filter(
        FileItem.id == file_id,
        FileItem.organization_id == current_user.organization_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.is_deleted = True
    item.deleted_at = datetime.now(timezone.utc)
    item.deleted_by_id = current_user.id

    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=AuditAction.DELETE,
        target_type="FOLDER" if item.is_folder else "FILE",
        target_id=item.id,
        target_name=item.name
    )
    db.add(audit)
    db.commit()

    return {"message": f"{'Folder' if item.is_folder else 'File'} moved to Recycle Bin"}
