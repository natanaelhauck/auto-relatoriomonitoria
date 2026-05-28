"""Read IA report student matching."""

from __future__ import annotations

import re
import string
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
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
            _clean_scalar(meeting.get("readia_report_url")),
            _clean_scalar(meeting.get("link_google_docs")),
            _clean_scalar(meeting.get("report_url")),
            _clean_scalar(meeting.get("raw_text")),
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
