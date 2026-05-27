"""Read IA report normalization and student matching."""

from __future__ import annotations

import json
import re
import string
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PAYLOAD_DIR = Path("data/read_payloads")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SUMMARY_KEYS = (
    "summary",
    "report_summary",
    "transcript_summary",
    "meeting_summary",
    "notes",
    "text",
    "transcript",
)
SUMMARY_FALLBACK_MAX_LENGTH = 1500
FIRST_NAME_STOPWORDS = {"aluno", "aluna", "monitoria"}


@dataclass(frozen=True)
class MatchResult:
    """Result of matching one student to one Read IA meeting."""

    confidence: int
    match_type: str
    meeting: dict[str, Any]


def normalize_text(text: Any) -> str:
    """Normalize text for conservative name matching."""
    normalized = str(text or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = re.sub(f"[{re.escape(string.punctuation)}]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def load_readia_meetings(
    payload_dir: Path = PAYLOAD_DIR,
    *,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    """Load and normalize saved Read IA webhook payloads."""
    meetings = []
    for path in sorted(payload_dir.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        meeting = normalize_readia_payload(document)
        meeting["source_file"] = path.name
        if report_date is None or meeting.get("date") == report_date:
            meetings.append(meeting)

    return meetings


def load_readia_meetings_from_sheet_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    report_date: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize Read IA payload rows loaded from Google Sheets."""
    meetings = []
    for row in rows:
        meeting = normalize_readia_sheet_row(row)
        row_received_date = _extract_date(row.get("received_at"))
        if (
            report_date is None
            or meeting.get("date") == report_date
            or row_received_date == report_date
        ):
            meetings.append(meeting)
    return meetings


def normalize_readia_sheet_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one row from the configured Read IA payloads sheet."""
    payload_json = _clean_scalar(row.get("payload_json"))
    payload = _parse_json_payload(payload_json)
    document = {
        "received_at": row.get("received_at"),
        "payload": payload if payload is not None else {"raw_text": payload_json},
    }
    meeting = normalize_readia_payload(document)

    for source_key, meeting_key in (
        ("meeting_id", "meeting_id"),
        ("title", "title"),
        ("summary", "summary"),
        ("report_url", "report_url"),
    ):
        value = _clean_scalar(row.get(source_key))
        if value:
            if meeting_key == "summary" and meeting.get("summary"):
                continue
            meeting[meeting_key] = value

    meeting["payload_json"] = payload_json or meeting.get("payload_json", "")
    return meeting


def normalize_readia_payload(document: Any) -> dict[str, Any]:
    """Normalize a saved Read IA payload into the fields used by matching."""
    if isinstance(document, Mapping):
        payload = document.get("payload", document)
        received_at = document.get("received_at")
    else:
        payload = document
        received_at = None

    title = _find_first(payload, ("title", "meeting_title"))
    meeting_id = _find_first(
        payload,
        ("meeting_id", "meetingId", "session_id", "sessionId", "id"),
    )
    payload_json = _json_text(payload)
    summary = _summary_from_payload(payload, payload_json)
    report_url = _find_first(payload, ("report_url", "url"))
    raw_text = _find_first(payload, ("raw_text",))
    participants_value = _find_first(payload, ("participants", "attendees"))
    explicit_emails = _find_first(payload, ("emails",))
    date_value = _find_first(payload, ("start_time", "created_at", "date"))

    participants = _string_list(participants_value)
    email_sources = [participants_value, explicit_emails, payload]
    emails = sorted(
        {
            _normalize_email(email)
            for source in email_sources
            for email in _extract_emails(source)
            if _normalize_email(email)
        }
    )

    return {
        "date": _extract_date(date_value) or _extract_date(received_at) or "",
        "received_at": _clean_scalar(received_at),
        "meeting_id": _clean_scalar(meeting_id),
        "start_time": _clean_scalar(date_value),
        "title": _clean_scalar(title),
        "summary": _clean_scalar(summary),
        "report_url": _clean_scalar(report_url),
        "participants": participants,
        "emails": emails,
        "raw_text": _clean_scalar(raw_text),
        "payload_json": payload_json,
    }


def match_student_to_meeting(
    student: Mapping[str, Any],
    meeting: dict[str, Any],
) -> MatchResult | None:
    """Match one active student to one normalized Read IA meeting."""
    match = score_subject_to_meeting(student, meeting)
    return match if match.confidence > 0 else None


def match_calendar_event_to_meeting(
    calendar_event: Mapping[str, Any],
    meeting: dict[str, Any],
) -> MatchResult | None:
    """Match one parsed calendar event to one normalized Read IA meeting."""
    match = score_calendar_event_to_meeting(calendar_event, meeting)
    return match if match.confidence > 0 else None


def score_calendar_event_to_meeting(
    calendar_event: Mapping[str, Any],
    meeting: dict[str, Any],
) -> MatchResult:
    """Return the calculated score for one parsed calendar event and meeting."""
    return score_subject_to_meeting(calendar_event, meeting)


def score_subject_to_meeting(
    subject: Mapping[str, Any],
    meeting: dict[str, Any],
) -> MatchResult:
    """Return the calculated score for one student-like subject and meeting."""
    matricula = _normalize_identifier(subject.get("matricula"))
    email = _normalize_email(subject.get("email"))
    full_name = normalize_text(subject.get("nome"))
    first_second_name = _first_second_name(full_name)
    first_name = _first_name(full_name)
    search_text = _meeting_search_text(meeting)
    normalized_search_text = normalize_text(search_text)
    identifier_search_text = _normalize_identifier(search_text)

    score = 0
    match_parts: list[str] = []

    if matricula and matricula in identifier_search_text:
        return MatchResult(100, "matricula", meeting)

    meeting_emails = {_normalize_email(item) for item in meeting.get("emails", [])}
    participant_emails = {
        _normalize_email(email_value)
        for participant in meeting.get("participants", [])
        for email_value in _extract_emails(participant)
    }
    if email and email in meeting_emails.union(participant_emails):
        score += 100
        match_parts.append("email")

    if _contains_normalized_phrase(normalized_search_text, full_name):
        score += 80
        match_parts.append("nome_completo")
    elif _contains_normalized_phrase(normalized_search_text, first_second_name):
        score += 60
        match_parts.append("primeiro_segundo_nome")
    elif _contains_first_name_and_important_surname(
        normalized_search_text,
        full_name,
    ):
        score += 55
        match_parts.append("primeiro_nome_sobrenome")
    elif _is_matchable_first_name(first_name) and _contains_normalized_phrase(
        normalized_search_text,
        first_name,
    ):
        score += 50
        match_parts.append("primeiro_nome")

    return MatchResult(score, "+".join(match_parts) or "sem_match", meeting)


def meeting_search_text(meeting: Mapping[str, Any]) -> str:
    """Return the exact meeting text used for matching."""
    return _meeting_search_text(meeting)


def best_match_student_to_meetings(
    student: Mapping[str, Any],
    meetings: Sequence[dict[str, Any]],
) -> MatchResult | None:
    """Return the best Read IA match for a student."""
    matches = [
        match
        for meeting in meetings
        if (match := match_student_to_meeting(student, meeting)) is not None
    ]
    if not matches:
        return None

    return max(matches, key=lambda match: match.confidence)


def best_match_calendar_event_to_meetings(
    calendar_event: Mapping[str, Any],
    meetings: Sequence[dict[str, Any]],
) -> MatchResult | None:
    """Return the best Read IA match for a parsed calendar event."""
    matches = [
        match
        for meeting in meetings
        if (match := match_calendar_event_to_meeting(calendar_event, meeting)) is not None
    ]
    if not matches:
        return None

    return max(matches, key=lambda match: match.confidence)


def _find_first(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value and value[key] not in (None, ""):
                return value[key]

        for item in value.values():
            found = _find_first(item, keys)
            if found not in (None, ""):
                return found

    if isinstance(value, list):
        for item in value:
            found = _find_first(item, keys)
            if found not in (None, ""):
                return found

    return None


def _summary_from_payload(payload: Any, payload_json: str) -> str:
    summary = _find_first(payload, SUMMARY_KEYS)
    summary_text = _clean_scalar(summary)
    if summary_text:
        return summary_text

    return _payload_json_summary(payload_json)


def _payload_json_summary(payload_json: str) -> str:
    text = _useful_text(payload_json)
    if not text:
        return ""
    return text[:SUMMARY_FALLBACK_MAX_LENGTH]


def _useful_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def _meeting_search_text(meeting: Mapping[str, Any]) -> str:
    participants = " ".join(
        _clean_scalar(participant) for participant in meeting.get("participants", [])
    )
    return " ".join(
        value
        for value in (
            _clean_scalar(meeting.get("title")),
            _clean_scalar(meeting.get("summary")),
            participants,
            _clean_scalar(meeting.get("report_url")),
            _clean_scalar(meeting.get("raw_text")),
            _clean_scalar(meeting.get("payload_json")),
        )
        if value
    )


def _contains_normalized_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _contains_first_name_and_important_surname(text: str, full_name: str) -> bool:
    first_name = _first_name(full_name)
    if not _contains_normalized_phrase(text, first_name):
        return False

    return any(
        _contains_normalized_phrase(text, surname)
        for surname in _important_surnames(full_name)
    )


def _important_surnames(full_name: str) -> list[str]:
    ignored = {
        "da",
        "de",
        "do",
        "das",
        "dos",
        "e",
    }
    parts = [part for part in full_name.split() if part and part not in ignored]
    if len(parts) <= 2:
        return []
    return parts[2:]


def _parse_json_payload(value: str) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [_clean_scalar(item) for item in value if _clean_scalar(item)]

    if isinstance(value, Mapping):
        text = " ".join(_clean_scalar(item) for item in value.values())
        return [text.strip()] if text.strip() else []

    text = _clean_scalar(value)
    return [text] if text else []


def _extract_emails(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, Mapping):
        emails = []
        for item in value.values():
            emails.extend(_extract_emails(item))
        return emails

    if isinstance(value, list):
        emails = []
        for item in value:
            emails.extend(_extract_emails(item))
        return emails

    return EMAIL_PATTERN.findall(str(value))


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).lower()


def _first_second_name(full_name: str) -> str:
    parts = [part for part in full_name.split() if part]
    if len(parts) < 2:
        return ""
    return " ".join(parts[:2])


def _first_name(full_name: str) -> str:
    parts = [part for part in full_name.split() if part]
    return parts[0] if parts else ""


def _is_matchable_first_name(first_name: str) -> bool:
    return len(first_name) >= 3 and first_name not in FIRST_NAME_STOPWORDS
