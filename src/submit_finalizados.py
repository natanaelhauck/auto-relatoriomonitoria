"""Submission flow for completed monitoring sessions."""

from __future__ import annotations

import sys

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_FINALIZADO = "Aluno finalizou o curso"


def submit_finalizados(
    dry_run: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
) -> int:
    """Submit reports for completed sessions."""
    settings = load_sheets_settings()
    return run_submission(
        sheet_name=settings.sheet_finalizados,
        status=STATUS_FINALIZADO,
        dry_run=dry_run,
        report_date=report_date,
        limit=limit,
        only_matricula=only_matricula,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia alunos finalizados para o Google Forms.")
    args = parser.parse_args()
    sys.exit(
        submit_finalizados(
            dry_run=args.dry_run,
            report_date=args.report_date,
            limit=args.limit,
            only_matricula=args.only_matricula,
        )
    )


if __name__ == "__main__":
    main()
