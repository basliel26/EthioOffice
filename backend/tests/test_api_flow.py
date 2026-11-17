import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_calendar_today():
    r = client.get("/api/v1/calendar/today")
    assert r.status_code == 200
    data = r.json()
    assert "ethiopian_date" in data
    assert "ዓ.ም" in data["ethiopian_date"]["formatted_amharic"]


def test_auth_login_and_me():
    # Login as seeded admin
    r = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@abyssinia.et"
    assert data["user"]["role"] == "ADMIN"
    assert "abyssinia" in data["user"]["organization"]["slug"]

    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test /auth/me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@abyssinia.et"


def test_files_and_folders():
    # Login
    r = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # List Company Drive folders
    r_files = client.get("/api/v1/files?drive_type=COMPANY", headers=headers)
    assert r_files.status_code == 200
    files = r_files.json()
    assert len(files) >= 2
    assert any("የ2019" in f["name"] for f in files)

    # Create new folder
    unique_folder_name = f"የ2019 የኦዲት ግኝቶች {uuid.uuid4().hex[:6]}"
    create_resp = client.post(
        "/api/v1/files/folder",
        json={"name": unique_folder_name, "drive_type": "COMPANY"},
        headers=headers
    )
    assert create_resp.status_code in [200, 201]
    assert create_resp.json()["name"] == unique_folder_name


def test_letter_registry():
    # Login
    r = client.post("/api/v1/auth/login", json={"email": "admin@abyssinia.et", "password": "Admin123!"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # List letters
    r_letters = client.get("/api/v1/letters?search=ABYSS/FIN/2019/001", headers=headers)
    assert r_letters.status_code == 200
    letters = r_letters.json()
    assert len(letters) >= 1
    assert any(l["reference_number"] == "ABYSS/FIN/2019/001" for l in letters)
    assert "ዓ.ም" in letters[0]["date_ec"]

    # Register new outward letter
    create_letter_resp = client.post(
        "/api/v1/letters",
        json={
            "reference_number": "ABYSS/FIN/2019/002",
            "direction": "OUTWARD",
            "subject": "የዓመታዊ ኦዲት ሪፖርት አቅርቦት ማሳወቂያ",
            "sender_entity": "አቢሲንያ ኮሜርሻል ኢንተርፕራይዝ",
            "recipient_entity": "የንግድና ቀጣናዊ ትስስር ሚኒስቴር",
            "notes": "በአካል የተላከ"
        },
        headers=headers
    )
    assert create_letter_resp.status_code == 200
    assert create_letter_resp.json()["reference_number"] == "ABYSS/FIN/2019/002"
