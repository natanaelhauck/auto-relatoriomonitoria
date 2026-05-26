"""Submission flow based on the daily agenda preview CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.course_detection import (
    describe_consumed_courses_from_text,
    detect_consumed_courses_from_text,
)
from src.models import MonitoriaPayload
from src.preview_monitoria_agenda_do_dia import PREVIEW_DIR
from src.submission_runner import (
    SUBMISSION_LOG_DIR,
    _today_sao_paulo,
    build_payloads,
    parse_positive_int,
    parse_report_date,
    run_prepared_batch,
)

STATUS_PRESENTE = "Presente"
STATUS_FALTA = "Falta"
MOTIVO_SEM_RESPOSTA = "Sem resposta"
RELATORIO_READIA_INDISPONIVEL = "Resumo não disponível"


def submit_monitoria_agenda_do_dia(
    *,
    dry_run: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    presentes_only: bool = False,
    faltas_only: bool = False,
    assume_yes: bool = False,
    preview_dir: Path = PREVIEW_DIR,
    log_dir: Path = SUBMISSION_LOG_DIR,
    submitter: Callable[[MonitoriaPayload], Any] | None = None,
) -> int:
    """Submit attendance and absence reports from a dated agenda preview CSV."""
    if presentes_only and faltas_only:
        raise ValueError("Use apenas um filtro: --presentes-only ou --faltas-only.")

    target_date = report_date or _today_sao_paulo()
    preview_path = preview_dir / f"preview_agenda_monitoria_{target_date}.csv"
    preview_rows = read_preview_rows(preview_path)
    selected_rows = select_preview_rows(
        preview_rows,
        only_matricula=only_matricula,
        presentes_only=presentes_only,
        faltas_only=faltas_only,
    )
    if limit is not None:
        selected_rows = selected_rows[:limit]

    payloads, ignored_rows = build_payloads_from_preview(selected_rows, target_date)
    kwargs: dict[str, Any] = {}
    if submitter is not None:
        kwargs["submitter"] = submitter

    return run_prepared_batch(
        payloads,
        dry_run=dry_run,
        total_rows=len(preview_rows),
        ignored_rows=ignored_rows,
        limit=limit,
        only_matricula=only_matricula,
        assume_yes=assume_yes,
        skip_existing=True,
        duplicate_scope="daily",
        log_dir=log_dir,
        dry_run_formatter=_dry_run_payload,
        **kwargs,
    )


def read_preview_rows(preview_path: Path) -> list[dict[str, str]]:
    """Read a generated agenda preview CSV."""
    if not preview_path.exists():
        raise RuntimeError(
            "CSV de preview nao encontrado. Gere antes com: "
            "python -m src.preview_monitoria_agenda_do_dia --date YYYY-MM-DD"
        )

    with preview_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def select_preview_rows(
    rows: list[dict[str, str]],
    *,
    only_matricula: str | None = None,
    presentes_only: bool = False,
    faltas_only: bool = False,
) -> list[dict[str, str]]:
    """Filter preview rows eligible for submission."""
    selected = []
    wanted_matricula = only_matricula.strip().casefold() if only_matricula else ""

    for row in rows:
        status = _form_status(row.get("status"))
        if status not in {STATUS_PRESENTE, STATUS_FALTA}:
            continue
        if presentes_only and status != STATUS_PRESENTE:
            continue
        if faltas_only and status != STATUS_FALTA:
            continue
        row_matricula = row.get("matricula", "").strip().casefold()
        if wanted_matricula and row_matricula != wanted_matricula:
            continue
        selected.append(row)

    return selected


def build_payloads_from_preview(
    rows: list[dict[str, str]],
    report_date: str,
) -> tuple[list[MonitoriaPayload], list[tuple[int, str]]]:
    """Build form payloads from preview rows that already have a sendable status."""
    payloads: list[MonitoriaPayload] = []
    ignored_rows: list[tuple[int, str]] = []

    for index, row in enumerate(rows, start=1):
        status = _form_status(row.get("status"))
        batch_rows = [_submission_row(row, status)]
        defaults = (
            {"motivo_falta": MOTIVO_SEM_RESPOSTA}
            if status == STATUS_FALTA
            else None
        )
        row_payloads, row_ignored = build_payloads(
            batch_rows,
            status,
            report_date,
            payload_defaults=defaults,
        )
        payloads.extend(row_payloads)
        ignored_rows.extend((index, reason) for _, reason in row_ignored)

    return payloads, ignored_rows


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for daily agenda preview submissions."""
    parser = argparse.ArgumentParser(
        description="Envia Presente/Falta a partir do preview diario da agenda."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do preview no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra exatamente o que seria enviado sem submeter ao Google Forms.",
    )
    parser.add_argument(
        "--limit",
        type=parse_positive_int,
        help="Limita a quantidade de linhas enviaveis processadas.",
    )
    parser.add_argument(
        "--only-matricula",
        help="Processa apenas a matricula informada.",
    )
    parser.add_argument(
        "--presentes-only",
        action="store_true",
        help="Processa apenas linhas Presente.",
    )
    parser.add_argument(
        "--faltas-only",
        action="store_true",
        help="Processa apenas linhas Falta.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma automaticamente o envio real. Use apenas em agendamentos.",
    )
    return parser


