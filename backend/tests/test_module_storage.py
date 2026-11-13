"""
Comprehensive Automated Test Suite for Module 4: File Storage & Hierarchy Engine
Tests:
1. Streamed chunk upload (64KB chunks) & SHA-256 integrity calculation.
2. Content-Addressable Storage (CAS) Deduplication and shared disk payload safety.
3. Hierarchical directory tree navigation and recursive breadcrumbs resolution.
4. Cycle-safe folder moves with Anti-Loop prevention (ancestor graph walk).
5. File and folder renaming with sibling duplicate collision prevention.
6. Personal Drive vs Company Drive tenant isolation and cross-user authorization.
7. Cascading soft-delete and cascading restore lifecycles (Recycle Bin).
8. Permanent purge with physical file unlinking and storage quota reclamation.
9. Enterprise License Read-Only write lockdown enforcement across storage mutations.
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
from app.models.file import FileItem, FileVersion, DriveType
from app.services.storage_service import storage_provider

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_tenant_and_users(slug_prefix: str = "storage"):
    """Helper to provision a tenant with an Admin and a Staff user."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword123!"

    prov_payload = {
        "organization_name": f"Storage Test Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Storage Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    # Login Admin
    login_admin = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
    assert login_admin.status_code == 200
    admin_token = login_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Staff User
    staff_email = f"staff@{slug}.et"
    create_staff = client.post(
        "/api/v1/auth/users",
        json={
            "email": staff_email,
            "full_name": "Abebe Kebede",
            "password": password,
            "role": "STAFF",
        },
        headers=admin_headers,
    )
    assert create_staff.status_code == 201

    login_staff = client.post("/api/v1/auth/login", json={"email": staff_email, "password": password})
    assert login_staff.status_code == 200
    staff_token = login_staff.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    return {
        "slug": slug,
        "admin_headers": admin_headers,
        "admin_email": admin_email,
        "staff_headers": staff_headers,
        "staff_email": staff_email,
    }


# =====================================================================
# Test 1: Streamed Chunk Upload and SHA-256 Checksum
# =====================================================================

def test_streamed_chunk_upload_and_sha256(db_session):
    """
    Verifies that files larger than 64KB stream correctly in chunks,
    compute exact SHA-256 integrity hash, persist physical bytes, and can be downloaded.
    """
    tenant = create_test_tenant_and_users("stream")
    headers = tenant["admin_headers"]

    # Generate 128KB of deterministic data (exceeds 64KB chunk buffer)
    chunk_pattern = b"EthioOfficeSecureChunkData2026!" * 4  # 124 bytes
    file_bytes = (chunk_pattern * 1050)[:131072]  # Exactly 128 KB
    expected_sha256 = hashlib.sha256(file_bytes).hexdigest()
    filename = "national_audit_report.bin"

    # Upload using streaming endpoint
    files = {"file": (filename, io.BytesIO(file_bytes), "application/octet-stream")}
    data = {"drive_type": "PERSONAL"}
    r = client.post("/api/v1/files/upload", files=files, data=data, headers=headers)
    assert r.status_code == 201
    file_info = r.json()

    file_id = file_info["id"]
    assert file_info["name"] == filename
    assert file_info["size_bytes"] == len(file_bytes)
    assert file_info["drive_type"] == "PERSONAL"
    assert file_info["ec_created_at"] is not None
    assert "ዓ.ም" in file_info["ec_created_at"]

    # Verify database record
    db_item = db_session.query(FileItem).filter(FileItem.id == uuid.UUID(file_id)).first()
    assert db_item is not None
    assert db_item.current_version is not None
    assert db_item.current_version.checksum_sha256 == expected_sha256
    assert storage_provider.exists(db_item.current_version.storage_path)

    # Download file and assert byte-for-byte fidelity
    r_dl = client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert r_dl.status_code == 200
    assert r_dl.content == file_bytes


# =====================================================================
# Test 2: Content-Addressable Storage (CAS) Deduplication
# =====================================================================

def test_content_addressable_storage_deduplication(db_session):
    """
    Verifies that uploading identical content across different files reuses
    the existing physical disk payload, prevents redundant storage,
    and deleting one file does not destroy the other's disk payload.
    """
    tenant = create_test_tenant_and_users("cas-dedup")
    headers = tenant["admin_headers"]

    identical_content = b"Confidential National Bank Circular - Directive 849/2019"
    expected_sha256 = hashlib.sha256(identical_content).hexdigest()

    # Upload File 1
    files_1 = {"file": ("directive_finance.pdf", io.BytesIO(identical_content), "application/pdf")}
    r1 = client.post("/api/v1/files/upload", files=files_1, data={"drive_type": "COMPANY"}, headers=headers)
    assert r1.status_code == 201
    file1_id = r1.json()["id"]

    # Upload File 2 with identical content but different name in Personal Drive
    files_2 = {"file": ("directive_copy_personal.pdf", io.BytesIO(identical_content), "application/pdf")}
    r2 = client.post("/api/v1/files/upload", files=files_2, data={"drive_type": "PERSONAL"}, headers=headers)
    assert r2.status_code == 201
    file2_id = r2.json()["id"]

    # Verify both FileItem records exist independently
    f1 = db_session.query(FileItem).filter(FileItem.id == uuid.UUID(file1_id)).first()
    f2 = db_session.query(FileItem).filter(FileItem.id == uuid.UUID(file2_id)).first()
    assert f1.id != f2.id
    assert f1.name != f2.name

    # Verify they both share the exact same storage_path
    v1 = f1.current_version
    v2 = f2.current_version
    assert v1.checksum_sha256 == expected_sha256
    assert v2.checksum_sha256 == expected_sha256
    assert v1.storage_path == v2.storage_path
    assert "Deduplicated" in v2.change_summary

    # Purge file 1: ensure payload is NOT deleted because file 2 is still referencing it!
    r_purge1 = client.delete(f"/api/v1/files/{file1_id}/purge", headers=headers)
    assert r_purge1.status_code == 200

    # Verify disk payload is still alive and file 2 downloads successfully
    assert storage_provider.exists(v2.storage_path)
    r_dl2 = client.get(f"/api/v1/files/{file2_id}/download", headers=headers)
    assert r_dl2.status_code == 200
    assert r_dl2.content == identical_content

    # Now purge file 2: disk payload should now be physically deleted
    r_purge2 = client.delete(f"/api/v1/files/{file2_id}/purge", headers=headers)
    assert r_purge2.status_code == 200
    assert not storage_provider.exists(v2.storage_path)


# =====================================================================
# Test 3: Hierarchical Directory Tree and Breadcrumbs
# =====================================================================

def test_hierarchical_directory_tree_and_breadcrumbs(db_session):
    """
    Verifies nested directory creation, calculated subfolder/file counts,
    and multi-level breadcrumbs path resolution from leaf back to root.
    """
    tenant = create_test_tenant_and_users("tree")
    headers = tenant["admin_headers"]

    # 1. Root folder: Legal & Compliance
    r_root = client.post("/api/v1/files/folder", json={"name": "Legal & Compliance", "drive_type": "COMPANY"}, headers=headers)
    assert r_root.status_code == 201
    root_id = r_root.json()["id"]

    # 2. Child folder: Directives
    r_child = client.post("/api/v1/files/folder", json={"name": "Directives", "parent_id": root_id}, headers=headers)
    assert r_child.status_code == 201
    child_id = r_child.json()["id"]

    # 3. Grandchild folder: 2019 Circulars
    r_grandchild = client.post("/api/v1/files/folder", json={"name": "2019 Circulars", "parent_id": child_id}, headers=headers)
    assert r_grandchild.status_code == 201
    grandchild_id = r_grandchild.json()["id"]

    # 4. Upload file into grandchild folder
    content = b"Banking circular NBE/001"
    files = {"file": ("NBE_001.pdf", io.BytesIO(content), "application/pdf")}
    r_file = client.post(
        "/api/v1/files/upload",
        files=files,
        data={"parent_id": grandchild_id, "drive_type": "COMPANY"},
        headers=headers
    )
    assert r_file.status_code == 201
    file_id = r_file.json()["id"]

    # 5. Check breadcrumbs on grandchild folder
    r_crumbs_folder = client.get(f"/api/v1/files/{grandchild_id}/breadcrumbs", headers=headers)
    assert r_crumbs_folder.status_code == 200
    crumbs_folder = r_crumbs_folder.json()
    assert len(crumbs_folder) == 3
    assert crumbs_folder[0]["name"] == "Legal & Compliance"
    assert crumbs_folder[0]["is_folder"] is True
    assert crumbs_folder[1]["name"] == "Directives"
    assert crumbs_folder[1]["is_folder"] is True
    assert crumbs_folder[2]["name"] == "2019 Circulars"
    assert crumbs_folder[2]["is_folder"] is True

    # 6. Check breadcrumbs on file
    r_crumbs_file = client.get(f"/api/v1/files/{file_id}/breadcrumbs", headers=headers)
    assert r_crumbs_file.status_code == 200
    crumbs_file = r_crumbs_file.json()
    assert len(crumbs_file) == 4
    assert crumbs_file[3]["name"] == "NBE_001.pdf"
    assert crumbs_file[3]["is_folder"] is False

    # 7. Check subfolder count on Legal & Compliance
    r_list = client.get("/api/v1/files?drive_type=COMPANY", headers=headers)
    assert r_list.status_code == 200
    root_item = next(f for f in r_list.json() if f["id"] == root_id)
    assert root_item["subfolder_count"] == 1


# =====================================================================
# Test 4: Folder Move Cycle Detection (Anti-Loop)
# =====================================================================

def test_folder_move_cycle_detection(db_session):
    """
    Verifies that moving a folder into itself or any of its descendant children
    is rejected with 400 Bad Request (CYCLE_DETECTED), preserving graph integrity.
    """
    tenant = create_test_tenant_and_users("cycle")
    headers = tenant["admin_headers"]

    # Create Folder A -> Folder B -> Folder C
    r_a = client.post("/api/v1/files/folder", json={"name": "Folder A", "drive_type": "COMPANY"}, headers=headers)
    folder_a_id = r_a.json()["id"]

    r_b = client.post("/api/v1/files/folder", json={"name": "Folder B", "parent_id": folder_a_id}, headers=headers)
    folder_b_id = r_b.json()["id"]

    r_c = client.post("/api/v1/files/folder", json={"name": "Folder C", "parent_id": folder_b_id}, headers=headers)
    folder_c_id = r_c.json()["id"]

    # 1. Attempt to move Folder A into itself -> REJECTED
    r_self = client.patch(f"/api/v1/files/{folder_a_id}/move", json={"new_parent_id": folder_a_id}, headers=headers)
    assert r_self.status_code == 400
    assert r_self.json()["detail"]["code"] == "CYCLE_DETECTED"

    # 2. Attempt to move Folder A into its child Folder B -> REJECTED
    r_child = client.patch(f"/api/v1/files/{folder_a_id}/move", json={"new_parent_id": folder_b_id}, headers=headers)
    assert r_child.status_code == 400
    assert r_child.json()["detail"]["code"] == "CYCLE_DETECTED"

    # 3. Attempt to move Folder A into its grandchild Folder C -> REJECTED
    r_grandchild = client.patch(f"/api/v1/files/{folder_a_id}/move", json={"new_parent_id": folder_c_id}, headers=headers)
    assert r_grandchild.status_code == 400
    assert r_grandchild.json()["detail"]["code"] == "CYCLE_DETECTED"

    # 4. Create independent Folder D, move Folder C into Folder D -> SUCCESS
    r_d = client.post("/api/v1/files/folder", json={"name": "Folder D", "drive_type": "COMPANY"}, headers=headers)
    folder_d_id = r_d.json()["id"]

    r_valid_move = client.patch(f"/api/v1/files/{folder_c_id}/move", json={"new_parent_id": folder_d_id}, headers=headers)
    assert r_valid_move.status_code == 200

    # Verify updated breadcrumbs of Folder C
    r_crumbs = client.get(f"/api/v1/files/{folder_c_id}/breadcrumbs", headers=headers)
    crumbs = r_crumbs.json()
    assert len(crumbs) == 2
    assert crumbs[0]["name"] == "Folder D"
    assert crumbs[1]["name"] == "Folder C"


# =====================================================================
# Test 5: File Rename and Duplicate Name Prevention
# =====================================================================

def test_file_rename_and_duplicate_prevention(db_session):
    """
    Verifies renaming files and folders, and blocks duplicate names within the same directory.
    """
    tenant = create_test_tenant_and_users("rename")
    headers = tenant["admin_headers"]

    # Create two folders in Company drive root
    r1 = client.post("/api/v1/files/folder", json={"name": "Human Resources", "drive_type": "COMPANY"}, headers=headers)
    assert r1.status_code == 201
    hr_id = r1.json()["id"]

    r2 = client.post("/api/v1/files/folder", json={"name": "Finance", "drive_type": "COMPANY"}, headers=headers)
    assert r2.status_code == 201

    # 1. Rename "Human Resources" to "People & Culture" -> SUCCESS
    r_rename = client.patch(f"/api/v1/files/{hr_id}/rename", json={"name": "People & Culture"}, headers=headers)
    assert r_rename.status_code == 200
    assert r_rename.json()["name"] == "People & Culture"

    # 2. Attempt to rename to "Finance" (duplicate under root) -> 409 CONFLICT
    r_conflict = client.patch(f"/api/v1/files/{hr_id}/rename", json={"name": "Finance"}, headers=headers)
    assert r_conflict.status_code == 409


# =====================================================================
# Test 6: Personal Drive vs Company Drive Partitioning
# =====================================================================

def test_personal_vs_company_drive_isolation(db_session):
    """
    Verifies that Personal Drive files are isolated per user (Staff B cannot see or download Staff A's personal files),
    while Company Drive files are visible across the organization.
    """
    tenant = create_test_tenant_and_users("drive-iso")
    admin_headers = tenant["admin_headers"]
    staff_headers = tenant["staff_headers"]

    # 1. Staff user uploads a secret file to Personal Drive
    secret_bytes = b"Staff Member Private Payslip"
    files = {"file": ("payslip_private.pdf", io.BytesIO(secret_bytes), "application/pdf")}
    r_upload = client.post(
        "/api/v1/files/upload",
        files=files,
        data={"drive_type": "PERSONAL"},
        headers=staff_headers,
    )
    assert r_upload.status_code == 201
    secret_file_id = r_upload.json()["id"]

    # 2. Admin lists Personal Drive: Admin sees only their own personal drive files, not Staff's
    r_admin_personal = client.get("/api/v1/files?drive_type=PERSONAL", headers=admin_headers)
    assert r_admin_personal.status_code == 200
    assert all(f["id"] != secret_file_id for f in r_admin_personal.json())

    # 3. Staff user lists Personal Drive: sees their file
    r_staff_personal = client.get("/api/v1/files?drive_type=PERSONAL", headers=staff_headers)
    assert r_staff_personal.status_code == 200
    assert any(f["id"] == secret_file_id for f in r_staff_personal.json())

    # 4. Upload file to Company Drive by Admin
    company_bytes = b"All-Staff Holiday Notice 2026"
    files_co = {"file": ("holiday_notice.pdf", io.BytesIO(company_bytes), "application/pdf")}
    r_co = client.post(
        "/api/v1/files/upload",
        files=files_co,
        data={"drive_type": "COMPANY"},
        headers=admin_headers,
    )
    assert r_co.status_code == 201
    co_file_id = r_co.json()["id"]

    # 5. Staff user lists Company Drive: sees the company notice
    r_staff_co = client.get("/api/v1/files?drive_type=COMPANY", headers=staff_headers)
    assert r_staff_co.status_code == 200
    assert any(f["id"] == co_file_id for f in r_staff_co.json())

    # 6. Staff downloads Company file -> 200 OK
    r_dl_co = client.get(f"/api/v1/files/{co_file_id}/download", headers=staff_headers)
    assert r_dl_co.status_code == 200
    assert r_dl_co.content == company_bytes


# =====================================================================
# Test 7: Cascading Soft-Delete and Cascading Restore
# =====================================================================

def test_cascading_soft_delete_and_restore(db_session):
    """
    Verifies that moving a folder to the Recycle Bin recursively soft-deletes
    all descendant subfolders and files, and restoring restores the whole tree.
    """
    tenant = create_test_tenant_and_users("cascade")
    headers = tenant["admin_headers"]

    # Create Folder Tree: Project Alpha -> Specs -> [spec1.txt, spec2.txt]
    r_root = client.post("/api/v1/files/folder", json={"name": "Project Alpha", "drive_type": "COMPANY"}, headers=headers)
    root_id = r_root.json()["id"]

    r_sub = client.post("/api/v1/files/folder", json={"name": "Specs", "parent_id": root_id}, headers=headers)
    sub_id = r_sub.json()["id"]

    file1 = {"file": ("spec1.txt", io.BytesIO(b"Specification Part 1"), "text/plain")}
    r_f1 = client.post("/api/v1/files/upload", files=file1, data={"parent_id": sub_id, "drive_type": "COMPANY"}, headers=headers)
    f1_id = r_f1.json()["id"]

    file2 = {"file": ("spec2.txt", io.BytesIO(b"Specification Part 2"), "text/plain")}
    r_f2 = client.post("/api/v1/files/upload", files=file2, data={"parent_id": sub_id, "drive_type": "COMPANY"}, headers=headers)
    f2_id = r_f2.json()["id"]

    # 1. Soft-delete root folder "Project Alpha"
    r_del = client.delete(f"/api/v1/files/{root_id}", headers=headers)
    assert r_del.status_code == 200
    assert r_del.json()["affected_count"] == 4  # Root + Sub + 2 Files

    # 2. Verify all 4 items are marked is_deleted in DB
    items = db_session.query(FileItem).filter(
        FileItem.id.in_([uuid.UUID(root_id), uuid.UUID(sub_id), uuid.UUID(f1_id), uuid.UUID(f2_id)])
    ).all()
    assert len(items) == 4
    assert all(i.is_deleted is True for i in items)

    # 3. Verify normal Company drive list does NOT include "Project Alpha"
    r_list = client.get("/api/v1/files?drive_type=COMPANY", headers=headers)
    assert all(f["id"] != root_id for f in r_list.json())

    # 4. Verify TRASH drive includes the items
    r_trash = client.get("/api/v1/files?drive_type=TRASH", headers=headers)
    assert r_trash.status_code == 200
    assert any(f["id"] == root_id for f in r_trash.json())

    # 5. Cascading Restore
    r_restore = client.post(f"/api/v1/files/{root_id}/restore", headers=headers)
    assert r_restore.status_code == 200
    assert r_restore.json()["restored_count"] == 4

    # 6. Verify all items are active again
    db_session.expire_all()
    items_restored = db_session.query(FileItem).filter(
        FileItem.id.in_([uuid.UUID(root_id), uuid.UUID(sub_id), uuid.UUID(f1_id), uuid.UUID(f2_id)])
    ).all()
    assert all(i.is_deleted is False for i in items_restored)


# =====================================================================
# Test 8: Permanent Purge and Storage Quota Reclamation
# =====================================================================

def test_permanent_purge_quota_reclamation(db_session):
    """
    Verifies that permanently purging a file:
    1. Unlinks the physical payload from disk.
    2. Decrements used_storage_bytes from the Organization record.
    """
    tenant = create_test_tenant_and_users("quota-reclaim")
    headers = tenant["admin_headers"]
    slug = tenant["slug"]

    org = db_session.query(Organization).filter(Organization.slug == slug).first()
    initial_used = org.used_storage_bytes

    # Upload 50,000 bytes
    payload = b"X" * 50000
    files = {"file": ("large_quota_test.bin", io.BytesIO(payload), "application/octet-stream")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=headers)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]

    db_session.refresh(org)
    assert org.used_storage_bytes == initial_used + 50000

    # Purge item permanently
    r_purge = client.delete(f"/api/v1/files/{file_id}/purge", headers=headers)
    assert r_purge.status_code == 200
    assert r_purge.json()["freed_bytes"] == 50000

    # Verify quota reclaimed in database
    db_session.refresh(org)
    assert org.used_storage_bytes == initial_used

    # Verify item no longer exists in database
    deleted_item = db_session.query(FileItem).filter(FileItem.id == uuid.UUID(file_id)).first()
    assert deleted_item is None


