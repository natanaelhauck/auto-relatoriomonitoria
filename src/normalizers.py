"""Normalization helpers for spreadsheet and Read IA data."""

from collections.abc import Mapping
from typing import Any

from src.models import ReportSubmission


def normalize_spreadsheet_row(row: Mapping[str, Any], report_type: str) -> ReportSubmission:
    """Convert a spreadsheet row into a report submission."""
    raise NotImplementedError("Spreadsheet normalization is not implemented yet.")


def normalize_readia_payload(payload: Mapping[str, Any]) -> ReportSubmission:
    """Convert a Read IA webhook payload into a report submission."""
    raise NotImplementedError("Read IA normalization is not implemented yet.")
