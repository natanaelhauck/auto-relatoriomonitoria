"""Tests for weekly automatic submission."""

from src.sheets_client import SheetsSettings
from src.weekly_auto_submit import build_weekly_payloads


def test_envio_semanal_junta_nao_agendados_e_finalizados(monkeypatch) -> None:
    settings = SheetsSettings(
        service_account_file="credentials/google-service-account.json",
        spreadsheet_id="sheet-id",
        sheet_nao_agendados="Em Análise",
        sheet_finalizados="Finalizaram",
        sheet_faltas="Faltas",
        sheet_presentes="Presentes",
        default_agente="Natanael",
    )

    def fake_read_sheet_rows(sheet_name: str):
        if sheet_name == "Em Análise":
            return [{"nome": "Aluno Um", "matricula": "PDITA001", "agente": "Natanael"}]
        if sheet_name == "Finalizaram":
            return [{"nome": "Aluno Dois", "matricula": "PDITA002", "agente": "Natanael"}]
        return []

    monkeypatch.setattr("src.weekly_auto_submit.read_sheet_rows", fake_read_sheet_rows)

    payloads, ignored, total_rows = build_weekly_payloads(settings, "2026-05-05")

    assert total_rows == 2
    assert ignored == []
    assert [payload.status for payload in payloads] == [
        "Aluno não agendado(Fantasma)",
        "Aluno finalizou o curso",
    ]
