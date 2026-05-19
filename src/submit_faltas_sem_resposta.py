"""Submission flow for absences without response."""

from __future__ import annotations

import sys

from src.sheets_client import load_sheets_settings
from src.submission_runner import build_parser, run_submission

STATUS_FALTA = "Falta"
MOTIVO_SEM_RESPOSTA = "Sem resposta"


def submit_faltas_sem_resposta(dry_run: bool = False) -> int:
    """Submit absence reports using the default no-response reason."""
    settings = load_sheets_settings()
    return run_submission(
        sheet_name=settings.sheet_faltas,
        status=STATUS_FALTA,
        dry_run=dry_run,
        payload_defaults={"motivo_falta": MOTIVO_SEM_RESPOSTA},
        allow_missing_sheet=True,
    )


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia faltas sem resposta para o Google Forms.")
    args = parser.parse_args()
    sys.exit(submit_faltas_sem_resposta(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
