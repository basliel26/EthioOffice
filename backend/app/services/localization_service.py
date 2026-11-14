"""
Comprehensive Domain Service for Module 8: Ethiopian Localization Engine (ባሕረ ሐሳብ - Bahire Hasab)
Pure-algorithmic, zero-external-dependency implementation covering:
1. Exact Bi-directional Gregorian <-> Ethiopian Calendar conversion with leap-year handling.
2. Complete Bahire Hasab Computus (Wenber, Abektie, Metqe, Evangelist, movable fasts/feasts).
3. Bi-directional Ge'ez numerals conversion (1 to 1,000,000+).
4. Amharic phonetic search normalizer (homophone collapsing for ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ).
5. Ethiopian fiscal year bounds, quarters, and Pagume reconciliation period.
6. Public holiday and working day SLA deadline calculator.
7. Currency amount-to-words spelling in formal Amharic prose.
"""

from datetime import date, timedelta
from typing import Tuple, List, Dict, Optional, Any
import re

from app.schemas.localization import (
    DateConversionResponse,
    HolidayItem,
    BahireHasabResponse,
    FiscalQuarterItem,
    FiscalYearResponse,
    WorkingDayCheckResponse,
    WorkingDaysAddResponse,
    AmountToWordsResponse,
)

# =====================================================================
# Constants & Reference Tables
# =====================================================================

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

AMHARIC_DAYS_OF_WEEK = [
    ("ሰኞ", "Monday"),
    ("ማክሰኞ", "Tuesday"),
    ("ረቡዕ", "Wednesday"),
    ("ሐሙስ", "Thursday"),
    ("ዓርብ", "Friday"),
    ("ቅዳሜ", "Saturday"),
    ("እሑድ", "Sunday"),
]

EVANGELISTS = [
    "ዮሐንስ",  # 0
    "ማቴዎስ",  # 1
    "ማርቆስ",  # 2
    "ሉቃስ",   # 3 (Leap Year)
]

# Julian Day Number offset for Ethiopian Calendar
JD_OFFSET = 1723856

# Ge'ez Numeral Glyphs
GEEZ_ONES = {
    1: "፩", 2: "፪", 3: "፫", 4: "፬", 5: "፭",
    6: "፮", 7: "፯", 8: "፰", 9: "፱"
}
GEEZ_TENS = {
    10: "፲", 20: "፳", 30: "፴", 40: "፵", 50: "፶",
    60: "፷", 70: "፸", 80: "፹", 90: "፺"
}
GEEZ_HUNDRED = "፻"
GEEZ_TEN_THOUSAND = "፼"

GEEZ_DIGIT_MAP = {
    "፩": 1, "፪": 2, "፫": 3, "፬": 4, "፭": 5,
    "፮": 6, "፯": 7, "፰": 8, "፱": 9,
    "፲": 10, "፳": 20, "፴": 30, "፵": 40, "፶": 50,
    "፷": 60, "፸": 70, "፹": 80, "፺": 90,
    "፻": 100, "፼": 10000
}

# Amharic Phonetic Homophone Normalization Mapping
AMHARIC_HOMOPHONE_MAP = {
    # Ha family -> ሀ
    'ሐ': 'ሀ', 'ኀ': 'ሀ',
    'ሑ': 'ሁ', 'ኁ': 'ሁ',
    'ሒ': 'ሂ', 'ኂ': 'ሂ',
    'ሓ': 'ሃ', 'ኃ': 'ሃ',
    'ሔ': 'ሄ', 'ኄ': 'ሄ',
    'ሕ': 'ህ', 'ኅ': 'ህ',
    'ሖ': 'ሆ', 'ኆ': 'ሆ',
    # Se family -> ሰ
    'ሠ': 'ሰ', 'ሡ': 'ሱ', 'ሢ': 'ሲ', 'ሣ': 'ሳ', 'ሤ': 'ሴ', 'ሥ': 'ስ', 'ሦ': 'ሶ',
    # A family -> አ
    'ዐ': 'አ', 'ዑ': 'ኡ', 'ዒ': 'ኢ', 'ዓ': 'ኣ', 'ዔ': 'ኤ', 'ዕ': 'እ', 'ዖ': 'ኦ',
    # Tse family -> ጸ
    'ፀ': 'ጸ', 'ፁ': 'ጹ', 'ፂ': 'ጺ', 'ፃ': 'ጻ', 'ፄ': 'ጼ', 'ፅ': 'ጽ', 'ፆ': 'ጾ',
}

