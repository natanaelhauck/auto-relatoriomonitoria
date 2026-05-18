"""Google Forms submission client."""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import requests
from dotenv import load_dotenv

from src.models import MonitoriaPayload

FORM_VIEW_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLScqJcE8_wd3NrCdaP36TyotY8b9LMk1mRI6ceAZ8symajfz7g/viewform"
)

# TODO: If the Google Form is edited, reextract these entry IDs from the form HTML.
ENTRY_IDS = {
    "nome": "entry.615656428",
    "matricula": "entry.531507362",
    "data": "entry.1496596961",
    "agente": "entry.1608308280",
    "status": "entry.5905294",
    "motivo_falta": "entry.714327850",
    "outro_motivo": "entry.1096396211",
    "relatorio_readia": "entry.1761763556",
    "link_readia": "entry.1753304014",
    "nao_consumiu": "entry.489293306",
    "modulo_1": "entry.362814364",
    "modulo_2": "entry.831821133",
    "modulo_3": "entry.1947309664",
    "modulo_4": "entry.1513577166",
}

COURSE_ENTRY_IDS = {
    "Scratch": ENTRY_IDS["modulo_1"],
    "No Code": ENTRY_IDS["modulo_1"],
    "Introdução à Web": ENTRY_IDS["modulo_1"],
    "Linux": ENTRY_IDS["modulo_1"],
    "Python I": ENTRY_IDS["modulo_1"],
    "JavaScript": ENTRY_IDS["modulo_2"],
    "Banco de Dados": ENTRY_IDS["modulo_2"],
    "Programação Orientada a Objetos": ENTRY_IDS["modulo_2"],
    "Python II": ENTRY_IDS["modulo_2"],
    "Fundamentos de interface": ENTRY_IDS["modulo_3"],
    "Desenvolvimento de websites com mentalidade ágil": ENTRY_IDS["modulo_3"],
    "Desenvolvimento de Interfaces Web Frameworks Front-End": ENTRY_IDS["modulo_3"],
    "React JS": ENTRY_IDS["modulo_3"],
    "Programação Multiplataforma com React Native": ENTRY_IDS["modulo_3"],
    "Programação Multiplataforma com Flutter": ENTRY_IDS["modulo_3"],
    "Padrão de Projeto de Software": ENTRY_IDS["modulo_4"],
    "Desenvolvimento de APIs RESTful": ENTRY_IDS["modulo_4"],
    "Desenvolvimento Nativo para Android": ENTRY_IDS["modulo_4"],
    "Framework Full Stack para Web": ENTRY_IDS["modulo_4"],
    "Teste de Software para Web": ENTRY_IDS["modulo_4"],
    "Teste de Software para Mobile": ENTRY_IDS["modulo_4"],
    "Não consumiu": ENTRY_IDS["nao_consumiu"],
    "Não assistiu": ENTRY_IDS["nao_consumiu"],
    "Desafio Final": ENTRY_IDS["nao_consumiu"],
}


def view_to_form_response(view_url: str) -> str:
    """Convert a Google Forms view URL to its formResponse endpoint."""
    parsed_url = urlparse(view_url)
    path = parsed_url.path

    if path.endswith("/viewform"):
        path = path[: -len("/viewform")] + "/formResponse"
    elif not path.endswith("/formResponse"):
        path = path.rstrip("/") + "/formResponse"

    return urlunparse(parsed_url._replace(path=path, query="", fragment=""))


def submit_monitoria(payload: MonitoriaPayload) -> requests.Response:
    """Submit a monitoring report payload to Google Forms."""
    load_dotenv()

    form_url = os.getenv("FORM_URL", FORM_VIEW_URL).strip() or FORM_VIEW_URL
    response_url = view_to_form_response(form_url)
    form_data = _payload_to_form_data(payload)

    return requests.post(
        response_url,
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )


def _payload_to_form_data(payload: MonitoriaPayload) -> list[tuple[str, str]]:
    form_data = [
        (ENTRY_IDS["nome"], payload.nome),
        (ENTRY_IDS["matricula"], payload.matricula),
        (ENTRY_IDS["agente"], payload.agente),
        (ENTRY_IDS["status"], payload.status),
        ("fvv", "1"),
        ("pageHistory", "0"),
    ]

    form_data.extend(_date_fields(payload.data))
    form_data.extend(_optional_field(ENTRY_IDS["relatorio_readia"], payload.relatorio_readia))
    form_data.extend(_optional_field(ENTRY_IDS["link_readia"], payload.link_readia))
    form_data.extend(_optional_field(ENTRY_IDS["motivo_falta"], payload.motivo_falta))
    form_data.extend(_optional_field(ENTRY_IDS["outro_motivo"], payload.outro_motivo))
    form_data.extend(_course_fields(payload.cursos_consumidos))

    return form_data


def _date_fields(value: str) -> list[tuple[str, str]]:
    date_value = datetime.strptime(value, "%Y-%m-%d").date()
    entry_id = ENTRY_IDS["data"]

    return [
        (f"{entry_id}_year", str(date_value.year)),
        (f"{entry_id}_month", str(date_value.month)),
        (f"{entry_id}_day", str(date_value.day)),
    ]


def _optional_field(entry_id: str, value: str | None) -> list[tuple[str, str]]:
    if value is None or value == "":
        return []
    return [(entry_id, value)]


def _course_fields(cursos_consumidos: Iterable[str]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []

    for course in cursos_consumidos:
        entry_id = COURSE_ENTRY_IDS.get(course)
        if entry_id is None:
            raise ValueError(f"Curso sem entry ID configurado: {course}")
        fields.append((entry_id, course))

    return fields
