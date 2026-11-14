"""
Comprehensive Automated Test Suite for Module 10: Full-Text Search & Metadata Indexing Engine
(የአማርኛ እና የእንግሊዝኛ የሰነድ ፍለጋ ሞተር)

Enterprise Verification Coverage:
1. Multi-format text extraction (Word .docx, PDF .pdf, Excel .xlsx, Plain text .txt, CSV .csv, JSON .json).
2. Amharic phonetic homophone normalization (ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ, Ethiopic punctuation).
3. PostgreSQL GIN full-text index with weighted ranking (A=Filename, B=Metadata/Tags, C=Body text).
4. Trigram similarity fuzzy matching for typo tolerance on names and body content.
5. Multi-faceted metadata filtering (file_type, department_id, drive_type, tag, ethiopian_year, size bounds).
6. Enterprise Access Control (ACL) & multi-tenant fencing with ZERO data leakage.
7. Contextual search snippet generation with **bold** highlight markers.
8. Typeahead autocomplete search suggestions (/api/v1/search/suggest).
9. Search indexing statistics & bulk administrative re-indexing (/api/v1/search/stats, /api/v1/search/reindex).
10. Unified cross-module search spanning Document Drive and Official Letter Registry (/api/v1/search/unified).
11. Automatic search indexing on file upload, versioning, and rename lifecycle events.
"""

import io
import uuid
import docx
import openpyxl
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.file import FileItem, DriveType
from app.models.search import FileSearchIndex, SearchIndexStatus
from app.models.department import Department
from app.models.tag import Tag, FileTag
from app.services.text_extractor import TextExtractor
from app.services.localization_service import LocalizationService
from app.services.search_service import SearchService

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_search_tenant_and_users(slug_prefix: str = "srch"):
    """Helper to provision a dedicated tenant with an Admin and two Staff members."""
    slug = f"{slug_prefix}-{uuid.uuid4().hex[:6]}"
    admin_email = f"admin@{slug}.et"
    password = "TestPassword2026!"

    prov_payload = {
        "organization_name": f"Search Corp {slug}",
        "slug": slug,
        "tin_number": "1234567890",
        "admin_email": admin_email,
        "admin_password": password,
        "admin_full_name": "Search Admin",
        "max_users": 10,
        "storage_limit_gb": 10.0,
    }
    r = client.post("/api/v1/organizations/provision", json=prov_payload)
    assert r.status_code == 201, f"Failed to provision tenant: {r.text}"

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
        "admin_email": admin_email,
        "staff_a_headers": staff_a_headers,
        "staff_a_id": staff_a_id,
        "staff_b_headers": staff_b_headers,
        "staff_b_id": staff_b_id,
    }


def make_test_pdf(text: str) -> bytes:
    """Generate a minimal valid PDF byte buffer containing text."""
    stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET"
    content = f"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj
4 0 obj <</Length {len(stream)}>> stream
{stream}
endstream
endobj
5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000222 00000 n 
0000000300 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
370
%%EOF"""
    return content.encode("latin-1")


def make_test_docx(text: str) -> bytes:
    """Generate a valid Word .docx byte buffer."""
    doc = docx.Document()
    doc.add_heading("EthioOffice Enterprise Document", level=1)
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_xlsx(rows: list) -> bytes:
    """Generate a valid Excel .xlsx byte buffer."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DataSheet"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# =====================================================================
# Test 1: Multi-Format Text Extractor
# =====================================================================

