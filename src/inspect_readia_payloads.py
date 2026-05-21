"""Inspect saved Read IA webhook payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PAYLOAD_DIR = Path("data/read_payloads")
FIELD_NAMES = (
    "title",
    "meeting_title",
    "summary",
    "report_url",
    "url",
    "participants",
    "attendees",
    "emails",
)


def inspect_readia_payloads(payload_dir: Path = PAYLOAD_DIR) -> int:
    """Print a compact summary of saved Read IA payload files."""
    payload_files = sorted(payload_dir.glob("*.json"))
    if not payload_files:
        print(f"Nenhum payload Read IA encontrado em {payload_dir.as_posix()}/")
        return 0

    for path in payload_files:
        print(f"Arquivo: {path.name}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  erro: {exc}")
            continue

        if isinstance(document, Mapping):
            print(f"  received_at: {document.get('received_at', '')}")
            payload = document.get("payload", document)
        else:
            print("  received_at: ")
            payload = document

        found_fields = _find_fields(payload)
        if found_fields:
            for field_name, values in found_fields.items():
                print(f"  {field_name}: {_preview(values)}")
        else:
            print("  campos encontrados: nenhum")

    return 0


def _find_fields(value: Any) -> dict[str, list[Any]]:
    found: dict[str, list[Any]] = {}
    _collect_fields(value, found)
    return found


def _collect_fields(value: Any, found: dict[str, list[Any]]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FIELD_NAMES:
                found.setdefault(key_text, []).append(item)
            _collect_fields(item, found)
        return

    if isinstance(value, list):
        for item in value:
            _collect_fields(item, found)


def _preview(values: list[Any]) -> str:
    rendered = []
    for value in values[:3]:
        text = json.dumps(value, ensure_ascii=False)
        if len(text) > 180:
            text = f"{text[:177]}..."
        rendered.append(text)
    return "; ".join(rendered)


def main() -> None:
    """CLI entry point."""
    raise SystemExit(inspect_readia_payloads())


if __name__ == "__main__":
    main()
