import uuid
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models.letter import LetterDirection, LetterStatus, LetterConfidentiality, LetterUrgency, DeliveryMethod

client = TestClient(app)


def get_auth_token(email: str = "admin@abyssinia.et", password: str = "Admin123!") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Failed to login: {r.text}"
    return r.json()["access_token"]


def test_inward_letter_registration_and_ethiopian_dates():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "direction": "INWARD",
        "subject": "የ2018 ዓ.ም የኦዲት ሪፖርት ማሳወቂያ",
        "sender_entity": "የፌደራል ዋና ኦዲተር መ/ቤት (OFAG)",
        "sender_contact": "+251 11 551 2233",
        "recipient_entity": "አቢሲኒያ ኢንተርፕራይዝ ዋና ዳይሬክተር",
        "external_reference_number": "OFAG/FIN/998/18",
        "urgency": "NORMAL",
        "confidentiality": "NORMAL",
        "notes": "የመጀመሪያ ደረጃ ኦዲት ማጠቃለያ ሪፖርት",
    }

    resp = client.post("/api/v1/letters", json=payload, headers=headers)
    assert resp.status_code in [200, 201], resp.text
    data = resp.json()

    assert data["direction"] == "INWARD"
    assert data["status"] == "RECEIVED"
    assert data["subject"] == payload["subject"]
    assert data["external_reference_number"] == "OFAG/FIN/998/18"
    assert data["reference_number"] is not None
    assert "ዓ.ም" in data["date_ec"]
    assert data["due_date_gc"] is not None
    assert data["due_date_ec"] is not None
    assert "ዓ.ም" in data["due_date_ec"]


def test_sequential_reference_numbering():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch finance department ID
    depts_resp = client.get("/api/v1/departments", headers=headers)
    assert depts_resp.status_code == 200
    depts = depts_resp.json()
    fin_dept = next((d for d in depts if d["code"] == "FIN"), None)
    assert fin_dept is not None

    # Register first letter for FIN
    l1 = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "department_id": fin_dept["id"],
        "subject": "የታክስ ክሊራንስ ደብዳቤ ፩",
        "sender_entity": "የገቢዎች ሚኒስቴር",
        "recipient_entity": "ፋይናንስ ክፍል",
    }, headers=headers).json()

    # Register second letter for FIN
    l2 = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "department_id": fin_dept["id"],
        "subject": "የታክስ ክሊራንስ ደብዳቤ ፪",
        "sender_entity": "የገቢዎች ሚኒስቴር",
        "recipient_entity": "ፋይናንስ ክፍል",
    }, headers=headers).json()

    assert l1["reference_number"] != l2["reference_number"]
    assert "FIN" in l1["reference_number"]
    assert "FIN" in l2["reference_number"]

    # Extract sequence integers
    num1 = int(l1["reference_number"].split("/")[-1])
    num2 = int(l2["reference_number"].split("/")[-1])
    assert num2 == num1 + 1


def test_urgency_and_ethiopian_sla_calculation():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    # Very urgent letter (1 working day SLA)
    v_urgent = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "አስቸኳይ የፍርድ ቤት ትዕዛዝ",
        "sender_entity": "የፌደራል ከፍተኛ ፍርድ ቤት",
        "recipient_entity": "ሕግ ክፍል",
        "urgency": "VERY_URGENT",
    }, headers=headers).json()

    # Normal letter (5 working days SLA)
    normal = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "የዓመታዊ ስብሰባ ጥሪ",
        "sender_entity": "አክሲዮን ማኅበር",
        "recipient_entity": "ዋና ሥራ አስኪያጅ",
        "urgency": "NORMAL",
    }, headers=headers).json()

    assert v_urgent["due_date_gc"] <= normal["due_date_gc"]
    assert v_urgent["urgency"] == "VERY_URGENT"
    assert normal["urgency"] == "NORMAL"


