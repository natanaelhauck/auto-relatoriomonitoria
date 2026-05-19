"""Google Sheets access client."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)

HEADER_ALIASES = {
    "nome": "nome",
    "nome do aluno": "nome",
    "aluno": "nome",
    "matricula": "matricula",
    "ra": "matricula",
    "pdita": "matricula",
    "pdita/pd": "matricula",
    "agente": "agente",
    "agente de sucesso": "agente",
}


@dataclass(frozen=True)
class SheetsSettings:
    """Google Sheets settings loaded from environment variables."""

    service_account_file: str
    spreadsheet_id: str
    sheet_nao_agendados: str
    sheet_finalizados: str
    sheet_faltas: str
    default_agente: str


def read_sheet_rows(sheet_name: str, *, allow_missing_sheet: bool = False) -> list[dict[str, Any]]:
    """Read and normalize rows from a Google Sheets tab.

    Configuration is loaded from `.env`:
        GOOGLE_SERVICE_ACCOUNT_FILE: service account JSON file path.
        GOOGLE_SPREADSHEET_ID: target spreadsheet id.
        DEFAULT_AGENTE: fallback agent when the row does not include one.

    Args:
        sheet_name: Google Sheets tab name.

    Returns:
        Rows with common columns normalized to `nome`, `matricula`, and
        `agente`. Rows without `nome` or `matricula` are ignored.
    """
    settings = load_sheets_settings()

    service = _build_sheets_service(settings.service_account_file)
    try:
        values = _get_sheet_values(service, settings.spreadsheet_id, sheet_name)
    except HttpError as exc:
        if allow_missing_sheet and _is_missing_sheet_error(exc):
            print(f"AVISO - aba nao encontrada no Google Sheets: {sheet_name}")
            return []
        raise

    header_index = _find_header_index(values)
    if header_index is None:
        return []

    headers = [_normalize_header(header) for header in values[header_index]]
    rows: list[dict[str, Any]] = []

    for raw_row in values[header_index + 1 :]:
        if _is_empty_row(raw_row):
            continue

        row = _normalize_row(headers, raw_row, settings.default_agente)
        if row.get("nome") and row.get("matricula"):
            rows.append(row)

    return rows


def load_sheets_settings() -> SheetsSettings:
    """Load Google Sheets settings from `.env`."""
    load_dotenv()

    return SheetsSettings(
        service_account_file=_required_env("GOOGLE_SERVICE_ACCOUNT_FILE"),
        spreadsheet_id=_required_env("GOOGLE_SPREADSHEET_ID"),
        sheet_nao_agendados=_required_env("SHEET_NAO_AGENDADOS"),
        sheet_finalizados=_required_env("SHEET_FINALIZADOS"),
        sheet_faltas=_required_env("SHEET_FALTAS"),
        default_agente=os.getenv("DEFAULT_AGENTE", "").strip(),
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_sheets_service(service_account_file: str) -> Any:
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _get_sheet_values(service: Any, spreadsheet_id: str, sheet_name: str) -> list[list[Any]]:
    escaped_sheet_name = sheet_name.replace("'", "''")
    range_name = f"'{escaped_sheet_name}'!A:ZZ"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def _is_missing_sheet_error(exc: HttpError) -> bool:
    return exc.resp.status == 400 and "Unable to parse range" in str(exc)


def _find_header_index(values: list[list[Any]]) -> int | None:
    for index, row in enumerate(values):
        normalized_headers = [_normalize_header(cell) for cell in row]
        if "nome" in normalized_headers:
            return index

    return None


def _is_empty_row(row: list[Any]) -> bool:
    return not any(_clean_cell(value) for value in row)


def _normalize_row(
    headers: list[str | None],
    raw_row: list[Any],
    default_agente: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {}

    for index, value in enumerate(raw_row):
        if index >= len(headers):
            continue

        normalized_header = headers[index]
        if normalized_header is None:
            continue

        row[normalized_header] = _clean_cell(value)

    if default_agente and not row.get("agente"):
        row["agente"] = default_agente

    return row


def _normalize_header(header: Any) -> str | None:
    key = _normalize_text(header)
    return HEADER_ALIASES.get(key)


def _normalize_text(value: Any) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def _clean_cell(value: Any) -> str:
    return str(value).strip()
