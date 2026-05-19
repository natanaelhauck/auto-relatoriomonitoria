"""Weekly automatic submission for monitoring reports."""

from __future__ import annotations

import sys

from src.sheets_client import SheetsSettings, load_sheets_settings, read_sheet_rows
from src.submission_runner import (
    build_parser,
    build_payloads,
    run_prepared_batch,
    _today_sao_paulo,
)
from src.submit_finalizados import STATUS_FINALIZADO
from src.submit_nao_agendados import STATUS_NAO_AGENDADO


def weekly_auto_submit(
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    report_date: str | None = None,
    limit: int | None = None,
) -> int:
    """Submit weekly unscheduled and completed student reports."""
    settings = load_sheets_settings()
    payloads, ignored_rows, total_rows = build_weekly_payloads(
        settings,
        report_date or _today_sao_paulo(),
        limit=limit,
    )

    return run_prepared_batch(
        payloads,
        dry_run=dry_run,
        total_rows=total_rows,
        ignored_rows=ignored_rows,
        limit=limit,
        assume_yes=assume_yes,
        skip_existing=True,
    )


def build_weekly_payloads(
    settings: SheetsSettings,
    report_date: str,
    *,
    limit: int | None = None,
) -> tuple[list, list[tuple[int, str]], int]:
    """Build the combined weekly payload list from configured sheets."""
    nao_agendados_rows = read_sheet_rows(settings.sheet_nao_agendados)
    finalizados_rows = read_sheet_rows(settings.sheet_finalizados)
    total_rows = len(nao_agendados_rows) + len(finalizados_rows)

    nao_agendados_payloads, nao_agendados_ignored = build_payloads(
        nao_agendados_rows,
        STATUS_NAO_AGENDADO,
        report_date,
    )
    finalizados_payloads, finalizados_ignored = build_payloads(
        finalizados_rows,
        STATUS_FINALIZADO,
        report_date,
    )

    payloads = nao_agendados_payloads + finalizados_payloads
    if limit is not None:
        payloads = payloads[:limit]

    ignored_rows = nao_agendados_ignored + [
        (row_number + len(nao_agendados_rows), reason)
        for row_number, reason in finalizados_ignored
    ]

    return payloads, ignored_rows, total_rows


def main() -> None:
    """CLI entry point."""
    parser = build_parser("Envia automaticamente os relatorios semanais.")
    args = parser.parse_args()
    sys.exit(
        weekly_auto_submit(
            dry_run=args.dry_run,
            assume_yes=args.yes,
            report_date=args.report_date,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
