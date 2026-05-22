"""Tests for Read IA payload sheet inspection."""

from src import inspect_readia_sheet


def test_inspect_readia_sheet_mostra_totais_datas_e_hits(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        inspect_readia_sheet,
        "read_readia_payload_rows",
        lambda: [
            {
                "received_at": "2026-05-21T14:30:00-03:00",
                "meeting_id": "meet-antigo",
                "title": "Payload antigo",
                "summary": "Resumo antigo",
                "report_url": "https://read.ai/report/antigo",
                "payload_json": '{"notes": "Outro dia"}',
            },
            {
                "received_at": "2026-05-22T14:30:00-03:00",
                "meeting_id": "meet-123",
                "title": "Monitoria",
                "summary": "Resumo da monitoria",
                "report_url": "https://read.ai/report/123",
                "payload_json": '{"notes": "Maria Silva PDITA123 participou"}',
            },
        ],
    )
    monkeypatch.setattr(
        inspect_readia_sheet,
        "_load_known_students",
        lambda: [{"nome": "Maria Silva", "matricula": "PDITA123"}],
    )

    exit_code = inspect_readia_sheet.inspect_readia_sheet(report_date="2026-05-22")

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Total payloads na aba: 2" in output
    assert "  2026-05-21: 1" in output
    assert "  2026-05-22: 1" in output
    assert "Payloads exibidos: 1" in output
    assert "meeting_id: meet-123" in output
    assert "meeting_id: meet-antigo" not in output
    assert "payload_json contem aluno conhecido: sim - Maria Silva PDITA123" in output
