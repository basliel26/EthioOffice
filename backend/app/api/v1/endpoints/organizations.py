from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User
from app.services.tenant_service import (
    TenantService, 
    TenantNotFoundError, 
    DepartmentConflictError,
)
from app.schemas.tenant import (
    OrganizationResponse, 
    OrganizationUpdate, 
    StorageQuotaResponse,
    TenantBrandingPublicResponse,
    TenantProvisionRequest,
    TenantProvisionResponse,
)

router = APIRouter()


@router.get("/branding/{slug}", response_model=TenantBrandingPublicResponse)
def get_tenant_branding(
    slug: str,
    db: Session = Depends(get_db),
):
    """
    Public endpoint for branded pre-login portal resolution.
    Returns corporate name, logo, theme color, and active status.
    """
    try:
        return TenantService.get_branding_by_slug(db, slug)
    except TenantNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/provision", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_tenant(
    payload: TenantProvisionRequest,
    db: Session = Depends(get_db),
):
    """
    1-Click Automated Enterprise Tenant Provisioning:
    Creates Organization, binds commercial license, provisions admin user,
    default Ethiopian departments (FIN, HR, OPS), and root company drive spaces.
    """
    try:
        return TenantService.provision_tenant(db, payload)
    except DepartmentConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TenantNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/profile", response_model=OrganizationResponse)
def update_organization_profile(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Update organization profile (name, TIN number, logo, branding color, status).
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
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
