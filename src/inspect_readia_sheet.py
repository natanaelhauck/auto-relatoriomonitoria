"""Inspect Read IA webhook payloads stored in Google Sheets."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.sheets_client import read_readia_payload_rows


def inspect_readia_sheet(limit: int = 10) -> int:
    """Print a compact summary of the latest Read IA payload rows."""
    rows = read_readia_payload_rows(limit=limit)
    if not rows:
        print("Nenhum payload Read IA encontrado na aba do Google Sheets.")
        return 0

    for row in rows:
        print(f"received_at: {row.get('received_at', '')}")
        print(f"  meeting_id: {row.get('meeting_id', '')}")
        print(f"  title: {row.get('title', '')}")
        print(f"  summary: {_preview(row.get('summary', ''))}")
        print(f"  report_url: {row.get('report_url', '')}")
        print(f"  payload_json: {_preview_payload(row.get('payload_json', ''))}")

    return 0


def _preview(value: Any, max_length: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _preview_payload(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _preview(text)

    return _preview(json.dumps(parsed, ensure_ascii=False))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mostra os ultimos payloads Read IA salvos no Google Sheets."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Quantidade de linhas finais para mostrar.",
    )
    args = parser.parse_args()
    raise SystemExit(inspect_readia_sheet(limit=args.limit))


if __name__ == "__main__":
    main()
