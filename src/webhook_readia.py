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

PAYLOAD_DIR = Path("data/read_payloads")
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
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
    return jsonify(result), 202


def handle_readia_webhook(
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, Any] | None = None,
) -> dict[str, str]:
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

    return {"status": "saved", "path": str(file_path)}


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
    for key in ("session_id", "sessionId", "meeting_id", "meetingId", "id"):
        value = _find_value(payload, key)
        if value:
            return _safe_filename_part(str(value))

    return None


def _find_value(value: Any, target_key: str) -> Any:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) == target_key:
                return item

        for item in value.values():
            found = _find_value(item, target_key)
            if found is not None:
                return found

    if isinstance(value, list):
        for item in value:
            found = _find_value(item, target_key)
            if found is not None:
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
