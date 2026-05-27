"""Generate a daily preview using Google Calendar events and Read IA Google Docs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from src.calendar_client import get_events_for_date, parse_student_from_calendar_title
from src.course_detection import describe_consumed_courses_from_text
from src.readia_matcher import (
    MatchResult,
    best_match_calendar_event_to_meetings,
    meeting_search_text,
    score_calendar_event_to_meeting,
)
from src.readia_docs_client import list_readia_docs_for_date
from src.submission_runner import _today_sao_paulo, parse_report_date

PREVIEW_DIR = Path("data/previews")
MOTIVO_SEM_RESPOSTA = "Sem resposta"
CSV_FIELDS = [
    "data",
    "categoria",
    "status",
    "nome",
    "matricula",
    "calendar_title",
    "calendar_start",
    "calendar_end",
    "match_confidence",
    "match_type",
    "readia_title",
    "readia_summary",
    "readia_report_url",
    "cursos_consumidos",
    "motivo_deteccao_curso",
    "motivo_falta",
    "observacao",
]
DEBUG_CSV_FIELDS = [
    "calendar_nome",
    "calendar_matricula",
    "calendar_title",
    "readia_title",
    "readia_summary",
    "readia_report_url",
    "score",
    "motivos_score",
    "texto_usado_para_match",
]


def preview_monitoria_agenda_do_dia(
    *,
    report_date: str | None = None,
    preview_dir: Path = PREVIEW_DIR,
) -> int:
    """Read calendar events and Read IA Google Docs, then write a review CSV."""
    target_date = report_date or _today_sao_paulo()
    events = get_events_for_date(target_date)
    meetings = list_readia_docs_for_date(target_date)
    rows = build_agenda_preview_rows(events, meetings, target_date)
    csv_path = write_agenda_preview_csv(rows, target_date, preview_dir=preview_dir)
    debug_rows = build_debug_readia_match_rows(events, meetings, target_date)
    debug_csv_path = write_debug_readia_matches_csv(
        debug_rows,
        target_date,
        preview_dir=preview_dir,
    )
    counts = _category_counts(rows)

    print(f"Total eventos agenda: {len(events)}")
    print(f"Total docs Read IA na data: {len(meetings)}")
    print(f"Presentes confirmados: {counts['presentes_confirmados']}")
    print(f"Matches fracos: {counts['matches_fracos']}")
    if counts["matches_fracos"]:
        _print_weak_matches(rows)
    print(f"Faltas candidatas: {counts['faltas_candidatas']}")
    print(f"Caminho CSV: {csv_path}")
    print(f"Caminho CSV debug: {debug_csv_path}")
    return 0


def build_agenda_preview_rows(
    events: list[dict[str, Any]],
    meetings: list[dict[str, Any]],
    report_date: str,
) -> list[dict[str, Any]]:
    """Build review rows from calendar events and Read IA meetings."""
    rows = []
    for event in events:
        parsed_student = parse_student_from_calendar_title(str(event.get("title", "")))
        if parsed_student is None:
            rows.append(_unparsed_event_row(event, report_date))
            continue

        calendar_subject = {
            **parsed_student,
            "calendar_start": event.get("start", ""),
        }
        match = best_match_calendar_event_to_meetings(calendar_subject, meetings)
        rows.append(_matched_event_row(event, parsed_student, match, report_date))
    return rows


def write_agenda_preview_csv(
    rows: list[dict[str, Any]],
    report_date: str,
    *,
    preview_dir: Path = PREVIEW_DIR,
) -> Path:
    """Write agenda preview rows to a dated CSV file."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    csv_path = preview_dir / f"preview_agenda_monitoria_{report_date}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def build_debug_readia_match_rows(
    events: list[dict[str, Any]],
    meetings: list[dict[str, Any]],
    report_date: str,
) -> list[dict[str, Any]]:
    """Build one debug row for each calendar event and Read IA doc pair."""
    rows = []
    for event in events:
        parsed_student = parse_student_from_calendar_title(str(event.get("title", "")))
        for meeting in meetings:
            if parsed_student is None:
                rows.append(
                    _debug_row(
                        event,
                        {"nome": "", "matricula": ""},
                        meeting,
                        score=0,
                        motivos_score="evento_nao_parseado",
                    )
                )
                continue

            calendar_subject = {
                **parsed_student,
                "calendar_start": event.get("start", ""),
            }
            score = score_calendar_event_to_meeting(calendar_subject, meeting)
            rows.append(
                _debug_row(
                    event,
                    parsed_student,
                    meeting,
                    score=score.confidence,
                    motivos_score=score.match_type,
                )
            )
    return rows