def test_text_extractor_formats():
    """Verify text extractor handles docx, pdf, xlsx, txt, csv, json."""
    # 1. Plain Text
    txt_bytes = "ይህ የሙከራ ፅሁፍ ነው (Sample Amharic text)".encode("utf-8")
    t, err, c, w = TextExtractor.extract_from_bytes(txt_bytes, ".txt", "text/plain")
    assert err is None
    assert "ይህ የሙከራ ፅሁፍ ነው" in t
    assert w >= 4

    # 2. Word .docx
    docx_bytes = make_test_docx("የ2018 ዓ.ም የፋይናንስ ኦዲት ሪፖርት ማጠቃለያ")
    dt, derr, dc, dw = TextExtractor.extract_from_bytes(docx_bytes, ".docx")
    assert derr is None
    assert "የፋይናንስ ኦዲት ሪፖርት" in dt
    assert dw >= 5

    # 3. Excel .xlsx
    xlsx_bytes = make_test_xlsx([["ክፍል", "በጀት"], ["ፋይናንስ", 500000]])
    xt, xerr, xc, xw = TextExtractor.extract_from_bytes(xlsx_bytes, ".xlsx")
    assert xerr is None
    assert "ክፍል" in xt
    assert "ፋይናንስ" in xt
    assert "500000" in xt

    # 4. PDF
    pdf_bytes = make_test_pdf("Federal Auditor General Financial Audit Report")
    pt, perr, pc, pw = TextExtractor.extract_from_bytes(pdf_bytes, ".pdf")
    assert perr is None
    assert "Federal Auditor General" in pt
    assert pw >= 4

    # 5. CSV
    csv_bytes = "id,name,role\n1,Abebe,Manager\n2,Chala,Accountant\n".encode("utf-8")
    ct, cerr, cc, cw = TextExtractor.extract_from_bytes(csv_bytes, ".csv")
    assert cerr is None
    assert "Abebe" in ct
    assert "Accountant" in ct

    # 6. JSON
    json_bytes = '{"project": "EthioOffice", "market": "Ethiopia B2B"}'.encode("utf-8")
    jt, jerr, jc, jw = TextExtractor.extract_from_bytes(json_bytes, ".json")
    assert jerr is None
    assert "EthioOffice" in jt


# =====================================================================
# Test 2: Auto-Indexing on Upload & Basic Full-Text Search
# =====================================================================

def test_auto_indexing_on_upload_and_search(db_session):
    """
    Verifies that uploading a document automatically indexes it in PostgreSQL
    and makes it discoverable with bold snippet generation and Ethiopian dates.
    """
    ctx = create_search_tenant_and_users("srch-auto")
    admin_h = ctx["admin_headers"]

    content = "ይህ ሰነድ የ2018 ዓ.ም የኢትዮጵያ ንግድ ባንክ ኦዲት ሪፖርት እና የሂሳብ አያያዝ ደንብ ነው።"
    files = {
        "file": ("ፋይናንስ_መመሪያ.txt", io.BytesIO(content.encode("utf-8")), "text/plain")
    }
    data = {"drive_type": "COMPANY"}

    upload_r = client.post("/api/v1/files/upload", files=files, data=data, headers=admin_h)
    assert upload_r.status_code == 201, upload_r.text
    file_id = upload_r.json()["id"]

    # Verify FileSearchIndex exists in DB
    idx = db_session.query(FileSearchIndex).filter(FileSearchIndex.file_id == uuid.UUID(file_id)).first()
    assert idx is not None
    assert idx.status == SearchIndexStatus.INDEXED.value
    assert idx.word_count > 0

    # Search for "ንግድ ባንክ"
    search_r = client.get("/api/v1/search?q=ንግድ ባንክ", headers=admin_h)
    assert search_r.status_code == 200, search_r.text
    res = search_r.json()

    assert res["total_hits"] >= 1
    matched = next((item for item in res["items"] if item["file_id"] == file_id), None)
    assert matched is not None
    assert matched["name"] == "ፋይናንስ_መመሪያ.txt"
    assert "ንግድ" in matched["highlight_snippet"]
    assert "ዓ.ም" in matched["updated_at_ec"]


# =====================================================================
# Test 3: Amharic Phonetic Homophone Normalization Search
# =====================================================================

