"""Webhook entry points for Read IA integrations."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

PAYLOAD_DIR = Path("data/read_payloads")
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
SECRET_KEYWORDS = (
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "password",
    "secret",
    "token",
)

app = Flask(__name__)


@app.post("/read-webhook")
def read_webhook() -> tuple[Any, int]:
    """Receive a Read IA webhook payload and persist a sanitized copy."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_json"}), 400

    result = handle_readia_webhook(payload)
    return jsonify(result), 202


def handle_readia_webhook(payload: Mapping[str, Any]) -> dict[str, str]:
    """Save a sanitized Read IA webhook payload.

    Args:
        payload: Raw webhook payload received from Read IA.

    Returns:
        Metadata about the saved payload.
    """
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    sanitized_payload = _remove_secrets(payload)
    session_id = _extract_session_id(sanitized_payload)
    file_path = PAYLOAD_DIR / _build_payload_filename(session_id)

    file_path.write_text(
        json.dumps(sanitized_payload, ensure_ascii=False, indent=2),
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
    timestamp = datetime.now(SAO_PAULO_TZ).strftime("%Y%m%dT%H%M%S%z")
    if session_id:
        return f"{timestamp}_{session_id}.json"
    return f"{timestamp}.json"


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:80]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
