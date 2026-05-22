"""Tests for Read IA student matching and daily preview classification."""

from src.preview_monitoria_do_dia import build_preview_rows
from src.readia_matcher import (
    load_readia_meetings_from_sheet_rows,
    match_student_to_meeting,
)


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


def test_primeiro_segundo_nome_no_titulo_gera_confianca_30() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(title="Maria Silva and Natanael Hauck"),
    )

    assert result is not None
    assert result.confidence == 30
    assert result.match_type == "primeiro_segundo_nome"


def test_primeiro_segundo_nome_no_resumo_gera_confianca_30() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(
            title="Monitoria manual",
            summary="Resumo gerado para Maria Silva durante a monitoria.",
        ),
    )

    assert result is not None
    assert result.confidence == 30
    assert result.match_type == "primeiro_segundo_nome"


def test_nome_completo_no_payload_json_gera_confianca_50() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(payload_json='{"notes": "Atendimento de Maria Silva Santos"}'),
    )

    assert result is not None
    assert result.confidence == 50
    assert result.match_type == "nome_completo"


def test_primeiro_nome_no_participante_gera_confianca_15() -> None:
    result = match_student_to_meeting(
        _student(),
        _meeting(participants=["Maria"]),
    )

    assert result is not None
    assert result.confidence == 15
    assert result.match_type == "primeiro_nome"


def test_load_readia_meetings_from_sheet_rows_normaliza_e_filtra_data() -> None:
    meetings = load_readia_meetings_from_sheet_rows(
        [
            {
                "received_at": "2026-05-21T14:30:00-03:00",
                "meeting_id": "meet-1",
                "title": "Monitoria",
                "summary": "Resumo",
                "report_url": "https://read.ai/report/meet-1",
                "payload_json": (
                    '{"participants": ["Maria Silva"], "notes": "PDITA001"}'
                ),
            },
            {
                "received_at": "2026-05-20T14:30:00-03:00",
                "meeting_id": "meet-2",
                "payload_json": '{"title": "Outro dia"}',
            },
        ],
        report_date="2026-05-21",
    )

    assert len(meetings) == 1
    assert meetings[0]["meeting_id"] == "meet-1"
    assert meetings[0]["date"] == "2026-05-21"
    assert meetings[0]["participants"] == ["Maria Silva"]
    assert "PDITA001" in meetings[0]["payload_json"]


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
        "payload_json": "",
    }
    meeting.update(overrides)
    return meeting