def write_debug_readia_matches_csv(
    rows: list[dict[str, Any]],
    report_date: str,
    *,
    preview_dir: Path = PREVIEW_DIR,
) -> Path:
    """Write debug rows with every event x Read IA doc combination."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    csv_path = preview_dir / f"debug_matches_{report_date}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DEBUG_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the agenda preview command."""
    parser = argparse.ArgumentParser(
        description="Gera preview diario por Google Agenda e Read IA."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do preview no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    return parser


def _matched_event_row(
    event: dict[str, Any],
    student: dict[str, str],
    match: MatchResult | None,
    report_date: str,
) -> dict[str, Any]:
    if match is None:
        return _base_row(
            event,
            student,
            report_date,
            categoria="faltas_candidatas",
            status="Falta",
            match_confidence=0,
            match_type="sem_match",
            motivo_falta=MOTIVO_SEM_RESPOSTA,
            observacao="sem match Read IA no dia",
        )

    if match.confidence >= 50:
        categoria = "presentes_confirmados"
        status = "Presente"
        observacao = "match confirmado"
        readia_summary = match.meeting.get("summary", "")
        course_detection = describe_consumed_courses_from_text(readia_summary)
        cursos_consumidos = ", ".join(course_detection.courses)
        motivo_deteccao_curso = course_detection.reason
        motivo_falta = ""
    else:
        categoria = "matches_fracos"
        status = "Falta"
        observacao = "score abaixo de 50; enviado como falta"
        readia_summary = ""
        cursos_consumidos = ""
        motivo_deteccao_curso = ""
        motivo_falta = MOTIVO_SEM_RESPOSTA

    return _base_row(
        event,
        student,
        report_date,
        categoria=categoria,
        status=status,
        match_confidence=match.confidence,
        match_type=match.match_type,
        readia_title=match.meeting.get("title", ""),
        readia_summary=readia_summary,
        readia_report_url=match.meeting.get("report_url", ""),
        cursos_consumidos=cursos_consumidos,
        motivo_deteccao_curso=motivo_deteccao_curso,
        motivo_falta=motivo_falta,
        observacao=observacao,
    )


def _unparsed_event_row(event: dict[str, Any], report_date: str) -> dict[str, Any]:
    return _base_row(
        event,
        {"nome": "", "matricula": ""},
        report_date,
        categoria="eventos_nao_parseados",
        status="Revisar",
        match_confidence=0,
        match_type="sem_matricula_no_titulo",
        observacao="evento sem nome/matricula reconhecivel no titulo",
    )


def _base_row(
    event: dict[str, Any],
    student: dict[str, str],
    report_date: str,
    *,
    categoria: str,
    status: str,
    match_confidence: int,
    match_type: str,
    observacao: str,
    readia_title: str = "",
    readia_summary: str = "",
    readia_report_url: str = "",
    cursos_consumidos: str = "",
    motivo_deteccao_curso: str = "",
    motivo_falta: str = "",
) -> dict[str, Any]:
    return {
        "data": report_date,
        "categoria": categoria,
        "status": status,
        "nome": student.get("nome", ""),
        "matricula": student.get("matricula", ""),
        "calendar_title": event.get("title", ""),
        "calendar_start": event.get("start", ""),
        "calendar_end": event.get("end", ""),
        "match_confidence": match_confidence,
        "match_type": match_type,
        "readia_title": readia_title,
        "readia_summary": readia_summary,
        "readia_report_url": readia_report_url,
        "cursos_consumidos": cursos_consumidos,
        "motivo_deteccao_curso": motivo_deteccao_curso,
        "motivo_falta": motivo_falta,
        "observacao": observacao,
    }


def _debug_row(
    event: dict[str, Any],
    student: dict[str, str],
    meeting: dict[str, Any],
    *,
    score: int,
    motivos_score: str,
) -> dict[str, Any]:
    return {
        "calendar_nome": student.get("nome", ""),
        "calendar_matricula": student.get("matricula", ""),
        "calendar_title": event.get("title", ""),
        "readia_title": meeting.get("title", ""),
        "readia_summary": _preview_cell(meeting.get("summary", "")),
        "readia_report_url": meeting.get("report_url", ""),
        "score": score,
        "motivos_score": motivos_score,
        "texto_usado_para_match": meeting_search_text(meeting),
    }


def _preview_cell(value: Any, max_length: int = 300) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "presentes_confirmados": 0,
        "matches_fracos": 0,
        "faltas_candidatas": 0,
        "eventos_nao_parseados": 0,
    }
    for row in rows:
        categoria = str(row.get("categoria", ""))
        if categoria in counts:
            counts[categoria] += 1
    return counts


def _print_weak_matches(rows: list[dict[str, Any]]) -> None:
    print("Matches fracos:")
    for row in rows:
        if row.get("categoria") != "matches_fracos":
            continue
        print(
            "  "
            f"{row.get('nome', '')} | {row.get('matricula', '')} | "
            f"score={row.get('match_confidence', '')} | "
            f"{row.get('match_type', '')} | "
            f"{row.get('readia_title', '')}"
        )


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = preview_monitoria_agenda_do_dia(report_date=args.report_date)
    except RuntimeError as exc:
        print(f"ERRO - {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
