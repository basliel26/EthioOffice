import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, License, LicenseTier, OrganizationStatus, LicenseHistory
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.core.licensing import (
    generate_license_token,
    verify_license_token,
    get_server_hardware_fingerprint,
    evaluate_license_lifecycle,
    LicenseStatus,
)
from app.services.capability_service import CapabilityService, LicenseReadOnlyLockdownError

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------
# Test 1: Hardware Node-Locking (Anti-VM Cloning)
# ---------------------------------------------------------

def test_hardware_node_locking():
    """
    Verifies that licenses pinned to a specific hardware fingerprint:
    1. Pass verification on authorized server node.
    2. Fail verification when running on an unauthorized/cloned node.
    """
    current_fp = get_server_hardware_fingerprint()
    rogue_fp = "NODE-DEAD-BEEF-0000-9999"

    # 1. License locked to current host
    token_valid_host = generate_license_token(
        organization_slug="node-test-bank",
        tier="ENTERPRISE",
        max_users=100,
        storage_limit_gb=500,
        features=["CORE_STORAGE"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        machine_fingerprint=current_fp,
    )

    is_valid, payload, err = verify_license_token(
        token=token_valid_host,
        expected_org_slug="node-test-bank",
        expected_machine_fingerprint=current_fp,
        enforce_node_lock=True
    )
    assert is_valid is True
    assert payload["machine_fingerprint"] == current_fp

    # 2. Same license checked on rogue machine fails node-lock check
    is_valid_rogue, _, err_rogue = verify_license_token(
        token=token_valid_host,
        expected_org_slug="node-test-bank",
        expected_machine_fingerprint=rogue_fp,
        enforce_node_lock=True
    )
    assert is_valid_rogue is False
    assert "Hardware Node-Lock violation" in err_rogue


# ---------------------------------------------------------
# Test 2: License Expiry Write-Lockdown (Read-Only Mode)
# ---------------------------------------------------------

def test_license_expiry_write_lockdown(db_session):
    """
    Verifies that when a tenant's license is EXPIRED past grace period:
    1. Write operations (creating departments, provisioning users) are BLOCKED with 403.
    2. Read operations and renewal activation remain accessible.
    """
    unique_slug = f"lockdown-{uuid.uuid4().hex[:6]}"

    # Provision tenant
    prov_payload = {
        "organization_name": "Lockdown Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": f"admin@{unique_slug}.et",
        "admin_password": "Password123!",
        "admin_full_name": "Lockdown Admin",
        "max_users": 20,
        "storage_limit_gb": 100.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    login_r = client.post("/api/v1/auth/login", json={
        "email": f"admin@{unique_slug}.et",
        "password": "Password123!"
    })
    headers = {"Authorization": f"Bearer {login_r.json()['access_token']}"}

    # Manually backdate license so it expired 30 days ago (grace period is 14 days -> completely EXPIRED)
    org = db_session.query(Organization).filter(Organization.slug == unique_slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
    lic.grace_period_days = 14
    db_session.commit()

    # Attempt write 1: Create department -> BLOCKED 403
    dept_payload = {
        "name": "R&D Branch",
        "code": f"RD_{uuid.uuid4().hex[:4].upper()}",
    }
    r_dept = client.post("/api/v1/departments", json=dept_payload, headers=headers)
    assert r_dept.status_code == 403
    assert r_dept.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # Attempt write 2: Provision user -> BLOCKED 403
    user_payload = {
        "email": f"newemp@{unique_slug}.et",
        "password": "Password123!",
        "full_name": "New Emp",
    }
    r_user = client.post("/api/v1/auth/users", json=user_payload, headers=headers)
    assert r_user.status_code == 403
    assert r_user.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # Read operation remains accessible (viewing departments)
    r_read = client.get("/api/v1/departments", headers=headers)
    assert r_read.status_code == 200

    # Renewal activation remains accessible!
    renewal_key = generate_license_token(
        organization_slug=unique_slug,
        tier="BUSINESS",
        max_users=50,
        storage_limit_gb=200,
        features=["CORE_STORAGE", "DEPARTMENT_HIERARCHY", "CUSTOM_BRANDING"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    r_act = client.post("/api/v1/licenses/activate", json={"license_key": renewal_key}, headers=headers)
    assert r_act.status_code == 200

    # After activation, write access is restored!
    r_dept_after = client.post("/api/v1/departments", json=dept_payload, headers=headers)
    assert r_dept_after.status_code == 201


# ---------------------------------------------------------
# Test 3: Brute-Force Account Lockout & Admin Unlock
# ---------------------------------------------------------

def test_brute_force_account_lockout_and_unlock(db_session):
    """
    Verifies OWASP/INSA account lockout defense:
    1. 4 incorrect passwords report remaining attempts.
    2. 5th incorrect attempt locks account for 15 minutes (HTTP 423 Locked).
    3. Administrator can unlock the account via POST /users/{id}/unlock.
    """
    unique_slug = f"brute-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{unique_slug}.et"
    victim_email = f"victim@{unique_slug}.et"

    client.post("/api/v1/organizations/provision", json={
        "organization_name": "Brute Defense Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": "Password123!",
        "admin_full_name": "Brute Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    })

    admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Create target employee
    r_create = client.post("/api/v1/auth/users", json={
        "email": victim_email,
        "password": "VictimPassword123!",
        "full_name": "Victim Employee",
    }, headers=admin_headers)
    assert r_create.status_code == 201
    victim_id = r_create.json()["id"]

    # 4 Failed login attempts
    for attempt in range(1, 5):
        r_fail = client.post("/api/v1/auth/login", json={"email": victim_email, "password": f"WrongPass{attempt}!"})
        assert r_fail.status_code == 401
        assert f"{5 - attempt} ሙከራዎች ቀርተዋል" in r_fail.json()["detail"] or "attempts remaining" in r_fail.json()["detail"]

    # 5th Failed attempt triggers lockout
    r_lock = client.post("/api/v1/auth/login", json={"email": victim_email, "password": "WrongPass5!"})
    assert r_lock.status_code == 423
    assert r_lock.json()["detail"]["code"] == "ACCOUNT_LOCKED"

    # Even with the CORRECT password now, login is rejected because account is locked!
    r_locked_correct = client.post("/api/v1/auth/login", json={"email": victim_email, "password": "VictimPassword123!"})
    assert r_locked_correct.status_code == 423
    assert r_locked_correct.json()["detail"]["code"] == "ACCOUNT_LOCKED"

    # Admin unlocks the employee account
    r_unlock = client.post(f"/api/v1/auth/users/{victim_id}/unlock", headers=admin_headers)
    assert r_unlock.status_code == 200

    # Employee can now login successfully!
    r_success = client.post("/api/v1/auth/login", json={"email": victim_email, "password": "VictimPassword123!"})
    assert r_success.status_code == 200
    assert "access_token" in r_success.json()


# ---------------------------------------------------------
# Test 4: Corporate IP / CIDR Perimeter Whitelisting
# ---------------------------------------------------------

def test_corporate_ip_cidr_whitelisting(db_session):
    """
    Verifies that when allowed_ip_ranges is configured:
    1. Logins from whitelisted CIDR subnets succeed.
    2. Logins from unauthorized external IPs are rejected with 403 IP_ACCESS_DENIED.
    """
    unique_slug = f"ip-fence-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{unique_slug}.et"

    client.post("/api/v1/organizations/provision", json={
        "organization_name": "IP Fence Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": "Password123!",
        "admin_full_name": "Fence Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    })

    admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Configure corporate subnet whitelist: 10.0.0.0/8 and 192.168.1.0/24
    r_patch = client.patch("/api/v1/organizations/profile", json={
        "allowed_ip_ranges": "10.0.0.0/8, 192.168.1.0/24, 127.0.0.1"
    }, headers=admin_headers)
    assert r_patch.status_code == 200

    # 1. Login with local authorized IP (127.0.0.1 - default testclient IP) -> SUCCEEDS
    r_ok = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
    assert r_ok.status_code == 200

    # 2. Update allowed_ip_ranges to strictly exclude localhost (e.g. only 10.10.0.0/16)
    client.patch("/api/v1/organizations/profile", json={
        "allowed_ip_ranges": "10.10.0.0/16"
    }, headers=admin_headers)

    # Login from testclient (127.0.0.1) is now BLOCKED 403
    r_blocked = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
    assert r_blocked.status_code == 403
    assert r_blocked.json()["detail"]["code"] == "IP_ACCESS_DENIED"


# ---------------------------------------------------------
# Test 5: License Activation History & User Session Context
# ---------------------------------------------------------

def test_license_activation_history_and_user_session_context(db_session):
    """
    Verifies:
    1. LicenseHistory audit records are stored on activation.
    2. GET /api/v1/licenses/history returns chronological entries.
    3. User profile (/auth/me and login) contains real-time license context.
    """
    unique_slug = f"hist-test-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{unique_slug}.et"

    client.post("/api/v1/organizations/provision", json={
        "organization_name": "History Test Corp",
        "slug": unique_slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": "Password123!",
        "admin_full_name": "History Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    })

    admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "Password123!"})
    token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # Verify /auth/me contains license status context in organization summary
    r_me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert r_me.status_code == 200
    me_org = r_me.json()["organization"]
    assert me_org["license_tier"] == "BUSINESS"
    assert me_org["license_status"] in ["VALID", "EXPIRING_SOON"]
    assert me_org["days_remaining"] >= 360

    # Activate an ENTERPRISE license
    ent_key = generate_license_token(
        organization_slug=unique_slug,
        tier="ENTERPRISE",
        max_users=250,
        storage_limit_gb=1000,
        features=["CORE_STORAGE", "CUSTOM_BRANDING", "AUDIT_EXPORT"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=730),
    )
    r_act = client.post("/api/v1/licenses/activate", json={"license_key": ent_key}, headers=admin_headers)
    assert r_act.status_code == 200

    # Verify license history endpoint
    r_hist = client.get("/api/v1/licenses/history", headers=admin_headers)
    assert r_hist.status_code == 200
    history = r_hist.json()
    assert len(history) >= 1
    latest_entry = history[0]
    assert latest_entry["tier"] == "ENTERPRISE"
    assert latest_entry["max_users"] == 250
    assert latest_entry["storage_limit_gb"] == 1000.0
    assert latest_entry["activated_by_email"] == admin_email
