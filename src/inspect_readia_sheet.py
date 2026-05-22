"""Inspect Read IA webhook payloads stored in Google Sheets."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from typing import Any

from src.readia_matcher import normalize_readia_sheet_row, normalize_text
from src.sheets_client import (
    load_sheets_settings,
    read_readia_payload_rows,
    read_sheet_rows,
)
from src.submission_runner import parse_report_date


def inspect_readia_sheet(
    *,
    report_date: str | None = None,
    limit: int | None = None,
) -> int:
    """Print a compact summary of the latest Read IA payload rows."""
    rows = read_readia_payload_rows()
    if not rows:
        print("Nenhum payload Read IA encontrado na aba do Google Sheets.")
        return 0

    normalized_rows = [normalize_readia_sheet_row(row) for row in rows]
    date_counts = Counter(row.get("date") or "sem_data" for row in normalized_rows)
    known_students = _load_known_students()

    print(f"Total payloads na aba: {len(rows)}")
    print("Payloads por data:")
    for date_value, count in sorted(date_counts.items()):
        print(f"  {date_value}: {count}")

    display_pairs = [
        (row, meeting)
        for row, meeting in zip(rows, normalized_rows, strict=True)
        if report_date is None or meeting.get("date") == report_date
    ]
    if limit is not None and limit > 0:
        display_pairs = display_pairs[-limit:]

    if report_date:
        print(f"Filtro de data: {report_date}")
    print(f"Payloads exibidos: {len(display_pairs)}")
    if known_students:
        print(f"Alunos conhecidos carregados: {len(known_students)}")
    else:
        print("Alunos conhecidos carregados: 0")

    for row, meeting in display_pairs:
        payload_json = str(row.get("payload_json", "") or "")
        known_hits = _known_student_hits(payload_json, known_students)
        print(f"received_at: {row.get('received_at', '')}")
        print(f"  meeting_id: {row.get('meeting_id', '')}")
        print(f"  title: {row.get('title', '')}")
        print(f"  data_normalizada: {meeting.get('date', '')}")
        print(f"  summary: {_preview(row.get('summary', ''), max_length=300)}")
        print(f"  report_url: {row.get('report_url', '')}")
        print(f"  payload_json contem aluno conhecido: {_format_known_hits(known_hits)}")

    return 0


def _load_known_students() -> list[dict[str, str]]:
    try:
        settings = load_sheets_settings()
        rows = read_sheet_rows(settings.sheet_ativos)
    except Exception as exc:
        print(f"AVISO - nao foi possivel carregar alunos conhecidos: {exc}")
        return []

    return [
        {
            "nome": str(row.get("nome", "")).strip(),
            "matricula": str(row.get("matricula", "")).strip(),
        }
        for row in rows
        if str(row.get("nome", "")).strip() or str(row.get("matricula", "")).strip()
    ]


def _known_student_hits(
    payload_json: str,
    students: list[Mapping[str, str]],
) -> list[str]:
    normalized_payload = normalize_text(payload_json)
    identifier_payload = _normalize_identifier(payload_json)
    hits = []

    for student in students:
        name = str(student.get("nome", "")).strip()
        matricula = str(student.get("matricula", "")).strip()
        hit_reasons = []
        if matricula and _normalize_identifier(matricula) in identifier_payload:
            hit_reasons.append("matricula")
        if name and _contains_normalized_phrase(normalized_payload, normalize_text(name)):
            hit_reasons.append("nome")

        if hit_reasons:
            label = f"{name} {matricula}".strip()
            hits.append(f"{label} ({'+'.join(hit_reasons)})")

    return hits


def _format_known_hits(hits: list[str]) -> str:
    if not hits:
        return "nao"
    return "sim - " + "; ".join(hits)


def _contains_normalized_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _normalize_identifier(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _preview(value: Any, max_length: int = 300) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mostra os ultimos payloads Read IA salvos no Google Sheets."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Quantidade de linhas finais para mostrar apos o filtro de data.",
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Filtra payloads exibidos pela data YYYY-MM-DD.",
    )
    args = parser.parse_args()
    raise SystemExit(
        inspect_readia_sheet(report_date=args.report_date, limit=args.limit)
    )


if __name__ == "__main__":
    main()
