"""Date and time utility functions."""

import calendar
from datetime import datetime, timedelta


def get_month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Get the start and end datetimes for a given month."""
    start = datetime(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def get_week_bounds(date: datetime | None = None) -> tuple[datetime, datetime]:
    """Get Monday 00:00 to Sunday 23:59 for the week containing date."""
    if date is None:
        date = datetime.utcnow()
    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def get_today_bounds() -> tuple[datetime, datetime]:
    """Get start and end of today (UTC)."""
    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end


def next_month(year: int, month: int) -> tuple[int, int]:
    """Get next month's year and month."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def prev_month(year: int, month: int) -> tuple[int, int]:
    """Get previous month's year and month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def format_date_ru(dt: datetime) -> str:
    """Format datetime as Russian-style date string."""
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date_short(dt: datetime) -> str:
    """Format datetime as short date."""
    return dt.strftime("%d.%m.%Y")