def test_outward_letter_approval_lifecycle():
    # Staff creates draft
    staff_token = get_auth_token("abebe@abyssinia.et", "Staff123!")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    admin_token = get_auth_token("admin@abyssinia.et", "Admin123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Draft outward letter
    draft_resp = client.post("/api/v1/letters", json={
        "direction": "OUTWARD",
        "subject": "የግዥ ፈቃድ ጥያቄ አቀራረብ",
        "sender_entity": "አቢሲኒያ ኢንተርፕራይዝ",
        "recipient_entity": "የኢትዮጵያ ንግድ ባንክ",
        "urgency": "URGENT",
    }, headers=staff_headers)
    assert draft_resp.status_code in [200, 201]
    letter_id = draft_resp.json()["id"]
    assert draft_resp.json()["status"] == "DRAFT"

    # 2. Submit for approval
    submit_resp = client.post(f"/api/v1/letters/{letter_id}/submit", headers=staff_headers)
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "PENDING_APPROVAL"

    # 3. Staff attempts to approve (Unauthorized)
    forbidden_resp = client.post(f"/api/v1/letters/{letter_id}/approve", headers=staff_headers)
    assert forbidden_resp.status_code == 403

    # 4. Manager rejects with reason
    reject_resp = client.post(f"/api/v1/letters/{letter_id}/reject", json={
        "action": "REJECT",
        "rejection_reason": "እባክዎ የተጠቃሚውን በጀት ኮድ ጨምረው እንደገና ያቅርቡ",
    }, headers=admin_headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"
    assert "በጀት ኮድ" in reject_resp.json()["rejection_reason"]

    # 5. Drafter updates and resubmits
    client.patch(f"/api/v1/letters/{letter_id}", json={
        "notes": "የበጀት ኮድ FIN-2018-04 ታክሏል"
    }, headers=staff_headers)
    client.post(f"/api/v1/letters/{letter_id}/submit", headers=staff_headers)

    # 6. Admin approves
    approve_resp = client.post(f"/api/v1/letters/{letter_id}/approve", headers=admin_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"
    assert approve_resp.json()["approved_at_gc"] is not None

    # 7. Dispatch letter
    dispatch_resp = client.post(f"/api/v1/letters/{letter_id}/dispatch", json={
        "delivery_method": "EMAIL",
    }, headers=staff_headers)
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["status"] == "DISPATCHED"
    assert dispatch_resp.json()["delivery_method"] == "EMAIL"
    assert "ዓ.ም" in dispatch_resp.json()["dispatched_at_ec"]


def test_security_classification_clearance():
    admin_token = get_auth_token("admin@abyssinia.et", "Admin123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    staff_token = get_auth_token("abebe@abyssinia.et", "Staff123!")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 1. Admin creates STRICTLY_CONFIDENTIAL letter
    conf_letter = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "በጣም ምስጢራዊ የዳይሬክተሮች ቦርድ ቃለ-ጉባዔ",
        "sender_entity": "የዳይሬክተሮች ቦርድ ሰብሳቢ",
        "recipient_entity": "ዋና ሥራ አስፈጻሚ",
        "confidentiality": "STRICTLY_CONFIDENTIAL",
    }, headers=admin_headers).json()

    letter_id = conf_letter["id"]

    # 2. Admin can access it
    admin_get = client.get(f"/api/v1/letters/{letter_id}", headers=admin_headers)
    assert admin_get.status_code == 200

    # 3. Staff (not author or assignee) cannot access it
    staff_get = client.get(f"/api/v1/letters/{letter_id}", headers=staff_headers)
    assert staff_get.status_code == 403


def test_departmental_routing_chain_of_custody():
    admin_token = get_auth_token("admin@abyssinia.et", "Admin123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    staff_token = get_auth_token("abebe@abyssinia.et", "Staff123!")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Get departments
    depts = client.get("/api/v1/departments", headers=admin_headers).json()
    ops_dept = next(d for d in depts if d["code"] == "OPS")

    # 1. Register letter
    letter = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "የአቅርቦት እቃዎች ግምገማ ጥያቄ",
        "sender_entity": "አቅራቢ ድርጅት",
        "recipient_entity": "ዋና መዝገብ ቤት",
    }, headers=admin_headers).json()

    # 2. Route letter to Operations Department
    route_resp = client.post(f"/api/v1/letters/{letter['id']}/route", json={
        "to_department_id": ops_dept["id"],
        "action_required": "FOR_ACTION",
        "instructions": "እባክዎ የቀረቡትን የዋጋ ዝርዝሮች ገምግመው ሪፖርት ያቅርቡ",
    }, headers=admin_headers)
    assert route_resp.status_code in [200, 201]
    routing_data = route_resp.json()
    routing_id = routing_data["id"]
    assert routing_data["status"] == "PENDING"
    assert routing_data["action_required"] == "FOR_ACTION"

    # 3. Operations staff acknowledges receipt
    ack_resp = client.patch(f"/api/v1/letters/routings/{routing_id}/acknowledge", headers=admin_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

    # 4. Operations staff completes the routing task
    comp_resp = client.patch(f"/api/v1/letters/routings/{routing_id}/complete", json={
        "response_notes": "ግምገማው ተጠናቆ የውሳኔ ሃሳብ ለፋይናንስ ተልኳል",
    }, headers=admin_headers)
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"
    assert "ግምገማው ተጠናቆ" in comp_resp.json()["response_notes"]

    # Verify routing history on letter detail
    detail = client.get(f"/api/v1/letters/{letter['id']}", headers=admin_headers).json()
    assert len(detail["routings"]) >= 1
    assert detail["routings"][0]["status"] == "COMPLETED"


def test_amharic_search_and_filtering():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    unique_subject = f"የሠራተኞች የሕክምና ኢንሹራንስ ውል {uuid.uuid4().hex[:6]}"
    client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": unique_subject,
        "sender_entity": "አንበሳ ኢንሹራንስ ኩባንያ",
        "recipient_entity": "የሰው ኃይል ክፍል",
    }, headers=headers)

    # Search by exact and normalized keyword
    search_resp = client.get(f"/api/v1/letters?search=ኢንሹራንስ", headers=headers)
    assert search_resp.status_code == 200
    letters = search_resp.json()
    assert len(letters) >= 1
    assert any("ኢንሹራንስ" in l["subject"] for l in letters)


