"""Submission flow for attendee reports from Read IA."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.forms_client import submit_monitoria
from src.models import MonitoriaPayload
from src.submission_runner import _today_sao_paulo

PAYLOAD_DIR = Path("data/read_payloads")
STATUS_PRESENTE = "Presente"
DEFAULT_CURSOS_CONSUMIDOS = ["Não consumiu"]


def submit_presentes_readia(dry_run: bool = False) -> None:
    """Submit attendance reports produced from saved Read IA payloads."""
    read_payloads = load_readia_payloads(PAYLOAD_DIR)
    monitoria_payloads = build_presentes_payloads(read_payloads)

    print(f"Payloads Read IA encontrados: {len(read_payloads)}")
    print(f"Presencas prontas para envio: {len(monitoria_payloads)}")

    if not monitoria_payloads:
        return

    if dry_run:
        for payload in monitoria_payloads:
            print(f"[DRY-RUN] {asdict(payload)}")
        return

    confirmation = input("Digite ENVIAR para confirmar o envio: ").strip()
    if confirmation != "ENVIAR":
        print("Envio cancelado.")
        return

    for payload in monitoria_payloads:
        try:
            response = submit_monitoria(payload)
            if response.ok:
                print(
                    f"[OK] {payload.nome} ({payload.matricula}) "
                    f"- HTTP {response.status_code}"
                )
            else:
                print(
                    f"[ERRO] {payload.nome} ({payload.matricula}) "
                    f"- HTTP {response.status_code}: {response.text[:200]}"
                )
        except Exception as exc:
            print(f"[ERRO] {payload.nome} ({payload.matricula}) - {exc}")


def load_readia_payloads(payload_dir: Path) -> list[dict[str, Any]]:
    """Load saved Read IA webhook payloads from disk."""
    if not payload_dir.exists():
        return []

    payloads: list[dict[str, Any]] = []
    for path in sorted(payload_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[ERRO] Payload invalido ignorado: {path} - {exc}")
            continue

        if isinstance(payload, dict):
            payloads.append(payload)

    return payloads


def build_presentes_payloads(payloads: Iterable[Mapping[str, Any]]) -> list[MonitoriaPayload]:
    """Build form payloads from Read IA data.

    The matching between Read IA sessions and scheduled students is intentionally
    isolated in `match_student_for_readia_payload`. A future version should use
    agenda events or spreadsheet rows to resolve the student when the Read IA
    payload does not include enough student metadata.
    """
    load_dotenv()
    default_agente = os.getenv("DEFAULT_AGENTE", "").strip()
    monitoria_payloads: list[MonitoriaPayload] = []

    for payload in payloads:
        student = match_student_for_readia_payload(payload)
        summary = _first_text(payload, ("summary", "report_summary", "resumo"))
        report_url = _first_text(payload, ("report_url", "reportUrl", "url"))

        if student is None or not summary:
            continue

        monitoria_payloads.append(
            MonitoriaPayload(
                nome=student["nome"],
                matricula=student["matricula"],
                data=_today_sao_paulo(),
                agente=student["agente"] or default_agente,
                status=STATUS_PRESENTE,
                relatorio_readia=summary,
                link_readia=report_url,
                cursos_consumidos=DEFAULT_CURSOS_CONSUMIDOS.copy(),
            )
        )

    return monitoria_payloads


def match_student_for_readia_payload(payload: Mapping[str, Any]) -> dict[str, str] | None:
    """Resolve the student for a Read IA payload.

    Current behavior is deliberately conservative: it only accepts payloads that
    already contain `nome`/`matricula` or common aliases. Later this function can
    cross-check agenda events or Google Sheets rows using session timestamps,
    attendee emails, meeting titles, or session ids.
    """
    nome = _first_text(payload, ("nome", "student_name", "studentName", "aluno"))
    matricula = _first_text(payload, ("matricula", "matrícula", "ra", "student_id"))
    agente = _first_text(payload, ("agente", "agente_sucesso", "success_agent"))

    if not nome or not matricula:
        return None

    return {
        "nome": nome,
        "matricula": matricula,
        "agente": agente or "",
    }


def _first_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _find_value(payload, key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _find_value(value: Any, target_key: str) -> Any:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() == target_key.casefold():
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


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Envia presencas a partir de payloads salvos do Read IA."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria enviado sem submeter ao Google Forms.",
    )
    args = parser.parse_args()
    submit_presentes_readia(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
