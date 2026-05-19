"""Shared command-line runner for spreadsheet-to-form submissions."""

from __future__ import annotations

import argparse
import csv
import os
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.forms_client import submit_monitoria
from src.models import MonitoriaPayload
from src.sheets_client import read_sheet_rows

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
SUBMISSION_LOG_DIR = Path("data/submission_logs")


def build_parser(description: str) -> argparse.ArgumentParser:
    """Build a parser with the common submission options."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria enviado sem submeter ao Google Forms.",
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        type=parse_report_date,
        help="Data do relatorio no formato YYYY-MM-DD. Padrao: hoje em America/Sao_Paulo.",
    )
    parser.add_argument(
        "--limit",
        type=parse_positive_int,
        help="Limita a quantidade de alunos processados.",
    )
    parser.add_argument(
        "--only-matricula",
        help="Processa apenas a matricula informada.",
    )
    return parser


def run_submission(
    *,
    sheet_name: str,
    status: str,
    dry_run: bool,
    payload_defaults: dict[str, Any] | None = None,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    allow_missing_sheet: bool = False,
    submitter: Callable[[MonitoriaPayload], Any] = submit_monitoria,
) -> int:
    """Read students from a sheet and submit each one to Google Forms."""
    rows = read_sheet_rows(
        sheet_name,
        allow_missing_sheet=dry_run or allow_missing_sheet,
    )
    return run_batch(
        rows,
        status,
        dry_run,
        payload_defaults=payload_defaults,
        report_date=report_date,
        limit=limit,
        only_matricula=only_matricula,
        submitter=submitter,
    )


def run_batch(
    rows: list[dict[str, Any]],
    status: str,
    dry_run: bool,
    *,
    payload_defaults: dict[str, Any] | None = None,
    report_date: str | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    submitter: Callable[[MonitoriaPayload], Any] = submit_monitoria,
) -> int:
    """Submit a batch of normalized student rows.

    Returns:
        Exit code 0 when every valid row is processed successfully, otherwise 1.
    """
    filtered_rows = _filter_rows(rows, only_matricula=only_matricula)
    limited_rows = filtered_rows[:limit] if limit is not None else filtered_rows
    payloads, ignored_rows = _build_payloads(
        limited_rows,
        status,
        payload_defaults or {},
        report_date or _today_sao_paulo(),
    )

    print(f"Total de linhas lidas: {len(rows)}")
    if only_matricula:
        print(f"Filtro matricula: {only_matricula}")
    if limit is not None:
        print(f"Limite: {limit}")
    print(f"Total validas: {len(payloads)}")
    print(f"Total ignoradas: {len(rows) - len(payloads)}")

    for row_number, reason in ignored_rows:
        print(f"IGNORADA - linha {row_number} - {reason}")

    if dry_run:
        for payload in payloads:
            print(f"[DRY-RUN] {asdict(payload)}")
        return 1 if ignored_rows else 0

    if not payloads:
        return 1 if ignored_rows else 0

    confirmation = input("Digite exatamente ENVIAR para confirmar o envio: ").strip()
    if confirmation != "ENVIAR":
        print("Envio cancelado.")
        return 1

    log_path = _new_submission_log_path()
    had_error = bool(ignored_rows)

    with log_path.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=[
                "timestamp",
                "nome",
                "matricula",
                "data",
                "agente",
                "status",
                "resultado",
                "detalhe",
            ],
        )
        writer.writeheader()

        for payload in payloads:
            resultado, detalhe = _send_payload(payload, submitter)
            writer.writerow(_log_row(payload, resultado, detalhe))

            if resultado == "OK":
                print(f"OK - {payload.nome} - {payload.matricula}")
            else:
                had_error = True
                print(f"ERRO - {payload.nome} - {payload.matricula} - {detalhe}")

            time.sleep(0.5)

    print(f"Log de envio: {log_path}")
    return 1 if had_error else 0


def _build_payloads(
    rows: list[dict[str, Any]],
    status: str,
    payload_defaults: dict[str, Any],
    report_date: str,
) -> tuple[list[MonitoriaPayload], list[tuple[int, str]]]:
    payloads: list[MonitoriaPayload] = []
    ignored_rows: list[tuple[int, str]] = []

    for index, row in enumerate(rows, start=1):
        try:
            payloads.append(_row_to_payload(row, status, payload_defaults, report_date))
        except ValueError as exc:
            ignored_rows.append((index, str(exc)))

    return payloads, ignored_rows


def _row_to_payload(
    row: dict[str, Any],
    status: str,
    payload_defaults: dict[str, Any],
    report_date: str,
) -> MonitoriaPayload:
    load_dotenv()
    default_agente = os.getenv("DEFAULT_AGENTE", "").strip()
    nome = str(row.get("nome", "")).strip()
    matricula = str(row.get("matricula", "")).strip()
    agente = str(row.get("agente", "")).strip() or default_agente

    if not nome:
        raise ValueError("nome vazio")
    if not matricula:
        raise ValueError("matricula vazia")

    return MonitoriaPayload(
        nome=nome,
        matricula=matricula,
        data=report_date,
        agente=agente,
        status=status,
        **payload_defaults,
    )


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    only_matricula: str | None,
) -> list[dict[str, Any]]:
    if not only_matricula:
        return rows

    wanted = only_matricula.strip().casefold()
    return [
        row
        for row in rows
        if str(row.get("matricula", "")).strip().casefold() == wanted
    ]


def parse_report_date(value: str) -> str:
    """Validate and normalize a report date argument."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "data invalida; use o formato YYYY-MM-DD"
        ) from exc


def parse_positive_int(value: str) -> int:
    """Validate a positive integer CLI argument."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit deve ser um inteiro positivo") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError("limit deve ser um inteiro positivo")

    return parsed


def _send_payload(
    payload: MonitoriaPayload,
    submitter: Callable[[MonitoriaPayload], Any],
) -> tuple[str, str]:
    try:
        response = submitter(payload)
    except Exception as exc:
        return "ERRO", str(exc)

    if response.ok:
        return "OK", f"HTTP {response.status_code}"

    return "ERRO", f"HTTP {response.status_code}: {response.text[:200]}"


def _new_submission_log_path() -> Path:
    SUBMISSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(SAO_PAULO_TZ).strftime("%Y%m%dT%H%M%S%z")
    return SUBMISSION_LOG_DIR / f"{timestamp}.csv"


def _log_row(payload: MonitoriaPayload, resultado: str, detalhe: str) -> dict[str, str]:
    return {
        "timestamp": datetime.now(SAO_PAULO_TZ).isoformat(),
        "nome": payload.nome,
        "matricula": payload.matricula,
        "data": payload.data,
        "agente": payload.agente,
        "status": payload.status,
        "resultado": resultado,
        "detalhe": detalhe,
    }


def _today_sao_paulo() -> str:
    return datetime.now(SAO_PAULO_TZ).date().isoformat()
