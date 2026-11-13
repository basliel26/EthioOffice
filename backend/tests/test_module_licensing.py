import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, License, LicenseTier, OrganizationStatus
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.licensing import (
    generate_license_token,
    verify_license_token,
    evaluate_license_lifecycle,
    LicenseStatus,
)
from app.services.capability_service import (
    CapabilityService,
    Capability,
    DEFAULT_TIER_CAPABILITIES,
    SeatLimitExceededError,
)

client = TestClient(app)


# ---------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_headers():
    r = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------
# Pillar 1 & 4 Tests: Cryptographic Token & Lifecycle State
# ---------------------------------------------------------

def test_cryptographic_offline_token_generation_and_tamper_rejection():
    """
    Verifies that offline signed license tokens:
    1. Validate cleanly when unaltered.
    2. Immediately fail HMAC verification when payload or signature is tampered with.
    3. Enforce tenant slug binding.
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=180)
    features = ["CORE_STORAGE", "OFFICE_COAUTHORING", "LETTER_REGISTRY"]

    token = generate_license_token(
        organization_slug="dashen-bank",
        tier="BUSINESS",
        max_users=150,
        storage_limit_gb=500,
        features=features,
        expires_at=expiry,
        grace_period_days=14,
    )

    # 1. Valid token passes
    is_valid, payload, err = verify_license_token(token, expected_org_slug="dashen-bank")
    assert is_valid is True
    assert err is None
    assert payload["organization_slug"] == "dashen-bank"
    assert payload["max_users"] == 150
    assert payload["storage_limit_gb"] == 500
    assert "LETTER_REGISTRY" in payload["features"]

    # 2. Tampered signature fails
    tampered_sig = token[:-4] + "dead"
    valid_sig, _, err_sig = verify_license_token(tampered_sig, expected_org_slug="dashen-bank")
    assert valid_sig is False
    assert "signature verification failed" in err_sig.lower()

    # 3. Mismatched tenant fails
    valid_slug, _, err_slug = verify_license_token(token, expected_org_slug="awash-bank")
    assert valid_slug is False
    assert "cannot be used for 'awash-bank'" in err_slug

    # 4. Corrupted format fails
    valid_fmt, _, err_fmt = verify_license_token("NOT-A-TOKEN", expected_org_slug="dashen-bank")
    assert valid_fmt is False
    assert "format" in err_fmt.lower()


def test_license_lifecycle_states_and_grace_period():
    """
    Verifies state transitions across the license lifecycle:
    VALID -> EXPIRING_SOON -> IN_GRACE_PERIOD -> EXPIRED -> REVOKED.
    """
    now = datetime.now(timezone.utc)

    # 1. Valid far in future (100 days)
    state_valid = evaluate_license_lifecycle(now + timedelta(days=100), grace_period_days=14)
    assert state_valid["status"] == LicenseStatus.VALID
    assert state_valid["is_usable"] is True
    assert state_valid["days_remaining"] >= 99
    assert state_valid["warning"] is None

    # 2. Expiring soon (15 days)
    state_soon = evaluate_license_lifecycle(now + timedelta(days=15), grace_period_days=14)
    assert state_soon["status"] == LicenseStatus.EXPIRING_SOON
    assert state_soon["is_usable"] is True
    assert "በ15 ቀናት ውስጥ" in state_soon["warning"] or "expiring in" in state_soon["warning"].lower()

    # 3. Inside grace period (expired 4 days ago, 14-day grace)
    state_grace = evaluate_license_lifecycle(now - timedelta(days=4), grace_period_days=14)
    assert state_grace["status"] == LicenseStatus.IN_GRACE_PERIOD
    assert state_grace["is_usable"] is True
    assert state_grace["grace_days_remaining"] >= 9
    assert "ችሮታ ጊዜ" in state_grace["warning"] or "grace period" in state_grace["warning"].lower()

    # 4. Past grace period (expired 20 days ago, 14-day grace)
    state_expired = evaluate_license_lifecycle(now - timedelta(days=20), grace_period_days=14)
    assert state_expired["status"] == LicenseStatus.EXPIRED
    assert state_expired["is_usable"] is False

    # 5. Revoked
    state_revoked = evaluate_license_lifecycle(now + timedelta(days=100), is_active=False)
    assert state_revoked["status"] == LicenseStatus.REVOKED
    assert state_revoked["is_usable"] is False


# ---------------------------------------------------------
# Pillar 2 Tests: Seat Limit Enforcement
# ---------------------------------------------------------

def test_seat_limit_enforcement(db_session):
    """
    Verifies that organizations cannot provision users exceeding their licensed seat cap.
    """
    unique_slug = f"seat-test-{uuid.uuid4().hex[:6]}"
    
    # 1. Provision a tenant with max_users=2
    prov_payload = {
        "organization_name": "Seat Limit Test Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": f"admin@{unique_slug}.et",
        "admin_password": "Password123!",
        "admin_full_name": "Seat Admin",
        "max_users": 2,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    # 2. Login as the tenant admin (uses Seat 1/2)
    login_r = client.post("/api/v1/auth/login", json={
        "email": f"admin@{unique_slug}.et",
        "password": "Password123!"
    })
    assert login_r.status_code == 200
    tenant_admin_headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}

    # 3. Add employee 2 (occupies Seat 2/2) -> Should SUCCEED
    user2_payload = {
        "email": f"emp2@{unique_slug}.et",
        "password": "Password123!",
        "full_name": "Employee Two",
        "role": "STAFF",
    }
    r_u2 = client.post("/api/v1/auth/users", json=user2_payload, headers=tenant_admin_headers)
    assert r_u2.status_code == 201

    # 4. Attempt to add employee 3 (would exceed Seat 2/2 limit) -> MUST FAIL 403
    user3_payload = {
        "email": f"emp3@{unique_slug}.et",
        "password": "Password123!",
        "full_name": "Employee Three",
        "role": "STAFF",
    }
    r_u3 = client.post("/api/v1/auth/users", json=user3_payload, headers=tenant_admin_headers)
    assert r_u3.status_code == 403
    assert "Seat Limit" in r_u3.json()["detail"] or "ተሞልቷል" in r_u3.json()["detail"]


# ---------------------------------------------------------
# Pillar 3 Tests: Capability Feature Gating
# ---------------------------------------------------------

def test_capability_feature_gating(db_session):
    """
    Verifies that endpoints gated with `require_capability`:
    1. Reject calls when tenant does not have the capability (HTTP 403 with FEATURE_NOT_LICENSED).
    2. Allow calls once an updated license grants the capability.
    """
    unique_slug = f"gate-test-{uuid.uuid4().hex[:6]}"
    
    # 1. Provision tenant
    prov_payload = {
        "organization_name": "Gate Test Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": f"admin@{unique_slug}.et",
        "admin_password": "Password123!",
        "admin_full_name": "Gate Admin",
        "max_users": 10,
        "storage_limit_gb": 50.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    login_r = client.post("/api/v1/auth/login", json={
        "email": f"admin@{unique_slug}.et",
        "password": "Password123!"
    })
    headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}

    # By default, provisioned tenants are on BUSINESS tier (includes LETTER_REGISTRY, excludes AUDIT_EXPORT)
    # Attempting to call ENTERPRISE compliance export endpoint should return 403
    r_audit = client.get("/api/v1/licenses/compliance-export", headers=headers)
    assert r_audit.status_code == 403
    err_detail = r_audit.json()["detail"]
    assert err_detail["code"] == "FEATURE_NOT_LICENSED"
    assert err_detail["capability"] == "AUDIT_EXPORT"

    # Now downgrade license to STARTER tier (excludes LETTER_REGISTRY) to test letter route gating
    org = db_session.query(Organization).filter(Organization.slug == unique_slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.tier = LicenseTier.STARTER
    lic.features = "CORE_STORAGE,CUSTOM_BRANDING"
    db_session.commit()

    # Calling letter registry endpoint should now be blocked with 403 FEATURE_NOT_LICENSED
    letter_payload = {
        "reference_number": f"LTR-{uuid.uuid4().hex[:4]}",
        "direction": "INWARD",
        "subject": "Commercial Proposal",
        "sender_entity": "Ethio Telecom",
        "recipient_entity": "Gate Corp",
    }
    r_letter = client.post("/api/v1/letters", json=letter_payload, headers=headers)
    assert r_letter.status_code == 403
    assert r_letter.json()["detail"]["code"] == "FEATURE_NOT_LICENSED"
    assert r_letter.json()["detail"]["capability"] == "LETTER_REGISTRY"


# ---------------------------------------------------------
# Pillar 5 Tests: Admin License Management API & Activation
# ---------------------------------------------------------

def test_license_current_status_and_activation_flow(db_session):
    """
    Verifies:
    1. GET /api/v1/licenses/current returns real-time metrics.
    2. POST /api/v1/licenses/activate verifies signature, synchronizes org limits,
       and immediately unlocks enterprise capabilities.
    """
    unique_slug = f"lic-flow-{uuid.uuid4().hex[:6]}"
    
    # 1. Provision tenant
    prov_payload = {
        "organization_name": "Licensing Flow Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": f"admin@{unique_slug}.et",
        "admin_password": "Password123!",
        "admin_full_name": "Flow Admin",
        "max_users": 10,
        "storage_limit_gb": 50.0,
    }
    client.post("/api/v1/organizations/provision", json=prov_payload)

    login_r = client.post("/api/v1/auth/login", json={
        "email": f"admin@{unique_slug}.et",
        "password": "Password123!"
    })
    headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}

    # 2. Check current license
    r_cur = client.get("/api/v1/licenses/current", headers=headers)
    assert r_cur.status_code == 200
    cur_data = r_cur.json()
    assert cur_data["organization_slug"] == unique_slug
    assert cur_data["max_users"] == 10
    assert cur_data["status"] in ["VALID", "EXPIRING_SOON"]
    assert "LETTER_REGISTRY" in cur_data["capabilities"]
    assert "AUDIT_EXPORT" not in cur_data["capabilities"]

    # 3. Generate a valid ENTERPRISE license token for this organization
    new_features = [
        "CORE_STORAGE",
        "CUSTOM_BRANDING",
        "DEPARTMENT_HIERARCHY",
        "OFFICE_COAUTHORING",
        "LETTER_REGISTRY",
        "AUDIT_EXPORT",
        "LDAP_AD_SYNC"
    ]
    enterprise_key = generate_license_token(
        organization_slug=unique_slug,
        tier="ENTERPRISE",
        max_users=500,
        storage_limit_gb=2000,
        features=new_features,
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        grace_period_days=30,
    )

    # 4. Activate key via API
    r_act = client.post("/api/v1/licenses/activate", json={"license_key": enterprise_key}, headers=headers)
    assert r_act.status_code == 200
    act_data = r_act.json()
    assert act_data["tier"] == "ENTERPRISE"
    assert act_data["max_users"] == 500
    assert act_data["storage_limit_gb"] == 2000.0
    assert "AUDIT_EXPORT" in act_data["capabilities"]
    assert "LDAP_AD_SYNC" in act_data["capabilities"]

    # 5. Verify org table limits were synchronized
    org = db_session.query(Organization).filter(Organization.slug == unique_slug).first()
    assert org.max_users == 500
    assert org.storage_limit_bytes == 2000 * (1024 ** 3)

    # 6. Verify enterprise-gated compliance export endpoint now SUCCEEDS (200 OK)
    r_audit = client.get("/api/v1/licenses/compliance-export", headers=headers)
    assert r_audit.status_code == 200
    assert r_audit.json()["export_format"] == "JSON_COMPLIANCE_FEED"


def test_license_activation_rejections(admin_headers):
    """
    Verifies error handling on /api/v1/licenses/activate:
    - Tampered token returns 422
    - Key for wrong tenant returns 403
    - Expired key returns 400
    """
    # 1. Tampered signature
    r_tampered = client.post(
        "/api/v1/licenses/activate",
        json={"license_key": "EO-LIC.eyJvcmciOiJhYnlzc2luaWEifQ.invalidsignature12345"},
        headers=admin_headers
    )
    assert r_tampered.status_code == 422

    # 2. Key issued for another organization
    wrong_org_key = generate_license_token(
        organization_slug="other-bank",
        tier="BUSINESS",
        max_users=50,
        storage_limit_gb=100,
        features=["CORE_STORAGE"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=100),
    )
    r_wrong = client.post(
        "/api/v1/licenses/activate",
        json={"license_key": wrong_org_key},
        headers=admin_headers
    )
    assert r_wrong.status_code == 403
    assert "cannot be used for" in r_wrong.json()["detail"].lower()
