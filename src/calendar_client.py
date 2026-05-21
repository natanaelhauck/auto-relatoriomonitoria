"""Google Calendar access helpers for daily monitoring previews."""

from __future__ import annotations

import os
import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)
MATRICULA_PATTERN = re.compile(r"\b(P[A-Z]{2,5}\d+)\b", re.IGNORECASE)


def get_events_for_date(date_str: str) -> list[dict[str, Any]]:
    """Return Google Calendar events for a date in YYYY-MM-DD format."""
    load_dotenv()
    service_account_file = _required_env("GOOGLE_SERVICE_ACCOUNT_FILE")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip() or "primary"
    timezone_name = (
        os.getenv("GOOGLE_CALENDAR_TIMEZONE", "America/Sao_Paulo").strip()
        or "America/Sao_Paulo"
    )
    timezone = ZoneInfo(timezone_name)
    start, end = _date_bounds(date_str, timezone)
    service = _build_calendar_service(service_account_file)

    try:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                timeZone=timezone_name,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            "Nao foi possivel ler o Google Agenda. Habilite a Google Calendar "
            "API no projeto da service account, verifique GOOGLE_CALENDAR_ID e "
            "compartilhe a agenda com o e-mail da service account usada em "
            "GOOGLE_SERVICE_ACCOUNT_FILE."
        ) from exc

    return [_normalize_event(event) for event in result.get("items", [])]


def parse_student_from_calendar_title(title: str) -> dict[str, str] | None:
    """Extract student name and enrollment id from a calendar event title."""
    title_text = str(title or "").strip()
    match = MATRICULA_PATTERN.search(title_text)
    if not match:
        return None

    name = title_text[: match.start()]
    name = re.sub(r"\s+\band\b.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip(" -|")
    if not name:
        return None

    return {
        "nome": name,
        "matricula": match.group(1).upper(),
    }


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_calendar_service(service_account_file: str) -> Any:
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _date_bounds(
    date_str: str,
    timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    date_value = datetime.strptime(date_str, "%Y-%m-%d").date()
    start = datetime.combine(date_value, time.min, tzinfo=timezone)
    end = start + timedelta(days=1)
    return start, end


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": event.get("summary", ""),
        "start": _event_datetime(event.get("start", {})),
        "end": _event_datetime(event.get("end", {})),
        "description": event.get("description", ""),
        "attendees": event.get("attendees", []),
    }


def _event_datetime(value: dict[str, Any]) -> str:
    return str(value.get("dateTime") or value.get("date") or "")
