"""Shared command-line runner for spreadsheet-to-form submissions."""

from __future__ import annotations

import argparse
import csv
import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.date_utils import get_iso_week_info
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
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma automaticamente o envio real. Use apenas em agendamentos.",
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
    assume_yes: bool = False,
    skip_existing: bool = False,
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
        assume_yes=assume_yes,
        skip_existing=skip_existing,
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
    assume_yes: bool = False,
    skip_existing: bool = False,
    log_dir: Path = SUBMISSION_LOG_DIR,
    submitter: Callable[[MonitoriaPayload], Any] = submit_monitoria,
) -> int:
    """Submit a batch of normalized student rows.

    Returns:
        Exit code 0 when every valid row is processed successfully, otherwise 1.
    """
    filtered_rows = _filter_rows(rows, only_matricula=only_matricula)
    limited_rows = filtered_rows[:limit] if limit is not None else filtered_rows
    payloads, ignored_rows = build_payloads(
        limited_rows,
        status,
        report_date or _today_sao_paulo(),
        payload_defaults=payload_defaults,
    )

    return run_prepared_batch(
        payloads,
        dry_run=dry_run,
        total_rows=len(rows),
        ignored_rows=ignored_rows,
        filtered_count=len(filtered_rows),
        limit=limit,
        only_matricula=only_matricula,
        assume_yes=assume_yes,
        skip_existing=skip_existing,
        log_dir=log_dir,
        submitter=submitter,
    )


def run_prepared_batch(
    payloads: list[MonitoriaPayload],
    *,
    dry_run: bool,
    total_rows: int,
    ignored_rows: list[tuple[int, str]] | None = None,
    filtered_count: int | None = None,
    limit: int | None = None,
    only_matricula: str | None = None,
    assume_yes: bool = False,
    skip_existing: bool = False,
    log_dir: Path = SUBMISSION_LOG_DIR,
    submitter: Callable[[MonitoriaPayload], Any] = submit_monitoria,
) -> int:
    """Process already built payloads with optional duplicate skipping."""
    ignored_rows = ignored_rows or []
    existing_keys = load_existing_submission_keys(log_dir) if skip_existing else set()
    payloads_to_send: list[MonitoriaPayload] = []
    skipped_count = 0

    for payload in payloads:
        if _payload_key(payload) in existing_keys:
            skipped_count += 1
            print(
                f"PULADO - {payload.nome} - {payload.matricula} "
                "- já enviado nesta semana/status"
            )
            continue
        payloads_to_send.append(payload)

    print(f"Total de linhas lidas: {total_rows}")
    if only_matricula:
        print(f"Filtro matricula: {only_matricula}")
    if limit is not None:
        print(f"Limite: {limit}")
    print(f"Total validas: {len(payloads)}")
    print(f"Total ignoradas: {total_rows - len(payloads)}")
    if skip_existing:
        print(f"Total puladas por duplicidade: {skipped_count}")

    for row_number, reason in ignored_rows:
        print(f"IGNORADA - linha {row_number} - {reason}")

    if dry_run:
        for payload in payloads_to_send:
            print(f"[DRY-RUN] {asdict(payload)}")
        return 1 if ignored_rows else 0

    if not payloads_to_send:
        return 1 if ignored_rows else 0

    if not assume_yes:
        confirmation = input("Digite exatamente ENVIAR para confirmar o envio: ").strip()
        if confirmation != "ENVIAR":
            print("Envio cancelado.")
            return 1

    log_path = _new_submission_log_path(log_dir)
    had_error = bool(ignored_rows)

    with log_path.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=[
                "timestamp",
                "nome",
                "matricula",
                "data",
                "iso_year",
                "iso_week",
                "agente",
                "status",
                "resultado",
                "detalhe",
            ],
        )
        writer.writeheader()

        for payload in payloads_to_send:
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


def build_payloads(
    rows: list[dict[str, Any]],
    status: str,
    report_date: str,
    *,
    payload_defaults: dict[str, Any] | None = None,
) -> tuple[list[MonitoriaPayload], list[tuple[int, str]]]:
    payloads: list[MonitoriaPayload] = []
    ignored_rows: list[tuple[int, str]] = []

    for index, row in enumerate(rows, start=1):
        try:
            payloads.append(_row_to_payload(row, status, payload_defaults or {}, report_date))
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
    extra_fields = _payload_extra_fields(row, payload_defaults)

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
        **extra_fields,
    )


def _payload_extra_fields(
    row: dict[str, Any],
    payload_defaults: dict[str, Any],
) -> dict[str, Any]:
    extra_fields = dict(payload_defaults)

    for field_name in (
        "motivo_falta",
        "outro_motivo",
        "relatorio_readia",
        "link_readia",
    ):
        value = str(row.get(field_name, "")).strip()
        if value:
            extra_fields[field_name] = value

    cursos_consumidos = _parse_courses(row.get("cursos_consumidos"))
    if cursos_consumidos:
        extra_fields["cursos_consumidos"] = cursos_consumidos

    return extra_fields


def _parse_courses(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value or "").strip()
    if not text:
        return []

    return [course.strip() for course in re.split(r"[,;|\n]+", text) if course.strip()]


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


def load_existing_submission_keys(log_dir: Path = SUBMISSION_LOG_DIR) -> set[tuple[str, str, int, int]]:
    """Load successful submission keys from previous CSV logs."""
    if not log_dir.exists():
        return set()

    keys: set[tuple[str, str, int, int]] = set()
    for path in log_dir.glob("*.csv"):
        try:
            with path.open(newline="", encoding="utf-8") as log_file:
                for row in csv.DictReader(log_file):
                    if row.get("resultado") == "OK":
                        key = _log_row_key(row)
                        if key is not None:
                            keys.add(key)
        except OSError:
            continue

    return keys


def _log_row_key(row: dict[str, str]) -> tuple[str, str, int, int] | None:
    matricula = str(row.get("matricula", "")).strip().casefold()
    status = str(row.get("status", "")).strip()
    if not matricula or not status:
        return None

    try:
        if row.get("iso_year") and row.get("iso_week"):
            iso_year = int(str(row["iso_year"]).strip())
            iso_week = int(str(row["iso_week"]).strip())
        else:
            week_info = get_iso_week_info(str(row.get("data", "")).strip())
            iso_year = week_info["iso_year"]
            iso_week = week_info["iso_week"]
    except (ValueError, KeyError):
        return None

    return (matricula, status, iso_year, iso_week)


def _payload_key(payload: MonitoriaPayload) -> tuple[str, str, int, int]:
    week_info = get_iso_week_info(payload.data)
    return (
        payload.matricula.strip().casefold(),
        payload.status.strip(),
        week_info["iso_year"],
        week_info["iso_week"],
    )


def _new_submission_log_path(log_dir: Path = SUBMISSION_LOG_DIR) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(SAO_PAULO_TZ).strftime("%Y%m%dT%H%M%S%z")
    return log_dir / f"{timestamp}.csv"


def _log_row(payload: MonitoriaPayload, resultado: str, detalhe: str) -> dict[str, str]:
    week_info = get_iso_week_info(payload.data)
    return {
        "timestamp": datetime.now(SAO_PAULO_TZ).isoformat(),
        "nome": payload.nome,
        "matricula": payload.matricula,
        "data": payload.data,
        "iso_year": str(week_info["iso_year"]),
        "iso_week": str(week_info["iso_week"]),
        "agente": payload.agente,
        "status": payload.status,
        "resultado": resultado,
        "detalhe": detalhe,
    }


def _today_sao_paulo() -> str:
    return datetime.now(SAO_PAULO_TZ).date().isoformat()