AMHARIC_PUNCTUATION_REGEX = re.compile(r'[\u1361-\u1368\.,;:!?\(\)\[\]\{\}"\'`፦፨]+')

# Number-to-Words Amharic Vocabulary
AMHARIC_UNITS_WORDS = {
    0: "", 1: "አንድ", 2: "ሁለት", 3: "ሦስት", 4: "አራት",
    5: "አምስት", 6: "ስድስት", 7: "ሰባት", 8: "ስምንት", 9: "ዘጠኝ"
}
AMHARIC_TEENS_WORDS = {
    10: "አሥር", 11: "አሥራ አንድ", 12: "አሥራ ሁለት", 13: "አሥራ ሦስት",
    14: "አሥራ አራት", 15: "አሥራ አምስት", 16: "አሥራ ስድስት",
    17: "አሥራ ሰባት", 18: "አሥራ ስምንት", 19: "አሥራ ዘጠኝ"
}
AMHARIC_TENS_WORDS = {
    20: "ሃያ", 30: "ሠላሳ", 40: "አርባ", 50: "አምሳ",
    60: "ስድሳ", 70: "ሰባ", 80: "ሰማንያ", 90: "ዘጠና"
}


# =====================================================================
# Domain Service Implementation
# =====================================================================

class LocalizationService:

    # -----------------------------------------------------------------
    # 1. Calendar Bi-directional Conversion & Formatting
    # -----------------------------------------------------------------

    @classmethod
    def gregorian_to_jdn(cls, year: int, month: int, day: int) -> int:
        a = (14 - month) // 12
        y = year + 4800 - a
        m = month + 12 * a - 3
        return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045

    @classmethod
    def jdn_to_gregorian(cls, jdn: int) -> Tuple[int, int, int]:
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

    @classmethod
    def gregorian_to_ethiopian(cls, g_date: date) -> Tuple[int, int, int]:
        """Converts a Gregorian date into Ethiopian (year, month, day)."""
        jdn = cls.gregorian_to_jdn(g_date.year, g_date.month, g_date.day)
        r = (jdn - JD_OFFSET) % 1461
        n = (r % 365) + 365 * (r // 1460)
        year = 4 * ((jdn - JD_OFFSET) // 1461) + (r // 365) - (r // 1460)
        month = (n // 30) + 1
        day = (n % 30) + 1
        return year, month, day

    @classmethod
    def ethiopian_to_gregorian(cls, e_year: int, e_month: int, e_day: int) -> date:
        """Converts an Ethiopian date (year, month, day) into Gregorian date."""
        if e_month < 1 or e_month > 13:
            raise ValueError(f"የኢትዮጵያ ወር ከ1 እስከ 13 መሆን አለበት (Invalid Ethiopian month: {e_month})")

        is_leap = (e_year + 1) % 4 == 0
        max_pagume = 6 if is_leap else 5
        if e_month == 13 and (e_day < 1 or e_day > max_pagume):
            raise ValueError(f"በ{e_year} ዓ.ም ጳጉሜ {max_pagume} ቀናት ብቻ አሏት (Pagume has {max_pagume} days in year {e_year})")
        elif e_month < 13 and (e_day < 1 or e_day > 30):
            raise ValueError(f"የኢትዮጵያ ወር 30 ቀናት ብቻ አሉት (Invalid day {e_day} for month {e_month})")

        jdn = (JD_OFFSET + 365) + 365 * (e_year - 1) + (e_year // 4) + 30 * (e_month - 1) + e_day - 1
        gy, gm, gd = cls.jdn_to_gregorian(jdn)
        return date(gy, gm, gd)

    @classmethod
    def is_ethiopian_leap_year(cls, e_year: int) -> bool:
        """Ethiopian leap year occurs every 4 years when (e_year + 1) % 4 == 0 (Evangelist Luke)."""
        return (e_year + 1) % 4 == 0

    @classmethod
    def get_evangelist(cls, e_year: int) -> str:
        """Returns the Evangelist (ወንጌላዊ) of the Ethiopian year."""
        amete_alem = 5500 + e_year
        return EVANGELISTS[amete_alem % 4]

    @classmethod
    def format_date_conversion(cls, g_date: date) -> DateConversionResponse:
        """Returns a rich date conversion response."""
        ey, em, ed = cls.gregorian_to_ethiopian(g_date)
        m_am, m_en = ETHIOPIAN_MONTHS[em - 1]
        weekday_idx = g_date.weekday()
        d_am, d_en = AMHARIC_DAYS_OF_WEEK[weekday_idx]
        evangelist = cls.get_evangelist(ey)
        is_leap = cls.is_ethiopian_leap_year(ey)

        geez_day = cls.arabic_to_geez(ed)
        geez_year = cls.arabic_to_geez(ey)
        geez_date_str = f"{geez_day} {m_am} {geez_year} ዓ.ም"

        return DateConversionResponse(
            gregorian_date=g_date,
            ethiopian_year=ey,
            ethiopian_month=em,
            ethiopian_day=ed,
            month_name_amharic=m_am,
            month_name_english=m_en,
            formatted_amharic=f"{ed} {m_am} {ey} ዓ.ም",
            formatted_english=f"{ed} {m_en} {ey} E.C.",
            geez_date=geez_date_str,
            day_of_week_amharic=d_am,
            day_of_week_english=d_en,
            evangelist=evangelist,
            is_leap_year=is_leap,
        )

    # -----------------------------------------------------------------
    # 2. Bahire Hasab (ባሕረ ሐሳብ) Computus Engine
    # -----------------------------------------------------------------

    @classmethod
    def compute_bahire_hasab(cls, e_year: int) -> BahireHasabResponse:
        """
        Calculates the complete Ethiopian Computus (ባሕረ ሐሳብ) for a given year:
        - Wenber (ወንበር), Abektie (አበቅቴ), Metqe (መጥቅዕ), Evangelist (ወንጌላዊ).
        - All movable fasts and feasts anchored on Nineveh Fast (ጾመ ነነዌ).
        - All fixed national public holidays.
        """
        amete_alem = 5500 + e_year
        evangelist = cls.get_evangelist(e_year)
        is_leap = cls.is_ethiopian_leap_year(e_year)
        pagume_days = 6 if is_leap else 5

        wenber = (e_year - 1) % 19
        abektie = (wenber * 11) % 30
        metqe = (wenber * 19) % 30

        # Day of week for Meskerem 1
        new_year_greg = cls.ethiopian_to_gregorian(e_year, 1, 1)
        tinte_qemer = AMHARIC_DAYS_OF_WEEK[new_year_greg.weekday()][0]

        # Determine Metqe Month and Day
        if metqe > 14:
            metqe_month = 1  # መስከረም
            metqe_day = metqe
        else:
            metqe_month = 2  # ጥቅምት
            metqe_day = metqe

        # Find Nineveh Fast date
        metqe_greg = cls.ethiopian_to_gregorian(e_year, metqe_month, metqe_day)
        metqe_dow = metqe_greg.weekday()  # 0=Mon, ..., 6=Sun

        # Table of Tewsak (ተውሳክ) from Metqe to Nineveh
        # Mon=6, Tue=5, Wed=4, Thu=3, Fri=2, Sat=8, Sun=7
        tewsak_map = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 8, 6: 7}
        tewsak = tewsak_map[metqe_dow]

        # Nineveh anchor date in Gregorian
        nineveh_day_raw = metqe_day + tewsak
        if metqe_month == 1:
            if nineveh_day_raw > 30:
                nineveh_month = 6  # Yakatit
                nineveh_day = nineveh_day_raw - 30
            else:
                nineveh_month = 5  # Tir
                nineveh_day = nineveh_day_raw
        else:  # metqe_month == 2
            nineveh_month = 6  # Yakatit
            nineveh_day = (nineveh_day_raw - 30) if nineveh_day_raw > 30 else nineveh_day_raw

        nineveh_greg = cls.ethiopian_to_gregorian(e_year, nineveh_month, nineveh_day)

        # Offsets from Nineveh to Movable Feasts & Fasts
        movable_specs = [
            ("ጾመ ነነዌ", "Nineveh Fast", 0, False),
            ("ዓቢይ ጾም", "Great Lent", 14, False),
            ("ደብረ ዘይት", "Mount of Olives (Debre Zeyt)", 41, False),
            ("ሆሣዕና", "Palm Sunday (Hosanna)", 62, False),
            ("ስቅለት", "Good Friday (Siklet)", 67, True),  # Public holiday in Ethiopia
            ("ትንሣኤ / ፋሲካ", "Easter (Fasika)", 69, True),   # Public holiday
            ("ርክበ ካህናት", "Rikbe Kahnat", 93, False),
            ("ዕርገት", "Ascension", 108, False),
            ("ጰራቅሊጦስ", "Pentecost", 118, False),
            ("ጾመ ሐዋርያት", "Apostles' Fast", 119, False),
            ("ጾመ ድህነት", "Fast of Salvation", 121, False),
        ]

        movable_holidays: List[HolidayItem] = []
        for name_am, name_en, offset, is_pub in movable_specs:
            h_greg = nineveh_greg + timedelta(days=offset)
            h_ey, h_em, h_ed = cls.gregorian_to_ethiopian(h_greg)
            m_am = ETHIOPIAN_MONTHS[h_em - 1][0]
            movable_holidays.append(
                HolidayItem(
                    name_amharic=name_am,
                    name_english=name_en,
                    ethiopian_month=h_em,
                    ethiopian_day=h_ed,
                    ethiopian_date_formatted=f"{h_ed} {m_am} {h_ey} ዓ.ም",
                    gregorian_date=h_greg,
                    is_public_holiday=is_pub,
                )
            )

        # Fixed Ethiopian National & Public Holidays
        fixed_specs = [
            ("እንቁጣጣሽ (አዲስ ዓመት)", "Enkutatash (Ethiopian New Year)", 1, 1),
            ("መስቀል", "Finding of the True Cross (Meskel)", 1, 17),
            ("ጥምቀት", "Epiphany (Timket)", 5, 11),
            ("የአድዋ ድል በዓል", "Victory of Adwa", 6, 23),
            ("የኢትዮጵያ አርበኞች ቀን", "Patriots' Victory Day", 8, 27),
            ("ግንቦት 20 (ደርግ የወደቀበት ቀን)", "National Day (Derg Downfall)", 9, 20),
        ]

        fixed_holidays: List[HolidayItem] = []
        for name_am, name_en, m, d in fixed_specs:
            g_d = cls.ethiopian_to_gregorian(e_year, m, d)
            m_am = ETHIOPIAN_MONTHS[m - 1][0]
            fixed_holidays.append(
                HolidayItem(
                    name_amharic=name_am,
                    name_english=name_en,
                    ethiopian_month=m,
                    ethiopian_day=d,
                    ethiopian_date_formatted=f"{d} {m_am} {e_year} ዓ.ም",
                    gregorian_date=g_d,
                    is_public_holiday=True,
                )
            )

        return BahireHasabResponse(
            ethiopian_year=e_year,
            amete_alem=amete_alem,
            wenber=wenber,
            abektie=abektie,
            metqe=metqe,
            evangelist=evangelist,
            is_leap_year=is_leap,
            pagume_days=pagume_days,
            tinte_qemer=tinte_qemer,
            movable_holidays=movable_holidays,
            fixed_holidays=fixed_holidays,
        )

    # -----------------------------------------------------------------
    # 3. Ge'ez Numerals (ፊደላዊ ቁጥሮች) Bi-directional Engine
    # -----------------------------------------------------------------

    @classmethod
    def arabic_to_geez(cls, number: int) -> str:
        """
        Converts an Arabic integer (1 to 1,000,000+) into authentic Ge'ez numerals.
        Example: 2018 -> ፳፻፲፰, 1 -> ፩, 100 -> ፻, 10000 -> ፼, 250000 -> ፳፭፼
        """
        if number <= 0:
            return str(number)

        def convert_less_than_100(n: int) -> str:
            res = ""
            tens = (n // 10) * 10
            ones = n % 10
            if tens in GEEZ_TENS:
                res += GEEZ_TENS[tens]
            if ones in GEEZ_ONES:
                res += GEEZ_ONES[ones]
            return res

        # Split into base-100 pairs from right to left
        s = str(number)
        if len(s) % 2 != 0:
            s = "0" + s

        pairs = [int(s[i:i + 2]) for i in range(0, len(s), 2)]
        total_pairs = len(pairs)
        result = ""

        for idx, pair in enumerate(pairs):
            pos_from_right = total_pairs - idx - 1
            pair_geez = convert_less_than_100(pair)

            if pos_from_right == 0:
                result += pair_geez
            else:
                sep = GEEZ_HUNDRED if (pos_from_right % 2 == 1) else GEEZ_TEN_THOUSAND
                if pair == 0:
                    continue
                elif pair == 1:
                    # In Ge'ez: 1 before 100 or 10000 is omitted if at start of term
                    if idx == 0:
                        result += sep
                    else:
                        result += GEEZ_ONES[1] + sep
                else:
                    result += pair_geez + sep

        return result or GEEZ_ONES[1]

    @classmethod
    def geez_to_arabic(cls, geez_str: str) -> int:
        """
        Converts a Ge'ez numeral string (e.g. ፳፻፲፰) back into its Arabic integer value (2018).
        """
        clean_str = geez_str.strip()
        if not clean_str:
            return 0

        # Parse compound Ge'ez numbers
        total = 0
        current_pair = 0

        for char in clean_str:
            if char in GEEZ_DIGIT_MAP:
                val = GEEZ_DIGIT_MAP[char]
                if val == 100:
                    multiplier = current_pair if current_pair > 0 else 1
                    total += multiplier * 100
                    current_pair = 0
                elif val == 10000:
                    multiplier = current_pair if current_pair > 0 else 1
                    total = (total + multiplier) * 10000
                    current_pair = 0
                else:
                    current_pair += val
            else:
                pass  # Ignore whitespace or non-geez characters

        total += current_pair
        return total

    # -----------------------------------------------------------------
    # 4. Amharic Phonetic Search Normalizer (የፊደል ቅርጽ ማስተካከያ)
    # -----------------------------------------------------------------

    @classmethod
    def normalize_amharic(cls, text: str, strip_punctuation: bool = True) -> str:
        """
        Collapses Amharic phonetic homophones into canonical representations:
        - ሀ/ሐ/ኀ -> ሀ
        - ሰ/ሠ -> ሰ
        - አ/ዐ -> አ
        - ጸ/ፀ -> ጸ
        - Normalizes Ethiopic punctuation (።, ፡, ፣, ፤, ፦).
        """
        if not text:
            return ""

        chars = []
        for ch in text:
            chars.append(AMHARIC_HOMOPHONE_MAP.get(ch, ch))

        normalized = "".join(chars)
        if strip_punctuation:
            normalized = AMHARIC_PUNCTUATION_REGEX.sub(" ", normalized)
            normalized = " ".join(normalized.split())

        return normalized

    # -----------------------------------------------------------------
    # 5. Ethiopian Fiscal Year & Working Day SLA Engine
    # -----------------------------------------------------------------

    @classmethod
    def get_fiscal_year_details(cls, ref_date: date) -> FiscalYearResponse:
        """
        Calculates Ethiopian Fiscal Year (Hamle 1 – Sene 30) quarters and Pagume reconciliation period.
        """
        ey, em, ed = cls.gregorian_to_ethiopian(ref_date)
        fiscal_year = ey if em >= 11 else ey - 1
        fy_label = f"የ{fiscal_year}/{fiscal_year + 1} የሒሳብ ዓመት"

        start_date = cls.ethiopian_to_gregorian(fiscal_year, 11, 1)  # 1 Hamle
        end_date = cls.ethiopian_to_gregorian(fiscal_year + 1, 10, 30)  # 30 Sene

        # Quarters specification
        q1_start = cls.ethiopian_to_gregorian(fiscal_year, 11, 1)
        q1_end = cls.ethiopian_to_gregorian(fiscal_year + 1, 1, 30)

        q2_start = cls.ethiopian_to_gregorian(fiscal_year + 1, 2, 1)
        q2_end = cls.ethiopian_to_gregorian(fiscal_year + 1, 4, 30)

        q3_start = cls.ethiopian_to_gregorian(fiscal_year + 1, 5, 1)
        q3_end = cls.ethiopian_to_gregorian(fiscal_year + 1, 7, 30)

        q4_start = cls.ethiopian_to_gregorian(fiscal_year + 1, 8, 1)
        q4_end = cls.ethiopian_to_gregorian(fiscal_year + 1, 10, 30)

        quarters = [
            FiscalQuarterItem(
                quarter="Q1",
                name_amharic="1ኛ ሩብ ዓመት",
                ethiopian_range="ሐምሌ 1 - መስከረም 30",
                start_date=q1_start,
                end_date=q1_end,
                is_active=(q1_start <= ref_date <= q1_end)
            ),
            FiscalQuarterItem(
                quarter="Q2",
                name_amharic="2ኛ ሩብ ዓመት",
                ethiopian_range="ጥቅምት 1 - ታኅሣሥ 30",
                start_date=q2_start,
                end_date=q2_end,
                is_active=(q2_start <= ref_date <= q2_end)
            ),
            FiscalQuarterItem(
                quarter="Q3",
                name_amharic="3ኛ ሩብ ዓመት",
                ethiopian_range="ጥር 1 - መጋቢት 30",
                start_date=q3_start,
                end_date=q3_end,
                is_active=(q3_start <= ref_date <= q3_end)
            ),
            FiscalQuarterItem(
                quarter="Q4",
                name_amharic="4ኛ ሩብ ዓመት",
                ethiopian_range="ሚያዝያ 1 - ሰኔ 30",
                start_date=q4_start,
                end_date=q4_end,
                is_active=(q4_start <= ref_date <= q4_end)
            ),
        ]

        active_quarter = "Q1"
        for q in quarters:
            if q.is_active:
                active_quarter = q.quarter
                break

        is_reconciliation = (em == 13)  # Pagume is year-end closure

        return FiscalYearResponse(
            fiscal_year=fiscal_year,
            fiscal_year_label=fy_label,
            start_date=start_date,
            end_date=end_date,
            current_quarter="PAGUME_CLOSING" if is_reconciliation else active_quarter,
            is_reconciliation_period=is_reconciliation,
            quarters=quarters,
        )

    @classmethod
    def is_working_day(cls, check_date: date) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a given date is an Ethiopian working business day.
        Returns (is_working_day, reason_if_not).
        """
        # 1. Check Weekend (Saturday=5, Sunday=6)
        weekday = check_date.weekday()
        if weekday == 5:
            return False, "ቅዳሜ (Saturday Weekend)"
        elif weekday == 6:
            return False, "እሑድ (Sunday Weekend)"

        # 2. Check Public Holidays for the year
        ey, em, ed = cls.gregorian_to_ethiopian(check_date)
        computus = cls.compute_bahire_hasab(ey)

        for h in computus.fixed_holidays:
            if h.gregorian_date == check_date:
                return False, f"{h.name_amharic} (የመንግስት የሕዝብ በዓል)"

        for h in computus.movable_holidays:
            if h.is_public_holiday and h.gregorian_date == check_date:
                return False, f"{h.name_amharic} (የመንግስት የሕዝብ በዓል)"

        return True, None

    @classmethod
    def add_working_days(cls, start_date: date, days_to_add: int) -> WorkingDaysAddResponse:
        """
        Calculates an Ethiopian business day deadline (SLA calculator)
        by skipping weekends and official public holidays.
        """
        current = start_date
        added = 0
        skipped_weekends = 0
        skipped_holidays: List[str] = []

        while added < days_to_add:
            current += timedelta(days=1)
            is_work, reason = cls.is_working_day(current)
            if is_work:
                added += 1
            else:
                if current.weekday() in (5, 6):
                    skipped_weekends += 1
                else:
                    skipped_holidays.append(f"{current.isoformat()}: {reason}")

        target_ey, target_em, target_ed = cls.gregorian_to_ethiopian(current)
        m_am = ETHIOPIAN_MONTHS[target_em - 1][0]
        formatted_et = f"{target_ed} {m_am} {target_ey} ዓ.ም"

        return WorkingDaysAddResponse(
            start_date=start_date,
            days_to_add=days_to_add,
            target_date=current,
            target_date_ethiopian=formatted_et,
            skipped_weekend_days=skipped_weekends,
            skipped_holidays=skipped_holidays,
        )

    # -----------------------------------------------------------------
    # 6. Currency Amount-to-Words in Amharic (የገንዘብ መጠን በቃላት)
    # -----------------------------------------------------------------

    @classmethod
    def number_to_amharic_words(
        cls,
        amount: float,
        currency_name: str = "ብር",
        subunit_name: str = "ሳንቲም"
    ) -> str:
        """
        Converts decimal currency amounts into formal Amharic financial prose.
        Example: 1524.50 -> "አንድ ሺህ አምስት መቶ ሃያ አራት ብር ከአምሳ ሳንቲም"
        """
        if amount == 0:
            return f"ዜሮ {currency_name}"

        # Split into integer and cents
        total_cents = round(amount * 100)
        birr_part = total_cents // 100
        cents_part = total_cents % 100

        def convert_three_digits(n: int) -> str:
            res = []
            hundreds = n // 100
            remainder = n % 100

            if hundreds > 0:
                res.append(f"{AMHARIC_UNITS_WORDS[hundreds]} መቶ")

            if remainder in AMHARIC_TEENS_WORDS:
                res.append(AMHARIC_TEENS_WORDS[remainder])
            elif remainder >= 20:
                tens = (remainder // 10) * 10
                ones = remainder % 10
                tens_str = AMHARIC_TENS_WORDS[tens]
                if ones > 0:
                    res.append(f"{tens_str} {AMHARIC_UNITS_WORDS[ones]}")
                else:
                    res.append(tens_str)
            elif 0 < remainder < 10:
                res.append(AMHARIC_UNITS_WORDS[remainder])

            return " ".join(res)

        parts = []

        # Billions
        billions = birr_part // 1_000_000_000
        birr_part %= 1_000_000_000
        if billions > 0:
            parts.append(f"{convert_three_digits(billions)} ቢሊዮን")

        # Millions
        millions = birr_part // 1_000_000
        birr_part %= 1_000_000
        if millions > 0:
            parts.append(f"{convert_three_digits(millions)} ሚሊዮን")

        # Thousands
        thousands = birr_part // 1000
        birr_part %= 1000
        if thousands > 0:
            parts.append(f"{convert_three_digits(thousands)} ሺህ")

        # Hundreds & Remaining
        if birr_part > 0:
            parts.append(convert_three_digits(birr_part))

        birr_text = " ".join(parts).strip() or "ዜሮ"
        result = f"{birr_text} {currency_name}"

        if cents_part > 0:
            cents_text = convert_three_digits(cents_part)
            result += f" ከ{cents_text} {subunit_name}"

        return result.strip()
