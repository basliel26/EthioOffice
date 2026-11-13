"""
EthioOffice Cryptographic Licensing & Capability Token Engine
Designed for on-premise, private cloud, and air-gapped Ethiopian enterprise deployments.
Uses HMAC-SHA256 signed tamper-proof offline license tokens.
"""

import json
import base64
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional, List
import enum

from app.core.config import settings


class LicenseStatus(str, enum.Enum):
    VALID = "VALID"
    EXPIRING_SOON = "EXPIRING_SOON"  # <= 30 days remaining
    IN_GRACE_PERIOD = "IN_GRACE_PERIOD"  # Past expiry, within grace window
    EXPIRED = "EXPIRED"  # Past grace window, write access locked
    REVOKED = "REVOKED"


class LicenseTier(str, enum.Enum):
    STARTER = "STARTER"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


def generate_license_token(
    organization_slug: str,
    tier: str,
    max_users: int,
    storage_limit_gb: int,
    features: List[str],
    expires_at: datetime,
    license_id: Optional[str] = None,
    issued_at: Optional[datetime] = None,
    grace_period_days: int = 14,
    signing_secret: Optional[str] = None,
) -> str:
    """
    Generate an offline cryptographically signed EthioOffice commercial license key.
    Format: EO-LIC.<base64_payload>.<signature_hex>
    """
    secret = signing_secret or settings.LICENSE_SIGNING_KEY or settings.SECRET_KEY
    now = issued_at or datetime.now(timezone.utc)
    
    # Ensure timezone awareness
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    lic_id = license_id or f"LIC-{now.strftime('%Y%m')}-{organization_slug.upper()[:6]}-{hashlib.md5(f'{organization_slug}:{now}'.encode()).hexdigest()[:6].upper()}"

    payload = {
        "license_id": lic_id,
        "organization_slug": organization_slug.lower().strip(),
        "tier": tier.upper().strip(),
        "max_users": int(max_users),
        "storage_limit_gb": int(storage_limit_gb),
        "features": sorted(list(set(features))),
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "grace_period_days": int(grace_period_days),
    }

    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")
    
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return f"EO-LIC.{payload_b64}.{signature}"


