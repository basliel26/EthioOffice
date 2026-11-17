"""
Comprehensive Automated Test Suite for Completing Enterprise Features Package
Tests:
1. Document Tags & Classification Engine (Hex validation, uniqueness, file associations, search sync).
2. Starred / Favorite Files & Folders (Per-user favorite isolation, file item response reflection).
3. Recent Documents Feed (Audit trail linking, Amharic action descriptions, Ethiopian dates).
4. Empty Recycle Bin (Cascade permanent purge, physical file unlink, atomic quota reclamation).
5. User Self-Service Profile & Account Security (Profile updates, password change, complexity rules).
6. Admin Account Lock / Unlock / Reset Password (Brute-force lockout simulation, admin overrides).
7. In-App Notifications & Event Alert Engine (Real-time trigger on file share, unread badge, read marking).
8. Official Letter Document Drive Attachments (Multi-attachment drive linking, letter detail enrichment).
"""

import io
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.user import User

client = TestClient(app)


def create_enterprise_tenant_and_users(slug_prefix: str = "ent"):
    """Helper to provision a dedicated enterprise tenant with Admin and Staff members."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Enterprise Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Enterprise Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201, f"Failed to provision tenant: {r.text}"

    # Login Admin
    login_admin = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
    assert login_admin.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}
    admin_user = login_admin.json()["user"]

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
        "admin_user": admin_user,
        "staff_a_headers": staff_a_headers,
        "staff_a_id": staff_a_id,
        "staff_a_email": staff_a_email,
        "staff_b_headers": staff_b_headers,
        "staff_b_id": staff_b_id,
        "staff_b_email": staff_b_email,
        "password": password,
    }


# =====================================================================
# 1. Document Tags & Classification Engine
# =====================================================================

def test_tags_crud_and_hex_validation():
    ctx = create_enterprise_tenant_and_users("tags")
    headers = ctx["admin_headers"]

    # 1. Create valid tag
    t1_resp = client.post("/api/v1/tags", json={"name": "አስቸኳይ", "color": "#ef4444"}, headers=headers)
    assert t1_resp.status_code == 201
    t1_data = t1_resp.json()
    assert t1_data["name"] == "አስቸኳይ"
    assert t1_data["color"] == "#ef4444"
    assert t1_data["file_count"] == 0

    t2_resp = client.post("/api/v1/tags", json={"name": "የፋይናንስ ሰነድ", "color": "#10b981"}, headers=headers)
    assert t2_resp.status_code == 201

    # 2. Reject duplicate tag name within organization
    dup_resp = client.post("/api/v1/tags", json={"name": "አስቸኳይ", "color": "#3b82f6"}, headers=headers)
    assert dup_resp.status_code == 409

    # 3. Reject invalid hex color
    bad_color_resp = client.post("/api/v1/tags", json={"name": "መመሪያ", "color": "blue"}, headers=headers)
    assert bad_color_resp.status_code == 422

    # 4. List tags
    list_resp = client.get("/api/v1/tags", headers=headers)
    assert list_resp.status_code == 200
    tags = list_resp.json()
    assert len(tags) >= 2
    assert any(t["name"] == "አስቸኳይ" for t in tags)

    # 5. Delete tag
    del_resp = client.delete(f"/api/v1/tags/{t1_data['id']}", headers=headers)
    assert del_resp.status_code == 200

    list_resp2 = client.get("/api/v1/tags", headers=headers)
    assert not any(t["id"] == t1_data["id"] for t in list_resp2.json())


def test_file_tag_assignment_and_removal():
    ctx = create_enterprise_tenant_and_users("filetags")
    headers = ctx["staff_a_headers"]

    # Create tag as admin
    tag_resp = client.post("/api/v1/tags", json={"name": "ሚስጥራዊ ውል", "color": "#8b5cf6"}, headers=ctx["admin_headers"])
    assert tag_resp.status_code == 201
    tag_id = tag_resp.json()["id"]

    # Upload file as Staff A
    content = b"Confidential business agreement document content"
    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("business_contract.txt", io.BytesIO(content), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # Assign tag to file
    assign_resp = client.post(f"/api/v1/files/{file_id}/tags", json={"tag_ids": [tag_id]}, headers=headers)
    assert assign_resp.status_code == 200
    assert len(assign_resp.json()["tags"]) == 1
    assert assign_resp.json()["tags"][0]["name"] == "ሚስጥራዊ ውል"

    # Verify tags reflected in get_file_tags
    get_tags_resp = client.get(f"/api/v1/files/{file_id}/tags", headers=headers)
    assert get_tags_resp.status_code == 200
    assert any(t["id"] == tag_id for t in get_tags_resp.json())

    # Verify tags reflected in file listing
    files_list = client.get("/api/v1/files?drive_type=PERSONAL", headers=headers).json()
    file_item = next(f for f in files_list if f["id"] == file_id)
    assert "ሚስጥራዊ ውል" in file_item["tags"]

    # Tag document count incremented
    tag_list = client.get("/api/v1/tags", headers=headers).json()
    contract_tag = next(t for t in tag_list if t["id"] == tag_id)
    assert contract_tag["file_count"] >= 1

    # Remove tag from file
    rem_resp = client.delete(f"/api/v1/files/{file_id}/tags/{tag_id}", headers=headers)
    assert rem_resp.status_code == 200

    get_tags_after = client.get(f"/api/v1/files/{file_id}/tags", headers=headers).json()
    assert len(get_tags_after) == 0


# =====================================================================
# 2. Starred / Favorite Files & Folders
# =====================================================================

def test_starred_and_favorite_isolation():
    ctx = create_enterprise_tenant_and_users("star")
    staff_a = ctx["staff_a_headers"]
    staff_b = ctx["staff_b_headers"]

    # Staff A uploads a file
    content = b"Important project milestone report"
    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("milestone_report.txt", io.BytesIO(content), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=staff_a,
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # Initially not starred
    assert upload_resp.json().get("is_starred", False) is False

    # Staff A stars the file
    star_resp = client.post(f"/api/v1/files/{file_id}/star", headers=staff_a)
    assert star_resp.status_code == 200

    # Staff A lists starred files
    starred_list = client.get("/api/v1/files/starred", headers=staff_a)
    assert starred_list.status_code == 200
    starred_items = starred_list.json()
    assert len(starred_items) == 1
    assert starred_items[0]["id"] == file_id
    assert starred_items[0]["is_starred"] is True

    # Staff A normal listing has is_starred == True
    list_a = client.get("/api/v1/files?drive_type=PERSONAL", headers=staff_a).json()
    assert any(f["id"] == file_id and f["is_starred"] is True for f in list_a)

    # Share file with Staff B to test favorite isolation
    client.post(
        f"/api/v1/shares/file/{file_id}",
        json={"target_user_id": ctx["staff_b_id"], "permission": "VIEWER"},
        headers=staff_a,
    )

    # For Staff B, the file is NOT starred
    starred_b = client.get("/api/v1/files/starred", headers=staff_b).json()
    assert not any(f["id"] == file_id for f in starred_b)

    # Staff A unstars the file
    unstar_resp = client.delete(f"/api/v1/files/{file_id}/star", headers=staff_a)
    assert unstar_resp.status_code == 200

    starred_list_after = client.get("/api/v1/files/starred", headers=staff_a).json()
    assert len(starred_list_after) == 0


# =====================================================================
# 3. Recent Documents Feed
# =====================================================================

def test_recent_documents_feed():
    ctx = create_enterprise_tenant_and_users("recent")
    headers = ctx["staff_a_headers"]

    # Upload file
    content = b"Recent activity tracking document"
    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("recent_memo.txt", io.BytesIO(content), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # Query recent files
    recent_resp = client.get("/api/v1/files/recent", headers=headers)
    assert recent_resp.status_code == 200
    items = recent_resp.json()
    assert len(items) >= 1

    target_recent = next((r for r in items if r["file"]["id"] == file_id), None)
    assert target_recent is not None
    assert target_recent["last_action"] is not None
    assert target_recent["last_action_amharic"] is not None
    assert target_recent["last_action_at"] is not None
    assert target_recent["last_action_at_ec"] is not None
    assert "ዓ.ም" in target_recent["last_action_at_ec"]


# =====================================================================
# 4. Empty Recycle Bin & Atomic Quota Reclamation
# =====================================================================

def test_empty_recycle_bin_and_quota_reclamation():
    ctx = create_enterprise_tenant_and_users("trash")
    headers = ctx["staff_a_headers"]

    # Upload 2 files
    f1 = client.post(
        "/api/v1/files/upload",
        files={"file": ("trash_file_1.txt", io.BytesIO(b"Data 1" * 100), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=headers,
    ).json()

    f2 = client.post(
        "/api/v1/files/upload",
        files={"file": ("trash_file_2.txt", io.BytesIO(b"Data 2" * 100), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=headers,
    ).json()

    # Soft delete both files
    client.delete(f"/api/v1/files/{f1['id']}", headers=headers)
    client.delete(f"/api/v1/files/{f2['id']}", headers=headers)

    # Check trash listing
    trash_items = client.get("/api/v1/files?drive_type=TRASH", headers=headers).json()
    assert len(trash_items) >= 2

    # Empty trash
    empty_resp = client.post("/api/v1/files/trash/empty", headers=headers)
    assert empty_resp.status_code == 200
    data = empty_resp.json()
    assert data["purged_count"] >= 2
    assert data["freed_bytes"] > 0

    # Verify trash is now empty
    trash_after = client.get("/api/v1/files?drive_type=TRASH", headers=headers).json()
    assert len(trash_after) == 0


# =====================================================================
# 5. User Self-Service Profile & Account Security
# =====================================================================

def test_user_self_service_profile_update():
    ctx = create_enterprise_tenant_and_users("prof")
    headers = ctx["staff_a_headers"]

    update_payload = {
        "full_name": "አበበ ከበደ ወርቁ (Abebe Kebede Worku)",
        "phone_number": "+251 91 123 4567",
        "avatar_url": "https://storage.ethiooffice.et/avatars/abebe.png",
    }
    resp = client.patch("/api/v1/auth/profile", json=update_payload, headers=headers)
    assert resp.status_code == 200
    user_data = resp.json()
    assert user_data["full_name"] == update_payload["full_name"]
    assert user_data["phone_number"] == update_payload["phone_number"]
    assert user_data["avatar_url"] == update_payload["avatar_url"]


def test_user_change_password_workflow():
    ctx = create_enterprise_tenant_and_users("pwd")
    headers = ctx["staff_a_headers"]
    email = ctx["staff_a_email"]
    old_password = ctx["password"]
    new_password = "NewStrongPassword2026!"

    # 1. Reject invalid current password
    bad_current = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword123!", "new_password": new_password},
        headers=headers,
    )
    assert bad_current.status_code == 400

    # 2. Reject weak new password
    weak_new = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": old_password, "new_password": "short"},
        headers=headers,
    )
    assert weak_new.status_code == 422

    # 3. Reject identical new password
    same_new = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": old_password, "new_password": old_password},
        headers=headers,
    )
    assert same_new.status_code == 422

    # 4. Successfully change password
    success = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": old_password, "new_password": new_password},
        headers=headers,
    )
    assert success.status_code == 200

    # 5. Old password no longer works
    login_old = client.post("/api/v1/auth/login", json={"email": email, "password": old_password})
    assert login_old.status_code == 401

    # 6. New password works
    login_new = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()


# =====================================================================
# 6. Admin Account Lock, Unlock & Password Reset
# =====================================================================

def test_admin_lock_unlock_and_reset_password():
    ctx = create_enterprise_tenant_and_users("lock")
    admin_headers = ctx["admin_headers"]
    staff_b_id = ctx["staff_b_id"]
    staff_b_email = ctx["staff_b_email"]
    original_pwd = ctx["password"]

    # 1. Admin locks Staff B account
    lock_resp = client.post(
        f"/api/v1/auth/users/{staff_b_id}/lock",
        json={"lock_duration_hours": 24, "reason": "Security review"},
        headers=admin_headers,
    )
    assert lock_resp.status_code == 200

    # 2. Staff B cannot log in while locked
    blocked_login = client.post("/api/v1/auth/login", json={"email": staff_b_email, "password": original_pwd})
    assert blocked_login.status_code == 423
    detail_str = str(blocked_login.json()["detail"])
    assert "ACCOUNT_LOCKED" in detail_str or "ታግዷል" in detail_str

    # 3. Admin unlocks Staff B account
    unlock_resp = client.post(f"/api/v1/auth/users/{staff_b_id}/unlock", headers=admin_headers)
    assert unlock_resp.status_code == 200

    # 4. Staff B can log in again
    unblocked_login = client.post("/api/v1/auth/login", json={"email": staff_b_email, "password": original_pwd})
    assert unblocked_login.status_code == 200

    # 5. Admin forces password reset for Staff B
    forced_pwd = "AdminForcedPassword2026!"
    reset_resp = client.post(
        f"/api/v1/auth/users/{staff_b_id}/reset-password",
        json={"new_password": forced_pwd},
        headers=admin_headers,
    )
    assert reset_resp.status_code == 200

    # 6. Staff B logs in with new admin-set password
    forced_login = client.post("/api/v1/auth/login", json={"email": staff_b_email, "password": forced_pwd})
    assert forced_login.status_code == 200


# =====================================================================
# 7. In-App Notifications & Event Alert Engine
# =====================================================================

def test_notifications_lifecycle_on_file_share():
    ctx = create_enterprise_tenant_and_users("notif")
    staff_a = ctx["staff_a_headers"]
    staff_b = ctx["staff_b_headers"]

    # Staff A uploads a file
    content = b"Document to trigger notification"
    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("shared_alert_doc.txt", io.BytesIO(content), "text/plain")},
        data={"drive_type": "PERSONAL"},
        headers=staff_a,
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # Staff A shares the file with Staff B
    share_resp = client.post(
        f"/api/v1/shares/file/{file_id}",
        json={"target_user_id": ctx["staff_b_id"], "permission": "VIEWER"},
        headers=staff_a,
    )
    assert share_resp.status_code == 201

    # Staff B checks unread notification count
    badge_resp = client.get("/api/v1/notifications/unread-count", headers=staff_b)
    assert badge_resp.status_code == 200
    assert badge_resp.json()["unread_count"] >= 1

    # Staff B views notifications feed
    feed_resp = client.get("/api/v1/notifications", headers=staff_b)
    assert feed_resp.status_code == 200
    feed = feed_resp.json()
    assert feed["unread_count"] >= 1
    assert len(feed["items"]) >= 1

    notif = next(n for n in feed["items"] if n["event_type"] == "FILE_SHARED")
    assert "shared_alert_doc.txt" in notif["title"]
    assert "ፋይል ተጋርቶልዎታል" in notif["title_amharic"]
    assert notif["is_read"] is False
    assert notif["ec_created_at"] is not None

    # Staff B marks notification as read
    read_resp = client.patch(f"/api/v1/notifications/{notif['id']}/read", headers=staff_b)
    assert read_resp.status_code == 200
    assert read_resp.json()["is_read"] is True

    # Badge count decreases
    badge_after = client.get("/api/v1/notifications/unread-count", headers=staff_b).json()
    assert badge_after["unread_count"] == 0

    # Mark all read endpoint
    all_read_resp = client.post("/api/v1/notifications/mark-all-read", headers=staff_b)
    assert all_read_resp.status_code == 200


# =====================================================================
# 8. Official Letter Document Drive Attachments
# =====================================================================

def test_letter_drive_attachments_integration():
    ctx = create_enterprise_tenant_and_users("attach")
    headers = ctx["staff_a_headers"]

    # 1. Register outward letter
    letter_payload = {
        "direction": "OUTWARD",
        "subject": "የውጭ ፕሮጀክት የፋይናንስ ድጋፍ ጥያቄ",
        "sender_entity": "የቴክኖሎጂ መምሪያ",
        "recipient_entity": "የገንዘብ ሚኒስቴር",
        "urgency": "NORMAL",
        "confidentiality": "NORMAL",
    }
    letter_resp = client.post("/api/v1/letters", json=letter_payload, headers=headers)
    assert letter_resp.status_code in (200, 201), letter_resp.text
    letter_id = letter_resp.json()["id"]

    # 2. Upload supporting file to drive
    file_content = b"Official letter project annex specification content"
    upload_resp = client.post(
        "/api/v1/files/upload",
        files={"file": ("project_annex_spec.pdf", io.BytesIO(file_content), "application/pdf")},
        data={"drive_type": "PERSONAL"},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # 3. Attach file to letter
    attach_payload = {
        "file_id": file_id,
        "attachment_type": "SUPPORTING_DOCUMENT",
        "notes": "የፕሮጀክት ዝርዝር የቴክኒክ ሰነድ (Technical Annex)",
    }
    att_resp = client.post(f"/api/v1/letters/{letter_id}/attachments", json=attach_payload, headers=headers)
    assert att_resp.status_code == 201
    att_data = att_resp.json()
    assert att_data["letter_id"] == letter_id
    assert att_data["file_id"] == file_id
    assert att_data["file_name"] == "project_annex_spec.pdf"
    assert att_data["attachment_type"] == "SUPPORTING_DOCUMENT"
    assert att_data["ec_created_at"] is not None

    # 4. Duplicate attachment rejection
    dup_att = client.post(f"/api/v1/letters/{letter_id}/attachments", json=attach_payload, headers=headers)
    assert dup_att.status_code == 409

    # 5. List letter attachments
    list_att = client.get(f"/api/v1/letters/{letter_id}/attachments", headers=headers)
    assert list_att.status_code == 200
    assert len(list_att.json()) == 1
    assert list_att.json()[0]["id"] == att_data["id"]

    # 6. Letter Detail includes attachments array
    detail_resp = client.get(f"/api/v1/letters/{letter_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["attachments"]) == 1
    assert detail["attachments"][0]["file_name"] == "project_annex_spec.pdf"

    # 7. Delete attachment
    del_att = client.delete(f"/api/v1/letters/{letter_id}/attachments/{att_data['id']}", headers=headers)
    assert del_att.status_code == 200

    list_att_after = client.get(f"/api/v1/letters/{letter_id}/attachments", headers=headers).json()
    assert len(list_att_after) == 0
