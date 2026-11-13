from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User
from app.services.tenant_service import (
    TenantService, 
    TenantNotFoundError, 
    StorageQuotaExceededError
)
from app.schemas.tenant import (
    OrganizationResponse, 
    OrganizationUpdate, 
    StorageQuotaResponse
)

router = APIRouter()


@router.get("/profile", response_model=OrganizationResponse)
def get_organization_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get organization profile details for the authenticated employee's company.
    """
    try:
        org = TenantService.get_organization(db, current_user.organization_id)
        return org
    except TenantNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/profile", response_model=OrganizationResponse)
def update_organization_profile(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Update organization profile (name, TIN number, logo, branding color).
    Requires ADMIN privileges.
    """
    try:
        org = TenantService.update_organization(
            db=db,
            org_id=current_admin.organization_id,
            payload=payload,
            actor=current_admin
        )
        return org
    except TenantNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/storage-quota", response_model=StorageQuotaResponse)
def get_storage_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check current organization storage usage and quota limits.
    """
    try:
        return TenantService.get_storage_quota(db, current_user.organization_id)
    except TenantNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
