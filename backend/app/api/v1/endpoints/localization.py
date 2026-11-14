import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel

from app.services.localization_service import LocalizationService
from app.schemas.localization import (
    DateConversionResponse,
    BahireHasabResponse,
    GeezToNumberResponse,
    NumberToGeezResponse,
    AmharicNormalizationRequest,
    AmharicNormalizationResponse,
    FiscalYearResponse,
    WorkingDayCheckResponse,
    WorkingDaysAddResponse,
    AmountToWordsResponse,
)

router = APIRouter()


@router.get("/today", response_model=DateConversionResponse)
def get_today_localized():
    """
    Returns today's synchronized date in Ethiopian (EC) and Gregorian (GC) formats,
    including Ge'ez numerals, Evangelist of the year, day of week, and leap year status.
    """
    return LocalizationService.format_date_conversion(date.today())


@router.get("/convert", response_model=DateConversionResponse)
def convert_date(
    g_date: Optional[date] = Query(None, description="Gregorian date (YYYY-MM-DD)"),
    e_year: Optional[int] = Query(None, description="Ethiopian year (e.g. 2018)"),
    e_month: Optional[int] = Query(None, ge=1, le=13, description="Ethiopian month (1-13)"),
    e_day: Optional[int] = Query(None, ge=1, le=30, description="Ethiopian day (1-30)"),
):
    """
    Bi-directional date conversion between Gregorian and Ethiopian calendars.
    Pass either 'g_date' OR ('e_year', 'e_month', 'e_day').
    """
    if g_date:
        return LocalizationService.format_date_conversion(g_date)
    elif e_year and e_month and e_day:
        try:
            converted_g = LocalizationService.ethiopian_to_gregorian(e_year, e_month, e_day)
            return LocalizationService.format_date_conversion(converted_g)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'g_date' OR ('e_year', 'e_month', 'e_day') parameters."
        )


@router.get("/bahire-hasab/{year}", response_model=BahireHasabResponse)
def get_bahire_hasab_computus(year: int):
    """
    Computes complete Ethiopian Computus (ባሕረ ሐሳብ) for the given Ethiopian year:
    Calculates Wenber, Abektie, Metqe, Evangelist, all movable fasts (Nineveh, Great Lent,
    Fasika/Easter, Ascension, Pentecost), and national public holidays.
    """
    if year < 1 or year > 9999:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Year must be between 1 and 9999")
    return LocalizationService.compute_bahire_hasab(year)


@router.get("/geez-numbers/to-geez", response_model=NumberToGeezResponse)
def convert_to_geez(number: int = Query(..., ge=1, description="Positive integer to convert")):
    """
    Converts an Arabic integer (1 to 1,000,000+) into official Ge'ez numerals (e.g. 2018 -> ፳፻፲፰).
    """
    geez_str = LocalizationService.arabic_to_geez(number)
    return NumberToGeezResponse(arabic_number=number, geez_number=geez_str)


@router.get("/geez-numbers/to-arabic", response_model=GeezToNumberResponse)
def convert_to_arabic(geez: str = Query(..., description="Ge'ez numeral string (e.g. ፳፻፲፰)")):
    """
    Converts a Ge'ez numeral string back into its Arabic integer value.
    """
    arabic_val = LocalizationService.geez_to_arabic(geez)
    if arabic_val == 0 and geez.strip() not in ("0", ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Ge'ez numeral string")
    return GeezToNumberResponse(geez_number=geez, arabic_number=arabic_val)


@router.post("/normalize-amharic", response_model=AmharicNormalizationResponse)
def normalize_amharic_text(payload: AmharicNormalizationRequest):
    """
    Amharic phonetic search normalizer:
    Collapses homophone character families (ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ) into canonical forms,
    standardizes punctuation, and tokenizes text for search indexing.
    """
    norm = LocalizationService.normalize_amharic(payload.text, strip_punctuation=payload.strip_punctuation)
    tokens = norm.split()
    return AmharicNormalizationResponse(
        original_text=payload.text,
        normalized_text=norm,
        tokens=tokens,
    )


@router.get("/fiscal-year", response_model=FiscalYearResponse)
def get_fiscal_year(ref_date: Optional[date] = Query(None, description="Reference date (defaults to today)")):
    """
    Returns Ethiopian Fiscal Year (Hamle 1 – Sene 30) quarters, boundaries,
    and identifies the Pagume year-end reconciliation period.
    """
    target = ref_date or date.today()
    return LocalizationService.get_fiscal_year_details(target)


@router.get("/working-days/check", response_model=WorkingDayCheckResponse)
def check_working_day(check_date: date = Query(..., description="Date to verify")):
    """
    Checks whether a specific date is an Ethiopian business working day,
    taking into account weekends and official national public holidays.
    """
    is_work, reason = LocalizationService.is_working_day(check_date)
    ey, em, ed = LocalizationService.gregorian_to_ethiopian(check_date)
    m_am = LocalizationService.format_date_conversion(check_date).month_name_amharic
    return WorkingDayCheckResponse(
        date=check_date,
        date_ethiopian=f"{ed} {m_am} {ey} ዓ.ም",
        is_working_day=is_work,
        reason=reason,
    )


@router.get("/working-days/add", response_model=WorkingDaysAddResponse)
def add_business_days(
    start_date: date = Query(..., description="Start date"),
    days: int = Query(..., ge=1, le=365, description="Number of business days to add"),
):
    """
    Calculates SLA resolution deadlines by adding N Ethiopian working days,
    automatically skipping weekends and public holidays.
    """
    return LocalizationService.add_working_days(start_date, days)


@router.get("/amount-to-words", response_model=AmountToWordsResponse)
def convert_amount_to_words(
    amount: float = Query(..., ge=0, description="Monetary decimal amount"),
    currency: str = Query("ብር", description="Currency title in Amharic (defaults to ብር)"),
    subunit: str = Query("ሳንቲም", description="Subunit title in Amharic (defaults to ሳንቲም)"),
):
    """
    Converts decimal monetary amounts into formal Amharic prose for checks,
    vouchers, and official invoices (e.g. 1524.50 -> አንድ ሺህ አምስት መቶ ሃያ አራት ብር ከአምሳ ሳንቲም).
    """
    words = LocalizationService.number_to_amharic_words(amount, currency_name=currency, subunit_name=subunit)
    formatted = f"{amount:,.2f} {currency}"
    return AmountToWordsResponse(
        amount=amount,
        words_amharic=words,
        currency=currency,
        formatted_amount=formatted,
    )
