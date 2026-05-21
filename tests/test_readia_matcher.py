"""Tests for Read IA student matching and daily preview classification."""

from src.preview_monitoria_do_dia import build_preview_rows
from src.readia_matcher import match_student_to_meeting


def test_matricula_no_titulo_gera_confianca_100() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Maria Silva PDITA001 and Natanael Hauck"),
    )

    assert result is not None
    assert result.confidence == 100
    assert result.match_type == "matricula"


def test_email_nos_participantes_gera_confianca_100() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(
            title="Monitoria manual",
            participants=["Maria Silva <maria@example.com>"],
            emails=["maria@example.com"],
        ),
    )

    assert result is not None
    assert result.confidence == 100
    assert result.match_type == "email"


def test_primeiro_segundo_nome_no_titulo_gera_confianca_85() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Maria Silva and Natanael Hauck"),
    )

    assert result is not None
    assert result.confidence == 85
    assert result.match_type == "primeiro_segundo_nome_titulo"


def test_primeiro_segundo_nome_no_resumo_gera_match_fraco_65() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(
            title="Monitoria manual",
            summary="Resumo gerado para Maria Silva durante a monitoria.",
        ),
    )

    assert result is not None
    assert result.confidence == 65
    assert result.match_type == "primeiro_segundo_nome_resumo"


def test_aluno_sem_match_vira_falta_candidata() -> None:
    rows = build_preview_rows(
        [_student()],
        [_meeting(title="Monitoria manual", summary="Sem dados do aluno.")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "faltas_candidatas"
    assert rows[0]["match_confidence"] == 0
    assert rows[0]["match_type"] == "sem_match"


def _student() -> dict[str, str]:
    return {
        "nome": "Maria Silva Santos",
        "matricula": "PDITA001",
        "email": "maria@example.com",
    }


def _meeting(**overrides: object) -> dict[str, object]:
    meeting = {
        "date": "2026-05-21",
        "title": "",
        "summary": "",
        "report_url": "https://read.ai/report/abc",
        "participants": [],
        "emails": [],
        "raw_text": "",
    }
    meeting.update(overrides)
    return meeting
