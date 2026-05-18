"""Google Sheets access client."""

from collections.abc import Iterable
from typing import Any


def read_sheet_rows(spreadsheet_id: str, range_name: str) -> Iterable[dict[str, Any]]:
    """Read rows from a Google Sheets range.

    Args:
        spreadsheet_id: Google Sheets document identifier.
        range_name: A1 notation range to read.
    """
    raise NotImplementedError("Google Sheets reading is not implemented yet.")
