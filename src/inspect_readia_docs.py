"""Inspect Read IA Google Docs reports for a date."""

from __future__ import annotations

import argparse
from typing import Any

from src.readia_docs_client import list_readia_docs_for_date
from src.submission_runner import parse_report_date


def inspect_readia_docs(*, report_date: str) -> int:
    """Print a compact summary of Read IA docs found for a date."""
    docs = list_readia_docs_for_date(report_date)
    print(f"Data: {report_date}")
    print(f"Total docs encontrados: {len(docs)}")
    for doc in docs:
        print(f"titulo: {doc.get('title', '')}")
        print(f"  data: {doc.get('date', '')}")
        print(f"  meeting: {doc.get('meeting', '')}")
        print(f"  summary: {_preview(doc.get('summary', ''), 300)}")
        print(f"  link: {doc.get('report_url', '')}")
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


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = inspect_readia_docs(report_date=args.report_date)
    except RuntimeError as exc:
        print(f"ERRO - {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
