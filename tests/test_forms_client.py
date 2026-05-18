"""Tests for Google Forms payload mapping."""

import pytest

from src.forms_client import FORM_FIELDS, build_form_data
from src.models import MonitoriaPayload


def as_dict(form_data: list[tuple[str, str]]) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for key, value in form_data:
        mapped.setdefault(key, []).append(value)
    return mapped


def test_payload_valido_nao_agendado_gera_dados_corretos() -> None:
    payload = MonitoriaPayload(
        nome="Aluno Teste",
        matricula="123",
        data="2026-05-18",
        agente="Natanael",
        status="Aluno não agendado(Fantasma)",
        motivo_falta="Sem resposta",
        relatorio_readia="Resumo",
    )

    data = as_dict(build_form_data(payload))

    assert data[FORM_FIELDS["nome"]] == ["Aluno Teste"]
    assert data[FORM_FIELDS["matricula"]] == ["123"]
    assert data[FORM_FIELDS["agente"]] == ["Natanael"]
    assert data[FORM_FIELDS["status"]] == ["Aluno não agendado(Fantasma)"]
    assert f'{FORM_FIELDS["data"]}_year' in data
    assert FORM_FIELDS["motivo_falta"] not in data
    assert FORM_FIELDS["relatorio_readia"] not in data


def test_payload_valido_finalizado_gera_dados_corretos() -> None:
    payload = MonitoriaPayload(
        nome="Aluno Finalizado",
        matricula="456",
        data="2026-05-18",
        agente="Natanael",
        status="Aluno finalizou o curso",
    )

    data = as_dict(build_form_data(payload))

    assert data[FORM_FIELDS["nome"]] == ["Aluno Finalizado"]
    assert data[FORM_FIELDS["matricula"]] == ["456"]
    assert data[FORM_FIELDS["status"]] == ["Aluno finalizou o curso"]
    assert FORM_FIELDS["motivo_falta"] not in data
    assert FORM_FIELDS["relatorio_readia"] not in data


def test_falta_sem_motivo_vira_sem_resposta() -> None:
    payload = MonitoriaPayload(
        nome="Aluno Falta",
        matricula="789",
        data="2026-05-18",
        agente="Natanael",
        status="Falta",
    )

    data = as_dict(build_form_data(payload))

    assert data[FORM_FIELDS["motivo_falta"]] == ["Sem resposta"]


def test_status_invalido_levanta_value_error() -> None:
    payload = MonitoriaPayload(
        nome="Aluno Teste",
        matricula="123",
        data="2026-05-18",
        agente="Natanael",
        status="Outro status",
    )

    with pytest.raises(ValueError, match="Status inválido"):
        build_form_data(payload)


def test_nome_vazio_levanta_value_error() -> None:
    payload = MonitoriaPayload(
        nome="",
        matricula="123",
        data="2026-05-18",
        agente="Natanael",
        status="Falta",
    )

    with pytest.raises(ValueError, match="nome"):
        build_form_data(payload)
