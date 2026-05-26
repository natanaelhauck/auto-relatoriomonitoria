"""Google Sheets access client."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
READIA_PAYLOAD_COLUMNS = (
    "received_at",
    "meeting_id",
    "title",
    "summary",
    "report_url",
    "payload_json",
    "payload_json_size",
    "sheet_status",
    "sheet_error",
)
HEADER_ALIASES = {
    "data": "data",
    "nome": "nome",
    "nome do aluno": "nome",
    "aluno": "nome",
    "matricula": "matricula",
    "ra": "matricula",
    "pdita": "matricula",
    "pdita/pd": "matricula",
    "email": "email",
    "e-mail": "email",
    "email do aluno": "email",
    "e-mail do aluno": "email",
    "agente": "agente",
    "agente de sucesso": "agente",
    "motivo": "motivo_falta",
    "motivo da falta": "motivo_falta",
    "motivo_falta": "motivo_falta",
    "relatorio do read ia": "relatorio_readia",
    "relatorio_readia": "relatorio_readia",
    "link do read ia": "link_readia",
    "link_readia": "link_readia",
    "curso": "cursos_consumidos",
    "cursos": "cursos_consumidos",
    "curso ou cursos": "cursos_consumidos",
    "cursos_consumidos": "cursos_consumidos",
    "status": "status",
    "observacao": "observacao",
    "observacao/observacoes": "observacao",
    "observacoes": "observacao",
}


@dataclass(frozen=True)
class SheetsSettings:
    """Google Sheets settings loaded from environment variables."""

    service_account_file: str | None
    spreadsheet_id: str
    sheet_nao_agendados: str
    sheet_finalizados: str
    sheet_presentes: str
    sheet_ativos: str
    default_agente: str
    sheet_readia_payloads: str = "ReadIA Payloads"
    service_account_json: str | None = None


def read_sheet_rows(sheet_name: str, *, allow_missing_sheet: bool = False) -> list[dict[str, Any]]:
    """Read and normalize rows from a Google Sheets tab.

    Configuration is loaded from `.env`:
        GOOGLE_SERVICE_ACCOUNT_JSON: complete service account JSON content.
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

    service = _build_sheets_service(settings)
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


def append_readia_payload(row: Mapping[str, Any]) -> str:
    """Append one sanitized Read IA webhook payload to Google Sheets."""
    settings = load_sheets_settings()
    service = _build_sheets_service(settings)
    sheet_name = settings.sheet_readia_payloads

    _ensure_readia_payload_sheet(service, settings.spreadsheet_id, sheet_name)
    existing_rows = _read_table_rows(service, settings.spreadsheet_id, sheet_name)
    if _has_duplicate_readia_payload(row, existing_rows):
        return "duplicate_skipped"

    row_to_append = dict(row)
    row_to_append.setdefault("sheet_status", "saved")
    row_to_append.setdefault("sheet_error", "")
    _append_sheet_values(
        service,
        settings.spreadsheet_id,
        sheet_name,
        [[_clean_cell(row_to_append.get(column, "")) for column in READIA_PAYLOAD_COLUMNS]],
        columns_count=len(READIA_PAYLOAD_COLUMNS),
    )
    return "saved"


def read_readia_payload_rows(limit: int | None = None) -> list[dict[str, Any]]:
    """Read Read IA payload rows from the configured Google Sheets tab."""
    settings = load_sheets_settings()
    service = _build_sheets_service(settings)

    try:
        values = _get_sheet_values(
            service,
            settings.spreadsheet_id,
            settings.sheet_readia_payloads,
        )
    except HttpError as exc:
        if _is_missing_sheet_error(exc):
            print(
                "AVISO - aba de payloads Read IA nao encontrada no Google Sheets: "
                f"{settings.sheet_readia_payloads}"
            )
            return []
        raise

    if not values:
        return []

    headers = [_clean_cell(header) for header in values[0]]
    rows: list[dict[str, Any]] = []

    for raw_row in values[1:]:
        if _is_empty_row(raw_row):
            continue

        row = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = _clean_cell(raw_row[index]) if index < len(raw_row) else ""
        rows.append(row)

    if limit == 0:
        return []

    if limit is not None and limit > 0:
        return rows[-limit:]

    return rows


