"""Shared command-line runner for spreadsheet-to-form submissions."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.forms_client import submit_monitoria
from src.models import MonitoriaPayload
from src.sheets_client import read_sheet_rows

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


def build_parser(description: str) -> argparse.ArgumentParser:
    """Build a parser with the common submission options."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria enviado sem submeter ao Google Forms.",
    )
    return parser


def run_submission(
    *,
    sheet_name: str,
    status: str,
    dry_run: bool,
    payload_defaults: dict[str, Any] | None = None,
    submitter: Callable[[MonitoriaPayload], Any] = submit_monitoria,
) -> None:
    """Read students from a sheet and submit each one to Google Forms."""
    rows = read_sheet_rows(sheet_name)
    payloads = [_row_to_payload(row, status, payload_defaults or {}) for row in rows]

    print(f"Alunos encontrados na aba '{sheet_name}': {len(payloads)}")

    if not payloads:
        return

    if dry_run:
        for payload in payloads:
            print(f"[DRY-RUN] {asdict(payload)}")
        return

    confirmation = input("Digite ENVIAR para confirmar o envio: ").strip()
    if confirmation != "ENVIAR":
        print("Envio cancelado.")
        return

    for payload in payloads:
        try:
            response = submitter(payload)
            if response.ok:
                print(
                    f"[OK] {payload.nome} ({payload.matricula}) "
                    f"- HTTP {response.status_code}"
                )
            else:
                print(
                    f"[ERRO] {payload.nome} ({payload.matricula}) "
                    f"- HTTP {response.status_code}: {response.text[:200]}"
                )
        except Exception as exc:
            print(f"[ERRO] {payload.nome} ({payload.matricula}) - {exc}")


def _row_to_payload(
    row: dict[str, Any],
    status: str,
    payload_defaults: dict[str, Any],
) -> MonitoriaPayload:
    return MonitoriaPayload(
        nome=str(row["nome"]).strip(),
        matricula=str(row["matricula"]).strip(),
        data=_today_sao_paulo(),
        agente=str(row.get("agente", "")).strip(),
        status=status,
        **payload_defaults,
    )


def _today_sao_paulo() -> str:
    return datetime.now(SAO_PAULO_TZ).date().isoformat()
