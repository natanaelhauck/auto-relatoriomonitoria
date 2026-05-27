"""Tests for Read IA student matching and daily preview classification."""

from src.readia_matcher import match_student_to_meeting


def test_matricula_no_titulo_gera_confianca_100() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Monitoria PDITA001 and Natanael Hauck"),
    )

    assert result is not None
    assert result.confidence == 100
    assert result.match_type == "matricula"


def test_email_nos_participantes_gera_confianca_100() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(
            title="Monitoria manual",
            emails=["maria@example.com"],
        ),
    )

    assert result is not None
    assert result.confidence == 100
    assert result.match_type == "email"


def test_primeiro_segundo_nome_no_titulo_gera_confianca_60() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Maria Silva and Natanael Hauck"),
    )

    assert result is not None
    assert result.confidence == 60
    assert result.match_type == "primeiro_segundo_nome"


def test_primeiro_segundo_nome_no_resumo_gera_confianca_60() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(
            title="Monitoria manual",
            summary="Resumo gerado para Maria Silva durante a monitoria.",
        ),
    )

    assert result is not None
    assert result.confidence == 60
    assert result.match_type == "primeiro_segundo_nome"


def test_nome_completo_no_raw_text_gera_confianca_80() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(raw_text="Atendimento de Maria Silva Santos"),
    )

    assert result is not None
    assert result.confidence == 80
    assert result.match_type == "nome_completo"


def test_matricula_no_raw_text_gera_confianca_100() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(raw_text="aluno PDITA-001 participou"),
    )

    assert result is not None
    assert result.confidence == 100
    assert result.match_type == "matricula"


def test_nome_com_acento_bate_sem_acento_com_confianca_80() -> None:
    result = match_student_to_meeting(
        {"nome": "Kaik Otávio", "matricula": "PDITA870"},
        _meeting(summary="Kaik Otavio participou da monitoria."),
    )

    assert result is not None
    assert result.confidence == 80
    assert result.match_type == "nome_completo"


def test_primeiro_nome_no_participante_gera_confianca_50() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(participants=["Maria"]),
    )

    assert result is not None
    assert result.confidence == 50
    assert result.match_type == "primeiro_nome"


def test_aluno_sem_match_retorna_none() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Monitoria manual", summary="Sem dados do aluno."),
    )

    assert result is None


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
        "report_url": "https://docs.google.com/document/d/abc/edit",
        "participants": [],
        "emails": [],
        "raw_text": "",
    }
    meeting.update(overrides)
    return meeting
