"""Date helpers for report automation."""

from __future__ import annotations

from datetime import datetime


def get_iso_week_info(date_str: str) -> dict[str, int]:
    """Return ISO year and week for a date in YYYY-MM-DD format."""
    date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
    iso_calendar = date_value.isocalendar()
    return {
        "iso_year": iso_calendar.year,
        "iso_week": iso_calendar.week,
    }
