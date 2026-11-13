"""
EthioOffice Sharing & Access Control Endpoints (Module 6)
Provides internal user/department document sharing and public link management for employees.
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.file import FileItemResponse
from app.schemas.share import (
    ShareCreateRequest,
    ShareResponse,
    ShareLinkCreateRequest,
    ShareLinkResponse,
)
from app.services.share_service import (
    ShareService,
    ShareDomainError,
    ShareNotFoundError,
    ShareLinkNotFoundError,
    TargetUserNotFoundError,
    TargetDepartmentNotFoundError,
    CannotShareWithSelfError,
)
from app.services.storage_service import (
    FileItemNotFoundError,
    DriveAccessDeniedError,
)
from app.services.capability_service import LicenseReadOnlyLockdownError

router = APIRouter()


# =====================================================================
# Internal User & Department Sharing
# =====================================================================

@router.get("/with-me", response_model=List[FileItemResponse])
def list_shared_with_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all documents and folders shared with the current user directly or via department branches.
    """
    return ShareService.list_shared_with_me(db, current_user.organization_id, current_user)


@router.post("/file/{file_id}", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
def create_file_share(
    file_id: uuid.UUID,
    payload: ShareCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Share a document or folder with a colleague or department.
    """
    try:
        return ShareService.create_share(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
            target_user_id=payload.target_user_id,
            target_department_id=payload.target_department_id,
            permission=payload.permission,
            expires_at=payload.expires_at,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except CannotShareWithSelfError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (TargetUserNotFoundError, TargetDepartmentNotFoundError, FileItemNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ShareDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/file/{file_id}", response_model=List[ShareResponse])
def list_file_shares(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all active shares configured on a specific document or folder.
    """
    try:
        return ShareService.list_file_shares(db, current_user.organization_id, file_id, current_user)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{share_id}")
def revoke_share(
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke internal sharing permissions on a document.
    """
    try:
        ShareService.revoke_share(db, current_user.organization_id, share_id, current_user)
        return {"message": "Share revoked successfully"}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except ShareNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# =====================================================================
# External Public Links Management (for Employees)
# =====================================================================

@router.post("/links/file/{file_id}", response_model=ShareLinkResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    file_id: uuid.UUID,
    payload: ShareLinkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an external tokenized public link for a file or folder.
    """
    try:
        return ShareService.create_share_link(
            db=db,
            org_id=current_user.organization_id,
            file_id=file_id,
            actor=current_user,
            access_type=payload.access_type,
            password=payload.password,
            expires_at=payload.expires_at,
            max_downloads=payload.max_downloads,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ShareDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/links/file/{file_id}", response_model=List[ShareLinkResponse])
def list_share_links(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all active public links configured for a document.
    """
    try:
        return ShareService.list_file_links(db, current_user.organization_id, file_id, current_user)
    except FileItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/links/{link_id}")
def revoke_share_link(
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deactivate or revoke an external public link.
    """
    try:
        ShareService.revoke_share_link(db, current_user.organization_id, link_id, current_user)
        return {"message": "Share link revoked successfully"}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except ShareLinkNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
