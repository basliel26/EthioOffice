from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from app.core.ethiopian_calendar import (
    gregorian_to_ethiopian,
    ethiopian_to_gregorian,
    format_ethiopian_date,
    get_ethiopian_fiscal_year,
)

router = APIRouter()


@router.get("/today")
def get_today_calendar():
    """
    Returns today's date synchronized in Ethiopian and Gregorian formats.
    """
    today = date.today()
    ey, em, ed = gregorian_to_ethiopian(today)
    ec_formatted_amharic = format_ethiopian_date(today, in_amharic=True)
    ec_formatted_english = format_ethiopian_date(today, in_amharic=False)
    f_start, f_end = get_ethiopian_fiscal_year(today)

    return {
        "gregorian_date": today.isoformat(),
        "ethiopian_date": {
            "year": ey,
            "month": em,
            "day": ed,
            "formatted_amharic": ec_formatted_amharic,
            "formatted_english": ec_formatted_english,
        },
        "fiscal_year": {
            "label": f"የ{ey if em >= 11 else ey - 1}/{ey + 1 if em >= 11 else ey} የሒሳብ ዓመት",
            "start_date": f_start.isoformat(),
            "end_date": f_end.isoformat(),
        }
    }


@router.get("/convert")
def convert_calendar(
    g_date: Optional[date] = Query(None, description="Gregorian date to convert to Ethiopian"),
    e_year: Optional[int] = Query(None, description="Ethiopian year"),
    e_month: Optional[int] = Query(None, ge=1, le=13, description="Ethiopian month (1-13)"),
    e_day: Optional[int] = Query(None, ge=1, le=30, description="Ethiopian day (1-30)"),
):
    """
    Converts between Gregorian and Ethiopian dates bi-directionally.
    """
    if g_date:
        ey, em, ed = gregorian_to_ethiopian(g_date)
        return {
            "input_gregorian": g_date.isoformat(),
            "output_ethiopian": {
                "year": ey,
                "month": em,
                "day": ed,
                "formatted": format_ethiopian_date(g_date)
            }
        }
    elif e_year and e_month and e_day:
        try:
            converted_g = ethiopian_to_gregorian(e_year, e_month, e_day)
            return {
                "input_ethiopian": f"{e_day}/{e_month}/{e_year} ዓ.ም",
                "output_gregorian": converted_g.isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Ethiopian date: {e}")
    else:
        raise HTTPException(status_code=400, detail="Provide either g_date or (e_year, e_month, e_day)")
