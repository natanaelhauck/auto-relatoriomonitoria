"""Diagnose Read IA payload coverage for a Google Calendar day."""

from __future__ import annotations

import argparse
import re
from typing import Any

from src.calendar_client import get_events_for_date, parse_student_from_calendar_title
from src.readia_matcher import (
    MatchResult,
    best_match_calendar_event_to_meetings,
    load_readia_meetings_from_sheet_rows,
)
from src.sheets_client import read_readia_payload_rows
from src.submission_runner import _today_sao_paulo, parse_report_date

MATCH_CONFIDENCE_THRESHOLD = 50


def check_readia_webhook_today(*, report_date: str | None = None) -> int:
    """Print calendar events that do not have a confirmed Read IA payload."""
    target_date = report_date or _today_sao_paulo()
    events = get_events_for_date(target_date)
    payload_rows = read_readia_payload_rows()
    meetings = load_readia_meetings_from_sheet_rows(
        payload_rows,
        report_date=target_date,
    )
    missing_rows, unparsed_rows, matched_count = find_monitorias_without_payload(
        events,
        meetings,
        target_date,
    )

    print(f"Data: {target_date}")
    print(f"Total eventos agenda: {len(events)}")
    print(f"Total payloads Read IA recebidos na data: {_received_count(payload_rows, target_date)}")
    print(f"Total payloads Read IA considerados para a data: {len(meetings)}")
    print(f"Monitorias com payload confirmado: {matched_count}")
    print(f"Monitorias sem payload confirmado: {len(missing_rows)}")
    print(f"Eventos sem matricula reconhecivel: {len(unparsed_rows)}")

    if missing_rows:
        print("Monitorias sem payload:")
        for row in missing_rows:
            print(
                "  "
                f"{row['calendar_start']} | {row['nome']} | {row['matricula']} | "
                f"{row['calendar_title']} | score={row['match_confidence']} | "
                f"{row['match_type']}"
            )
    else:
        print("Monitorias sem payload: nenhuma")

    if unparsed_rows:
        print("Eventos sem matricula reconhecivel:")
        for row in unparsed_rows:
            print(f"  {row['calendar_start']} | {row['calendar_title']}")

    return 0


def find_monitorias_without_payload(
    events: list[dict[str, Any]],
    meetings: list[dict[str, Any]],
    report_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Return missing, unparsed, and confirmed-match counts for a day."""
    missing_rows = []
    unparsed_rows = []
    matched_count = 0

    for event in events:
        parsed_student = parse_student_from_calendar_title(str(event.get("title", "")))
        if parsed_student is None:
            unparsed_rows.append(_unparsed_row(event, report_date))
            continue

        match = best_match_calendar_event_to_meetings(
            {
                **parsed_student,
                "calendar_start": event.get("start", ""),
            },
            meetings,
        )
        if _is_confirmed_match(match):
            matched_count += 1
            continue

        missing_rows.append(_missing_row(event, parsed_student, match, report_date))

    return missing_rows, unparsed_rows, matched_count


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for Read IA webhook diagnostics."""
    parser = argparse.ArgumentParser(
        description="Compara Google Agenda e payloads Read IA recebidos na data."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do diagnostico no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    return parser


def _is_confirmed_match(match: MatchResult | None) -> bool:
    return match is not None and match.confidence >= MATCH_CONFIDENCE_THRESHOLD


def _missing_row(
    event: dict[str, Any],
    student: dict[str, str],
    match: MatchResult | None,
    report_date: str,
) -> dict[str, Any]:
    return {
        "data": report_date,
        "nome": student.get("nome", ""),
        "matricula": student.get("matricula", ""),
        "calendar_title": event.get("title", ""),
        "calendar_start": event.get("start", ""),
        "calendar_end": event.get("end", ""),
        "match_confidence": match.confidence if match is not None else 0,
        "match_type": match.match_type if match is not None else "sem_match",
    }


def _unparsed_row(event: dict[str, Any], report_date: str) -> dict[str, Any]:
    return {
        "data": report_date,
        "calendar_title": event.get("title", ""),
        "calendar_start": event.get("start", ""),
        "calendar_end": event.get("end", ""),
    }


def _received_count(rows: list[dict[str, Any]], target_date: str) -> int:
    return sum(
        1
        for row in rows
        if _date_from_value(row.get("received_at", "")) == target_date
    )


def _date_from_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    return ""


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = check_readia_webhook_today(report_date=args.report_date)
    except RuntimeError as exc:
        print(f"ERRO - {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
