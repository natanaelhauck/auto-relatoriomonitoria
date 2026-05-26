"""Webhook entry points for Read IA integrations."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, request

from src.sheets_client import append_readia_payload

PAYLOAD_DIR = Path("data/read_payloads")
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
MAX_SHEET_PAYLOAD_JSON_CHARS = 45000
TRUNCATED_PAYLOAD_WARNING = "[TRUNCADO - payload grande demais]"
MEETING_ID_KEYS = ("meeting_id", "meetingId", "session_id", "sessionId", "id")
TITLE_KEYS = ("title", "meeting_title", "meetingTitle")
SUMMARY_KEYS = ("summary", "report_summary", "reportSummary")
REPORT_URL_KEYS = ("report_url", "reportUrl", "url", "report_link", "reportLink")
SECRET_KEYWORDS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "client_secret",
    "password",
    "secret",
    "token",
)

app = Flask(__name__)


@app.get("/")
def index() -> Response:
    """Return a simple status page for browser checks."""
    return Response("Read IA webhook ativo", mimetype="text/plain")


@app.get("/health")
def health() -> tuple[Any, int]:
    """Return a health check response."""
    return jsonify({"status": "ok"}), 200


@app.post("/read-webhook")
def read_webhook() -> tuple[Any, int]:
    """Receive a Read IA webhook payload and persist a sanitized copy."""
    parsed_payload = request.get_json(silent=True)
    if isinstance(parsed_payload, Mapping):
        payload = parsed_payload
    else:
        payload = {"raw_text": request.get_data(as_text=True)}

    result = handle_readia_webhook(payload, headers=dict(request.headers))
    status_code = 500 if result.get("status") == "sheet_error" else 202
    return jsonify(result), status_code


def handle_readia_webhook(
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a sanitized Read IA webhook payload with request metadata."""
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    received_at = datetime.now(SAO_PAULO_TZ).isoformat()
    sanitized_payload = _remove_secrets(payload)
    sanitized_headers = _remove_secrets(headers or {})
    session_id = _extract_session_id(sanitized_payload)
    file_path = _next_available_path(PAYLOAD_DIR / _build_payload_filename(session_id))

    document = {
        "received_at": received_at,
        "headers": sanitized_headers,
        "payload": sanitized_payload,
    }
    file_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    sheet_row = build_readia_payload_row(sanitized_payload, received_at=received_at)
    sheet_status, sheet_error = _append_payload_to_sheet(sheet_row)
    if sheet_error:
        return {
            "status": "sheet_error",
            "path": str(file_path),
            "sheet_status": sheet_status,
            "error": sheet_error,
        }

    result = {"status": "saved", "path": str(file_path), "sheet_status": sheet_status}
    if sheet_error:
        result["sheet_error"] = sheet_error
    return result


def build_readia_payload_row(
    payload: Mapping[str, Any],
    *,
    received_at: str,
) -> dict[str, str]:
    """Build the Google Sheets row for a sanitized Read IA payload."""
    payload_json = json.dumps(payload, ensure_ascii=False)
    return {
        "received_at": received_at,
        "meeting_id": _clean_sheet_value(_find_first_value(payload, MEETING_ID_KEYS)),
        "title": _clean_sheet_value(_find_first_value(payload, TITLE_KEYS)),
        "summary": _clean_sheet_value(_find_first_value(payload, SUMMARY_KEYS)),
        "report_url": _clean_sheet_value(_find_first_value(payload, REPORT_URL_KEYS)),
        "payload_json": _sheet_payload_json(payload_json),
        "payload_json_size": str(len(payload_json)),
        "sheet_status": "saved",
        "sheet_error": "",
    }


def _append_payload_to_sheet(row: Mapping[str, Any]) -> tuple[str, str | None]:
    try:
        sheet_status = append_readia_payload(row) or "saved"
    except Exception as exc:
        message = (
            "AVISO - payload Read IA salvo localmente, mas falhou ao salvar "
            f"no Google Sheets: {exc}"
        )
        print(message)
        return "error", str(exc)

    return sheet_status, None


def _sheet_payload_json(payload_json: str) -> str:
    if len(payload_json) <= MAX_SHEET_PAYLOAD_JSON_CHARS:
        return payload_json

    max_payload_prefix_length = (
        MAX_SHEET_PAYLOAD_JSON_CHARS - len(TRUNCATED_PAYLOAD_WARNING) - 1
    )
    return (
        f"{TRUNCATED_PAYLOAD_WARNING}\n"
        f"{payload_json[:max(0, max_payload_prefix_length)]}"
    )


def _remove_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(secret in key_text for secret in SECRET_KEYWORDS):
                continue
            cleaned[key] = _remove_secrets(item)
        return cleaned

    if isinstance(value, list):
        return [_remove_secrets(item) for item in value]

    return value


def _extract_session_id(payload: Mapping[str, Any]) -> str | None:
    value = _find_first_value(payload, MEETING_ID_KEYS)
    if value:
        return _safe_filename_part(str(value))

    return None


def _find_first_value(value: Any, target_keys: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        for target_key in target_keys:
            for key, item in value.items():
                if str(key).casefold() == target_key.casefold() and item not in (
                    None,
                    "",
                ):
                    return item

        for item in value.values():
            found = _find_first_value(item, target_keys)
            if found not in (None, ""):
                return found

    if isinstance(value, list):
        for item in value:
            found = _find_first_value(item, target_keys)
            if found not in (None, ""):
                return found

    return None


def _build_payload_filename(session_id: str | None) -> str:
    timestamp = datetime.now(SAO_PAULO_TZ).strftime("%Y%m%dT%H%M%S")
    if session_id:
        return f"{timestamp}_readia_{session_id}.json"
    return f"{timestamp}_readia.json"


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Nao foi possivel criar arquivo unico em {path.parent}")


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:80]


def _clean_sheet_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (Mapping, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
    )