# =====================================================================
# Test 9: Storage Write Lockdown Enforcement (Expired License)
# =====================================================================

def test_storage_write_lockdown_enforcement(db_session):
    """
    Verifies that when a tenant's license enters expired write lockdown mode:
    1. Uploads, folder creations, renames, moves, and deletions are rejected with 403.
    2. File listing and file downloads continue to work seamlessly in Read-Only mode.
    """
    tenant = create_test_tenant_and_users("lockdown-storage")
    headers = tenant["admin_headers"]
    slug = tenant["slug"]

    # First, create a valid folder and upload a file while license is active
    r_f = client.post("/api/v1/files/folder", json={"name": "Active Docs", "drive_type": "PERSONAL"}, headers=headers)
    assert r_f.status_code == 201
    folder_id = r_f.json()["id"]

    content = b"Contract signed before expiry"
    files = {"file": ("active_contract.pdf", io.BytesIO(content), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"parent_id": folder_id, "drive_type": "PERSONAL"}, headers=headers)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]

    # Now backdate tenant license past grace period
    org = db_session.query(Organization).filter(Organization.slug == slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.expires_at = datetime.now(timezone.utc) - timedelta(days=20)
    lic.grace_period_days = 7
    db_session.commit()

    # 1. Attempt folder creation -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_folder = client.post("/api/v1/files/folder", json={"name": "Blocked Folder", "drive_type": "PERSONAL"}, headers=headers)
    assert r_blocked_folder.status_code == 403
    assert r_blocked_folder.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 2. Attempt file upload -> 403 LICENSE_LOCKDOWN_READ_ONLY
    files_new = {"file": ("blocked_doc.pdf", io.BytesIO(b"Blocked upload"), "application/pdf")}
    r_blocked_up = client.post("/api/v1/files/upload", files=files_new, data={"drive_type": "PERSONAL"}, headers=headers)
    assert r_blocked_up.status_code == 403
    assert r_blocked_up.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 3. Attempt folder rename -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_rename = client.patch(f"/api/v1/files/{folder_id}/rename", json={"name": "New Name"}, headers=headers)
    assert r_blocked_rename.status_code == 403
    assert r_blocked_rename.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 4. Attempt folder move -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_move = client.patch(f"/api/v1/files/{folder_id}/move", json={"new_parent_id": None}, headers=headers)
    assert r_blocked_move.status_code == 403
    assert r_blocked_move.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 5. Attempt delete -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_del = client.delete(f"/api/v1/files/{file_id}", headers=headers)
    assert r_blocked_del.status_code == 403
    assert r_blocked_del.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 6. Read-Only access: Listing files and downloading existing documents still SUCCEEDS
    r_list = client.get("/api/v1/files?drive_type=PERSONAL", headers=headers)
    assert r_list.status_code == 200

    r_download = client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert r_download.status_code == 200
    assert r_download.content == content
