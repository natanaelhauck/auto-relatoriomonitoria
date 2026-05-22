"""Tests for Google Calendar based monitoring preview."""

from pathlib import Path

from src import calendar_client
from src import preview_monitoria_agenda_do_dia as agenda_preview
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
        [_meeting(title="Monitoria PDITA123 and Natanael Hauck")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "presentes_confirmados"
    assert rows[0]["status"] == "Presenca"
    assert rows[0]["match_confidence"] == 100
    assert rows[0]["match_type"] == "matricula"


def test_evento_com_nome_completo_no_payload_json_vira_presente() -> None:
    rows = build_agenda_preview_rows(
        [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start="2026-05-21T10:00:00-03:00",
            )
        ],
        [_meeting(payload_json='{"notes": "Maria Silva Santos participou."}')],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "presentes_confirmados"
    assert rows[0]["status"] == "Presenca"
    assert rows[0]["match_confidence"] == 50
    assert rows[0]["match_type"] == "nome_completo"


def test_evento_com_primeiro_segundo_nome_vira_match_fraco_falta() -> None:
    rows = build_agenda_preview_rows(
        [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start="2026-05-21T10:00:00-03:00",
            )
        ],
        [_meeting(summary="Resumo gerado para Maria Silva.")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "matches_fracos"
    assert rows[0]["status"] == "Falta"
    assert rows[0]["match_confidence"] == 30
    assert rows[0]["match_type"] == "primeiro_segundo_nome"


def test_evento_sem_readia_vira_falta_candidata() -> None:
    rows = build_agenda_preview_rows(
        [_event(title="Maria Silva Santos PDITA123 and Natanael Hauck")],
        [],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "faltas_candidatas"
    assert rows[0]["status"] == "Falta"
    assert rows[0]["matricula"] == "PDITA123"
    assert rows[0]["match_type"] == "sem_match"


def test_evento_sem_matricula_vai_para_nao_parseados() -> None:
    rows = build_agenda_preview_rows(
        [_event(title="Monitoria manual")],
        [_meeting(title="Monitoria manual")],
        "2026-05-21",
    )

    assert rows[0]["categoria"] == "eventos_nao_parseados"
    assert rows[0]["status"] == "Revisar"
    assert rows[0]["match_type"] == "sem_matricula_no_titulo"


def test_preview_usa_payloads_readia_do_google_sheets(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        agenda_preview,
        "get_events_for_date",
        lambda report_date: [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start=f"{report_date}T10:00:00-03:00",
            )
        ],
    )
    monkeypatch.setattr(
        agenda_preview,
        "read_readia_payload_rows",
        lambda: [
            {
                "received_at": "2026-05-21T14:30:00-03:00",
                "title": "Monitoria",
                "summary": "",
                "report_url": "https://read.ai/report/abc",
                "payload_json": '{"notes": "Maria Silva Santos participou."}',
            }
        ],
    )

    preview_dir = Path("data/previews/test_calendar_preview")
    csv_path = preview_dir / "preview_agenda_monitoria_2026-05-21.csv"
    try:
        exit_code = agenda_preview.preview_monitoria_agenda_do_dia(
            report_date="2026-05-21",
            preview_dir=preview_dir,
        )
    finally:
        if csv_path.exists():
            csv_path.unlink()
        if preview_dir.exists():
            preview_dir.rmdir()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Total eventos agenda: 1" in output
    assert "Total payloads Read IA na planilha: 1" in output
    assert "Total payloads Read IA filtrados pela data: 1" in output
    assert "Presentes confirmados: 1" in output
    assert f"Caminho CSV: {csv_path}" in output


def test_preview_avisa_quando_planilha_tem_payloads_mas_data_nao(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        agenda_preview,
        "get_events_for_date",
        lambda report_date: [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start=f"{report_date}T10:00:00-03:00",
            )
        ],
    )
    monkeypatch.setattr(
        agenda_preview,
        "read_readia_payload_rows",
        lambda: [
            {
                "received_at": "2026-05-20T14:30:00-03:00",
                "title": "Monitoria",
                "payload_json": '{"notes": "Maria Silva Santos participou."}',
            }
        ],
    )

    preview_dir = Path("data/previews/test_calendar_preview_sem_data")
    csv_path = preview_dir / "preview_agenda_monitoria_2026-05-21.csv"
    try:
        exit_code = agenda_preview.preview_monitoria_agenda_do_dia(
            report_date="2026-05-21",
            preview_dir=preview_dir,
        )
    finally:
        if csv_path.exists():
            csv_path.unlink()
        if preview_dir.exists():
            preview_dir.rmdir()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Total payloads Read IA na planilha: 1" in output
    assert "Total payloads Read IA filtrados pela data: 0" in output
    assert "Existem payloads na planilha, mas nenhum para esta data." in output


def test_preview_gera_csv_debug_quando_payloads_na_data_sem_presenca(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        agenda_preview,
        "get_events_for_date",
        lambda report_date: [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start=f"{report_date}T10:00:00-03:00",
            )
        ],
    )
    monkeypatch.setattr(
        agenda_preview,
        "read_readia_payload_rows",
        lambda: [
            {
                "received_at": "2026-05-21T14:30:00-03:00",
                "meeting_id": "meet-sem-match",
                "title": "Monitoria de outro aluno",
                "summary": "Sem dados do aluno.",
                "payload_json": '{"notes": "Outro participante"}',
            }
        ],
    )

    preview_dir = Path("data/previews/test_calendar_preview_debug")
    csv_path = preview_dir / "preview_agenda_monitoria_2026-05-21.csv"
    debug_csv_path = preview_dir / "debug_readia_matches_2026-05-21.csv"
    try:
        exit_code = agenda_preview.preview_monitoria_agenda_do_dia(
            report_date="2026-05-21",
            preview_dir=preview_dir,
        )
        debug_content = debug_csv_path.read_text(encoding="utf-8")
    finally:
        if csv_path.exists():
            csv_path.unlink()
        if debug_csv_path.exists():
            debug_csv_path.unlink()
        if preview_dir.exists():
            preview_dir.rmdir()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Caminho CSV debug: {debug_csv_path}" in output
    assert "meet-sem-match" in debug_content
    assert "sem_match" in debug_content


def test_calendar_service_prioriza_json_da_service_account(monkeypatch) -> None:
    calls = {}

    class FakeCredentials:
        @staticmethod
        def from_service_account_info(info, scopes):
            calls["info"] = (info, scopes)
            return "credentials-from-info"

        @staticmethod
        def from_service_account_file(path, scopes):
            calls["file"] = (path, scopes)
            return "credentials-from-file"

    monkeypatch.setattr(calendar_client.service_account, "Credentials", FakeCredentials)
    monkeypatch.setattr(calendar_client, "build", lambda *args, **kwargs: (args, kwargs))

    service = calendar_client._build_calendar_service(
        service_account_file="credentials/google-service-account.json",
        service_account_json='{"type": "service_account"}',
    )

    assert calls["info"] == ({"type": "service_account"}, calendar_client.SCOPES)
    assert "file" not in calls
    assert service == (
        ("calendar", "v3"),
        {"credentials": "credentials-from-info", "cache_discovery": False},
    )


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
        "payload_json": "",
    }
    meeting.update(overrides)
    return meeting