def _submission_row(row: dict[str, str], status: str) -> dict[str, Any]:
    base_row: dict[str, Any] = {
        "nome": row.get("nome", ""),
        "matricula": row.get("matricula", ""),
    }
    if status == STATUS_PRESENTE:
        relatorio_readia = _readia_report(row)
        course_detection = describe_consumed_courses_from_text(relatorio_readia)
        base_row.update(
            {
                "relatorio_readia": relatorio_readia,
                "link_readia": row.get("readia_report_url", ""),
                "cursos_consumidos": course_detection.courses,
            }
        )
    elif status == STATUS_FALTA:
        base_row["motivo_falta"] = MOTIVO_SEM_RESPOSTA
    return base_row


def _readia_report(row: dict[str, str]) -> str:
    for field_name in ("readia_summary", "summary"):
        value = str(row.get(field_name, "")).strip()
        if value:
            return value
    return RELATORIO_READIA_INDISPONIVEL


def detect_courses_from_text(text: Any) -> list[str]:
    return detect_consumed_courses_from_text(str(text or ""))


def _dry_run_payload(payload: MonitoriaPayload) -> dict[str, Any]:
    data: dict[str, Any] = {
        "nome": payload.nome,
        "matricula": payload.matricula,
        "status": payload.status,
    }
    if payload.status == STATUS_PRESENTE:
        course_detection = describe_consumed_courses_from_text(payload.relatorio_readia)
        data.update(
            {
                "relatorio_readia": _preview_text(payload.relatorio_readia, 120),
                "link_readia": payload.link_readia or "",
                "cursos_consumidos": payload.cursos_consumidos,
                "motivo_deteccao_curso": course_detection.reason,
            }
        )
    if payload.status == STATUS_FALTA:
        data["motivo_falta"] = payload.motivo_falta or MOTIVO_SEM_RESPOSTA
    return data


def _preview_text(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _form_status(value: Any) -> str:
    status = str(value or "").strip()
    normalized = status.casefold().replace("ç", "c")
    if normalized == "presente" or normalized == "presenca":
        return STATUS_PRESENTE
    if normalized == "falta":
        return STATUS_FALTA
    return status


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    if args.presentes_only and args.faltas_only:
        parser.error("Use apenas um filtro: --presentes-only ou --faltas-only.")

    try:
        exit_code = submit_monitoria_agenda_do_dia(
            dry_run=args.dry_run,
            report_date=args.report_date,
            limit=args.limit,
            only_matricula=args.only_matricula,
            presentes_only=args.presentes_only,
            faltas_only=args.faltas_only,
            assume_yes=args.yes,
        )
    except RuntimeError as exc:
        print(f"ERRO - {exc}")
        exit_code = 1
    except ValueError as exc:
        print(f"ERRO - {exc}")
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
