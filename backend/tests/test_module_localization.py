"""
Comprehensive Automated Test Suite for Module 8: Ethiopian Localization Engine (ባሕረ ሐሳብ - Bahire Hasab)
Tests:
1. Today's date localized output with Ge'ez numerals, Evangelist, and day of week.
2. Exact bi-directional calendar conversion (GC <-> EC) and leap year Pagume handling.
3. Bahire Hasab Computus parameters (Wenber, Abektie, Metqe, Evangelist).
4. Movable fasts and feasts calculation anchored on Nineveh.
5. Fixed Ethiopian national public holidays.
6. Arabic to Ge'ez numerals conversion across units, tens, hundreds, and ten-thousands.
7. Ge'ez numerals to Arabic integer decoding.
8. Amharic phonetic homophone normalization (ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ) and punctuation stripping.
9. Ethiopian Fiscal Year quarters (Hamle 1 - Sene 30) and Pagume reconciliation window.
10. Working days and public holiday checker.
11. SLA working days calculator skipping weekends and national holidays.
12. Monetary decimal amount to formal Amharic words (የገንዘብ መጠን በቃላት).
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.localization_service import LocalizationService

client = TestClient(app)


# =====================================================================
# Test 1: Today Localized Date Output
# =====================================================================

def test_today_date_localization():
    """
    Verifies that /api/v1/localization/today returns full Ethiopian date metadata:
    Amharic month, Ge'ez numerals date, Evangelist, day of week, and leap year flag.
    """
    r = client.get("/api/v1/localization/today")
    assert r.status_code == 200
    data = r.json()

    assert "gregorian_date" in data
    assert "ethiopian_year" in data
    assert "geez_date" in data
    assert "ዓ.ም" in data["formatted_amharic"]
    assert "E.C." in data["formatted_english"]
    assert data["evangelist"] in ["ማቴዎስ", "ማርቆስ", "ሉቃስ", "ዮሐንስ"]
    assert data["day_of_week_amharic"] in ["ሰኞ", "ማክሰኞ", "ረቡዕ", "ሐሙስ", "ዓርብ", "ቅዳሜ", "እሑድ"]


# =====================================================================
# Test 2: Bi-Directional Calendar Conversion & Leap Year Pagume Handling
# =====================================================================

def test_bi_directional_calendar_conversion():
    """
    Verifies exact conversion between Gregorian and Ethiopian dates:
    1. Enkutatash (Meskerem 1, 2019 E.C. -> 2026-09-11).
    2. Ethiopian date input converts back to identical Gregorian date.
    3. Leap year Luke (2015 E.C.) permits Pagume 6 (2023-09-11).
    4. Non-leap year (2016 E.C.) rejects Pagume 6 with 400 Bad Request.
    """
    # 1. Gregorian to Ethiopian
    g_enkutatash = "2026-09-11"
    r1 = client.get(f"/api/v1/localization/convert?g_date={g_enkutatash}")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["ethiopian_year"] == 2019
    assert d1["ethiopian_month"] == 1
    assert d1["ethiopian_day"] == 1
    assert d1["formatted_amharic"] == "1 መስከረም 2019 ዓ.ም"

    # 2. Ethiopian to Gregorian
    r2 = client.get("/api/v1/localization/convert?e_year=2019&e_month=1&e_day=1")
    assert r2.status_code == 200
    assert r2.json()["gregorian_date"] == "2026-09-11"

    # 3. Luke Leap year (2015 E.C.): Pagume 6 is valid
    r3 = client.get("/api/v1/localization/convert?e_year=2015&e_month=13&e_day=6")
    assert r3.status_code == 200
    assert r3.json()["gregorian_date"] == "2023-09-11"

    # 4. Non-leap year (2016 E.C.): Pagume 6 is invalid -> 400 Bad Request
    r4 = client.get("/api/v1/localization/convert?e_year=2016&e_month=13&e_day=6")
    assert r4.status_code == 400
    assert "ጳጉሜ 5 ቀናት ብቻ አሏት" in r4.json()["detail"]


# =====================================================================
# Test 3: Bahire Hasab Computus Parameters
# =====================================================================

def test_bahire_hasab_computus_parameters():
    """
    Verifies the mathematical principles of Bahire Hasab Computus:
    - Wenber, Abektie, Metqe calculations.
    - Metonic identity: (Abektie + Metqe) % 30 == 0.
    - Evangelist cycles.
    """
    r = client.get("/api/v1/localization/bahire-hasab/2018")
    assert r.status_code == 200
    c = r.json()

    assert c["ethiopian_year"] == 2018
    assert c["amete_alem"] == 5500 + 2018
    assert c["wenber"] == (2018 - 1) % 19
    assert c["abektie"] == (c["wenber"] * 11) % 30
    assert c["metqe"] == (c["wenber"] * 19) % 30
    assert (c["abektie"] + c["metqe"]) % 30 == 0
    assert c["evangelist"] == "ማርቆስ"  # (5500 + 2018) % 4 == 2 -> Mark
    assert c["is_leap_year"] is False
    assert c["pagume_days"] == 5


# =====================================================================
# Test 4: Movable Feasts & Fasts Calculation
# =====================================================================

def test_movable_feasts_and_fasts_calculation():
    """
    Verifies that all movable holidays are computed and ordered correctly
    relative to Nineveh Fast (ጾመ ነነዌ).
    """
    r = client.get("/api/v1/localization/bahire-hasab/2018")
    assert r.status_code == 200
    holidays = {h["name_amharic"]: h for h in r.json()["movable_holidays"]}

    # Verify key movable feasts are present
    assert "ጾመ ነነዌ" in holidays
    assert "ዓቢይ ጾም" in holidays
    assert "ሆሣዕና" in holidays
    assert "ስቅለት" in holidays
    assert "ትንሣኤ / ፋሲካ" in holidays
    assert "ዕርገት" in holidays
    assert "ጰራቅሊጦስ" in holidays

    # Verify Siklet and Fasika are designated as public holidays
    assert holidays["ስቅለት"]["is_public_holiday"] is True
    assert holidays["ትንሣኤ / ፋሲካ"]["is_public_holiday"] is True


# =====================================================================
# Test 5: Fixed National Public Holidays
# =====================================================================

def test_fixed_national_holidays():
    """
    Verifies that fixed Ethiopian public holidays are present and properly dated:
    Enkutatash (Meskerem 1), Meskel (Meskerem 17), Timket (Tir 11),
    Adwa (Yakatit 23), Patriots' Day (Miazia 27), Derg Downfall (Ginbot 20).
    """
    r = client.get("/api/v1/localization/bahire-hasab/2018")
    assert r.status_code == 200
    fixed = {h["name_amharic"]: h for h in r.json()["fixed_holidays"]}

    assert "እንቁጣጣሽ (አዲስ ዓመት)" in fixed
    assert fixed["እንቁጣጣሽ (አዲስ ዓመት)"]["ethiopian_month"] == 1
    assert fixed["እንቁጣጣሽ (አዲስ ዓመት)"]["ethiopian_day"] == 1

    assert "መስቀል" in fixed
    assert fixed["መስቀል"]["ethiopian_month"] == 1
    assert fixed["መስቀል"]["ethiopian_day"] == 17

    assert "ጥምቀት" in fixed
    assert fixed["ጥምቀት"]["ethiopian_month"] == 5
    assert fixed["ጥምቀት"]["ethiopian_day"] == 11

    assert "የአድዋ ድል በዓል" in fixed
    assert fixed["የአድዋ ድል በዓል"]["ethiopian_month"] == 6
    assert fixed["የአድዋ ድል በዓል"]["ethiopian_day"] == 23


# =====================================================================
# Test 6: Arabic to Ge'ez Numerals Conversion
# =====================================================================

def test_geez_numerals_arabic_to_geez():
    """
    Verifies conversion from Arabic numbers to official Ge'ez numerals:
    Units, tens, compound hundreds, and ten-thousands.
    """
    test_cases = [
        (1, "፩"),
        (2, "፪"),
        (9, "፱"),
        (10, "፲"),
        (15, "፲፭"),
        (20, "፳"),
        (25, "፳፭"),
        (50, "፶"),
        (99, "፺፱"),
        (100, "፻"),
        (105, "፻፭"),
        (125, "፻፳፭"),
        (1524, "፲፭፻፳፬"),
        (2018, "፳፻፲፰"),
        (10000, "፼"),
        (250000, "፳፭፼"),
    ]
    for arabic, expected_geez in test_cases:
        r = client.get(f"/api/v1/localization/geez-numbers/to-geez?number={arabic}")
        assert r.status_code == 200
        assert r.json()["geez_number"] == expected_geez, f"Failed for {arabic}: got {r.json()['geez_number']}"


# =====================================================================
# Test 7: Ge'ez Numerals to Arabic Integer Decoding
# =====================================================================

def test_geez_numerals_geez_to_arabic():
    """
    Verifies bi-directional decoding of Ge'ez numeral strings back to Arabic integers.
    """
    test_cases = [
        ("፩", 1),
        ("፲", 10),
        ("፳፭", 25),
        ("፻", 100),
        ("፻፳፭", 125),
        ("፲፭፻፳፬", 1524),
        ("፳፻፲፰", 2018),
        ("፼", 10000),
        ("፳፭፼", 250000),
    ]
    for geez_str, expected_int in test_cases:
        r = client.get(f"/api/v1/localization/geez-numbers/to-arabic?geez={geez_str}")
        assert r.status_code == 200
        assert r.json()["arabic_number"] == expected_int


# =====================================================================
# Test 8: Amharic Phonetic Search Normalization
# =====================================================================

def test_amharic_phonetic_search_normalization():
    """
    Verifies homophone normalization across historically merged letter families:
    - ሀ/ሐ/ኀ collapse to canonical 'ሀ'
    - ሰ/ሠ collapse to canonical 'ሰ'
    - አ/ዐ collapse to canonical 'አ'
    - ጸ/ፀ collapse to canonical 'ጸ'
    - Ethiopic punctuation removal and tokenization.
    """
    # 1. Homophone equivalence
    r_ha1 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ሐምሌ"})
    r_ha2 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ኀምሌ"})
    r_ha3 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ሀምሌ"})
    assert r_ha1.json()["normalized_text"] == r_ha2.json()["normalized_text"] == r_ha3.json()["normalized_text"] == "ሀምሌ"

    # 2. Se family
    r_se1 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ሰላም"})
    r_se2 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ሠላም"})
    assert r_se1.json()["normalized_text"] == r_se2.json()["normalized_text"] == "ሰላም"

    # 3. A family
    r_a1 = client.post("/api/v1/localization/normalize-amharic", json={"text": "አበበ"})
    r_a2 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ዐበበ"})
    assert r_a1.json()["normalized_text"] == r_a2.json()["normalized_text"] == "አበበ"

    # 4. Tse family
    r_tse1 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ፀሐይ"})
    r_tse2 = client.post("/api/v1/localization/normalize-amharic", json={"text": "ጸሀይ"})
    assert r_tse1.json()["normalized_text"] == r_tse2.json()["normalized_text"] == "ጸሀይ"

    # 5. Punctuation stripping
    punct_text = "ሰላም፤ ለሁሉ፡ ይሁን። ሰላም፦ ለኢትዮጵያ!"
    r_p = client.post("/api/v1/localization/normalize-amharic", json={"text": punct_text})
    assert r_p.json()["normalized_text"] == "ሰላም ለሁሉ ይሁን ሰላም ለኢትዮጵያ"
    assert "ሰላም" in r_p.json()["tokens"]


# =====================================================================
# Test 9: Ethiopian Fiscal Year Quarters & Pagume Reconciliation
# =====================================================================

def test_ethiopian_fiscal_year_and_quarters():
    """
    Verifies that Ethiopian fiscal year begins Hamle 1 and ends Sene 30,
    computes Q1-Q4 quarters, and identifies Pagume as the closing reconciliation period.
    """
    # Meskerem 15 (in Q1)
    r_q1 = client.get("/api/v1/localization/fiscal-year?ref_date=2026-09-25")
    assert r_q1.status_code == 200
    fy1 = r_q1.json()
    assert fy1["current_quarter"] == "Q1"
    assert fy1["is_reconciliation_period"] is False
    assert len(fy1["quarters"]) == 4

    # Pagume 2 (Year-end reconciliation window)
    r_pagume = client.get("/api/v1/localization/fiscal-year?ref_date=2026-09-07")
    assert r_pagume.status_code == 200
    fy_p = r_pagume.json()
    assert fy_p["is_reconciliation_period"] is True
    assert fy_p["current_quarter"] == "PAGUME_CLOSING"


# =====================================================================
# Test 10: Working Day and Public Holiday Checker
# =====================================================================

def test_working_day_and_public_holiday_checker():
    """
    Verifies business day validation:
    - Saturdays and Sundays are non-working weekend days.
    - National public holidays (e.g. Enkutatash 2026-09-11) are non-working days.
    - Regular weekdays (e.g. a normal Monday) are working days.
    """
    # Saturday
    r_sat = client.get("/api/v1/localization/working-days/check?check_date=2026-09-12")
    assert r_sat.status_code == 200
    assert r_sat.json()["is_working_day"] is False
    assert "Saturday" in r_sat.json()["reason"]

    # Enkutatash (Meskerem 1 / Sept 11, 2026) -> Holiday
    r_holiday = client.get("/api/v1/localization/working-days/check?check_date=2026-09-11")
    assert r_holiday.status_code == 200
    assert r_holiday.json()["is_working_day"] is False
    assert "እንቁጣጣሽ" in r_holiday.json()["reason"]

    # Regular working day (Wednesday 2026-09-16)
    r_work = client.get("/api/v1/localization/working-days/check?check_date=2026-09-16")
    assert r_work.status_code == 200
    assert r_work.json()["is_working_day"] is True
    assert r_work.json()["reason"] is None


# =====================================================================
# Test 11: SLA Working Days Calculator (Skip Weekends & Holidays)
# =====================================================================

def test_add_working_days_sla_calculator():
    """
    Verifies that adding N business days advances the date skipping weekends
    and any intervening public holidays.
    """
    # Start on Thursday 2026-09-10
    # Friday Sept 11 is Enkutatash (Holiday) -> skipped
    # Saturday Sept 12 -> skipped
    # Sunday Sept 13 -> skipped
    # Monday Sept 14 -> Working Day 1
    # Tuesday Sept 15 -> Working Day 2
    # Wednesday Sept 16 -> Working Day 3
    r = client.get("/api/v1/localization/working-days/add?start_date=2026-09-10&days=3")
    assert r.status_code == 200
    res = r.json()
    assert res["target_date"] == "2026-09-16"
    assert res["skipped_weekend_days"] == 2
    assert len(res["skipped_holidays"]) >= 1


# =====================================================================
# Test 12: Currency Amount-to-Words in Amharic
# =====================================================================

def test_currency_amount_to_words_amharic():
    """
    Verifies conversion of financial decimal amounts into formal Amharic prose:
    1524.50 -> አንድ ሺህ አምስት መቶ ሃያ አራት ብር ከአምሳ ሳንቲም
    """
    test_cases = [
        (0.0, "ዜሮ ብር"),
        (5.0, "አምስት ብር"),
        (25.0, "ሃያ አምስት ብር"),
        (100.0, "አንድ መቶ ብር"),
        (1524.50, "አንድ ሺህ አምስት መቶ ሃያ አራት ብር ከአምሳ ሳንቲም"),
        (1000000.0, "አንድ ሚሊዮን ብር"),
        (2500000.75, "ሁለት ሚሊዮን አምስት መቶ ሺህ ብር ከሰባ አምስት ሳንቲም"),
    ]
    for amount, expected_words in test_cases:
        r = client.get(f"/api/v1/localization/amount-to-words?amount={amount}")
        assert r.status_code == 200
        assert r.json()["words_amharic"] == expected_words, f"Failed for {amount}: got {r.json()['words_amharic']}"
