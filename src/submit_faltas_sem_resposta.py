"""Submission flow for absence reports."""

from __future__ import annotations

import sys

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_FALTA = "Falta"
MOTIVO_SEM_RESPOSTA = "Sem resposta"


def submit_faltas_sem_resposta(
    dry_run: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    assume_yes: bool = False,
) -> int:
    """Submit absence reports from the configured absences sheet."""
    settings = load_sheets_settings()
    return run_submission(
        sheet_name=settings.sheet_faltas,
        status=STATUS_FALTA,
        dry_run=dry_run,
        payload_defaults={"motivo_falta": MOTIVO_SEM_RESPOSTA},
        report_date=report_date,
        limit=limit,
        only_matricula=only_matricula,
        allow_missing_sheet=True,
        assume_yes=assume_yes,
        skip_existing=True,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia faltas para o Google Forms.")
    args = parser.parse_args()
    sys.exit(
        submit_faltas_sem_resposta(
            dry_run=args.dry_run,
            report_date=args.report_date,
            limit=args.limit,
            only_matricula=args.only_matricula,
            assume_yes=args.yes,
        )
    )


if __name__ == "__main__":
    main()