def load_sheets_settings() -> SheetsSettings:
    """Load Google Sheets settings from `.env`."""
    load_dotenv()

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if not service_account_json and not service_account_file:
        raise RuntimeError(
            "Missing required environment variable: "
            "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE"
        )

    return SheetsSettings(
        service_account_file=service_account_file or None,
        spreadsheet_id=_required_env("GOOGLE_SPREADSHEET_ID"),
        sheet_nao_agendados=_required_env("SHEET_NAO_AGENDADOS"),
        sheet_finalizados=_required_env("SHEET_FINALIZADOS"),
        sheet_presentes=os.getenv("SHEET_PRESENTES", "Presentes").strip() or "Presentes",
        sheet_ativos=os.getenv("SHEET_ATIVOS", "Ativo").strip() or "Ativo",
        default_agente=os.getenv("DEFAULT_AGENTE", "").strip(),
        sheet_readia_payloads=(
            os.getenv("SHEET_READIA_PAYLOADS", "ReadIA Payloads").strip()
            or "ReadIA Payloads"
        ),
        service_account_json=service_account_json or None,
    )


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_sheets_service(settings_or_file: SheetsSettings | str | None) -> Any:
    if isinstance(settings_or_file, SheetsSettings):
        service_account_file = settings_or_file.service_account_file
        service_account_json = settings_or_file.service_account_json
    else:
        service_account_file = settings_or_file
        service_account_json = None

    credentials = _build_service_account_credentials(
        service_account_file=service_account_file,
        service_account_json=service_account_json,
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _build_service_account_credentials(
    *,
    service_account_file: str | None,
    service_account_json: str | None,
) -> service_account.Credentials:
    if service_account_json:
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Invalid GOOGLE_SERVICE_ACCOUNT_JSON: expected complete service "
                "account JSON content."
            ) from exc

        return service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES,
        )

    if service_account_file:
        return service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES,
        )

    raise RuntimeError(
        "Missing required environment variable: "
        "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE"
    )


def _get_sheet_values(service: Any, spreadsheet_id: str, sheet_name: str) -> list[list[Any]]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=_sheet_range(sheet_name, "A:ZZ"))
        .execute()
    )
    return result.get("values", [])


def _ensure_readia_payload_sheet(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
) -> None:
    created = _ensure_sheet_exists(service, spreadsheet_id, sheet_name)
    if created:
        print(
            "AVISO - aba de payloads Read IA nao existia no Google Sheets; "
            f"criada: {sheet_name}"
        )

    _ensure_sheet_header(
        service,
        spreadsheet_id,
        sheet_name,
        list(READIA_PAYLOAD_COLUMNS),
        warning_context="aba de payloads Read IA",
    )


def _ensure_sheet_exists(service: Any, spreadsheet_id: str, sheet_name: str) -> bool:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute()
    )
    titles = {
        sheet.get("properties", {}).get("title", "")
        for sheet in metadata.get("sheets", [])
    }
    if sheet_name in titles:
        return False

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
    ).execute()
    return True


def _get_sheet_header(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
) -> list[Any]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=_sheet_range(sheet_name, "A1:ZZ1"))
        .execute()
    )
    values = result.get("values", [])
    return values[0] if values else []


def _ensure_sheet_header(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    expected_header: list[str],
    *,
    warning_context: str,
) -> None:
    header = _get_sheet_header(service, spreadsheet_id, sheet_name)
    if not header:
        _set_sheet_header(service, spreadsheet_id, sheet_name, expected_header)
        return

    current_header = [_clean_cell(cell) for cell in header[: len(expected_header)]]
    expected_prefix = expected_header[: len(current_header)]
    if current_header == expected_prefix and current_header != expected_header:
        _set_sheet_header(service, spreadsheet_id, sheet_name, expected_header)
        return

    if current_header != expected_header:
        print(
            f"AVISO - cabecalho da {warning_context} difere do esperado. "
            f"Esperado: {', '.join(expected_header)}"
        )


def _set_sheet_header(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    columns: list[str],
) -> None:
    columns_count = len(columns)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=_sheet_range(sheet_name, f"A1:{_column_name(columns_count)}1"),
        valueInputOption="RAW",
        body={"values": [columns]},
    ).execute()


def _append_sheet_values(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    values: list[list[Any]],
    *,
    columns_count: int,
) -> None:
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=_sheet_range(sheet_name, f"A:{_column_name(columns_count)}"),
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def _read_table_rows(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
) -> list[dict[str, str]]:
    values = _get_sheet_values(service, spreadsheet_id, sheet_name)
    if not values:
        return []

    headers = [_clean_cell(header) for header in values[0]]
    rows: list[dict[str, str]] = []
    for raw_row in values[1:]:
        if _is_empty_row(raw_row):
            continue
        row = {}
        for index, header in enumerate(headers):
            if header:
                row[header] = _clean_cell(raw_row[index]) if index < len(raw_row) else ""
        rows.append(row)
    return rows


def _has_duplicate_readia_payload(
    row: Mapping[str, Any],
    existing_rows: list[Mapping[str, Any]],
) -> bool:
    meeting_id = _clean_cell(row.get("meeting_id", ""))
    report_url = _clean_cell(row.get("report_url", ""))
    if not meeting_id and not report_url:
        return False

    for existing_row in existing_rows:
        if meeting_id and meeting_id == _clean_cell(existing_row.get("meeting_id", "")):
            return True
        if report_url and report_url == _clean_cell(existing_row.get("report_url", "")):
            return True
    return False


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name or "A"


def _sheet_range(sheet_name: str, cell_range: str) -> str:
    escaped_sheet_name = sheet_name.replace("'", "''")
    return f"'{escaped_sheet_name}'!{cell_range}"


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
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text


def _clean_cell(value: Any) -> str:
    return str(value).strip()
