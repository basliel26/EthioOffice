"""
Comprehensive Automated Test Suite for Module 11: Audit, Compliance & Observability
(የቁጥጥር፣ የህግ ተገዢነት እና የደህንነት ክትትል ስርዓት)

Enterprise Verification Coverage:
1. Cryptographic hash-chained tamper-evident audit ledger (prev_hash -> entry_hash linkage).
2. Non-repudiation & direct database tampering detection down to the exact compromised row ID.
3. INSA-compliant payload sanitization (passwords, tokens, keys scrubbed).
4. Multi-attribute audit querying with Ethiopian Calendar timestamps (ዓ.ም) and localized Amharic labels.
5. Strict Role-Based Access Control (RBAC): Regular staff blocked (HTTP 403); Admin allowed.
6. Multi-tenant boundary isolation with zero cross-tenant audit leakage.
7. Executive Microsoft Excel (.xlsx) compliance audit export with corporate styling.
8. UTF-8 with BOM CSV audit export for SIEM tool compatibility.
9. Security anomaly detection engine (brute-force login spikes, mass downloads).
10. Operational system health and resource observability probe (DB pool, disk utilization, uptime).
11. Full audit action catalog with Amharic translations and categories.
"""

import io
import uuid
from datetime import datetime, timezone
import pytest
import openpyxl
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.audit import AuditLog, AuditAction
from app.models.user import User, UserRole
from app.services.audit_service import AuditService

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_audit_tenant_and_users(slug_prefix: str = "aud"):
    """Helper to provision a dedicated tenant with an Admin and a Staff member."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Audit Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Audit Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201, f"Failed to provision tenant: {r.text}"

    # Login Admin
    login_admin = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
    assert login_admin.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    # Staff User
    staff_email = f"staff@{slug}.et"
    r_staff = client.post(
        "/api/v1/auth/users",
        json={"email": staff_email, "full_name": "Almaz Ayana", "password": password, "role": "STAFF"},
        headers=admin_headers,
    )
    assert r_staff.status_code == 201
    staff_id = r_staff.json()["id"]
    login_staff = client.post("/api/v1/auth/login", json={"email": staff_email, "password": password})
    staff_headers = {"Authorization": f"Bearer {login_staff.json()['access_token']}"}

    return {
        "slug": slug,
        "admin_headers": admin_headers,
        "admin_email": admin_email,
        "staff_headers": staff_headers,
        "staff_id": staff_id,
    }


# =====================================================================
# Test 1: Event Recording & Cryptographic Hash Chaining
# =====================================================================

def test_audit_event_recording_and_hash_chaining(db_session):
    """
    Verifies that audit records form an immutable sequential SHA-256 hash chain
    and sensitive fields (passwords, tokens) are automatically redacted.
    """
    ctx = create_audit_tenant_and_users("aud-ev")
    user = db_session.query(User).filter(User.email == ctx["admin_email"]).first()
    org_id = user.organization_id
    actor_id = user.id

    # 1. Record first event
    e1 = AuditService.record_event(
        db=db_session,
        org_id=org_id,
        action=AuditAction.LOGIN,
        target_type="USER",
        target_name="User Login",
        target_id=actor_id,
        user_id=actor_id,
        details={"ip": "196.188.1.1", "password": "SuperSecretPassword123!", "token": "secret_jwt_token"},
        ip_address="196.188.1.1",
        severity="INFO",
    )

    assert e1.entry_hash is not None
    assert len(e1.entry_hash) == 64
    assert e1.details["password"] == "[REDACTED_CONFIDENTIAL]"
    assert e1.details["token"] == "[REDACTED_CONFIDENTIAL]"
    assert e1.details["ip"] == "196.188.1.1"

    # 2. Record second event
    e2 = AuditService.record_event(
        db=db_session,
        org_id=org_id,
        action=AuditAction.UPLOAD,
        target_type="FILE",
        target_name="Annual_Budget_2018.xlsx",
        target_id=uuid.uuid4(),
        user_id=actor_id,
        details={"size_bytes": 102400, "mime": "spreadsheet"},
        ip_address="196.188.1.1",
        severity="INFO",
    )

    assert e2.prev_hash == e1.entry_hash  # Chained to previous entry!
    assert e2.entry_hash is not None
    assert e2.entry_hash != e1.entry_hash

    # 3. Record third event
    e3 = AuditService.record_event(
        db=db_session,
        org_id=org_id,
        action=AuditAction.DOWNLOAD,
        target_type="FILE",
        target_name="Annual_Budget_2018.xlsx",
        target_id=uuid.uuid4(),
        user_id=actor_id,
        details={"version": 1},
        ip_address="196.188.1.1",
        severity="INFO",
    )

    assert e3.prev_hash == e2.entry_hash  # Chained to second entry!


# =====================================================================
# Test 2: Cryptographic Ledger Integrity Verification (Success)
# =====================================================================

def test_audit_ledger_integrity_verification_success(db_session):
    """
    Verifies that an uncorrupted audit ledger passes cryptographic integrity checks.
    """
    ctx = create_audit_tenant_and_users("aud-ver")
    admin_h = ctx["admin_headers"]

    # Verify integrity endpoint
    r = client.get("/api/v1/audit/integrity/verify", headers=admin_h)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["is_valid"] is True
    assert data["total_records_checked"] >= 1
    assert data["compromised_row_id"] is None
    assert data["error_message"] is None
    assert data["genesis_hash"] is not None


# =====================================================================
# Test 3: Tamper Detection on Database Modification
# =====================================================================

def test_audit_ledger_tamper_detection(db_session):
    """
    Simulates a database administrator or attacker tampering with a row in PostgreSQL directly.
    Verifies that the verification engine flags the tampering down to the exact row ID!
    """
    ctx = create_audit_tenant_and_users("aud-tamper")
    user = db_session.query(User).filter(User.email == ctx["admin_email"]).first()
    org_id = user.organization_id
    actor_id = user.id

    e1 = AuditService.record_event(
        db=db_session,
        org_id=org_id,
        action=AuditAction.LOGIN,
        target_type="USER",
        target_name="Login Session",
        user_id=actor_id,
    )
    e2 = AuditService.record_event(
        db=db_session,
        org_id=org_id,
        action=AuditAction.UPLOAD,
        target_type="FILE",
        target_name="Secret_Report.docx",
        user_id=actor_id,
    )

    # Legitimate state: valid
    res_before = AuditService.verify_ledger_integrity(db_session, org_id)
    assert res_before.is_valid is True

    # Attack: Attacker alters target_name directly in database to frame someone else or conceal action
    original_name = e2.target_name
    e2.target_name = "Altered_File_Name_By_Attacker.docx"
    db_session.commit()

    # Verification must fail and identify e2.id
    res_tampered = AuditService.verify_ledger_integrity(db_session, org_id)
    assert res_tampered.is_valid is False
    assert res_tampered.compromised_row_id == e2.id
    assert "Cryptographic signature mismatch" in res_tampered.error_message

    # Revert tamper
    e2.target_name = original_name
    db_session.commit()

    res_restored = AuditService.verify_ledger_integrity(db_session, org_id)
    assert res_restored.is_valid is True


# =====================================================================
# Test 4: Query Filtering & Ethiopian Calendar Date Formatting
# =====================================================================

def test_audit_query_filtering_and_ethiopian_dates():
    """
    Verifies that audit log queries support filtering by action, severity, target_type
    and include formatted Ethiopian calendar timestamps (ዓ.ም).
    """
    ctx = create_audit_tenant_and_users("aud-qry")
    admin_h = ctx["admin_headers"]

    # 1. Query all logs
    r_all = client.get("/api/v1/audit/logs?limit=50", headers=admin_h)
    assert r_all.status_code == 200
    data = r_all.json()
    assert data["total"] >= 1
    item = data["items"][0]

    assert "ec_created_at" in item
    assert "ዓ.ም" in item["ec_created_at"]
    assert "action_amharic" in item
    assert item["entry_hash"] is not None

    # 2. Filter by action
    r_action = client.get("/api/v1/audit/logs?action=UPLOAD", headers=admin_h)
    assert r_action.status_code == 200
    for it in r_action.json()["items"]:
        assert it["action"] == "UPLOAD"

    # 3. Filter by severity
    r_sev = client.get("/api/v1/audit/logs?severity=INFO", headers=admin_h)
    assert r_sev.status_code == 200
    for it in r_sev.json()["items"]:
        assert it["severity"] == "INFO"


# =====================================================================
# Test 5: Role-Based Access Control (RBAC)
# =====================================================================

def test_audit_role_access_control_fencing():
    """
    Verifies that regular STAFF users are strictly blocked from viewing or exporting audit logs (HTTP 403),
    while Organization Administrators have full access.
    """
    ctx = create_audit_tenant_and_users("aud-rbac")
    admin_h = ctx["admin_headers"]
    staff_h = ctx["staff_headers"]

    # 1. Staff blocked from query
    r1 = client.get("/api/v1/audit/logs", headers=staff_h)
    assert r1.status_code == 403

    # 2. Staff blocked from integrity verification
    r2 = client.get("/api/v1/audit/integrity/verify", headers=staff_h)
    assert r2.status_code == 403

    # 3. Staff blocked from Excel export
    r3 = client.get("/api/v1/audit/export/excel", headers=staff_h)
    assert r3.status_code == 403

    # 4. Staff blocked from CSV export
    r4 = client.get("/api/v1/audit/export/csv", headers=staff_h)
    assert r4.status_code == 403

    # 5. Staff blocked from dashboard summary
    r5 = client.get("/api/v1/audit/dashboard/summary", headers=staff_h)
    assert r5.status_code == 403

    # 6. Admin succeeds on all
    assert client.get("/api/v1/audit/logs", headers=admin_h).status_code == 200
    assert client.get("/api/v1/audit/integrity/verify", headers=admin_h).status_code == 200
    assert client.get("/api/v1/audit/dashboard/summary", headers=admin_h).status_code == 200


# =====================================================================
# Test 6: Multi-Tenant Boundary Isolation
# =====================================================================

def test_audit_multi_tenant_isolation():
    """
    Verifies that Tenant 2 Administrator CANNOT view or export any audit records belonging to Tenant 1.
    """
    t1 = create_audit_tenant_and_users("aud-t1")
    t2 = create_audit_tenant_and_users("aud-t2")

    r1 = client.get("/api/v1/audit/logs", headers=t1["admin_headers"])
    assert r1.status_code == 200
    t1_ids = {it["id"] for it in r1.json()["items"]}

    r2 = client.get("/api/v1/audit/logs", headers=t2["admin_headers"])
    assert r2.status_code == 200
    t2_ids = {it["id"] for it in r2.json()["items"]}

    # Zero overlap between tenant audit records
    assert t1_ids.isdisjoint(t2_ids)


# =====================================================================
# Test 7: Executive Excel (.xlsx) Compliance Export
# =====================================================================

def test_audit_excel_export_streaming():
    """
    Verifies that /api/v1/audit/export/excel delivers a valid, beautifully formatted
    Microsoft Excel (.xlsx) document with Ethiopian calendar dates and headers.
    """
    ctx = create_audit_tenant_and_users("aud-xl")
    admin_h = ctx["admin_headers"]

    r = client.get("/api/v1/audit/export/excel", headers=admin_h)
    assert r.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in r.headers["content-type"]
    assert "attachment; filename=" in r.headers["content-disposition"]

    # Parse with openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert "Audit Trail Report" in wb.sheetnames
    ws = wb["Audit Trail Report"]

    # Verify corporate title
    title_cell = ws["A1"].value
    assert "EthioOffice" in title_cell
    assert "የኦዲት ክትትል ሪፖርት" in title_cell

    # Verify column headers
    header_values = [cell.value for cell in ws[4]]
    assert "ተ.ቁ" in header_values
    assert "ቀን (EC ዓ.ም)" in header_values
    assert "ድርጊት (Action)" in header_values
    assert "ዲጂታል ፊርማ (Hash)" in header_values

    # Verify data rows exist
    assert ws.max_row >= 5


# =====================================================================
# Test 8: UTF-8 with BOM CSV Compliance Export
# =====================================================================

def test_audit_csv_export_streaming_with_bom():
    """
    Verifies that /api/v1/audit/export/csv delivers UTF-8 with BOM CSV
    ensuring Amharic Unicode compatibility in external spreadsheet and SIEM tools.
    """
    ctx = create_audit_tenant_and_users("aud-csv")
    admin_h = ctx["admin_headers"]

    r = client.get("/api/v1/audit/export/csv", headers=admin_h)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]

    # Verify UTF-8 BOM prefix (\xef\xbb\xbf)
    assert r.content.startswith(b"\xef\xbb\xbf")

    # Decode and check CSV header
    text_csv = r.content.decode("utf-8")
    assert "Date_EC" in text_csv
    assert "Action_Amharic" in text_csv
    assert "Entry_Hash" in text_csv


# =====================================================================
# Test 9: Security Anomaly Detection Engine
# =====================================================================

def test_audit_dashboard_summary_and_anomalies(db_session):
    """
    Verifies that /api/v1/audit/dashboard/summary aggregates action metrics
    and detects security anomalies (brute force login spikes).
    """
    ctx = create_audit_tenant_and_users("aud-anom")
    admin_h = ctx["admin_headers"]
    user = db_session.query(User).filter(User.email == ctx["admin_email"]).first()
    org = user.organization_id

    # Simulate 5 failed logins from suspicious IP
    suspicious_ip = "197.156.100.45"
    for _ in range(5):
        AuditService.record_event(
            db=db_session,
            org_id=org,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_name="Failed Authentication",
            details={"reason": "Invalid credentials"},
            ip_address=suspicious_ip,
            severity="WARNING",
            status="FAILED",
        )

    r = client.get("/api/v1/audit/dashboard/summary", headers=admin_h)
    assert r.status_code == 200
    data = r.json()

    assert data["total_events"] >= 5
    assert data["action_category_breakdown"]["SECURITY"] >= 5
    assert len(data["recent_anomalies"]) >= 1

    # Check brute force anomaly item
    bf_item = next((a for a in data["recent_anomalies"] if a["type"] == "BRUTE_FORCE"), None)
    assert bf_item is not None
    assert bf_item["severity"] == "CRITICAL"
    assert suspicious_ip in bf_item["ip_address"]
    assert "የተደጋገመ" in bf_item["description"]


# =====================================================================
# Test 10: Operational System Health & Resource Probe
# =====================================================================

def test_audit_system_health_probe():
    """
    Verifies /api/v1/audit/system/health operational observability endpoint
    inspecting database connectivity, disk storage, and process uptime.
    """
    ctx = create_audit_tenant_and_users("aud-hlth")
    admin_h = ctx["admin_headers"]

    r = client.get("/api/v1/audit/system/health", headers=admin_h)
    assert r.status_code == 200
    data = r.json()

    assert data["status"] in ("HEALTHY", "DEGRADED")
    assert data["database_connected"] is True
    assert data["disk_total_gb"] > 0
    assert data["disk_free_gb"] > 0
    assert data["uptime_seconds"] >= 0
    assert data["cpu_count"] >= 1
    assert data["version"] is not None


# =====================================================================
# Test 11: Audit Action Catalog
# =====================================================================

def test_audit_actions_catalog():
    """
    Verifies /api/v1/audit/actions returns the formal catalog of domain actions with Amharic names.
    """
    ctx = create_audit_tenant_and_users("aud-act")
    admin_h = ctx["admin_headers"]

    r = client.get("/api/v1/audit/actions", headers=admin_h)
    assert r.status_code == 200
    actions = r.json()

    assert len(actions) >= 15
    upload_act = next((a for a in actions if a["action"] == "UPLOAD"), None)
    assert upload_act is not None
    assert upload_act["name_amharic"] == "ሰነድ/ፋይል መስቀል"
    assert upload_act["category"] == "DOCUMENT"

    letter_act = next((a for a in actions if a["action"] == "LETTER_REGISTER"), None)
    assert letter_act is not None
    assert letter_act["name_amharic"] == "ደብዳቤ መመዝገብ"
    assert letter_act["category"] == "LETTER"
