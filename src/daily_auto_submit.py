"""Daily automatic submission from Google Calendar and Read IA payloads."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.models import MonitoriaPayload
from src.preview_monitoria_agenda_do_dia import (
    PREVIEW_DIR,
    preview_monitoria_agenda_do_dia,
)
from src.submission_runner import (
    SUBMISSION_LOG_DIR,
    _today_sao_paulo,
    parse_positive_int,
    parse_report_date,
)
from src.submit_monitoria_agenda_do_dia import submit_monitoria_agenda_do_dia


def daily_auto_submit(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    presentes_only: bool = False,
    faltas_only: bool = False,
    preview_dir: Path = PREVIEW_DIR,
    log_dir: Path = SUBMISSION_LOG_DIR,
    preview_runner: Callable[..., int] | None = None,
    submitter: Callable[[MonitoriaPayload], Any] | None = None,
) -> int:
    """Generate the daily preview and submit Presente/Falta rows from it."""
    if presentes_only and faltas_only:
        raise ValueError("Use apenas um filtro: --presentes-only ou --faltas-only.")

    target_date = report_date or _today_sao_paulo()
    run_preview = preview_runner or preview_monitoria_agenda_do_dia
    preview_exit_code = run_preview(report_date=target_date, preview_dir=preview_dir)
    if preview_exit_code != 0:
        return preview_exit_code

    return submit_monitoria_agenda_do_dia(
        dry_run=dry_run,
        report_date=target_date,
        limit=limit,
        presentes_only=presentes_only,
        faltas_only=faltas_only,
        assume_yes=assume_yes,
        preview_dir=preview_dir,
        log_dir=log_dir,
        submitter=submitter,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the daily automatic submission."""
    parser = argparse.ArgumentParser(
        description="Gera preview diario por agenda/Read IA e envia Presente/Falta."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do envio no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra exatamente o que seria enviado sem submeter ao Google Forms.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma automaticamente o envio real. Use apenas em agendamentos.",
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
        "--limit",
        type=parse_positive_int,
        help="Limita a quantidade de linhas enviaveis processadas.",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    if args.presentes_only and args.faltas_only:
        parser.error("Use apenas um filtro: --presentes-only ou --faltas-only.")

    try:
        exit_code = daily_auto_submit(
            dry_run=args.dry_run,
            assume_yes=args.yes,
            report_date=args.report_date,
            limit=args.limit,
            presentes_only=args.presentes_only,
            faltas_only=args.faltas_only,
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
