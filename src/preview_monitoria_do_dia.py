"""Generate a safe daily preview for attendance and absence candidates."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from src.readia_matcher import MatchResult, best_match_student_to_meetings, load_readia_meetings
from src.sheets_client import load_sheets_settings, read_sheet_rows
from src.submission_runner import _today_sao_paulo, parse_report_date

PREVIEW_DIR = Path("data/previews")
CSV_FIELDS = [
    "data",
    "categoria",
    "nome",
    "matricula",
    "email",
    "match_confidence",
    "match_type",
    "readia_title",
    "readia_report_url",
    "observacao",
]


def preview_monitoria_do_dia(
    *,
    report_date: str | None = None,
    preview_dir: Path = PREVIEW_DIR,
) -> int:
    """Read active students and Read IA payloads, then write a review CSV."""
    target_date = report_date or _today_sao_paulo()
    settings = load_sheets_settings()
    students = read_sheet_rows(settings.sheet_ativos)
    meetings = load_readia_meetings(report_date=target_date)
    rows = build_preview_rows(students, meetings, target_date)
    csv_path = write_preview_csv(rows, target_date, preview_dir=preview_dir)

    counts = _category_counts(rows)
    print(f"Total ativos: {len(students)}")
    print(f"Total payloads Read IA do dia: {len(meetings)}")
    print(f"Presentes confirmados: {counts['presentes_confirmados']}")
    print(f"Matches fracos: {counts['matches_fracos']}")
    print(f"Faltas candidatas: {counts['faltas_candidatas']}")
    print(f"Caminho do CSV gerado: {csv_path}")
    return 0


def build_preview_rows(
    students: list[dict[str, Any]],
    meetings: list[dict[str, Any]],
    report_date: str,
) -> list[dict[str, Any]]:
    """Build review rows for active students against Read IA meetings."""
    rows = []
    for student in students:
        match = best_match_student_to_meetings(student, meetings)
        rows.append(_preview_row(student, match, report_date))
    return rows


def write_preview_csv(
    rows: list[dict[str, Any]],
    report_date: str,
    *,
    preview_dir: Path = PREVIEW_DIR,
) -> Path:
    """Write preview rows to a dated CSV file."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    csv_path = preview_dir / f"preview_monitoria_{report_date}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the preview command."""
    parser = argparse.ArgumentParser(
        description="Gera preview diario de presencas e faltas por Read IA."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do preview no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    return parser


def _preview_row(
    student: dict[str, Any],
    match: MatchResult | None,
    report_date: str,
) -> dict[str, Any]:
    if match is None:
        return {
            "data": report_date,
            "categoria": "faltas_candidatas",
            "nome": student.get("nome", ""),
            "matricula": student.get("matricula", ""),
            "email": student.get("email", ""),
            "match_confidence": 0,
            "match_type": "sem_match",
            "readia_title": "",
            "readia_report_url": "",
            "observacao": "sem match Read IA no dia",
        }

    if match.confidence >= 50:
        categoria = "presentes_confirmados"
        observacao = "match confirmado"
    else:
        categoria = "matches_fracos"
        observacao = "revisar antes de enviar"

    return {
        "data": report_date,
        "categoria": categoria,
        "nome": student.get("nome", ""),
        "matricula": student.get("matricula", ""),
        "email": student.get("email", ""),
        "match_confidence": match.confidence,
        "match_type": match.match_type,
        "readia_title": match.meeting.get("title", ""),
        "readia_report_url": match.meeting.get("report_url", ""),
        "observacao": observacao,
    }


def _category_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "presentes_confirmados": 0,
        "matches_fracos": 0,
        "faltas_candidatas": 0,
    }
    for row in rows:
        categoria = str(row.get("categoria", ""))
        if categoria in counts:
            counts[categoria] += 1
    return counts


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(preview_monitoria_do_dia(report_date=args.report_date))


if __name__ == "__main__":
    main()
