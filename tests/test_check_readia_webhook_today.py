"""Tests for Read IA webhook diagnostics."""

from src import check_readia_webhook_today as check_readia


def test_check_readia_webhook_today_lista_monitorias_sem_payload(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        check_readia,
        "get_events_for_date",
        lambda report_date: [
            _event(
                title="Maria Silva Santos PDITA123 and Natanael Hauck",
                start=f"{report_date}T10:00:00-03:00",
            ),
            _event(
                title="Joao Souza PDITA456 and Natanael Hauck",
                start=f"{report_date}T11:00:00-03:00",
            ),
            _event(title="Monitoria sem matricula", start=f"{report_date}T12:00:00-03:00"),
        ],
    )
    monkeypatch.setattr(
        check_readia,
        "read_readia_payload_rows",
        lambda: [
            {
                "received_at": "2026-05-22T10:30:00-03:00",
                "meeting_id": "meet-maria",
                "title": "Monitoria PDITA123",
                "payload_json": '{"notes": "Maria Silva Santos participou."}',
            },
            {
                "received_at": "2026-05-21T10:30:00-03:00",
                "meeting_id": "meet-antigo",
                "title": "Payload antigo",
                "payload_json": "{}",
            },
        ],
    )

    exit_code = check_readia.check_readia_webhook_today(report_date="2026-05-22")

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Total eventos agenda: 3" in output
    assert "Total payloads Read IA recebidos na data: 1" in output
    assert "Monitorias com payload confirmado: 1" in output
    assert "Monitorias sem payload confirmado: 1" in output
    assert "Eventos sem matricula reconhecivel: 1" in output
    assert "Joao Souza | PDITA456" in output
    assert "Maria Silva Santos | PDITA123" not in output
    assert "Monitoria sem matricula" in output


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
