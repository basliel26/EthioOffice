"""
Comprehensive Automated Test Suite for Module 7: Euro-Office / ONLYOFFICE Collaborative Co-Authoring Connector
Tests:
1. Document configuration generation and HMAC-SHA256 JWT signature verification.
2. Unsupported non-office document type rejection.
3. Access control gating: VIEWER mode ("view") vs EDITOR mode ("edit").
4. Concurrency lock gating: Active checkout lock by colleague forces "view" mode.
5. Internal download streaming with signed token, RFC 5987 headers, and tamper rejection.
6. Callback Status 1: Active co-author presence tracking and live session roster.
7. Callback Status 6: Force-Save (Ctrl+S / AutoSave) intermediate revision commit while keeping session open.
8. Callback Status 2: Final save committing Version N+1 with CAS and session closing.
9. Callback Status 4: Closed without changes cleaning up session with zero version churn.
10. Callback HMAC-SHA256 signature verification and tamper rejection.
11. Enterprise License write lockdown blocking callbacks on expired/suspended tenants.
"""

import io
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.organization import Organization, License
from app.models.user import User
from app.models.file import FileItem, FileVersion
from app.models.eurooffice import EuroOfficeSession
from app.models.share import FileShare, SharePermission
from app.services.euro_office_service import EuroOfficeService

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_euro_tenant_and_users(slug_prefix: str = "euro"):
    """Helper to provision a tenant with an Admin and two Staff colleagues."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Euro Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Euro Admin",
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
# Test 1: Document Config Generation and HMAC-SHA256 JWT Signature
# =====================================================================

def test_document_config_generation_and_jwt_signature(db_session):
    """
    Verifies that requesting Euro-Office config generates a compliant ONLYOFFICE
    document configuration payload signed with the shared HMAC-SHA256 secret.
    """
    tenant = create_euro_tenant_and_users("config-sign")
    staff_a = tenant["staff_a_headers"]

    # Upload Word document (.docx)
    file_bytes = b"Initial Word Document Content for Euro-Office"
    files = {"file": ("National_Strategy_2026.docx", io.BytesIO(file_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]

    # Request Euro-Office Config
    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}?lang=en", headers=staff_a)
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()

    assert cfg["documentType"] == "word"
    assert cfg["document"]["fileType"] == "docx"
    assert cfg["document"]["title"] == "National_Strategy_2026.docx"
    assert cfg["editorConfig"]["mode"] == "edit"
    assert cfg["editorConfig"]["lang"] == "en"
    assert cfg["document"]["permissions"]["edit"] is True
    assert cfg["document"]["permissions"]["download"] is True
    assert "download" in cfg["document"]["url"]
    assert "callback" in cfg["editorConfig"]["callbackUrl"]

    # Verify HMAC-SHA256 Token
    token = cfg["token"]
    decoded = jwt.decode(token, settings.EURO_OFFICE_JWT_SECRET, algorithms=["HS256"])
    assert decoded["documentType"] == "word"
    assert decoded["document"]["title"] == "National_Strategy_2026.docx"
    assert decoded["editorConfig"]["mode"] == "edit"

    # Verify EuroOfficeSession created in DB
    session = db_session.query(EuroOfficeSession).filter(EuroOfficeSession.file_id == uuid.UUID(file_id)).first()
    assert session is not None
    assert session.document_key == cfg["document"]["key"]


# =====================================================================
# Test 2: Unsupported Document Type Rejection
# =====================================================================

def test_unsupported_document_type_rejection(db_session):
    """
    Verifies that attempting to open unsupported non-office files (e.g. .zip, .png)
    in Euro-Office is rejected with 400 Bad Request.
    """
    tenant = create_euro_tenant_and_users("unsup-type")
    staff_a = tenant["staff_a_headers"]

    # Upload ZIP archive
    zip_bytes = b"PK\x03\x04MockZipFileContent"
    files = {"file": ("backup_archive.zip", io.BytesIO(zip_bytes), "application/zip")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]

    # Attempt to request Euro-Office config -> 400 Bad Request
    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    assert r_cfg.status_code == 400
    assert r_cfg.json()["detail"]["code"] == "UNSUPPORTED_DOCUMENT_TYPE"


# =====================================================================
# Test 3: Access Control Gating: VIEWER vs EDITOR Mode
# =====================================================================

def test_view_only_vs_editor_mode_gating(db_session):
    """
    Verifies that a user with VIEWER permission receives mode='view' (read-only),
    and elevating the user to EDITOR switches mode to 'edit'.
    """
    tenant = create_euro_tenant_and_users("acl-gate")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    # Upload Excel Spreadsheet (.xlsx)
    xlsx_bytes = b"Spreadsheet Payroll Data"
    files = {"file": ("Financial_Audit.xlsx", io.BytesIO(xlsx_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # 1. Share with VIEWER
    client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id, "permission": "VIEWER"}, headers=staff_a)

    # Staff B requests config -> mode="view", edit=False
    r_b_view = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_b)
    assert r_b_view.status_code == 200
    cfg_b = r_b_view.json()
    assert cfg_b["documentType"] == "cell"
    assert cfg_b["editorConfig"]["mode"] == "view"
    assert cfg_b["document"]["permissions"]["edit"] is False
    assert cfg_b["document"]["permissions"]["review"] is False

    # 2. Elevate to EDITOR
    client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id, "permission": "EDITOR"}, headers=staff_a)

    # Staff B requests config again -> mode="edit", edit=True
    r_b_edit = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_b)
    assert r_b_edit.status_code == 200
    cfg_b_edit = r_b_edit.json()
    assert cfg_b_edit["editorConfig"]["mode"] == "edit"
    assert cfg_b_edit["document"]["permissions"]["edit"] is True
    assert cfg_b_edit["document"]["permissions"]["review"] is True


# =====================================================================
# Test 4: Concurrency Lock Gating: Active Lock Forces "view" Mode
# =====================================================================

def test_file_lock_forces_view_mode_for_others(db_session):
    """
    Verifies that when Staff A holds an exclusive checkout lock on a company document,
    Staff B receives mode='view' even though Staff B normally has editor rights.
    """
    tenant = create_euro_tenant_and_users("lock-force-view")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]

    # Upload presentation (.pptx) to COMPANY drive
    ppt_bytes = b"Quarterly Review Slides"
    files = {"file": ("Company_AllHands.pptx", io.BytesIO(ppt_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # Staff A acquires exclusive lock
    client.post(f"/api/v1/files/{file_id}/lock", json={"reason": "Working on presentation"}, headers=staff_a)

    # Staff B requests config -> Forced to mode="view" because file is locked by Staff A
    r_b_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_b)
    assert r_b_cfg.status_code == 200
    assert r_b_cfg.json()["editorConfig"]["mode"] == "view"
    assert r_b_cfg.json()["document"]["permissions"]["edit"] is False

    # Staff A (the lock owner) requests config -> Allowed mode="edit"
    r_a_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    assert r_a_cfg.status_code == 200
    assert r_a_cfg.json()["editorConfig"]["mode"] == "edit"
    assert r_a_cfg.json()["document"]["permissions"]["edit"] is True


# =====================================================================
# Test 5: Internal Download Streaming with Signed Token
# =====================================================================

def test_euro_office_internal_download_with_signed_token(db_session):
    """
    Verifies that the Document Server can stream the document payload using
    the short-lived download token, and tampering is rejected.
    """
    tenant = create_euro_tenant_and_users("dl-token")
    staff_a = tenant["staff_a_headers"]

    raw_doc = b"Document Payload Stream for ONLYOFFICE DocumentServer"
    files = {"file": ("የኢትዮጵያ_የስራ_መመሪያ.docx", io.BytesIO(raw_doc), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # Get config to obtain signed download token
    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    dl_url = r_cfg.json()["document"]["url"]
    token = dl_url.split("token=")[1]

    # 1. Successful download via query token
    r_dl = client.get(f"/api/v1/euro-office/download/{file_id}?token={token}")
    assert r_dl.status_code == 200
    assert r_dl.content == raw_doc
    assert "ETag" in r_dl.headers
    assert "Content-Disposition" in r_dl.headers

    # 2. Download without token -> 401 Unauthorized
    r_no_tok = client.get(f"/api/v1/euro-office/download/{file_id}")
    assert r_no_tok.status_code == 401

    # 3. Download with invalid token -> 401 Unauthorized
    r_bad_tok = client.get(f"/api/v1/euro-office/download/{file_id}?token=invalid.tampered.token")
    assert r_bad_tok.status_code == 401


# =====================================================================
# Test 6: Callback Status 1: Active Co-Author Presence Tracking
# =====================================================================

def test_callback_status_1_and_coauthor_presence(db_session):
    """
    Verifies that Document Server Status 1 (BEING_EDITED) updates the live co-author
    session roster and is accessible via the coauthors presence API.
    """
    tenant = create_euro_tenant_and_users("presence")
    staff_a = tenant["staff_a_headers"]
    staff_a_id = tenant["staff_a_id"]
    staff_b_id = tenant["staff_b_id"]

    files = {"file": ("Collaborative_Project.docx", io.BytesIO(b"Doc content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    # Document Server notifies that Staff A and Staff B joined the room
    cb_payload = {
        "key": doc_key,
        "status": 1,
        "users": [staff_a_id, staff_b_id],
    }
    r_cb = client.post("/api/v1/euro-office/callback", json=cb_payload)
    assert r_cb.status_code == 200
    assert r_cb.json()["error"] == 0

    # Query coauthors roster via API
    r_presence = client.get(f"/api/v1/euro-office/{file_id}/coauthors", headers=staff_a)
    assert r_presence.status_code == 200
    presence_data = r_presence.json()
    assert presence_data["is_editing"] is True
    assert presence_data["coauthor_count"] == 2
    user_names = [u["full_name"] for u in presence_data["coauthors"]]
    assert "Abebe Kebede" in user_names
    assert "Chala Tadesse" in user_names


# =====================================================================
# Test 7: Callback Status 6: Force-Save (Ctrl+S / AutoSave)
# =====================================================================

@patch("app.services.euro_office_service.fetch_edited_document")
def test_callback_status_6_forcesave_ctrl_s(mock_fetch, db_session):
    """
    Verifies that Status 6 (FORCE_SAVE) downloads the intermediate payload,
    increments document version (v1 -> v2), but leaves the editing room active.
    """
    mock_fetch.return_value = b"Intermediate Autosaved Word Document Content"

    tenant = create_euro_tenant_and_users("forcesave")
    staff_a = tenant["staff_a_headers"]
    staff_a_id = tenant["staff_a_id"]

    files = {"file": ("Draft_Policy.docx", io.BytesIO(b"Initial Draft"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    # Document Server triggers Status 6 (Forcesave)
    cb_payload = {
        "key": doc_key,
        "status": 6,
        "url": "http://documentserver:8080/cache/Draft_Policy.docx",
        "users": [staff_a_id],
    }
    r_cb = client.post("/api/v1/euro-office/callback", json=cb_payload)
    assert r_cb.status_code == 200
    assert r_cb.json()["error"] == 0

    # Verify version 2 was created
    r_versions = client.get(f"/api/v1/files/{file_id}/versions", headers=staff_a)
    assert r_versions.status_code == 200
    versions = r_versions.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert "Forcesave" in versions[0]["change_summary"]

    # Verify session is still active (editing is True)
    session = db_session.query(EuroOfficeSession).filter(EuroOfficeSession.file_id == uuid.UUID(file_id)).first()
    assert session.is_editing is True


# =====================================================================
# Test 8: Callback Status 2: Ready for Save (Commit Final Version)
# =====================================================================

@patch("app.services.euro_office_service.fetch_edited_document")
def test_callback_status_2_ready_for_save(mock_fetch, db_session):
    """
    Verifies that Status 2 (READY_FOR_SAVING) downloads the final edited document,
    creates version snapshot, and closes the editing room.
    """
    mock_fetch.return_value = b"Final Approved Word Document from Euro-Office"

    tenant = create_euro_tenant_and_users("final-save")
    staff_a = tenant["staff_a_headers"]
    staff_b = tenant["staff_b_headers"]
    staff_b_id = tenant["staff_b_id"]

    files = {"file": ("Agreement_Contract.docx", io.BytesIO(b"Original Contract"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    # Share with Staff B as Editor
    client.post(f"/api/v1/shares/file/{file_id}", json={"target_user_id": staff_b_id, "permission": "EDITOR"}, headers=staff_a)

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    # Document Server sends Status 2 with Staff B as the saving user
    cb_payload = {
        "key": doc_key,
        "status": 2,
        "url": "http://documentserver:8080/cache/Agreement_Contract.docx",
        "users": [staff_b_id],
    }
    r_cb = client.post("/api/v1/euro-office/callback", json=cb_payload)
    assert r_cb.status_code == 200
    assert r_cb.json()["error"] == 0

    # Verify version 2 committed
    r_versions = client.get(f"/api/v1/files/{file_id}/versions", headers=staff_a)
    assert r_versions.status_code == 200
    versions = r_versions.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert "Collaborative Save" in versions[0]["change_summary"]

    # Verify session closed
    session = db_session.query(EuroOfficeSession).filter(EuroOfficeSession.file_id == uuid.UUID(file_id)).first()
    assert session.is_editing is False
    assert session.active_users == []

    # Verify file download yields final payload
    r_dl = client.get(f"/api/v1/files/{file_id}/download", headers=staff_a)
    assert r_dl.status_code == 200
    assert r_dl.content == b"Final Approved Word Document from Euro-Office"


# =====================================================================
# Test 9: Callback Status 4: Closed Without Changes
# =====================================================================

def test_callback_status_4_closed_no_changes(db_session):
    """
    Verifies that Status 4 cleans up the active session without creating redundant versions.
    """
    tenant = create_euro_tenant_and_users("close-no-change")
    staff_a = tenant["staff_a_headers"]

    files = {"file": ("Reference_Manual.docx", io.BytesIO(b"Reference Content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    # Set status 1 first
    client.post("/api/v1/euro-office/callback", json={"key": doc_key, "status": 1, "users": [tenant["staff_a_id"]]})

    # Close with Status 4
    r_cb = client.post("/api/v1/euro-office/callback", json={"key": doc_key, "status": 4})
    assert r_cb.status_code == 200
    assert r_cb.json()["error"] == 0

    # Verify session cleaned up
    session = db_session.query(EuroOfficeSession).filter(EuroOfficeSession.file_id == uuid.UUID(file_id)).first()
    assert session.is_editing is False
    assert session.active_users == []

    # Verify version count remains exactly 1
    r_ver = client.get(f"/api/v1/files/{file_id}/versions", headers=staff_a)
    assert len(r_ver.json()) == 1


# =====================================================================
# Test 10: Callback HMAC-SHA256 Signature Verification and Tamper Defense
# =====================================================================

def test_callback_hmac_sha256_signature_verification_and_tamper_rejection(db_session):
    """
    Verifies that when callbacks include a JWT signature, valid signatures are accepted
    and tampered or untrusted signatures are rejected with 401 Unauthorized.
    """
    tenant = create_euro_tenant_and_users("sig-verify")
    staff_a = tenant["staff_a_headers"]

    files = {"file": ("Secure_Ledger.xlsx", io.BytesIO(b"Financial Ledger"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    valid_payload = {"key": doc_key, "status": 1, "users": [tenant["staff_a_id"]]}

    # 1. Sign with legitimate secret
    valid_jwt = jwt.encode(valid_payload, settings.EURO_OFFICE_JWT_SECRET, algorithm="HS256")
    r_ok = client.post("/api/v1/euro-office/callback", json={"token": valid_jwt})
    assert r_ok.status_code == 200

    # 2. Sign with fake attacker secret -> 401 Unauthorized
    attacker_jwt = jwt.encode(valid_payload, "attacker-fake-secret-key-67890", algorithm="HS256")
    r_attack = client.post("/api/v1/euro-office/callback", json={"token": attacker_jwt})
    assert r_attack.status_code == 401


# =====================================================================
# Test 11: Enterprise License Write Lockdown Enforcement
# =====================================================================

@patch("app.services.euro_office_service.fetch_edited_document")
def test_callback_write_lockdown_enforcement(mock_fetch, db_session):
    """
    Verifies that when a tenant's license enters write lockdown, Euro-Office save
    callbacks are rejected with 403 Forbidden (LICENSE_LOCKDOWN_READ_ONLY).
    """
    mock_fetch.return_value = b"Forbidden Revision Under Lockdown"

    tenant = create_euro_tenant_and_users("lockdown")
    staff_a = tenant["staff_a_headers"]
    slug = tenant["slug"]

    files = {"file": ("Tender_Spec.docx", io.BytesIO(b"Tender Spec Initial"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a)
    file_id = r_up.json()["id"]

    r_cfg = client.get(f"/api/v1/euro-office/config/{file_id}", headers=staff_a)
    doc_key = r_cfg.json()["document"]["key"]

    # Manually expire the organization's license to trigger write lockdown
    org = db_session.query(Organization).filter(Organization.slug == slug).first()
    lic = db_session.query(License).filter(License.organization_id == org.id).first()
    lic.expires_at = datetime.now(timezone.utc) - timedelta(days=60)
    db_session.commit()

    # Attempt save callback -> 403 Forbidden
    cb_payload = {
        "key": doc_key,
        "status": 2,
        "url": "http://documentserver:8080/cache/Tender_Spec.docx",
        "users": [tenant["staff_a_id"]],
    }
    r_lockdown = client.post("/api/v1/euro-office/callback", json=cb_payload)
    assert r_lockdown.status_code == 403
    assert r_lockdown.json()["detail"]["code"] == "LICENSE_LOCKDOWN_READ_ONLY"