def test_analytics_dashboard_summary():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/letters/analytics/summary", headers=headers)
    assert r.status_code == 200
    summary = r.json()

    assert "total_letters" in summary
    assert "inward_count" in summary
    assert "outward_count" in summary
    assert "by_department" in summary
    assert "by_urgency" in summary
    assert summary["total_letters"] >= 1


def test_archive_letter_lifecycle():
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    letter = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "የተጠናቀቀ የውል ስምምነት ሰነድ",
        "sender_entity": "ውጭ ጉዳይ ሚኒስቴር",
        "recipient_entity": "ዋና ዳይሬክተር",
    }, headers=headers).json()

    # Archive
    archive_resp = client.post(f"/api/v1/letters/{letter['id']}/archive", headers=headers)
    assert archive_resp.status_code == 200
    assert archive_resp.json()["status"] == "ARCHIVED"


import concurrent.futures
from app.core.database import SessionLocal
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.core.security import get_password_hash


def test_concurrency_sequential_reference_numbering():
    """Enterprise Hardening: Concurrency defense against duplicate reference numbers."""
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    depts = client.get("/api/v1/departments", headers=headers).json()
    hr_dept = next(d for d in depts if d["code"] == "HR")

    def register_single_letter(idx: int) -> str:
        r = client.post("/api/v1/letters", json={
            "direction": "INWARD",
            "department_id": hr_dept["id"],
            "subject": f"የቅጥር ማስታወቂያ ውድድር {idx}",
            "sender_entity": f"አመልካች {idx}",
            "recipient_entity": "የሰው ኃይል ክፍል",
        }, headers=headers)
        assert r.status_code in [200, 201]
        return r.json()["reference_number"]

    # Launch 10 simultaneous registration requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(register_single_letter, i) for i in range(10)]
        ref_numbers = [f.result() for f in futures]

    # Verify 100% uniqueness (zero collisions)
    assert len(ref_numbers) == 10
    assert len(set(ref_numbers)) == 10
    for ref in ref_numbers:
        assert "HR" in ref


def test_state_machine_illegal_transition_guards():
    """Enterprise Hardening: Defense against invalid state machine transitions."""
    staff_token = get_auth_token("abebe@abyssinia.et", "Staff123!")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    admin_token = get_auth_token("admin@abyssinia.et", "Admin123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create outward draft
    letter = client.post("/api/v1/letters", json={
        "direction": "OUTWARD",
        "subject": "ሕገ-ወጥ ሽግግር መከላከያ ደብዳቤ",
        "sender_entity": "አቢሲኒያ ኢንተርፕራይዝ",
        "recipient_entity": "የገቢዎች ቢሮ",
    }, headers=staff_headers).json()

    letter_id = letter["id"]

    # Guard 1: Cannot dispatch directly from DRAFT (regular staff)
    r_disp = client.post(f"/api/v1/letters/{letter_id}/dispatch", json={"delivery_method": "POSTAL"}, headers=staff_headers)
    assert r_disp.status_code == 400

    # Guard 2: Cannot approve directly from DRAFT
    r_app = client.post(f"/api/v1/letters/{letter_id}/approve", headers=admin_headers)
    assert r_app.status_code == 400

    # Guard 3: Rejecting without reason fails
    client.post(f"/api/v1/letters/{letter_id}/submit", headers=staff_headers)
    r_rej = client.post(f"/api/v1/letters/{letter_id}/reject", json={"action": "REJECT", "rejection_reason": "   "}, headers=admin_headers)
    assert r_rej.status_code == 400


def test_threaded_letter_reply_relationship():
    """Enterprise Hardening: Threaded inward-to-outward correspondence reply chain."""
    admin_token = get_auth_token("admin@abyssinia.et", "Admin123!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Inward letter received
    inward = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "subject": "የ2018 በጀት ማሻሻያ ጥያቄ",
        "sender_entity": "የኢንዱስትሪ ፓርኮች ኮርፖሬሽን",
        "recipient_entity": "ዋና ዳይሬክተር",
        "external_reference_number": "IPDC/BUD/01/2018",
    }, headers=admin_headers).json()

    # 2. Outward reply letter referencing the inward letter
    outward = client.post("/api/v1/letters", json={
        "direction": "OUTWARD",
        "subject": "ለበጀት ማሻሻያ ጥያቄ የተሰጠ ምላሽ",
        "sender_entity": "አቢሲኒያ ኢንተርፕራይዝ",
        "recipient_entity": "የኢንዱስትሪ ፓርኮች ኮርፖሬሽን",
        "reply_to_letter_id": inward["id"],
    }, headers=admin_headers).json()

    assert outward["reply_to_letter_id"] == inward["id"]

    # 3. Fetch inward letter detail and verify reply_count == 1
    inward_detail = client.get(f"/api/v1/letters/{inward['id']}", headers=admin_headers).json()
    assert inward_detail["reply_count"] >= 1


