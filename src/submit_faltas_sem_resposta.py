"""Submission flow for absence reports."""

from __future__ import annotations

import sys

from src.calendar_client import get_events_for_date
from src.preview_monitoria_agenda_do_dia import build_agenda_preview_rows
from src.readia_matcher import load_readia_meetings
from src.submission_runner import _today_sao_paulo, build_parser, run_batch

STATUS_FALTA = "Falta"
MOTIVO_SEM_RESPOSTA = "Sem resposta"


def submit_faltas_sem_resposta(
    dry_run: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    assume_yes: bool = False,
) -> int:
    """Submit absence reports from calendar events without a Read IA match."""
    target_date = report_date or _today_sao_paulo()
    rows = build_faltas_rows_from_agenda_readia(target_date)
    return run_batch(
        rows,
        status=STATUS_FALTA,
        dry_run=dry_run,
        payload_defaults={"motivo_falta": MOTIVO_SEM_RESPOSTA},
        report_date=target_date,
        limit=limit,
        only_matricula=only_matricula,
        assume_yes=assume_yes,
        skip_existing=True,
    )


def build_faltas_rows_from_agenda_readia(report_date: str) -> list[dict[str, str]]:
    """Return students scheduled in Calendar and absent from Read IA records."""
    events = get_events_for_date(report_date)
    meetings = load_readia_meetings(report_date=report_date)
    preview_rows = build_agenda_preview_rows(events, meetings, report_date)
    return [
        {
            "nome": str(row.get("nome", "")).strip(),
            "matricula": str(row.get("matricula", "")).strip(),
            "motivo_falta": MOTIVO_SEM_RESPOSTA,
        }
        for row in preview_rows
        if row.get("categoria") == "faltas_candidatas"
    ]


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
