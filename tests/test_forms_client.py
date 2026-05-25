"""Tests for Google Forms payload mapping."""

import pytest

from src.forms_client import FORM_FIELDS, build_form_data
from src.models import MonitoriaPayload


def as_dict(form_data: list[tuple[str, str]]) -> dict[str, list[str]]:
    mapped: dict[str, list[str]] = {}
    for key, value in form_data:
        mapped.setdefault(key, []).append(value)
    return mapped


def base_payload(status: str, **overrides: object) -> MonitoriaPayload:
    values = {
        "nome": "Aluno Teste",
        "matricula": "123",
        "data": "2026-05-18",
        "agente": "Natanael",
        "status": status,
    }
    values.update(overrides)
    return MonitoriaPayload(**values)


def assert_base_fields(data: dict[str, list[str]], status: str) -> None:
    assert data[FORM_FIELDS["nome"]] == ["Aluno Teste"]
    assert data[FORM_FIELDS["matricula"]] == ["123"]
    assert data[FORM_FIELDS["agente"]] == ["Natanael"]
    assert data[FORM_FIELDS["status"]] == [status]
    assert data[f'{FORM_FIELDS["data"]}_year'] == ["2026"]
    assert data[f'{FORM_FIELDS["data"]}_month'] == ["5"]
    assert data[f'{FORM_FIELDS["data"]}_day'] == ["18"]


def test_nao_agendado_monta_payload_com_campos_base() -> None:
    payload = base_payload(
        "Aluno não agendado(Fantasma)",
        motivo_falta="Sem resposta",
        relatorio_readia="Resumo",
        link_readia="https://read.ai/report",
    )

    data = as_dict(build_form_data(payload))

    assert_base_fields(data, "Aluno não agendado(Fantasma)")
    assert FORM_FIELDS["motivo_falta"] not in data
    assert FORM_FIELDS["relatorio_readia"] not in data
    assert FORM_FIELDS["link_readia"] not in data


def test_finalizado_monta_payload_com_campos_base() -> None:
    payload = base_payload(
        "Aluno finalizou o curso",
        relatorio_readia="Resumo",
        link_readia="https://read.ai/report",
    )

    data = as_dict(build_form_data(payload))

    assert_base_fields(data, "Aluno finalizou o curso")
    assert FORM_FIELDS["motivo_falta"] not in data
    assert FORM_FIELDS["relatorio_readia"] not in data
    assert FORM_FIELDS["link_readia"] not in data


def test_falta_monta_payload_com_motivo_sem_resposta() -> None:
    payload = base_payload("Falta")

    data = as_dict(build_form_data(payload))

    assert_base_fields(data, "Falta")
    assert data["pageHistory"] == ["0,1"]
    assert data[FORM_FIELDS["motivo_falta"]] == ["Sem resposta"]
    assert FORM_FIELDS["relatorio_readia"] not in data
    assert FORM_FIELDS["link_readia"] not in data


def test_presente_monta_payload_com_relatorio_e_link_readia() -> None:
    payload = base_payload(
        "Presente",
        relatorio_readia="Resumo da monitoria",
        link_readia="https://read.ai/report/abc",
        cursos_consumidos=["Não consumiu"],
    )

    data = as_dict(build_form_data(payload))

    assert_base_fields(data, "Presente")
    assert data["pageHistory"] == ["0,2,3"]
    assert data[FORM_FIELDS["relatorio_readia"]] == ["Resumo da monitoria"]
    assert data[FORM_FIELDS["link_readia"]] == ["https://read.ai/report/abc"]
    assert data[FORM_FIELDS["cursos_consumidos"]["nao_consumiu"]] == ["Não assistiu"]
    assert FORM_FIELDS["motivo_falta"] not in data


def test_presente_usa_defaults_quando_readia_ou_cursos_vazios() -> None:
    payload = base_payload("Presente")

    data = as_dict(build_form_data(payload))

    assert data[FORM_FIELDS["relatorio_readia"]] == ["Resumo não disponível"]
    assert data[FORM_FIELDS["cursos_consumidos"]["nao_consumiu"]] == ["Não assistiu"]
    assert FORM_FIELDS["link_readia"] not in data


def test_presente_aceita_cursos_como_string_separada_por_virgula() -> None:
    payload = base_payload(
        "Presente",
        relatorio_readia="Resumo da monitoria",
        cursos_consumidos="Python I, JavaScript",
    )

    data = as_dict(build_form_data(payload))

    assert data[FORM_FIELDS["cursos_consumidos"]["modulo_1"]] == ["Python I"]
    assert data[FORM_FIELDS["cursos_consumidos"]["modulo_2"]] == ["JavaScript"]


def test_status_invalido_levanta_value_error() -> None:
    payload = base_payload("Outro status")

    with pytest.raises(ValueError, match="Status inválido"):
        build_form_data(payload)


def test_nome_vazio_levanta_value_error() -> None:
    payload = base_payload("Falta", nome="")

    with pytest.raises(ValueError, match="nome"):
        build_form_data(payload)