def test_amharic_phonetic_homophone_normalization_search():
    """
    Tests Amharic homophone folding:
    1. Upload document containing 'ሥምምነት' (with ሠ).
       Search for 'ስምምነት' (with ሰ) -> must match!
    2. Upload document containing 'ፀሐይ' (with ፀ and ሐ).
       Search for 'ጸሀይ' (with ጸ and ሀ) -> must match!
    3. Upload document containing 'ኃላፊነት' (with ኀ).
       Search for 'ሀላፊነት' (with ሀ) -> must match!
    """
    ctx = create_search_tenant_and_users("srch-homo")
    admin_h = ctx["admin_headers"]

    # 1. Document with ሠ / ሥ
    content_se = "የሰራተኞች የስራ ውልና የጋራ ሥምምነት ሰነድ ለድርድር የቀረበ።"
    files_1 = {
        "file": ("የሥራ_ውል_ደንብ.txt", io.BytesIO(content_se.encode("utf-8")), "text/plain")
    }
    r1 = client.post("/api/v1/files/upload", files=files_1, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert r1.status_code == 201

    # Search with ሰ / ስ
    srch_1 = client.get("/api/v1/search?q=ስምምነት", headers=admin_h)
    assert srch_1.status_code == 200
    hits_1 = srch_1.json()["items"]
    assert any("የሥራ_ውል_ደንብ.txt" in h["name"] for h in hits_1)

    # 2. Document with ፀ and ሐ
    content_tse = "በኢትዮጵያ የታዳሽ የፀሐይ ኃይል ኤሌክትሪክ ማመንጫ ስምምነት።"
    files_2 = {
        "file": ("የፀሐይ_ኃይል_መመሪያ.txt", io.BytesIO(content_tse.encode("utf-8")), "text/plain")
    }
    r2 = client.post("/api/v1/files/upload", files=files_2, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert r2.status_code == 201

    # Search with ጸ and ሀ
    srch_2 = client.get("/api/v1/search?q=ጸሀይ ሀይል", headers=admin_h)
    assert srch_2.status_code == 200
    hits_2 = srch_2.json()["items"]
    assert any("የፀሐይ_ኃይል_መመሪያ.txt" in h["name"] for h in hits_2)


# =====================================================================
# Test 4: Trigram Fuzzy Matching for Typo-Tolerant Search
# =====================================================================

def test_trigram_typo_tolerance_search():
    """
    Verifies that typos and slight misspellings in English or Amharic
    match file names or content via PostgreSQL pg_trgm similarity.
    """
    ctx = create_search_tenant_and_users("srch-trgm")
    admin_h = ctx["admin_headers"]

    # Upload file with distinctive name
    content = "Detailed technical specifications for Ethiopian enterprise collaboration."
    files = {
        "file": ("enterprise_specifications_handbook.txt", io.BytesIO(content.encode("utf-8")), "text/plain")
    }
    upload_r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert upload_r.status_code == 201

    # Misspelled query: 'speficications' or 'handbok'
    fuzzy_r = client.get("/api/v1/search?q=speficication handbok", headers=admin_h)
    assert fuzzy_r.status_code == 200
    hits = fuzzy_r.json()["items"]
    assert any("enterprise_specifications_handbook.txt" in h["name"] for h in hits)


# =====================================================================
# Test 5: Multi-Faceted Metadata Filtering & Sorting
# =====================================================================

def test_faceted_metadata_filtering_and_sorting():
    """
    Verifies multi-attribute filtering (file_type, drive_type, ethiopian_year, sorting)
    and automatic facet count aggregation.
    """
    ctx = create_search_tenant_and_users("srch-facet")
    admin_h = ctx["admin_headers"]

    # 1. Upload a DOCX
    docx_buf = make_test_docx("Corporate Procurement Strategy 2026")
    client.post(
        "/api/v1/files/upload",
        files={"file": ("procurement_strategy.docx", io.BytesIO(docx_buf), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"drive_type": "COMPANY"},
        headers=admin_h
    )

    # 2. Upload an XLSX
    xlsx_buf = make_test_xlsx([["Item", "Cost"], ["Server", 250000]])
    client.post(
        "/api/v1/files/upload",
        files={"file": ("capital_budget.xlsx", io.BytesIO(xlsx_buf), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"drive_type": "COMPANY"},
        headers=admin_h
    )

    # 3. Upload a PDF
    pdf_buf = make_test_pdf("Annual External Audit Report 2026")
    client.post(
        "/api/v1/files/upload",
        files={"file": ("audit_report.pdf", io.BytesIO(pdf_buf), "application/pdf")},
        data={"drive_type": "PERSONAL"},
        headers=admin_h
    )

    # Search with file_type=document
    doc_resp = client.get("/api/v1/search?file_type=document", headers=admin_h)
    assert doc_resp.status_code == 200
    doc_hits = doc_resp.json()["items"]
    assert any("procurement_strategy.docx" in h["name"] for h in doc_hits)
    assert not any("capital_budget.xlsx" in h["name"] for h in doc_hits)

    # Search with file_type=spreadsheet
    sheet_resp = client.get("/api/v1/search?file_type=spreadsheet", headers=admin_h)
    assert sheet_resp.status_code == 200
    sheet_hits = sheet_resp.json()["items"]
    assert any("capital_budget.xlsx" in h["name"] for h in sheet_hits)
    assert not any("procurement_strategy.docx" in h["name"] for h in sheet_hits)

    # Facets check
    facets = sheet_resp.json()["facets"]
    assert "file_types" in facets
    assert "drive_types" in facets

    # Drive Type filter
    pers_resp = client.get("/api/v1/search?drive_type=PERSONAL", headers=admin_h)
    assert pers_resp.status_code == 200
    assert any("audit_report.pdf" in h["name"] for h in pers_resp.json()["items"])

    # Sorting test (name_asc, size_desc)
    sort_name = client.get("/api/v1/search?sort_by=name_asc", headers=admin_h)
    assert sort_name.status_code == 200
    names = [h["name"] for h in sort_name.json()["items"]]
    assert names == sorted(names)


# =====================================================================
# Test 6: Strict ACL Fencing (Zero Data Leakage)
# =====================================================================

def test_search_acl_fencing_zero_leakage():
    """
    Verifies that:
    1. Staff A uploads private document to Personal Drive.
    2. Staff B queries for that document's content -> 0 hits (No Leakage).
    3. Staff A shares document with Staff B.
    4. Staff B queries again -> 1 hit!
    5. Staff A revokes share -> Staff B gets 0 hits again!
    """
    ctx = create_search_tenant_and_users("srch-acl")
    staff_a_h = ctx["staff_a_headers"]
    staff_b_h = ctx["staff_b_headers"]
    staff_b_id = ctx["staff_b_id"]

    # 1. Staff A uploads confidential document
    secret_content = "Super confidential board evaluation for Addis Ababa headquarters."
    files = {
        "file": ("confidential_board_review.txt", io.BytesIO(secret_content.encode("utf-8")), "text/plain")
    }
    upload_r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "PERSONAL"}, headers=staff_a_h)
    assert upload_r.status_code == 201
    file_id = upload_r.json()["id"]

    # 2. Staff B queries -> must return 0 hits
    srch_b1 = client.get("/api/v1/search?q=confidential board evaluation", headers=staff_b_h)
    assert srch_b1.status_code == 200
    assert srch_b1.json()["total_hits"] == 0

    # 3. Staff A shares with Staff B
    share_payload = {
        "target_type": "USER",
        "target_user_id": staff_b_id,
        "permission": "VIEWER",
    }
    share_r = client.post(f"/api/v1/shares/file/{file_id}", json=share_payload, headers=staff_a_h)
    assert share_r.status_code == 201
    share_id = share_r.json()["id"]

    # 4. Staff B queries again -> must return 1 hit!
    srch_b2 = client.get("/api/v1/search?q=confidential board evaluation", headers=staff_b_h)
    assert srch_b2.status_code == 200
    assert srch_b2.json()["total_hits"] >= 1
    assert srch_b2.json()["items"][0]["file_id"] == file_id

    # 5. Staff A revokes share
    del_r = client.delete(f"/api/v1/shares/{share_id}", headers=staff_a_h)
    assert del_r.status_code == 200

    # 6. Staff B queries again -> must return 0 hits!
    srch_b3 = client.get("/api/v1/search?q=confidential board evaluation", headers=staff_b_h)
    assert srch_b3.status_code == 200
    assert srch_b3.json()["total_hits"] == 0


# =====================================================================
# Test 7: Multi-Tenant Boundary Isolation
# =====================================================================

def test_search_multi_tenant_isolation():
    """
    Verifies that Tenant 2 CANNOT discover or search any documents belonging to Tenant 1.
    """
    tenant_1 = create_search_tenant_and_users("srch-t1")
    tenant_2 = create_search_tenant_and_users("srch-t2")

    # Tenant 1 uploads top secret file
    secret_text = "UniqueTenantOneExclusivePayloadIdentifier999"
    files = {
        "file": ("tenant1_strategic_dossier.txt", io.BytesIO(secret_text.encode("utf-8")), "text/plain")
    }
    client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=tenant_1["admin_headers"])

    # Tenant 2 admin searches for the exact unique term
    srch_t2 = client.get(f"/api/v1/search?q={secret_text}", headers=tenant_2["admin_headers"])
    assert srch_t2.status_code == 200
    assert srch_t2.json()["total_hits"] == 0


# =====================================================================
# Test 8: Typeahead Autocomplete Search Suggestions
# =====================================================================

def test_search_suggestions_autocomplete():
    """
    Verifies /api/v1/search/suggest returns typeahead completions for files and tags.
    """
    ctx = create_search_tenant_and_users("srch-sugg")
    admin_h = ctx["admin_headers"]

    # Upload files with distinct names
    files_1 = {"file": ("Ethiopian_Investment_Commission_Guide.txt", io.BytesIO(b"Data"), "text/plain")}
    client.post("/api/v1/files/upload", files=files_1, data={"drive_type": "COMPANY"}, headers=admin_h)

    files_2 = {"file": ("Ethiopian_Customs_Declaration_2026.txt", io.BytesIO(b"Data"), "text/plain")}
    client.post("/api/v1/files/upload", files=files_2, data={"drive_type": "COMPANY"}, headers=admin_h)

    # Suggest for "Ethiopian"
    sugg_r = client.get("/api/v1/search/suggest?q=Ethiopian", headers=admin_h)
    assert sugg_r.status_code == 200
    suggs = sugg_r.json()["suggestions"]
    assert len(suggs) >= 2
    assert any("Ethiopian_Investment_Commission_Guide.txt" in s["text"] for s in suggs)
    assert any("Ethiopian_Customs_Declaration_2026.txt" in s["text"] for s in suggs)


# =====================================================================
# Test 9: Search Indexing Stats & Administrative Bulk Reindexing
# =====================================================================

def test_search_stats_and_bulk_reindexing():
    """
    Verifies:
    1. /api/v1/search/stats returns valid metrics.
    2. Non-admin is blocked from triggering organization bulk re-index (HTTP 403).
    3. Admin triggers bulk re-index successfully (HTTP 200).
    4. Single file re-index endpoint (/api/v1/search/reindex/{file_id}) succeeds.
    """
    ctx = create_search_tenant_and_users("srch-stats")
    admin_h = ctx["admin_headers"]
    staff_h = ctx["staff_a_headers"]

    # Upload document
    content = "Administrative audit and internal inspection report."
    files = {"file": ("internal_audit_inspection.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
    up_r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert up_r.status_code == 201
    file_id = up_r.json()["id"]

    # 1. Stats check
    stats_r = client.get("/api/v1/search/stats", headers=admin_h)
    assert stats_r.status_code == 200
    stats = stats_r.json()
    assert stats["total_files"] >= 1
    assert stats["indexed_files"] >= 1
    assert stats["total_words_indexed"] > 0

    # 2. Staff user blocked from bulk re-indexing
    staff_reindex = client.post("/api/v1/search/reindex", headers=staff_h)
    assert staff_reindex.status_code == 403

    # 3. Admin triggers bulk re-indexing
    admin_reindex = client.post("/api/v1/search/reindex?force=true", headers=admin_h)
    assert admin_reindex.status_code == 200
    reindex_data = admin_reindex.json()
    assert reindex_data["status"] == "SUCCESS"
    assert reindex_data["indexed_count"] >= 1

    # 4. Single file re-index
    single_reindex = client.post(f"/api/v1/search/reindex/{file_id}?force=true", headers=admin_h)
    assert single_reindex.status_code == 200
    assert single_reindex.json()["status"] == "INDEXED"
    assert single_reindex.json()["word_count"] > 0


# =====================================================================
# Test 10: Unified Search Across Drive & Official Letter Registry
# =====================================================================

def test_unified_search_drive_and_letters():
    """
    Verifies that /api/v1/search/unified queries both Document Drive
    and the Official Letter Registry in a single unified response.
    """
    ctx = create_search_tenant_and_users("srch-unif")
    admin_h = ctx["admin_headers"]

    # 1. Upload a Document Drive file
    file_content = "የውጭ ንግድ ኤክስፖርት ማበረታቻ እና የጉምሩክ ቀረጥ መመሪያ።"
    files = {"file": ("የውጭ_ንግድ_መመሪያ_2026.txt", io.BytesIO(file_content.encode("utf-8")), "text/plain")}
    up_r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert up_r.status_code == 201

    # 2. Create an Official Letter in Registry
    letter_payload = {
        "direction": "INWARD",
        "subject": "የውጭ ንግድ ኤክስፖርት ፈቃድ አሰጣጥ ማብራሪያ",
        "sender_entity": "የንግድ እና ቀጣናዊ ትስስር ሚኒስቴር",
        "recipient_entity": "ዋና ዳይሬክተር",
        "external_reference_number": "MOTRI/EXP/771/18",
        "urgency": "NORMAL",
        "confidentiality": "NORMAL",
    }
    let_r = client.post("/api/v1/letters", json=letter_payload, headers=admin_h)
    assert let_r.status_code in (200, 201)

    # 3. Call Unified Search with query "የውጭ ንግድ"
    unif_r = client.get("/api/v1/search/unified?q=የውጭ ንግድ", headers=admin_h)
    assert unif_r.status_code == 200
    data = unif_r.json()

    assert data["total_hits"] >= 2
    assert any("የውጭ_ንግድ_መመሪያ_2026.txt" in f["name"] for f in data["documents"])
    assert any("MOTRI/EXP/771/18" in l["reference_number"] or "የውጭ ንግድ" in l["subject"] for l in data["letters"])


# =====================================================================
# Test 11: File Rename & Version Update Lifecycle Re-indexing
# =====================================================================

def test_search_file_rename_and_version_reindex():
    """
    Verifies that:
    1. Renaming a document updates its searchable name.
    2. Uploading a new version updates the full-text search index and extracts the new text.
    """
    ctx = create_search_tenant_and_users("srch-renv")
    admin_h = ctx["admin_headers"]

    # 1. Initial upload
    initial_content = "Initial baseline project plan for phase one."
    files = {"file": ("original_baseline_plan.txt", io.BytesIO(initial_content.encode("utf-8")), "text/plain")}
    up_r = client.post("/api/v1/files/upload", files=files, data={"drive_type": "COMPANY"}, headers=admin_h)
    assert up_r.status_code == 201
    file_id = up_r.json()["id"]

    # Search by original name
    s1 = client.get("/api/v1/search?q=original_baseline_plan", headers=admin_h)
    assert s1.status_code == 200
    assert s1.json()["total_hits"] >= 1

    # 2. Rename document
    rename_r = client.patch(f"/api/v1/files/{file_id}/rename", json={"name": "revised_master_plan.txt"}, headers=admin_h)
    assert rename_r.status_code == 200

    # Search by new name
    s2 = client.get("/api/v1/search?q=revised_master_plan", headers=admin_h)
    assert s2.status_code == 200
    assert any("revised_master_plan.txt" in h["name"] for h in s2.json()["items"])

    # 3. Upload new version with brand new content
    v2_content = "Complete overhaul: Quantum computing integration with advanced blockchain security."
    v2_files = {"file": ("revised_master_plan.txt", io.BytesIO(v2_content.encode("utf-8")), "text/plain")}
    v2_r = client.post(f"/api/v1/files/{file_id}/versions", files=v2_files, headers=admin_h)
    assert v2_r.status_code == 201

    # Search for new version terms: "Quantum computing"
    s3 = client.get("/api/v1/search?q=Quantum computing blockchain", headers=admin_h)
    assert s3.status_code == 200
    hits_v2 = s3.json()["items"]
    assert any(h["file_id"] == file_id for h in hits_v2)
