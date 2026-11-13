"""
EthioOffice Capability Matrix & Feature Gating Service
Enforces subscription tier capabilities and seat limits across multi-tenant organizations.
"""

import uuid
import enum
from typing import Set, Tuple, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.organization import Organization, License, LicenseTier
from app.models.user import User


class Capability(str, enum.Enum):
    CORE_STORAGE = "CORE_STORAGE"
    CUSTOM_BRANDING = "CUSTOM_BRANDING"
    DEPARTMENT_HIERARCHY = "DEPARTMENT_HIERARCHY"
    OFFICE_COAUTHORING = "OFFICE_COAUTHORING"
    LETTER_REGISTRY = "LETTER_REGISTRY"
    AUDIT_EXPORT = "AUDIT_EXPORT"
    LDAP_AD_SYNC = "LDAP_AD_SYNC"


DEFAULT_TIER_CAPABILITIES = {
    LicenseTier.STARTER: [
        Capability.CORE_STORAGE,
        Capability.CUSTOM_BRANDING,
    ],
    LicenseTier.BUSINESS: [
        Capability.CORE_STORAGE,
        Capability.CUSTOM_BRANDING,
        Capability.DEPARTMENT_HIERARCHY,
        Capability.OFFICE_COAUTHORING,
        Capability.LETTER_REGISTRY,
    ],
    LicenseTier.ENTERPRISE: [
        Capability.CORE_STORAGE,
        Capability.CUSTOM_BRANDING,
        Capability.DEPARTMENT_HIERARCHY,
        Capability.OFFICE_COAUTHORING,
        Capability.LETTER_REGISTRY,
        Capability.AUDIT_EXPORT,
        Capability.LDAP_AD_SYNC,
    ],
}


class SeatLimitExceededError(Exception):
    """Raised when an organization attempts to provision users beyond licensed seats."""
    pass


class FeatureNotLicensedError(Exception):
    """Raised when an organization attempts to access an unlicensed feature."""
    pass


class CapabilityService:
    @classmethod
    def get_organization_capabilities(cls, db: Session, org_id: uuid.UUID) -> Set[str]:
        """
        Retrieves the effective set of capability strings enabled for an organization.
        If custom features are saved on the license, they are returned.
        Otherwise falls back to the default matrix for the license tier.
        """
        lic = db.query(License).filter(License.organization_id == org_id, License.is_active == True).first()
        if not lic:
            # Default to STARTER if no license is configured
            return {c.value for c in DEFAULT_TIER_CAPABILITIES[LicenseTier.STARTER]}

        if lic.features and lic.features.strip():
            # Parse comma-separated list
            custom_features = {f.strip().upper() for f in lic.features.split(",") if f.strip()}
            if custom_features:
                return custom_features

        # Fallback to tier defaults
        tier_enum = lic.tier if isinstance(lic.tier, LicenseTier) else LicenseTier(str(lic.tier))
        tier_caps = DEFAULT_TIER_CAPABILITIES.get(tier_enum, DEFAULT_TIER_CAPABILITIES[LicenseTier.STARTER])
        return {c.value for c in tier_caps}

    @classmethod
    def has_capability(cls, db: Session, org_id: uuid.UUID, capability: Capability) -> bool:
        """
        Checks whether the organization possesses a specific capability.
        """
        enabled = cls.get_organization_capabilities(db, org_id)
        return capability.value in enabled

    @classmethod
    def check_seat_limit(cls, db: Session, org_id: uuid.UUID) -> Tuple[bool, int, int]:
        """
        Checks if the organization has available seats for new users.
        Returns: (can_add: bool, active_seats_count: int, max_seats: int)
        """
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            return False, 0, 0

        active_count = db.query(User).filter(
            User.organization_id == org_id,
            User.is_active == True
        ).count()

        max_seats = org.max_users
        can_add = active_count < max_seats
        return can_add, active_count, max_seats

    @classmethod
    def enforce_seat_limit(cls, db: Session, org_id: uuid.UUID) -> None:
        """
        Raises SeatLimitExceededError if no more user seats are available under the license.
        """
        can_add, active_count, max_seats = cls.check_seat_limit(db, org_id)
        if not can_add:
            raise SeatLimitExceededError(
                f"የተፈቀደው የተጠቃሚዎች ቁጥር (Seat Limit) ተሞልቷል። እባክዎ ፈቃድዎን ያሻሽሉ "
                f"(Organization has reached its license seat limit: {active_count}/{max_seats} users occupied. Please upgrade your license.)"
            )


def require_capability(required_capability: Capability):
    """
    FastAPI dependency factory to gate endpoint access based on tenant capability.
    Usage:
        @router.get('/endpoint', dependencies=[Depends(require_capability(Capability.LETTER_REGISTRY))])
    """
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not current_user.organization_id:
            return

        if not current_user.is_superuser:
            has_cap = CapabilityService.has_capability(db, current_user.organization_id, required_capability)
            if not has_cap:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FEATURE_NOT_LICENSED",
                        "capability": required_capability.value,
                        "message": f"Feature '{required_capability.value}' is not enabled for your organization's subscription tier. Please upgrade your EthioOffice license.",
                        "message_am": f"ይህ ገፅታ ({required_capability.value}) በድርጅትዎ የፈቃድ ደረጃ ውስጥ አልተካተተም። እባክዎ ፈቃድዎን ያሻሽሉ።"
                    }
                )

    return dependency
