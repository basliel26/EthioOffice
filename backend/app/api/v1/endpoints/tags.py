"""
FastAPI Endpoints for Document Tags & Taxonomy Classification Engine
Enables color-coded tagging of enterprise documents, duplicate prevention, and file associations.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, FileTagAssignRequest, FileTagResponse
from app.services.tag_service import (
    TagService,
    TagDomainError,
    TagNotFoundError,
    TagConflictError,
)
from app.services.storage_service import FileItemNotFoundError, DriveAccessDeniedError
from app.services.capability_service import LicenseReadOnlyLockdownError

router = APIRouter()


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new color-coded classification tag for the organization.
    """
    try:
        return TagService.create_tag(
            db=db,
            org_id=current_user.organization_id,
            name=payload.name,
            color=payload.color,
            actor=current_user,
        )
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except TagConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (TagDomainError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=List[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lists all tags defined in the organization along with assigned document counts.
    """
    return TagService.list_tags(db=db, org_id=current_user.organization_id)


@router.delete("/{tag_id}", status_code=status.HTTP_200_OK)
def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a tag from the organization and clears file associations, triggering search index updates.
    """
    try:
        TagService.delete_tag(
            db=db,
            org_id=current_user.organization_id,
            tag_id=tag_id,
            actor=current_user,
        )
        return {"message": "Tag deleted successfully"}
    except LicenseReadOnlyLockdownError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "LICENSE_LOCKDOWN_READ_ONLY", "message": str(e)})
    except TagNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DriveAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TagDomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
