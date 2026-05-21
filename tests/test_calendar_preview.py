"""Tests for Google Calendar based monitoring preview."""

from src.calendar_client import parse_student_from_calendar_title
from src.preview_monitoria_agenda_do_dia import build_agenda_preview_rows


def test_parse_titulo_com_nome_e_pdita() -> None:
    student = parse_student_from_calendar_title(
        "Maria Silva Santos PDITA123 and Natanael Hauck"
    )

    assert student == {
        "nome": "Maria Silva Santos",
        "matricula": "PDITA123",
    }


def test_parse_titulo_com_pdbd_remove_natanael() -> None:
    student = parse_student_from_calendar_title(
        "Octávio Augusto de Araújo Américo PDBD163 and Natanael Hauck"
    )

    assert student == {
        "nome": "Octávio Augusto de Araújo Américo",
        "matricula": "PDBD163",
    }


def test_evento_com_matricula_no_readia_vira_presente() -> None:
    rows = build_agenda_preview_rows(
        [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start="2026-05-21T10:00:00-03:00",
            )
        ],
        [_meeting(title="Maria Silva PDITA123 and Natanael Hauck")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "presentes_confirmados"
    assert rows[0]["match_confidence"] == 100
    assert rows[0]["match_type"] == "matricula"


def test_evento_sem_readia_vira_falta_candidata() -> None:
    rows = build_agenda_preview_rows(
        [_event(title="Maria Silva Santos PDITA123 and Natanael Hauck")],
        [],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "faltas_candidatas"
    assert rows[0]["matricula"] == "PDITA123"
    assert rows[0]["match_type"] == "sem_match"


def test_evento_sem_matricula_vai_para_nao_parseados() -> None:
    rows = build_agenda_preview_rows(
        [_event(title="Monitoria manual")],
        [_meeting(title="Monitoria manual")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "eventos_nao_parseados"
    assert rows[0]["match_type"] == "sem_matricula_no_titulo"


def _event(**overrides: str) -> dict[str, object]:
    event = {
        "title": "",
        "start": "",
        "end": "",
        "description": "",
        "attendees": [],
    }
    event.update(overrides)
    return event


def _meeting(**overrides: object) -> dict[str, object]:
    meeting = {
        "date": "2026-05-21",
        "start_time": "",
        "title": "",
        "summary": "",
        "report_url": "https://read.ai/report/abc",
        "participants": [],
        "emails": [],
        "raw_text": "",
    }
    meeting.update(overrides)
    return meeting
