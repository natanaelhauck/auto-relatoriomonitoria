"""Read IA payload normalization and student matching."""

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


def normalize_readia_payload(document: Any) -> dict[str, Any]:
    """Normalize a saved Read IA payload into the fields used by matching."""
    if isinstance(document, Mapping):
        payload = document.get("payload", document)
        received_at = document.get("received_at")
    else:
        payload = document
        received_at = None

    title = _find_first(payload, ("title", "meeting_title"))
    summary = _find_first(payload, ("summary", "report_summary"))
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
        "title": _clean_scalar(title),
        "summary": _clean_scalar(summary),
        "report_url": _clean_scalar(report_url),
        "participants": participants,
        "emails": emails,
        "raw_text": _clean_scalar(raw_text),
    }


def match_student_to_meeting(
    student: Mapping[str, Any],
    meeting: dict[str, Any],
) -> MatchResult | None:
    """Match one active student to one normalized Read IA meeting."""
    matricula = _normalize_identifier(student.get("matricula"))
    email = _normalize_email(student.get("email"))
    full_name = normalize_text(student.get("nome"))
    first_second_name = _first_second_name(full_name)

    title = normalize_text(meeting.get("title"))
    summary = normalize_text(meeting.get("summary"))
    raw_text = normalize_text(meeting.get("raw_text"))
    combined_text = f"{title} {summary} {raw_text}"

    if matricula and matricula in _normalize_identifier(combined_text):
        return MatchResult(100, "matricula", meeting)

    meeting_emails = {_normalize_email(item) for item in meeting.get("emails", [])}
    participant_emails = {
        _normalize_email(email_value)
        for participant in meeting.get("participants", [])
        for email_value in _extract_emails(participant)
    }
    if email and email in meeting_emails.union(participant_emails):
        return MatchResult(100, "email", meeting)

    if full_name and full_name in title:
        return MatchResult(95, "nome_completo_titulo", meeting)

    if first_second_name and first_second_name in title:
        return MatchResult(85, "primeiro_segundo_nome_titulo", meeting)

    summary_raw = f"{summary} {raw_text}"
    if full_name and full_name in summary_raw:
        return MatchResult(80, "nome_completo_resumo", meeting)

    if first_second_name and first_second_name in summary_raw:
        return MatchResult(65, "primeiro_segundo_nome_resumo", meeting)

    return None


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


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).lower()


def _first_second_name(full_name: str) -> str:
    parts = [part for part in full_name.split() if part]
    if len(parts) < 2:
        return ""
    return " ".join(parts[:2])