def verify_license_token(
    token: str,
    expected_org_slug: Optional[str] = None,
    signing_secret: Optional[str] = None,
    allow_grace_period: bool = True,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verifies an offline cryptographically signed EthioOffice license key.
    
    Returns:
        (is_valid: bool, payload: Optional[dict], error_message: Optional[str])
    """
    if not token or not isinstance(token, str):
        return False, None, "የፈቃድ ቁልፍ አልተሰጠም (License token is empty or invalid)"

    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != "EO-LIC":
        return False, None, "ትክክለኛ ያልሆነ የፈቃድ ቁልፍ ቅርጸት (Invalid EthioOffice license token format)"

    payload_b64 = parts[1]
    provided_signature = parts[2]
    secret = signing_secret or settings.LICENSE_SIGNING_KEY or settings.SECRET_KEY

    # 1. Constant-time signature verification (anti-tamper)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, provided_signature):
        return False, None, "የፈቃድ ፊርማ አልተዛመደም ወይም ተለውጧል (Cryptographic signature verification failed: license payload was tampered with)"

    # 2. Decode payload
    try:
        # Add back padding
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(f"{payload_b64}{padding}").decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as e:
        return False, None, f"የፈቃድ መረጃን ማንበብ አልተቻለም (Failed to decode license payload: {str(e)})"

    # 3. Required fields validation
    required_keys = ["organization_slug", "tier", "max_users", "storage_limit_gb", "issued_at", "expires_at"]
    for key in required_keys:
        if key not in payload:
            return False, None, f"ጎዶሎ የፈቃድ መረጃ ({key} is missing in license payload)"

    # 4. Tenant slug binding validation
    if expected_org_slug:
        if payload["organization_slug"].lower().strip() != expected_org_slug.lower().strip():
            return (
                False,
                payload,
                f"ይህ ፈቃድ ለ '{payload['organization_slug']}' የተሰጠ በመሆኑ ለ '{expected_org_slug}' አይሰራም "
                f"(License was issued for '{payload['organization_slug']}', cannot be used for '{expected_org_slug}')"
            )

    # 5. Temporal validity & clock-tampering detection
    try:
        now = datetime.now(timezone.utc)
        issued_at = datetime.fromisoformat(payload["issued_at"])
        expires_at = datetime.fromisoformat(payload["expires_at"])
        grace_days = int(payload.get("grace_period_days", 14))

        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # Anti clock-rollback: check if current time is suspiciously before issue date
        if now < (issued_at - timedelta(days=1)):
            return False, payload, "የስርዓት ሰዓት መዛባት ተገኝቷል (System clock tampering detected: current time precedes license issue date)"

        # Expiration & grace period check
        grace_deadline = expires_at + timedelta(days=grace_days)
        if now > grace_deadline:
            return (
                False,
                payload,
                f"የፈቃድ ጊዜው አልቋል (License expired on {expires_at.strftime('%Y-%m-%d')} and grace period has ended)"
            )

        if now > expires_at:
            if not allow_grace_period:
                return (
                    False,
                    payload,
                    f"የፈቃድ ጊዜው አልቋል (License expired on {expires_at.strftime('%Y-%m-%d')})"
                )

    except Exception as e:
        return False, payload, f"የፈቃድ ቀን ትክክለኛ አይደለም (Invalid license date formatting: {str(e)})"

    return True, payload, None


def evaluate_license_lifecycle(
    expires_at: datetime,
    grace_period_days: int = 14,
    is_active: bool = True
) -> Dict[str, Any]:
    """
    Computes real-time license lifecycle state, days remaining, and warning alerts.
    """
    if not is_active:
        return {
            "status": LicenseStatus.REVOKED,
            "days_remaining": 0,
            "grace_days_remaining": 0,
            "is_usable": False,
            "warning": "ይህ ፈቃድ በአስተዳዳሪው ታግዷል (License has been revoked/deactivated)",
        }

    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    delta = expires_at - now
    days_remaining = delta.days
    grace_deadline = expires_at + timedelta(days=grace_period_days)

    if now > grace_deadline:
        return {
            "status": LicenseStatus.EXPIRED,
            "days_remaining": days_remaining,
            "grace_days_remaining": 0,
            "is_usable": False,
            "warning": "የፈቃድ አገልግሎት ጊዜው ሙሉ በሙሉ አልቋል። እባክዎ አዲስ ፈቃድ ያስገቡ (License expired and grace period ended. Please activate a new license.)",
        }

    if now > expires_at:
        grace_delta = grace_deadline - now
        return {
            "status": LicenseStatus.IN_GRACE_PERIOD,
            "days_remaining": days_remaining,
            "grace_days_remaining": max(0, grace_delta.days),
            "is_usable": True,
            "warning": f"ፈቃድዎ አልቋል! በተሰጠው የ{grace_period_days} ቀናት የችሮታ ጊዜ ውስጥ ነዎት ({max(0, grace_delta.days)} ቀናት ቀርተዋል)። (In grace period: {max(0, grace_delta.days)} days remaining before lockdown)",
        }

    if days_remaining <= 30:
        return {
            "status": LicenseStatus.EXPIRING_SOON,
            "days_remaining": days_remaining,
            "grace_days_remaining": grace_period_days,
            "is_usable": True,
            "warning": f"ፈቃድዎ በ{days_remaining} ቀናት ውስጥ ያበቃል። እባክዎ ቀድመው ያድሱ (License expiring in {days_remaining} days. Please renew in advance.)",
        }

    return {
        "status": LicenseStatus.VALID,
        "days_remaining": days_remaining,
        "grace_days_remaining": grace_period_days,
        "is_usable": True,
        "warning": None,
    }
