import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.services.tenant_service import TenantService, StorageQuotaExceededError

client = TestClient(app)


@pytest.fixture
def admin_headers():
    r = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers():
    r = client.post("/api/v1/auth/login", json={"email": "abebe@abyssinia.et", "password": "Staff123!"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_public_tenant_branding_resolution():
    # Public resolution without token
    r = client.get("/api/v1/organizations/branding/abyssinia")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "abyssinia"
    assert "theme_color" in data
    assert data["is_active"] is True
    assert data["status"] == "ACTIVE"

    # Non-existent slug returns 404
    r_ghost = client.get("/api/v1/organizations/branding/non-existent-company-999")
    assert r_ghost.status_code == 404


def test_organization_profile_and_update(admin_headers, staff_headers):
    # 1. Staff can view profile
    r = client.get("/api/v1/organizations/profile", headers=staff_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "abyssinia"

    # 2. Staff cannot update profile (Forbidden)
    staff_update = client.patch(
        "/api/v1/organizations/profile",
        json={"name": "Hacked Name"},
        headers=staff_headers
    )
    assert staff_update.status_code == 403

    # 3. Admin can update profile with valid Ethiopian TIN
    admin_update = client.patch(
        "/api/v1/organizations/profile",
        json={
            "name": "አቢሲንያ ኮሜርሻል ኃ/የተ/የግ/ማ",
            "tin_number": "0099887766",
            "theme_color": "#047857"
        },
        headers=admin_headers
    )
    assert admin_update.status_code == 200
    updated_data = admin_update.json()
    assert updated_data["tin_number"] == "0099887766"
    assert updated_data["theme_color"] == "#047857"


def test_tin_and_theme_color_validation(admin_headers):
    # Invalid TIN (less than 10 digits)
    r_tin = client.patch(
        "/api/v1/organizations/profile",
        json={"tin_number": "12345"},
        headers=admin_headers
    )
    assert r_tin.status_code == 422

    # Invalid theme color (not hex)
    r_color = client.patch(
        "/api/v1/organizations/profile",
        json={"theme_color": "not-a-color"},
        headers=admin_headers
    )
    assert r_color.status_code == 422


def test_hierarchical_nested_departments(admin_headers):
    suffix = uuid.uuid4().hex[:4].upper()
    parent_code = f"DIS_{suffix}"
    child_code = f"BR_{suffix}"

    # 1. Create parent department (District / Division)
    r_parent = client.post(
        "/api/v1/departments",
        json={
            "name": f"South District HQ {suffix}",
            "code": parent_code,
            "description": "የደቡብ አዲስ አበባ ቀጣና ዋና መሥሪያ ቤት"
        },
        headers=admin_headers
    )
    assert r_parent.status_code == 201
    parent_id = r_parent.json()["id"]

    # 2. Create nested child department (Branch / Sub-unit)
    r_child = client.post(
        "/api/v1/departments",
        json={
            "name": f"Bole Branch {suffix}",
            "code": child_code,
            "parent_id": parent_id,
            "storage_quota_gb": 10.0,
        },
        headers=admin_headers
    )
    assert r_child.status_code == 201
    assert r_child.json()["code"] == child_code

    # 3. List departments and verify subdepartment count
    r_list = client.get("/api/v1/departments", headers=admin_headers)
    assert r_list.status_code == 200
    depts = {d["id"]: d for d in r_list.json()}
    assert depts[parent_id]["subdepartment_count"] >= 1


def test_department_storage_quota_enforcement(admin_headers):
    suffix = uuid.uuid4().hex[:4].upper()
    
    # Create dept with 5 GB quota
    r = client.post(
        "/api/v1/departments",
        json={
            "name": f"Audited Dept {suffix}",
            "code": f"AUD_{suffix}",
            "storage_quota_gb": 5.0,
        },
        headers=admin_headers
    )
    assert r.status_code == 201
    dept_id = uuid.UUID(r.json()["id"])

    # Check that requesting 6 GB fails on department quota
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="abyssinia").first()
        oversized_bytes = int(6 * (1024 ** 3))  # 6 GB
        with pytest.raises(StorageQuotaExceededError):
            TenantService.check_storage_budget(db, org.id, oversized_bytes, dept_id=dept_id)
    finally:
        db.close()


def test_1click_enterprise_tenant_provisioning():
    slug = f"bank-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"

    payload = {
        "organization_name": "Cooperative Bank of Oromia Partner",
        "slug": slug,
        "tin_number": "0044332211",
        "admin_email": admin_email,
        "admin_full_name": "Chala Dibaba",
        "admin_password": "SecurePassword2026!",
        "storage_limit_gb": 200.0,
        "max_users": 100,
    }

    # 1. Provision new tenant
    r = client.post("/api/v1/organizations/provision", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == slug
    assert data["admin_email"] == admin_email
    assert data["status"] == "ACTIVE"

    # 2. Login immediately with provisioned admin credentials
    r_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "SecurePassword2026!"})
    assert r_login.status_code == 200
    headers = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

    # 3. Verify auto-provisioned standard Ethiopian departments (FIN, HR, OPS)
    r_depts = client.get("/api/v1/departments", headers=headers)
    assert r_depts.status_code == 200
    dept_codes = [d["code"] for d in r_depts.json()]
    assert "FIN" in dept_codes
    assert "HR" in dept_codes
    assert "OPS" in dept_codes


def test_tenant_suspension_lifecycle(admin_headers):
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="abyssinia").first()
        
        # 1. Suspend the organization
        org.status = OrganizationStatus.SUSPENDED
        db.commit()

        # 2. Verify login is blocked with suspension message
        r_blocked = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
        assert r_blocked.status_code == 401
        assert "ታግዷል" in r_blocked.json()["detail"] or "suspended" in r_blocked.json()["detail"].lower()

        # 3. Restore to ACTIVE
        org.status = OrganizationStatus.ACTIVE
        db.commit()

        # 4. Verify login succeeds again
        r_active = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
        assert r_active.status_code == 200

    finally:
        db.close()
