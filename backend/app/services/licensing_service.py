"""
EthioOffice Commercial Licensing Service
Handles cryptographic key verification, offline activation, quota synchronization,
and real-time lifecycle status evaluation.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.organization import Organization, License, LicenseTier
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.core.licensing import (
    generate_license_token,
    verify_license_token,
    evaluate_license_lifecycle,
    LicenseStatus,
)
from app.services.capability_service import CapabilityService, DEFAULT_TIER_CAPABILITIES, Capability
from app.schemas.licensing import (
    CurrentLicenseResponse,
    LicenseGenerateRequest,
    LicenseGeneratedResponse,
)


class LicensingError(Exception):
    """Base exception for licensing errors."""
    pass


class LicenseNotFoundError(LicensingError):
    pass


class LicenseInvalidError(LicensingError):
    pass


class LicenseTenantMismatchError(LicensingError):
    pass


class LicenseExpiredError(LicensingError):
    pass


class LicensingService:
    @classmethod
    def get_current_license(cls, db: Session, org_id: uuid.UUID) -> CurrentLicenseResponse:
        """
        Retrieves real-time license information, seat utilization, storage usage,
        and expiry status for a given tenant.
        """
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise LicenseNotFoundError("ድርጅቱ አልተገኘም (Organization not found)")

        license_rec = db.query(License).filter(License.organization_id == org_id).first()

        active_users = db.query(User).filter(
            User.organization_id == org_id,
            User.is_active == True
        ).count()

        storage_limit_gb = round(org.storage_limit_bytes / (1024 ** 3), 2)
        used_storage_gb = round(org.used_storage_bytes / (1024 ** 3), 2)
        usage_pct = round((org.used_storage_bytes / org.storage_limit_bytes * 100), 1) if org.storage_limit_bytes > 0 else 0.0

        if not license_rec:
            # Baseline trial status when no license record has been entered
            now = datetime.now(timezone.utc)
            expiry = org.created_at + timedelta(days=30)
            lifecycle = evaluate_license_lifecycle(expiry, grace_period_days=14, is_active=True)
            capabilities = sorted(list(CapabilityService.get_organization_capabilities(db, org_id)))
            
            return CurrentLicenseResponse(
                organization_id=org.id,
                organization_name=org.name,
                organization_slug=org.slug,
                tier="TRIAL",
                license_key_masked="UNLICENSED-TRIAL",
                status=lifecycle["status"],
                is_usable=lifecycle["is_usable"],
                max_users=org.max_users,
                active_users=active_users,
                available_seats=max(0, org.max_users - active_users),
                storage_limit_gb=storage_limit_gb,
                used_storage_gb=used_storage_gb,
                storage_usage_percent=usage_pct,
                issued_at=org.created_at,
                expires_at=expiry,
                days_remaining=lifecycle["days_remaining"],
                grace_period_days=14,
                grace_days_remaining=lifecycle["grace_days_remaining"],
                warning=lifecycle["warning"],
                capabilities=capabilities,
            )

        # Mask license key: show prefix and trailing 6 characters
        masked_key = (
            license_rec.license_key[:12] + "..." + license_rec.license_key[-6:]
            if len(license_rec.license_key) > 20
            else "MASKED-KEY"
        )

        lifecycle = evaluate_license_lifecycle(
            expires_at=license_rec.expires_at,
            grace_period_days=license_rec.grace_period_days or 14,
            is_active=license_rec.is_active,
        )

        capabilities = sorted(list(CapabilityService.get_organization_capabilities(db, org_id)))

        return CurrentLicenseResponse(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            tier=license_rec.tier.value if hasattr(license_rec.tier, "value") else str(license_rec.tier),
            license_key_masked=masked_key,
            status=lifecycle["status"],
            is_usable=lifecycle["is_usable"],
            max_users=license_rec.max_users,
            active_users=active_users,
            available_seats=max(0, license_rec.max_users - active_users),
            storage_limit_gb=storage_limit_gb,
            used_storage_gb=used_storage_gb,
            storage_usage_percent=usage_pct,
            issued_at=license_rec.issued_at,
            expires_at=license_rec.expires_at,
            days_remaining=lifecycle["days_remaining"],
            grace_period_days=license_rec.grace_period_days or 14,
            grace_days_remaining=lifecycle["grace_days_remaining"],
            warning=lifecycle["warning"],
            capabilities=capabilities,
        )

    @classmethod
    def activate_license(
        cls,
        db: Session,
        org_id: uuid.UUID,
        license_key: str,
        actor: User,
    ) -> CurrentLicenseResponse:
        """
        Validates cryptographic offline signature, binds key to organization,
        and dynamically updates organization limits and granted capabilities.
        """
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise LicenseNotFoundError("ድርጅቱ አልተገኘም (Organization not found)")

        # Verify offline token
        is_valid, payload, error_msg = verify_license_token(
            token=license_key,
            expected_org_slug=org.slug,
            allow_grace_period=True,
        )

        if not is_valid:
            if "expired" in (error_msg or "").lower():
                raise LicenseExpiredError(error_msg)
            elif "cannot be used for" in (error_msg or "").lower():
                raise LicenseTenantMismatchError(error_msg)
            else:
                raise LicenseInvalidError(error_msg or "የፈቃድ ቁልፉ ትክክለኛ አይደለም (Invalid license key)")

        # Extract parameters from cryptographically validated payload
        tier_str = payload["tier"].upper()
        tier_enum = LicenseTier[tier_str] if tier_str in LicenseTier.__members__ else LicenseTier.BUSINESS
        max_users = int(payload["max_users"])
        storage_limit_gb = int(payload["storage_limit_gb"])
        storage_bytes = storage_limit_gb * (1024 ** 3)
        features_list = payload.get("features", [])
        features_str = ",".join(sorted(features_list))
        expires_at = datetime.fromisoformat(payload["expires_at"])
        issued_at = datetime.fromisoformat(payload["issued_at"])
        grace_days = int(payload.get("grace_period_days", 14))

        # Check existing license record
        license_rec = db.query(License).filter(License.organization_id == org_id).first()
        if not license_rec:
            license_rec = License(
                organization_id=org.id,
                license_key=license_key.strip(),
                tier=tier_enum,
                max_users=max_users,
                storage_limit_bytes=storage_bytes,
                features=features_str,
                grace_period_days=grace_days,
                issued_at=issued_at,
                expires_at=expires_at,
                is_active=True,
            )
            db.add(license_rec)
        else:
            license_rec.license_key = license_key.strip()
            license_rec.tier = tier_enum
            license_rec.max_users = max_users
            license_rec.storage_limit_bytes = storage_bytes
            license_rec.features = features_str
            license_rec.grace_period_days = grace_days
            license_rec.issued_at = issued_at
            license_rec.expires_at = expires_at
            license_rec.is_active = True

        # Synchronize organization table limits immediately
        org.max_users = max_users
        org.storage_limit_bytes = storage_bytes

        # Audit log activation
        audit = AuditLog(
            organization_id=org.id,
            user_id=actor.id,
            action=AuditAction.UPLOAD,
            target_type="LICENSE",
            target_id=license_rec.id,
            target_name=f"{tier_str} License",
            details={
                "tier": tier_str,
                "max_users": max_users,
                "storage_limit_gb": storage_limit_gb,
                "expires_at": expires_at.isoformat(),
                "action": "LICENSE_ACTIVATED",
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(license_rec)
        db.refresh(org)

        return cls.get_current_license(db, org.id)

    @classmethod
    def generate_license_for_tenant(
        cls,
        payload: LicenseGenerateRequest,
    ) -> LicenseGeneratedResponse:
        """
        Generates a signed offline key. Used by deployment operators or superadmin console.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=payload.valid_days)
        
        tier_enum = payload.tier
        if payload.custom_features:
            features = payload.custom_features
        else:
            features = [c.value for c in DEFAULT_TIER_CAPABILITIES.get(tier_enum, DEFAULT_TIER_CAPABILITIES[LicenseTier.BUSINESS])]

        key = generate_license_token(
            organization_slug=payload.organization_slug,
            tier=tier_enum.value,
            max_users=payload.max_users,
            storage_limit_gb=payload.storage_limit_gb,
            features=features,
            expires_at=expires_at,
            issued_at=now,
            grace_period_days=payload.grace_period_days,
        )

        return LicenseGeneratedResponse(
            license_key=key,
            organization_slug=payload.organization_slug,
            tier=tier_enum.value,
            max_users=payload.max_users,
            storage_limit_gb=payload.storage_limit_gb,
            features=features,
            issued_at=now,
            expires_at=expires_at,
            grace_period_days=payload.grace_period_days,
        )
