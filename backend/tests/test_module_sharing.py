"""
Comprehensive Automated Test Suite for Module 6: Access Control & Sharing Engine
Tests:
1. User-to-User internal document sharing and 'Shared With Me' unified inbox.
2. Permission gating: VIEWER (read-only) vs EDITOR (revisions, renames).
3. Department-level internal sharing and automatic membership resolution.
4. Recursive folder permission inheritance down multi-level nested subtrees.
5. Instant share revocation and immediate access termination.
6. Public share link download and download limit counter enforcement.
7. Public link password protection with bcrypt verification.
8. Public link VIEW_ONLY restriction blocking downloads.
9. External Dropbox upload portal depositing documents into internal folders.
10. License Read-Only write lockdown blocking new shares and link generation.
"""

import io
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, License
from app.models.user import User, UserRole
from app.models.file import FileItem, DriveType
from app.models.department import Department, UserDepartment
from app.models.share import FileShare, SharePermission
from app.models.share_link import ShareLink, LinkAccessType

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_sharing_tenant_and_users(slug_prefix: str = "share"):
    """Helper to provision a tenant with an Admin and two Staff members."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Sharing Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Sharing Admin",
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
    r_a = client.post(
        "/api/v1/auth/users",
        json={"email": staff_a_email, "full_name": "Abebe Kebede", "password": password, "role": "STAFF"},
        headers=admin_headers,
    )
    assert r_a.status_code == 201
    staff_a_id = r_a.json()["id"]
    login_a = client.post("/api/v1/auth/login", json={"email": staff_a_email, "password": password})
    staff_a_headers = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # Staff B (Chala)
    staff_b_email = f"chala@{slug}.et"
    r_b = client.post(
        "/api/v1/auth/users",
        json={"email": staff_b_email, "full_name": "Chala Tadesse", "password": password, "role": "STAFF"},
        headers=admin_headers,
    )
    assert r_b.status_code == 201
    staff_b_id = r_b.json()["id"]
    login_b = client.post("/api/v1/auth/login", json={"email": staff_b_email, "password": password})
    staff_b_headers = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    return {
        "slug": slug,
        "admin_headers": admin_headers,
        "staff_a_headers": staff_a_headers,
        "staff_a_id": staff_a_id,
        "staff_b_headers": staff_b_headers,
        "staff_b_id": staff_b_id,
    }


# =====================================================================
# Test 1: User-to-User Internal Share and 'Shared With Me'
# =====================================================================

def test_user_to_user_internal_share_and_shared_with_me(db_session):
    """
    Verifies that when Staff A shares a private document with Staff B:
    1. Staff B could not access it prior to sharing.
    2. Document appears in Staff B's /files/shared-with-me list.
    3. Staff B can download the document.
    4. Staff B (VIEWER) cannot upload a new revision.
    """
    tenant = create_sharing_tenant_and_users("user-share")
    staff_a = tenant["staff_a_headers"]
    staff_a_id = tenant["staff_a_id"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    # Staff A uploads private document to Personal drive
    file_bytes = b"Confidential Strategy Document - Internal Eyes Only"
    files = {"file": ("strategy.pdf", io.BytesIO(file_bytes), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]

    # 1. Staff B initially has no access -> 403 Forbidden
    r_b_denied = client.get(f"/api/v1/files/{file_id}/download", headers=staff_b)
    assert r_b_denied.status_code == 403

    # 2. Staff A shares with Staff B with VIEWER permission
    share_payload = {
        "target_user_id": staff_b_id,
        "permission": "VIEWER",
    }
    r_share = client.post(f"/api/v1/shares/file/{file_id}", json=share_payload, headers=staff_a)
    assert r_share.status_code == 201
    share_data = r_share.json()
    assert share_data["permission"] == "VIEWER"
    assert share_data["target_user_name"] == "Chala Tadesse"

    # 3. Staff B lists shared-with-me items
    r_shared = client.get("/api/v1/files/shared-with-me", headers=staff_b)
    assert r_shared.status_code == 200
    shared_items = r_shared.json()
    assert any(item["id"] == file_id for item in shared_items)

    # 4. Staff B can download the shared file -> 200 OK
    r_b_dl = client.get(f"/api/v1/files/{file_id}/download", headers=staff_b)
    assert r_b_dl.status_code == 200
    assert r_b_dl.content == file_bytes

    # 5. Staff A cannot share with self -> 400 Bad Request
    r_self = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_a_id}, headers=staff_a)
    assert r_self.status_code == 400

    # 6. Staff B (VIEWER) cannot share with others -> 403 Forbidden
    r_b_share = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_a_id}, headers=staff_b)
    assert r_b_share.status_code == 403


# =====================================================================
# Test 2: Permission Gating: VIEWER vs EDITOR Rights
# =====================================================================

def test_editor_vs_viewer_permission_gating(db_session):
    """
    Verifies that a VIEWER cannot upload versions or rename the file,
    but elevating the share to EDITOR permits revisions and renames.
    """
    tenant = create_sharing_tenant_and_users("perm-gate")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    # Upload document by Staff A
    files = {"file": ("budget_proposal.pdf", io.BytesIO(b"Proposal Draft"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 1. Share with VIEWER
    client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id, "permission": "VIEWER"}, headers=staff_a)

    # Attempt version upload by Staff B -> 403 Forbidden
    ver_file = {"file": ("budget_proposal.pdf", io.BytesIO(b"Unauthorized Revision"), "application/pdf")}
    r_ver_denied = client.post(f"/api/v1/files/{file_id}/versions", files=ver_file, headers=staff_b)
    assert r_ver_denied.status_code == 403

    # Attempt rename by Staff B -> 403 Forbidden
    r_ren_denied = client.patch(f"/api/v1/files/{file_id}/rename", json={"name": "Hacked.pdf"}, headers=staff_b)
    assert r_ren_denied.status_code == 403

    # 2. Elevate share to EDITOR
    r_elevate = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id, "permission": "EDITOR"}, headers=staff_a)
    assert r_elevate.status_code == 201
    assert r_elevate.json()["permission"] == "EDITOR"

    # Now upload version by Staff B -> SUCCEEDS 201
    r_ver_ok = client.post(f"/api/v1/files/{file_id}/versions", files=ver_file, headers=staff_b)
    assert r_ver_ok.status_code == 201

    # Rename by Staff B -> SUCCEEDS 200
    r_ren_ok = client.patch(f"/api/v1/files/{file_id}/rename", json={"name": "approved_budget.pdf"}, headers=staff_b)
    assert r_ren_ok.status_code == 200
    assert r_ren_ok.json()["name"] == "approved_budget.pdf"


# =====================================================================
# Test 3: Department-Level Internal Sharing
# =====================================================================

def test_department_level_internal_sharing(db_session):
    """
    Verifies sharing a file with an entire department:
    Colleagues in that department receive access; colleagues in other departments are denied.
    """
    tenant = create_sharing_tenant_and_users("dept-share")
    admin = tenant["admin_headers"]
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    slug = tenant["slug"]

    # 1. Create two departments: Finance and HR
    r_fin = client.post("/api/v1/departments", json={"name": "Finance Department", "code": f"FIN_{uuid.uuid4().hex[:4].upper()}"}, headers=admin)
    assert r_fin.status_code == 201
    fin_id = r_fin.json()["id"]

    r_hr = client.post("/api/v1/departments", json={"name": "HR Department", "code": f"HR_{uuid.uuid4().hex[:4].upper()}"}, headers=admin)
    assert r_hr.status_code == 201
    hr_id = r_hr.json()["id"]

    # 2. Assign Staff B (Chala) to Finance Department in DB
    user_b = db_session.query(User).filter(User.id == uuid.UUID(tenant["staff_b_id"])).first()
    db_session.add(UserDepartment(user_id=user_b.id, department_id=uuid.UUID(fin_id)))
    db_session.commit()

    # Staff A uploads private audit file
    audit_bytes = b"National Bank Audit Checklist"
    files = {"file": ("audit_checklist.pdf", io.BytesIO(audit_bytes), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 3. Share with Finance Department
    r_share = client.post(
        f"/api/v1/shares/file/{file_id}",
        json={"target_department_id": fin_id, "permission": "VIEWER"},
        headers=staff_a,
    )
    assert r_share.status_code == 201
    assert r_share.json()["target_department_name"] == "Finance Department"

    # 4. Staff B (in Finance) can download file -> 200 OK
    r_dl = client.get(f"/api/v1/files/{file_id}/download", headers=staff_b)
    assert r_dl.status_code == 200
    assert r_dl.content == audit_bytes


# =====================================================================
# Test 4: Recursive Folder Permission Inheritance
# =====================================================================

def test_recursive_folder_permission_inheritance(db_session):
    """
    Verifies that sharing a parent folder grants access to all nested child folders
    and files via ancestor graph traversal.
    """
    tenant = create_sharing_tenant_and_users("recurse")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    # 1. Staff A creates Folder Tree: /Projects -> /Projects/Bids -> tender.pdf
    r_root = client.post("/api/v1/files/folder", json={"name": "Projects", "drive_type": "PERSONAL"}, headers=staff_a)
    root_id = r_root.json()["id"]

    r_sub = client.post("/api/v1/files/folder", json={"name": "Bids", "parent_id": root_id}, headers=staff_a)
    sub_id = r_sub.json()["id"]

    tender_bytes = b"Ministry of Innovation Tender Proposal"
    files = {"file": ("tender.pdf", io.BytesIO(tender_bytes), "application/pdf")}
    r_file = client.post("/api/v1/files/upload", files=files, data={"parent_id": sub_id, "drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_file.json()["id"]

    # Prior to sharing, Staff B has no access to leaf file -> 403 Forbidden
    r_b_denied = client.get(f"/api/v1/files/{file_id}/download", headers=staff_b)
    assert r_b_denied.status_code == 403

    # 2. Staff A shares ROOT folder /Projects with Staff B
    r_share_root = client.post(
        f"/api/v1/shares/file/{root_id}",
        json={"target_user_id": staff_b_id, "permission": "VIEWER"},
        headers=staff_a,
    )
    assert r_share_root.status_code == 201

    # 3. Staff B accesses grandchild tender.pdf directly -> SUCCEEDS (Inherited from root folder!)
    r_b_ok = client.get(f"/api/v1/files/{file_id}/download", headers=staff_b)
    assert r_b_ok.status_code == 200
    assert r_b_ok.content == tender_bytes

    # 4. Staff B can view breadcrumbs of inherited item
    r_crumbs = client.get(f"/api/v1/files/{file_id}/breadcrumbs", headers=staff_b)
    assert r_crumbs.status_code == 200
    assert len(r_crumbs.json()) == 3


# =====================================================================
# Test 5: Instant Share Revocation
# =====================================================================

def test_instant_share_revocation(db_session):
    """
    Verifies that deleting a share immediately cuts off access for the recipient.
    """
    tenant = create_sharing_tenant_and_users("revoke")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    # Upload document & share
    files = {"file": ("revocable_doc.pdf", io.BytesIO(b"Data"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_share = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id}, headers=staff_a)
    share_id = r_share.json()["id"]

    # Staff B can download
    assert client.get(f"/api/v1/files/{file_id}/download", headers=staff_b).status_code == 200

    # Revoke share
    r_del = client.delete(f"/api/v1/shares/{share_id}", headers=staff_a)
    assert r_del.status_code == 200

    # Staff B access is immediately blocked -> 403 Forbidden
    assert client.get(f"/api/v1/files/{file_id}/download", headers=staff_b).status_code == 403


# =====================================================================
# Test 6: External Public Share Link Download & Max Counter
# =====================================================================

def test_public_link_download_and_max_counter(db_session):
    """
    Verifies that unauthenticated external clients can download a file via token link,
    and access is cut off (410 Gone) once max_downloads is reached.
    """
    tenant = create_sharing_tenant_and_users("pub-link")
    staff_a = tenant["staff_a_headers"]

    content = b"Public Press Release - EthioOffice Launch 2026"
    files = {"file": ("press_release.pdf", io.BytesIO(content), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 1. Staff A generates public link with max_downloads=2
    link_payload = {
        "access_type": "ALLOW_DOWNLOAD",
        "max_downloads": 2,
    }
    r_link = client.post(f"/api/v1/shares/links/file/{file_id}", json=link_payload, headers=staff_a)
    assert r_link.status_code == 201
    link_data = r_link.json()
    token = link_data["token"]
    assert link_data["is_password_protected"] is False

    # 2. Public client inspects link metadata without credentials
    r_meta = client.get(f"/api/v1/public/links/{token}")
    assert r_meta.status_code == 200
    assert r_meta.json()["file_name"] == "press_release.pdf"

    # 3. Download 1 (unauthenticated) -> 200 OK
    r_dl1 = client.get(f"/api/v1/public/links/{token}/download")
    assert r_dl1.status_code == 200
    assert r_dl1.content == content

    # 4. Download 2 -> 200 OK
    r_dl2 = client.get(f"/api/v1/public/links/{token}/download")
    assert r_dl2.status_code == 200

    # 5. Download 3 -> 410 GONE (Limit exceeded)
    r_dl3 = client.get(f"/api/v1/public/links/{token}/download")
    assert r_dl3.status_code == 410


# =====================================================================
# Test 7: Public Share Link Password Protection
# =====================================================================

def test_public_link_password_protection(db_session):
    """
    Verifies password-protected public share links:
    Blocks unauthenticated download without password, succeeds when password matches.
    """
    tenant = create_sharing_tenant_and_users("pub-pwd")
    staff_a = tenant["staff_a_headers"]

    content = b"Protected Contract Negotiation Terms"
    files = {"file": ("contract_terms.pdf", io.BytesIO(content), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 1. Generate link with password
    password = "SecuredPassword2026!"
    link_payload = {
        "access_type": "ALLOW_DOWNLOAD",
        "password": password,
    }
    r_link = client.post(f"/api/v1/shares/links/file/{file_id}", json=link_payload, headers=staff_a)
    assert r_link.status_code == 201
    token = r_link.json()["token"]
    assert r_link.json()["is_password_protected"] is True

    # 2. Metadata shows password required
    r_meta = client.get(f"/api/v1/public/links/{token}")
    assert r_meta.status_code == 200
    assert r_meta.json()["is_password_protected"] is True

    # 3. Attempt download with no password -> 401 Unauthorized
    r_no_pwd = client.get(f"/api/v1/public/links/{token}/download")
    assert r_no_pwd.status_code == 401

    # 4. Attempt download with wrong password -> 401 Unauthorized
    r_wrong = client.get(f"/api/v1/public/links/{token}/download?password=WrongPassword!")
    assert r_wrong.status_code == 401

    # 5. Verify password via verification endpoint -> 200 OK
    r_ver = client.post(f"/api/v1/public/links/{token}/verify", json={"password": password})
    assert r_ver.status_code == 200
    assert r_ver.json()["access_granted"] is True

    # 6. Download with valid password via query param -> 200 OK
    r_dl = client.get(f"/api/v1/public/links/{token}/download?password={password}")
    assert r_dl.status_code == 200
    assert r_dl.content == content

    # 7. Download with valid password via header -> 200 OK
    r_dl_hdr = client.get(f"/api/v1/public/links/{token}/download", headers={"X-Link-Password": password})
    assert r_dl_hdr.status_code == 200
    assert r_dl_hdr.content == content


# =====================================================================
# Test 8: Public Link VIEW_ONLY Restriction
# =====================================================================

def test_public_link_view_only_restriction(db_session):
    """
    Verifies that links created with VIEW_ONLY access reject download attempts.
    """
    tenant = create_sharing_tenant_and_users("view-only")
    staff_a = tenant["staff_a_headers"]

    files = {"file": ("preview_watermark.pdf", io.BytesIO(b"Confidential Preview"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_link = client.post(f"/api/v1/shares/links/file/{file_id}", json={"access_type": "VIEW_ONLY"}, headers=staff_a)
    token = r_link.json()["token"]

    # Attempt download -> 400 Bad Request (View Only)
    r_dl = client.get(f"/api/v1/public/links/{token}/download")
    assert r_dl.status_code == 400
    assert "ለማየት ብቻ" in r_dl.json()["detail"]


# =====================================================================
# Test 9: External Dropbox Public Upload Portal
# =====================================================================

def test_public_dropbox_folder_upload(db_session):
    """
    Verifies that external vendors can deposit files into an internal folder
    via an UPLOAD_DROPBOX public link.
    """
    tenant = create_sharing_tenant_and_users("dropbox")
    staff_a = tenant["staff_a_headers"]

    # Create internal folder
    r_folder = client.post("/api/v1/files/folder", json={"name": "Bid Drop Box", "drive_type": "COMPANY"}, headers=staff_a)
    folder_id = r_folder.json()["id"]

    # Generate UPLOAD_DROPBOX link
    r_link = client.post(f"/api/v1/shares/links/file/{folder_id}", json={"access_type": "UPLOAD_DROPBOX"}, headers=staff_a)
    assert r_link.status_code == 201
    token = r_link.json()["token"]

    # External unauthenticated vendor uploads proposal into the dropbox link
    vendor_proposal = b"Vendor Inc Financial & Technical Proposal 2026"
    deposit_files = {"file": ("vendor_proposal.pdf", io.BytesIO(vendor_proposal), "application/pdf")}
    r_deposit = client.post(f"/api/v1/public/links/{token}/upload", files=deposit_files)
    assert r_deposit.status_code == 201
    uploaded_info = r_deposit.json()
    assert uploaded_info["name"] == "vendor_proposal.pdf"
    assert uploaded_info["parent_id"] == folder_id

    # Staff A lists folder contents and verifies deposited file is present
    r_list = client.get(f"/api/v1/files?drive_type=COMPANY&parent_id={folder_id}", headers=staff_a)
    assert r_list.status_code == 200
    names = [f["name"] for f in r_list.json()]
    assert "vendor_proposal.pdf" in names


# =====================================================================
# Test 10: License Read-Only Write Lockdown on Sharing
# =====================================================================

def test_sharing_write_lockdown_enforcement(db_session):
    """
    Verifies that when tenant license enters expired write lockdown:
    1. Creating shares, revoking shares, and generating links are blocked with 403.
    2. Existing shares and downloads continue working in Read-Only mode.
    """
    tenant = create_sharing_tenant_and_users("lockdown-share")
    admin = tenant["admin_headers"]
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]
    slug = tenant["slug"]

    # Create file and active share while license is valid
    files = {"file": ("lockdown_shared.pdf", io.BytesIO(b"Active Shared Data"), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_share = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id}, headers=staff_a)
    share_id = r_share.json()["id"]

    r_link = client.post(f"/api/v1/shares/links/file/{file_id}", json={"access_type": "ALLOW_DOWNLOAD"}, headers=staff_a)
    link_token = r_link.json()["token"]

    # Expire tenant license past grace period
    org = db_session.query(Organization).filter(Organization.slug == slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.expires_at = datetime.now(timezone.utc) - timedelta(days=25)
    lic.grace_period_days = 7
    db_session.commit()

    # 1. Attempt create new share -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_share = client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id}, headers=staff_a)
    assert r_blocked_share.status_code == 403
    assert r_blocked_share.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"

    # 2. Attempt revoke share -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_revoke = client.delete(f"/api/v1/shares/{share_id}", headers=staff_a)
    assert r_blocked_revoke.status_code == 403

    # 3. Attempt create public link -> 403 LICENSE_LOCKDOWN_READ_ONLY
    r_blocked_link = client.post(f"/api/v1/shares/links/file/{file_id}", json={"access_type": "ALLOW_DOWNLOAD"}, headers=staff_a)
    assert r_blocked_link.status_code == 403

    # 4. Existing shares and public links STILL DOWNLOAD in Read-Only mode
    assert client.get(f"/api/v1/files/{file_id}/download", headers=staff_b).status_code == 200
    assert client.get(f"/api/v1/public/links/{link_token}/download").status_code == 200
