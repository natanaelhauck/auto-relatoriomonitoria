"""Submission flow for completed monitoring sessions."""

from __future__ import annotations

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_FINALIZADO = "Aluno finalizou o curso"


def submit_finalizados(dry_run: bool = False) -> None:
    """Submit reports for completed sessions."""
    settings = load_sheets_settings()
    run_submission(
        sheet_name=settings.sheet_finalizados,
        status=STATUS_FINALIZADO,
        dry_run=dry_run,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia alunos finalizados para o Google Forms.")
    args = parser.parse_args()
    submit_finalizados(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
