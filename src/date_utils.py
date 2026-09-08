"""
Date helper functions. The pipeline works entirely with standard ISO date
strings ("YYYY-MM-DD") so it can be used with any calendar system — swap
these helpers out if your source data uses a different calendar.
"""
from datetime import date, datetime, timedelta
from typing import List


def to_date(value) -> date:
    """Coerce a string / datetime / date into a plain `date` object."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    raise ValueError(f"Unrecognized date value: {value!r}")


def fmt(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def shift(date_str: str, days: int) -> str:
    return fmt(to_date(date_str) + timedelta(days=days))


def weekday_name(date_str: str) -> str:
    return to_date(date_str).strftime("%A")


def date_range(start_date: str, n_days: int) -> List[str]:
    start = to_date(start_date)
    return [fmt(start + timedelta(days=i)) for i in range(n_days)]
