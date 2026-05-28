"""Inspect Read IA Google Docs reports for a date."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from src.readia_docs_client import list_readia_docs_for_date
from src.submission_runner import parse_report_date


def inspect_readia_docs(*, report_date: str) -> int:
    """Print a compact summary of Read IA docs found for a date."""
    docs = list_readia_docs_for_date(report_date)
    _print(f"Data: {report_date}")
    _print(f"Total docs encontrados: {len(docs)}")
    for doc in docs:
        summary = str(doc.get("summary", "") or "").strip()
        link_readia = str(doc.get("readia_report_url", "") or "").strip()
        link_google_docs = str(doc.get("link_google_docs", "") or "").strip()
        _print(f"titulo: {doc.get('title', '')}")
        _print(f"  data: {doc.get('date', '')}")
        _print(f"  meeting: {doc.get('meeting', '')}")
        _print(f"  summary: {_preview(summary, 500)}")
        if not summary:
            _print("  AVISO: summary vazio")
        _print(f"  link_readia: {link_readia}")
        _print(f"  link_google_docs: {link_google_docs}")
        if link_readia and link_readia == link_google_docs:
            _print("  AVISO: usando link do Google Docs como fallback")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments for the Read IA Docs inspection command."""
    parser = argparse.ArgumentParser(
        description="Lista relatórios Read IA salvos como Google Docs."
    )
    parser.add_argument(
        "--date",
        dest="report_date",
        required=True,
        type=parse_report_date,
        help="Data dos documentos no formato YYYY-MM-DD.",
    )
    return parser


def _preview(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _print(value: Any) -> None:
    text = str(value)
    encoding = sys.stdout.encoding or "utf-8"
    safe_text = text.encode(encoding, errors="replace").decode(
        encoding,
        errors="replace",
    )
    print(safe_text)


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = inspect_readia_docs(report_date=args.report_date)
    except RuntimeError as exc:
        _print(f"ERRO - {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
