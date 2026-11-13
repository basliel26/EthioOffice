"""
Ethiopian Calendar (ባሕረ ሐሳብ) Conversion Utility.
Provides mathematically exact bi-directional conversion between Gregorian Calendar (GC)
and Ethiopian Calendar (EC), formatted Amharic strings, and fiscal year calculations.
"""

from datetime import date
from typing import Tuple

# Month names in Amharic and English phonetics
ETHIOPIAN_MONTHS = [
    ("መስከረም", "Meskerem"),
    ("ጥቅምት", "Tikimt"),
    ("ኅዳር", "Hidar"),
    ("ታኅሣሥ", "Tahsas"),
    ("ጥር", "Tir"),
    ("የካቲት", "Yakatit"),
    ("መጋቢት", "Megabit"),
    ("ሚያዝያ", "Miazia"),
    ("ግንቦት", "Ginbot"),
    ("ሰኔ", "Sene"),
    ("ሐምሌ", "Hamle"),
    ("ነሐሴ", "Nehase"),
    ("ጳጉሜ", "Pagume"),
]

# Era anchor for Ethiopian calendar in Julian Day Number
JD_OFFSET = 1723856


def gregorian_to_jdn(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def jdn_to_gregorian(jdn: int) -> Tuple[int, int, int]:
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return year, month, day


def gregorian_to_ethiopian(g_date: date) -> Tuple[int, int, int]:
    """
    Converts a Gregorian date (datetime.date) to Ethiopian date tuple (year, month, day).
    """
    jdn = gregorian_to_jdn(g_date.year, g_date.month, g_date.day)
    r = (jdn - JD_OFFSET) % 1461
    n = (r % 365) + 365 * (r // 1460)
    year = 4 * ((jdn - JD_OFFSET) // 1461) + (r // 365) - (r // 1460)
    month = (n // 30) + 1
    day = (n % 30) + 1
    return year, month, day


def ethiopian_to_gregorian(e_year: int, e_month: int, e_day: int) -> date:
    """
    Converts an Ethiopian date (year, month, day) to a Gregorian date (datetime.date).
    """
    jdn = (JD_OFFSET + 365) + 365 * (e_year - 1) + (e_year // 4) + 30 * (e_month - 1) + e_day - 1
    gy, gm, gd = jdn_to_gregorian(jdn)
    return date(gy, gm, gd)


def format_ethiopian_date(g_date: date, in_amharic: bool = True) -> str:
    """
    Returns a formatted Ethiopian date string.
    Example: '4 ኅዳር 2019 ዓ.ም' or '4 Hidar 2019 E.C.'
    """
    e_year, e_month, e_day = gregorian_to_ethiopian(g_date)
    month_name = ETHIOPIAN_MONTHS[e_month - 1][0] if in_amharic else ETHIOPIAN_MONTHS[e_month - 1][1]
    suffix = "ዓ.ም" if in_amharic else "E.C."
    return f"{e_day} {month_name} {e_year} {suffix}"


def get_ethiopian_fiscal_year(g_date: date) -> Tuple[date, date]:
    """
    Returns the Gregorian start and end dates for the Ethiopian fiscal year (Hamle 1 - Sene 30).
    """
    e_year, e_month, _ = gregorian_to_ethiopian(g_date)
    fiscal_year = e_year if e_month >= 11 else e_year - 1
    start_date = ethiopian_to_gregorian(fiscal_year, 11, 1)  # 1 Hamle
    end_date = ethiopian_to_gregorian(fiscal_year + 1, 10, 30)  # 30 Sene
    return start_date, end_date
