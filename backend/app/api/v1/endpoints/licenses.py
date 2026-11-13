"""
FastAPI Endpoints for Module 3: Licensing & Capability Engine
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.schemas.licensing import (
    CurrentLicenseResponse,
    LicenseActivationRequest,
    LicenseGenerateRequest,
    LicenseGeneratedResponse,
    LicenseHistoryResponse,
)
from app.services.licensing_service import (
    LicensingService,
    LicenseNotFoundError,
    LicenseInvalidError,
    LicenseTenantMismatchError,
    LicenseExpiredError,
)
from app.services.capability_service import require_capability, Capability

router = APIRouter()


@router.get("/current", response_model=CurrentLicenseResponse)
def get_current_license_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current organization license status, seat usage, storage limits, and active capabilities.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ተጠቃሚው ከአንድ ድርጅት ጋር አልተያያዘም (User is not associated with an organization)"
        )

    try:
        return LicensingService.get_current_license(db, current_user.organization_id)
    except LicenseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/activate", response_model=CurrentLicenseResponse)
def activate_license_key(
    payload: LicenseActivationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activate or renew an EthioOffice offline cryptographic license token.
    Restricted to Organization Administrators or Superusers.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ተጠቃሚው ከአንድ ድርጅት ጋር አልተያያዘም (User is not associated with an organization)"
        )

    if current_user.role != UserRole.ADMIN and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ፈቃድ የማስገባት ፈቃድ ያለው የአስተዳዳሪ ብቻ ነው (Only administrators can activate licenses)"
        )

    try:
        return LicensingService.activate_license(
            db=db,
            org_id=current_user.organization_id,
            license_key=payload.license_key,
            actor=current_user,
        )
    except LicenseExpiredError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LicenseTenantMismatchError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LicenseInvalidError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except LicenseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/history", response_model=List[LicenseHistoryResponse])
def get_license_activation_history(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """
    Get immutable audit log of all past license activations and tier upgrades for the organization.
    Requires ADMIN privileges.
    """
    return LicensingService.get_license_history(db, current_admin.organization_id)


@router.post("/generate", response_model=LicenseGeneratedResponse)
def generate_offline_license(
    payload: LicenseGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Issue a new cryptographically signed offline EthioOffice license key.
    Restricted to Superusers / Vendor deployment staff.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="የፈቃድ ቁልፍ የማመንጨት ፈቃድ የለዎትም (Superuser access required to generate license tokens)"
        )

    return LicensingService.generate_license_for_tenant(payload)


@router.get("/compliance-export", dependencies=[Depends(require_capability(Capability.AUDIT_EXPORT))])
def export_compliance_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export compliance audit logs for regulatory inspections (NBE, INSA).
    Restricted to license tiers holding the AUDIT_EXPORT capability (e.g. Enterprise).
    """
    from app.models.audit import AuditLog
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == current_user.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
        .all()
    )

    return {
        "organization_id": current_user.organization_id,
        "export_format": "JSON_COMPLIANCE_FEED",
        "record_count": len(logs),
        "records": [
            {
                "id": str(log.id),
                "action": log.action.value if hasattr(log.action, "value") else str(log.action),
                "target_type": log.target_type,
                "target_name": log.target_name,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }
