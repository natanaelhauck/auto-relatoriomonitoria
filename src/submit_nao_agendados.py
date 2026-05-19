"""Submission flow for reports of sessions not scheduled in advance."""

from __future__ import annotations

import sys

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_NAO_AGENDADO = "Aluno não agendado(Fantasma)"


def submit_nao_agendados(
    dry_run: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    assume_yes: bool = False,
) -> int:
    """Submit reports for unscheduled sessions."""
    settings = load_sheets_settings()
    return run_submission(
        sheet_name=settings.sheet_nao_agendados,
        status=STATUS_NAO_AGENDADO,
        dry_run=dry_run,
        report_date=report_date,
        limit=limit,
        only_matricula=only_matricula,
        assume_yes=assume_yes,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia alunos nao agendados para o Google Forms.")
    args = parser.parse_args()
    sys.exit(
        submit_nao_agendados(
            dry_run=args.dry_run,
            report_date=args.report_date,
            limit=args.limit,
            only_matricula=args.only_matricula,
            assume_yes=args.yes,
        )
    )


if __name__ == "__main__":
    main()
