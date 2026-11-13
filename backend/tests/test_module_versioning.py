"""
Comprehensive Automated Test Suite for Module 5: Versioning & Concurrency Control (File Locking)
Tests:
1. Sequential version upload (v1 -> v2) with change summary tracking.
2. Historical version payload streaming and SHA-256 ETag integrity.
3. Content-Addressable Storage (CAS) zero-byte version rollback / revert.
4. Exclusive check-out lock and concurrent mutation protection (HTTP 423 Locked).
5. Lock release and Administrative force-unlock with audit trail.
6. Automatic lock TTL expiration and takeover by another user.
7. Enterprise License Read-Only write lockdown enforcement on versions & locks.
"""

import io
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, License
from app.models.user import User, UserRole
from app.models.file import FileItem, FileVersion
from app.models.lock import FileLock

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_versioning_tenant_and_users(slug_prefix: str = "ver"):
    """Helper to provision a tenant with an Admin and two Staff colleagues."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Versioning Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Versioning Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    # Login Admin
    login_admin = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
    assert login_admin.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    # Staff A (Abebe)
    staff_a_email = f"abebe@{slug}.et"
    client.post(
        "/api/v1/auth/users",
        json={"email": staff_a_email, "full_name": "Abebe Kebede", "password": password, "role": "STAFF"},
        headers=admin_headers,
    )
    login_a = client.post("/api/v1/auth/login", json={"email": staff_a_email, "password": password})
    staff_a_headers = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Staff B (Chala)
    staff_b_email = f"chala@{slug}.et"
    client.post(
        "/api/v1/auth/users",
        json={"email": staff_b_email, "full_name": "Chala Tadesse", "password": password, "role": "STAFF"},
        headers=admin_headers,
    )
    login_b = client.post("/api/v1/auth/login", json={"email": staff_b_email, "password": password})
    staff_b_headers = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    return {
        "slug": slug,
        "admin_headers": admin_headers,
        "staff_a_headers": staff_a_headers,
        "staff_a_email": staff_a_email,
        "staff_b_headers": staff_b_headers,
        "staff_b_email": staff_b_email,
    }


# =====================================================================
# Test 1: Sequential Version Creation and Version List
# =====================================================================

def test_sequential_version_creation(db_session):
    """
    Verifies uploading v1 and v2: auto-incrementing version numbers,
    change summaries, and version history listing in newest-first order.
    """
    tenant = create_versioning_tenant_and_users("seq-ver")
    headers = tenant["staff_a_headers"]

    v1_content = b"EthioOffice System Architecture Specification v1.0"
    v2_content = b"EthioOffice System Architecture Specification v2.0 - With Microservices"

    # 1. Initial upload (v1)
    files_v1 = {"file": ("architecture_spec.pdf", io.BytesIO(v1_content), "application/pdf")}
    r_v1 = client.post("/api/v1/files/upload", files=files_v1, data={"drive_type": "COMPANY"}, headers=headers)
    assert r_v1.status_code == 201
    file_id = r_v1.json()["id"]

    # 2. Upload revision (v2)
    files_v2 = {"file": ("architecture_spec.pdf", io.BytesIO(v2_content), "application/pdf")}
    data_v2 = {"change_summary": "Added distributed cache and high-availability design"}
    r_v2 = client.post(f"/api/v1/files/{file_id}/versions", files=files_v2, data=data_v2, headers=headers)
    assert r_v2.status_code == 201
    file_resp = r_v2.json()
    assert file_resp["size_bytes"] == len(v2_content)

    # 3. List all versions
    r_list = client.get(f"/api/v1/files/{file_id}/versions", headers=headers)
    assert r_list.status_code == 200
    versions = r_list.json()
    assert len(versions) == 2

    # Verify descending order (v2 first, then v1)
    assert versions[0]["version_number"] == 2
    assert versions[0]["size_bytes"] == len(v2_content)
    assert versions[0]["change_summary"] == "Added distributed cache and high-availability design"
    assert versions[0]["created_by_name"] == "Abebe Kebede"
    assert versions[0]["ec_created_at"] is not None

    assert versions[1]["version_number"] == 1
    assert versions[1]["size_bytes"] == len(v1_content)


# =====================================================================
# Test 2: Historical Version Download and ETag Integrity
# =====================================================================

def test_historical_version_download_and_etag(db_session):
    """
    Verifies stream downloading specific historical versions (v1 vs v2)
    and verifies respective SHA-256 ETag integrity headers.
    """
    tenant = create_versioning_tenant_and_users("hist-dl")
    headers = tenant["staff_a_headers"]

    v1_content = b"Financial Directive 2018 - Baseline Draft"
    v2_content = b"Financial Directive 2019 - Approved Final"
    sha1 = hashlib.sha256(v1_content).hexdigest()
    sha2 = hashlib.sha256(v2_content).hexdigest()

    # Upload v1
    files_v1 = {"file": ("directive.pdf", io.BytesIO(v1_content), "application/pdf")}
    r_v1 = client.post("/api/v1/files/upload", files=files_v1, data={"drive_type": "COMPANY"}, headers=headers)
    file_id = r_v1.json()["id"]

    # Upload v2
    files_v2 = {"file": ("directive.pdf", io.BytesIO(v2_content), "application/pdf")}
    client.post(f"/api/v1/files/{file_id}/versions", files=files_v2, data={"change_summary": "Final approval"}, headers=headers)

    # 1. Download Version 1
    r_dl1 = client.get(f"/api/v1/files/{file_id}/versions/1/download", headers=headers)
    assert r_dl1.status_code == 200
    assert r_dl1.content == v1_content
    assert sha1 in r_dl1.headers.get("etag")

    # 2. Download Version 2
    r_dl2 = client.get(f"/api/v1/files/{file_id}/versions/2/download", headers=headers)
    assert r_dl2.status_code == 200
    assert r_dl2.content == v2_content
    assert sha2 in r_dl2.headers.get("etag")


# =====================================================================
# Test 3: CAS Zero-Byte Version Rollback / Revert
# =====================================================================

def test_version_rollback_revert_cas_zero_bytes(db_session):
    """
    Verifies that reverting document back to historical v1:
    1. Creates v3 pointing to v1 payload with summary 'Reverted to Version 1'.
    2. Updates current version pointer and file size.
    3. Reuses existing physical disk payload (0 extra quota bytes added).
    """
    tenant = create_versioning_tenant_and_users("revert-cas")
    headers = tenant["staff_a_headers"]
    slug = tenant["slug"]

    org = db_session.query(Organization).filter(Organization.slug == slug).first()

    content_v1 = b"Original baseline draft before erroneous edits"
    content_v2 = b"Erroneous edits that broke the accounting tables"

    # Upload v1
    files_v1 = {"file": ("accounting_sheet.xlsx", io.BytesIO(content_v1), "application/vnd.ms-excel")}
    r1 = client.post("/api/v1/files/upload", files=files_v1, data={"drive_type": "COMPANY"}, headers=headers)
    file_id = r1.json()["id"]

    # Upload v2
    files_v2 = {"file": ("accounting_sheet.xlsx", io.BytesIO(content_v2), "application/vnd.ms-excel")}
    client.post(f"/api/v1/files/{file_id}/versions", files=files_v2, data={"change_summary": "Bad edits"}, headers=headers)

    db_session.refresh(org)
    used_after_v2 = org.used_storage_bytes

    # Rollback / Revert to Version 1
    r_revert = client.post(f"/api/v1/files/{file_id}/versions/1/revert", headers=headers)
    assert r_revert.status_code == 200
    rev_info = r_revert.json()
    assert rev_info["size_bytes"] == len(content_v1)

    # Verify version 3 exists and reflects rollback
    r_versions = client.get(f"/api/v1/files/{file_id}/versions", headers=headers)
    versions = r_versions.json()
    assert len(versions) == 3
    assert versions[0]["version_number"] == 3
    assert "Reverted to Version 1" in versions[0]["change_summary"]

    # Verify download of current file returns v1 content
    r_dl = client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert r_dl.status_code == 200
    assert r_dl.content == content_v1

    # Verify CAS Zero-Byte storage impact: quota did NOT increase on revert!
    db_session.refresh(org)
    assert org.used_storage_bytes == used_after_v2


# =====================================================================
# Test 4: Exclusive Check-Out Lock and Concurrency Protection
# =====================================================================

def test_exclusive_checkout_lock_and_concurrency_protection(db_session):
    """
    Verifies that when Staff A locks a file:
    1. Lock details (locked_by, reason, expires_at) are exposed.
    2. Staff B is BLOCKED with 423 Locked on version upload, rename, move, delete.
    3. Staff A (lock holder) can modify the document without obstruction.
    """
    tenant = create_versioning_tenant_and_users("lock-guard")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]

    # Upload document by Staff A
    files = {"file": ("annual_procurement_plan.pdf", io.BytesIO(b"Procurement 2026"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 1. Staff A acquires exclusive lock
    lock_payload = {"reason": "Reviewing budget with CFO", "duration_minutes": 60}
    r_lock = client.post(f"/api/v1/files/{file_id}/lock", json=lock_payload, headers=staff_a)
    assert r_lock.status_code == 200
    lock_data = r_lock.json()
    assert lock_data["locked_by_name"] == "Abebe Kebede"
    assert lock_data["reason"] == "Reviewing budget with CFO"

    # Verify lock inspected via GET
    r_insp = client.get(f"/api/v1/files/{file_id}/lock", headers=staff_b)
    assert r_insp.status_code == 200
    assert r_insp.json()["locked_by_name"] == "Abebe Kebede"

    # 2. Staff B attempts mutation 1: Upload new version -> 423 LOCKED
    new_payload = {"file": ("annual_procurement_plan.pdf", io.BytesIO(b"Conflicting Edit"), "application/pdf")}
    r_b_ver = client.post(f"/api/v1/files/{file_id}/versions", files=new_payload, headers=staff_b)
    assert r_b_ver.status_code == 423
    assert r_b_ver.json()["detail"]["code"] == "FILE_LOCKED"
    assert "Abebe Kebede" in r_b_ver.json()["detail"]["message"]

    # 3. Staff B attempts mutation 2: Rename -> 423 LOCKED
    r_b_ren = client.patch(f"/api/v1/files/{file_id}/rename", json={"name": "Hacked Plan.pdf"}, headers=staff_b)
    assert r_b_ren.status_code == 423
    assert r_b_ren.json()["detail"]["code"] == "FILE_LOCKED"

    # 4. Staff B attempts mutation 3: Move -> 423 LOCKED
    r_b_mov = client.patch(f"/api/v1/files/{file_id}/move", json={"new_parent_id": None}, headers=staff_b)
    assert r_b_mov.status_code == 423
    assert r_b_mov.json()["detail"]["code"] == "FILE_LOCKED"

    # 5. Staff B attempts mutation 4: Delete -> 423 LOCKED
    r_b_del = client.delete(f"/api/v1/files/{file_id}", headers=staff_b)
    assert r_b_del.status_code == 423
    assert r_b_del.json()["detail"]["code"] == "FILE_LOCKED"

    # 6. Staff A (the lock owner) uploads new version -> SUCCEEDS
    a_payload = {"file": ("annual_procurement_plan.pdf", io.BytesIO(b"CFO Approved 2026"), "application/pdf")}
    r_a_ver = client.post(f"/api/v1/files/{file_id}/versions", files=a_payload, headers=staff_a)
    assert r_a_ver.status_code == 201


# =====================================================================
# Test 5: Lock Release and Admin Force-Unlock
# =====================================================================

def test_lock_release_and_admin_force_unlock(db_session):
    """
    Verifies that:
    1. A colleague cannot unlock another colleague's lock (403 Forbidden).
    2. An Admin can force-unlock any abandoned or stale lock.
    """
    tenant = create_versioning_tenant_and_users("force-unlock")
    admin_headers = tenant["admin_headers"]
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]

    # Upload document & lock by Staff A
    files = {"file": ("locked_tender.pdf", io.BytesIO(b"Tender Document"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Working on bid"}, headers=staff_a)

    # 1. Staff B tries to unlock -> 403 FORBIDDEN
    r_unlock_b = client.post(f"/api/v1/files/{file_id}/unlock", json={"force": False}, headers=staff_b)
    assert r_unlock_b.status_code == 403

    # 2. Staff B tries force=True -> 403 FORBIDDEN (Staff B is not Admin)
    r_force_b = client.post(f"/api/v1/files/{file_id}/unlock", json={"force": True}, headers=staff_b)
    assert r_force_b.status_code == 403

    # 3. Admin calls force-unlock -> 200 OK
    r_admin_unlock = client.post(f"/api/v1/files/{file_id}/unlock", json={"force": True}, headers=admin_headers)
    assert r_admin_unlock.status_code == 200

    # 4. Verify file is unlocked
    r_check = client.get(f"/api/v1/files/{file_id}/lock", headers=staff_b)
    assert r_check.status_code == 200
    assert r_check.json() is None

    # 5. Staff B can now acquire the lock
    r_lock_b = client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Staff B takeover"}, headers=staff_b)
    assert r_lock_b.status_code == 200
    assert r_lock_b.json()["locked_by_name"] == "Chala Tadesse"


# =====================================================================
# Test 6: Automatic Lock TTL Expiration
# =====================================================================

def test_lock_auto_expiration_ttl(db_session):
    """
    Verifies that when a lock expires past its TTL, another colleague
    can automatically acquire it without manual unlock intervention.
    """
    tenant = create_versioning_tenant_and_users("ttl-expire")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]

    files = {"file": ("ttl_test.pdf", io.BytesIO(b"TTL Document"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # Staff A acquires lock
    client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Short lock", "duration_minutes": 5}, headers=staff_a)

    # Manually backdate lock in database to 10 minutes ago
    lock = db_session.query(FileLock).filter(FileLock.file_id == uuid.UUID(file_id)).first()
    assert lock is not None
    lock.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    # Staff B checks lock: returns None (expired)
    r_check = client.get(f"/api/v1/files/{file_id}/lock", headers=staff_b)
    assert r_check.status_code == 200
    assert r_check.json() is None

    # Staff B acquires lock -> SUCCESS
    r_lock_b = client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Acquiring expired lock"}, headers=staff_b)
    assert r_lock_b.status_code == 200
    assert r_lock_b.json()["locked_by_name"] == "Chala Tadesse"


# =====================================================================
# Test 7: License Read-Only Write Lockdown on Versions & Locks
# =====================================================================

def test_versioning_and_locking_write_lockdown(db_session):
    """
    Verifies that when tenant license enters expired write lockdown mode:
    1. Version uploads, rollbacks, and acquiring locks are rejected with 403.
    2. Version history listing and downloading historical payloads continue to work.
    """
    tenant = create_versioning_tenant_and_users("lockdown-ver")
    admin_headers = tenant["admin_headers"]
    slug = tenant["slug"]

    # Upload document with 2 versions while active
    files_v1 = {"file": ("license_test.pdf", io.BytesIO(b"Version 1 content"), "application/pdf")}
    r1 = client.post("/api/v1/files/upload", files=files_v1, data={"drive_type": "COMPANY"}, headers=admin_headers)
    file_id = r1.json()["id"]

    files_v2 = {"file": ("license_test.pdf", io.BytesIO(b"Version 2 content"), "application/pdf")}
    client.post(f"/api/v1/files/{file_id}/versions", files=files_v2, headers=admin_headers)

    # Expire tenant license past grace period
    org = db_session.query(Organization).filter(Organization.slug == slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.expires_at = datetime.now(timezone.utc) - timedelta(days=25)
    lic.grace_period_days = 7
    db_session.commit()

    # 1. Attempt upload new version -> 403 LICENSE_LOCKDOWN_READ_ONLY
    files_v3 = {"file": ("license_test.pdf", io.BytesIO(b"Version 3 blocked"), "application/pdf")}
    r_v3 = client.post(f"/api/v1/files/{file_id}/versions", files=files_v3, headers=admin_headers)
    assert r_v3.status_code == 403
    assert r_v3.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 2. Attempt rollback / revert -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_rev = client.post(f"/api/v1/files/{file_id}/versions/1/revert", headers=admin_headers)
    assert r_rev.status_code == 403
    assert r_rev.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 3. Attempt lock acquisition -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_lock = client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Blocked lock"}, headers=admin_headers)
    assert r_lock.status_code == 403
    assert r_lock.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 4. Read operations continue to work (Read-Only access guaranteed)
    r_list = client.get(f"/api/v1/files/{file_id}/versions", headers=admin_headers)
    assert r_list.status_code == 200
    assert len(r_list.json()) == 2

    r_dl1 = client.get(f"/api/v1/files/{file_id}/versions/1/download", headers=admin_headers)
    assert r_dl1.status_code == 200
    assert r_dl1.content == b"Version 1 content"