def test_cross_tenant_letter_isolation():
    """Enterprise Hardening: Multi-tenancy cross-tenant leakage prevention."""
    from datetime import datetime, timedelta, timezone
    from app.models.organization import License, LicenseTier

    db = SessionLocal()
    tenant2_slug = f"tenant2-{uuid.uuid4().hex[:6]}"
    org2 = Organization(
        name="Second Enterprise Corp",
        slug=tenant2_slug,
        is_active=True,
    )
    db.add(org2)
    db.flush()

    lic2 = License(
        organization_id=org2.id,
        license_key=f"EO-KEY-{uuid.uuid4().hex[:12]}",
        tier=LicenseTier.ENTERPRISE,
        max_users=50,
        storage_limit_bytes=100 * 1024 * 1024 * 1024,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_active=True,
    )
    db.add(lic2)

    user2_email = f"user@{tenant2_slug}.et"
    user2 = User(
        organization_id=org2.id,
        email=user2_email,
        full_name="ሁለተኛ ተጠቃሚ",
        hashed_password=get_password_hash("Password123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user2)
    db.commit()

    try:
        # Login as tenant 2
        t2_token = get_auth_token(user2_email, "Password123!")
        t2_headers = {"Authorization": f"Bearer {t2_token}"}

        # Tenant 1 creates a letter
        t1_token = get_auth_token("admin@abyssinia.et", "Admin123!")
        t1_headers = {"Authorization": f"Bearer {t1_token}"}
        t1_letter = client.post("/api/v1/letters", json={
            "direction": "INWARD",
            "subject": "የቴናንት ፩ የግል ደብዳቤ",
            "sender_entity": "የኢትዮጵያ ንግድ ባንክ",
            "recipient_entity": "ቴናንት ፩",
        }, headers=t1_headers).json()

        # Tenant 2 attempts to fetch Tenant 1's letter directly -> 404 Not Found
        r_fetch = client.get(f"/api/v1/letters/{t1_letter['id']}", headers=t2_headers)
        assert r_fetch.status_code == 404

        # Tenant 2 lists letters -> Should NOT contain Tenant 1's letter
        r_list = client.get("/api/v1/letters", headers=t2_headers)
        assert r_list.status_code == 200
        t2_letters = r_list.json()
        assert not any(l["id"] == t1_letter["id"] for l in t2_letters)

    finally:
        # Cleanup tenant 2
        db.delete(lic2)
        db.delete(user2)
        db.delete(org2)
        db.commit()
        db.close()


def test_nonexistent_entity_guards():
    """Enterprise Hardening: Rejection of invalid foreign keys."""
    token = get_auth_token("admin@abyssinia.et", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    fake_id = str(uuid.uuid4())

    # Invalid department ID
    r_dept = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "department_id": fake_id,
        "subject": "የማይታወቅ ክፍል ደብዳቤ",
        "sender_entity": "አመልካች",
        "recipient_entity": "ክፍል",
    }, headers=headers)
    assert r_dept.status_code == 404

    # Invalid attachment file ID
    r_attach = client.post("/api/v1/letters", json={
        "direction": "INWARD",
        "attachment_file_id": fake_id,
        "subject": "የማይታወቅ አባሪ ደብዳቤ",
        "sender_entity": "አመልካች",
        "recipient_entity": "ክፍል",
    }, headers=headers)
    assert r_attach.status_code == 404
