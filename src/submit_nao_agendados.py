"""Submission flow for reports of sessions not scheduled in advance."""

from __future__ import annotations

import sys

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_NAO_AGENDADO = "Aluno não agendado(Fantasma)"


def submit_nao_agendados(dry_run: bool = False) -> int:
    """Submit reports for unscheduled sessions."""
    settings = load_sheets_settings()
    return run_submission(
        sheet_name=settings.sheet_nao_agendados,
        status=STATUS_NAO_AGENDADO,
        dry_run=dry_run,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia alunos nao agendados para o Google Forms.")
    args = parser.parse_args()
    sys.exit(submit_nao_agendados(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
