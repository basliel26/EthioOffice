from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DateConversionResponse(BaseModel):
    gregorian_date: date
    ethiopian_year: int
    ethiopian_month: int
    ethiopian_day: int
    month_name_amharic: str
    month_name_english: str
    formatted_amharic: str
    formatted_english: str
    geez_date: str
    day_of_week_amharic: str
    day_of_week_english: str
    evangelist: str
    is_leap_year: bool


class HolidayItem(BaseModel):
    name_amharic: str
    name_english: str
    ethiopian_month: int
    ethiopian_day: int
    ethiopian_date_formatted: str
    gregorian_date: date
    is_public_holiday: bool


class BahireHasabResponse(BaseModel):
    ethiopian_year: int
    amete_alem: int
    wenber: int
    abektie: int
    metqe: int
    evangelist: str
    is_leap_year: bool
    pagume_days: int
    tinte_qemer: str
    movable_holidays: List[HolidayItem]
    fixed_holidays: List[HolidayItem]


class GeezToNumberResponse(BaseModel):
    geez_number: str
    arabic_number: int


class NumberToGeezResponse(BaseModel):
    arabic_number: int
    geez_number: str


class AmharicNormalizationRequest(BaseModel):
    text: str
    strip_punctuation: bool = True


class AmharicNormalizationResponse(BaseModel):
    original_text: str
    normalized_text: str
    tokens: List[str]


class FiscalQuarterItem(BaseModel):
    quarter: str
    name_amharic: str
    ethiopian_range: str
    start_date: date
    end_date: date
    is_active: bool


class FiscalYearResponse(BaseModel):
    fiscal_year: int
    fiscal_year_label: str
    start_date: date
    end_date: date
    current_quarter: str
    is_reconciliation_period: bool
    quarters: List[FiscalQuarterItem]


class WorkingDayCheckResponse(BaseModel):
    date: date
    date_ethiopian: str
    is_working_day: bool
    reason: Optional[str] = None


class WorkingDaysAddResponse(BaseModel):
    start_date: date
    days_to_add: int
    target_date: date
    target_date_ethiopian: str
    skipped_weekend_days: int
    skipped_holidays: List[str]


class AmountToWordsResponse(BaseModel):
    amount: float
    words_amharic: str
    currency: str
    formatted_amount: str
