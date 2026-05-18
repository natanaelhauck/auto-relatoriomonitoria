"""Shared data models for report submissions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportSubmission:
    """Normalized report data before it is sent to Google Forms."""

    report_type: str
    fields: dict[str, Any] = field(default_factory=dict)
