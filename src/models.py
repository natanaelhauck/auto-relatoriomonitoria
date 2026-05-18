"""Shared data models for report submissions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportSubmission:
    """Normalized report data before it is sent to Google Forms."""

    report_type: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MonitoriaPayload:
    """Payload submitted to the monitoring Google Form."""

    nome: str
    matricula: str
    data: str
    agente: str
    status: str
    relatorio_readia: str | None = None
    link_readia: str | None = None
    cursos_consumidos: list[str] = field(default_factory=list)
    motivo_falta: str | None = None
    outro_motivo: str | None = None
