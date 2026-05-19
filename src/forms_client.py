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

ACCEPTED_STATUS = {
    "Presente",
    "Falta",
    "Aluno não agendado(Fantasma)",
    "Aluno finalizou o curso",
}

ACCEPTED_MOTIVOS_FALTA = {
    "Sem resposta",
    "Trabalho ou Estudo",
    "Questões Médicas",
    "Viajando",
    "Notebook com Suporte",
    "Atraso/Compromisso",
    "Reunião/Demanda (PD)",
    "Troca de turno",
    "Problema de Internet",
    "Outro",
}

# TODO: If the Google Form is edited, reextract these entry IDs from the form HTML.
FORM_FIELDS = {
    "nome": "entry.615656428",
    "matricula": "entry.531507362",
    "data": "entry.1496596961",
    "agente": "entry.1608308280",
    "status": "entry.5905294",
    "relatorio_readia": "entry.1761763556",
    "link_readia": "entry.1753304014",
    "motivo_falta": "entry.714327850",
    "outro_motivo": "entry.1096396211",
    "cursos_consumidos": {
        "nao_consumiu": "entry.489293306",
        "modulo_1": "entry.362814364",
        "modulo_2": "entry.831821133",
        "modulo_3": "entry.1947309664",
        "modulo_4": "entry.1513577166",
    },
}

COURSE_FIELDS = {
    "Scratch": (FORM_FIELDS["cursos_consumidos"]["modulo_1"], "Scratch"),
    "No Code": (FORM_FIELDS["cursos_consumidos"]["modulo_1"], "No Code"),
    "Introdução à Web": (FORM_FIELDS["cursos_consumidos"]["modulo_1"], "Introdução à Web"),
    "Linux": (FORM_FIELDS["cursos_consumidos"]["modulo_1"], "Linux"),
    "Python I": (FORM_FIELDS["cursos_consumidos"]["modulo_1"], "Python I"),
    "JavaScript": (FORM_FIELDS["cursos_consumidos"]["modulo_2"], "JavaScript"),
    "Banco de Dados": (FORM_FIELDS["cursos_consumidos"]["modulo_2"], "Banco de Dados"),
    "Programação Orientada a Objetos": (
        FORM_FIELDS["cursos_consumidos"]["modulo_2"],
        "Programação Orientada a Objetos",
    ),
    "Python II": (FORM_FIELDS["cursos_consumidos"]["modulo_2"], "Python II"),
    "Fundamentos de interface": (
        FORM_FIELDS["cursos_consumidos"]["modulo_3"],
        "Fundamentos de interface",
    ),
    "Desenvolvimento de websites com mentalidade ágil": (
        FORM_FIELDS["cursos_consumidos"]["modulo_3"],
        "Desenvolvimento de websites com mentalidade ágil",
    ),
    "Desenvolvimento de Interfaces Web Frameworks Front-End": (
        FORM_FIELDS["cursos_consumidos"]["modulo_3"],
        "Desenvolvimento de Interfaces Web Frameworks Front-End",
    ),
    "React JS": (FORM_FIELDS["cursos_consumidos"]["modulo_3"], "React JS"),
    "Programação Multiplataforma com React Native": (
        FORM_FIELDS["cursos_consumidos"]["modulo_3"],
        "Programação Multiplataforma com React Native",
    ),
    "Programação Multiplataforma com Flutter": (
        FORM_FIELDS["cursos_consumidos"]["modulo_3"],
        "Programação Multiplataforma com Flutter",
    ),
    "Padrão de Projeto de Software": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Padrão de Projeto de Software",
    ),
    "Desenvolvimento de APIs RESTful": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Desenvolvimento de APIs RESTful",
    ),
    "Desenvolvimento Nativo para Android": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Desenvolvimento Nativo para Android",
    ),
    "Framework Full Stack para Web": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Framework Full Stack para Web",
    ),
    "Teste de Software para Web": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Teste de Software para Web",
    ),
    "Teste de Software para Mobile": (
        FORM_FIELDS["cursos_consumidos"]["modulo_4"],
        "Teste de Software para Mobile",
    ),
    "Não consumiu": (FORM_FIELDS["cursos_consumidos"]["nao_consumiu"], "Não assistiu"),
    "Não assistiu": (FORM_FIELDS["cursos_consumidos"]["nao_consumiu"], "Não assistiu"),
    "Desafio Final": (FORM_FIELDS["cursos_consumidos"]["nao_consumiu"], "Desafio Final"),
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
    form_data = build_form_data(payload)

    return requests.post(
        response_url,
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )


def build_form_data(payload: MonitoriaPayload) -> list[tuple[str, str]]:
    """Validate and convert a monitoria payload to Google Forms fields."""
    validated_payload = _validate_payload(payload)
    form_data = [
        (FORM_FIELDS["nome"], validated_payload.nome.strip()),
        (FORM_FIELDS["matricula"], validated_payload.matricula.strip()),
        (FORM_FIELDS["agente"], validated_payload.agente.strip()),
        (FORM_FIELDS["status"], validated_payload.status.strip()),
        ("fvv", "1"),
        ("pageHistory", "0"),
    ]

    form_data.extend(_date_fields(validated_payload.data))

    if validated_payload.status == "Falta":
        form_data.append(
            (FORM_FIELDS["motivo_falta"], validated_payload.motivo_falta or "Sem resposta")
        )
        form_data.extend(
            _optional_field(FORM_FIELDS["outro_motivo"], validated_payload.outro_motivo)
        )

    if validated_payload.status == "Presente":
        form_data.extend(
            _optional_field(FORM_FIELDS["relatorio_readia"], validated_payload.relatorio_readia)
        )
        form_data.extend(_optional_field(FORM_FIELDS["link_readia"], validated_payload.link_readia))
        form_data.extend(_course_fields(validated_payload.cursos_consumidos))

    return form_data


def _validate_payload(payload: MonitoriaPayload) -> MonitoriaPayload:
    _require_text(payload.nome, "nome")
    _require_text(payload.matricula, "matricula")
    _require_text(payload.data, "data")
    _require_text(payload.agente, "agente")
    _require_text(payload.status, "status")

    if payload.status not in ACCEPTED_STATUS:
        raise ValueError(f"Status inválido: {payload.status}")

    datetime.strptime(payload.data, "%Y-%m-%d")

    if payload.status == "Falta":
        motivo_falta = payload.motivo_falta or "Sem resposta"
        if motivo_falta not in ACCEPTED_MOTIVOS_FALTA:
            raise ValueError(f"Motivo de falta inválido: {motivo_falta}")
        return MonitoriaPayload(
            nome=payload.nome,
            matricula=payload.matricula,
            data=payload.data,
            agente=payload.agente,
            status=payload.status,
            motivo_falta=motivo_falta,
            outro_motivo=payload.outro_motivo,
        )

    return payload


def _require_text(value: str | None, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise ValueError(f"Campo obrigatório ausente: {field_name}")


def _date_fields(value: str) -> list[tuple[str, str]]:
    date_value = datetime.strptime(value, "%Y-%m-%d").date()
    entry_id = FORM_FIELDS["data"]

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
        course_field = COURSE_FIELDS.get(course)
        if course_field is None:
            raise ValueError(f"Curso sem entry ID configurado: {course}")
        fields.append(course_field)

    return fields
