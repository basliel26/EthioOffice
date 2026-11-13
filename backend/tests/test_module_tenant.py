import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization
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


def test_department_creation_and_duplicate_prevention(admin_headers):
    # Unique code for test idempotency
    unique_code = f"LEG_{uuid.uuid4().hex[:4].upper()}"
    unique_name = f"Legal Dept {unique_code}"

    # 1. Create department
    r = client.post(
        "/api/v1/departments",
        json={
            "name": unique_name,
            "code": unique_code,
            "description": "የድርጅቱ የሕግ ማዕቀፍ"
        },
        headers=admin_headers
    )
    assert r.status_code == 201

    # 2. Attempt to create duplicate code in same org (Must fail with 409 Conflict)
    r_dup = client.post(
        "/api/v1/departments",
        json={
            "name": f"Duplicate Dept {unique_code}",
            "code": unique_code,
        },
        headers=admin_headers
    )
    assert r_dup.status_code == 409


def test_cross_tenant_isolation(admin_headers):
    db = SessionLocal()
    try:
        # Create a second tenant: "Awash Enterprise"
        org2 = db.query(Organization).filter_by(slug="awash-test").first()
        if not org2:
            org2 = Organization(
                name="Awash Test Enterprise",
                slug="awash-test",
                tin_number="0055443322",
                theme_color="#2563eb",
                max_users=50,
                storage_limit_bytes=50 * 1024 * 1024 * 1024,
            )
            db.add(org2)
            db.flush()

            admin2 = User(
                organization_id=org2.id,
                email="admin@awash.et",
                full_name="Dawit Awash",
                hashed_password=get_password_hash("Awash123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin2)
            db.commit()

        # Login as Admin of Org 2
        r_login2 = client.post("/api/v1/auth/login", json={"email": "admin@awash.et", "password": "Awash123!"})
        assert r_login2.status_code == 200
        headers2 = {"Authorization": f"Bearer {r_login2.json()['access_token']}"}

        # Org 2 can also create department code 'LEGAL' without collision!
        r_dept_org2 = client.post(
            "/api/v1/departments",
            json={
                "name": "Awash Legal Department",
                "code": "LEGAL",
            },
            headers=headers2
        )
        assert r_dept_org2.status_code in [201, 409]  # 201 or 409 if re-run

        # Org 2 cannot see Org 1's departments!
        r_list2 = client.get("/api/v1/departments", headers=headers2)
        assert r_list2.status_code == 200
        dept_names_org2 = [d["name"] for d in r_list2.json()]
        assert "ፋይናንስና ሒሳብ (Finance & Accounting)" not in dept_names_org2

    finally:
        db.close()


def test_storage_quota_enforcement(admin_headers):
    # Check quota response
    r = client.get("/api/v1/organizations/storage-quota", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "used_bytes" in data
    assert "limit_bytes" in data
    assert "percent_used" in data
    assert data["is_exceeded"] is False

    # Direct service budget check beyond limit
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="abyssinia").first()
        huge_bytes = org.storage_limit_bytes + 1024
        with pytest.raises(StorageQuotaExceededError):
            TenantService.check_storage_budget(db, org.id, huge_bytes)
    finally:
        db.close()
