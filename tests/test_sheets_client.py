"""Tests for Google Sheets row normalization."""

from unittest.mock import MagicMock

from src import sheets_client
from src.sheets_client import SheetsSettings, _normalize_header, _normalize_row


def test_faltas_aceitam_cabecalhos_alternativos_de_motivo() -> None:
    for raw_motivo_header in ("Motivo", "Motivo da Falta", "motivo_falta"):
        headers = [
            _normalize_header("NOME"),
            _normalize_header("PDITA"),
            _normalize_header(raw_motivo_header),
        ]
        row = _normalize_row(
            headers,
            ["Aluno Um", "PDITA001", "Trabalho ou Estudo"],
            default_agente="Natanael",
        )

        assert row["nome"] == "Aluno Um"
        assert row["matricula"] == "PDITA001"
        assert row["motivo_falta"] == "Trabalho ou Estudo"
        assert row["agente"] == "Natanael"


def test_append_readia_payload_ordena_colunas_sem_chamada_real(monkeypatch) -> None:
    settings = SheetsSettings(
        service_account_file="credentials/google-service-account.json",
        spreadsheet_id="sheet-id",
        sheet_nao_agendados="Em Analise",
        sheet_finalizados="Finalizaram",
        sheet_faltas="Faltas",
        sheet_presentes="Presentes",
        sheet_ativos="Ativo",
        default_agente="Natanael",
        sheet_readia_payloads="ReadIA Payloads",
    )
    service = object()
    appended = {}

    monkeypatch.setattr(sheets_client, "load_sheets_settings", lambda: settings)
    monkeypatch.setattr(sheets_client, "_build_sheets_service", lambda _: service)
    monkeypatch.setattr(
        sheets_client,
        "_ensure_readia_payload_sheet",
        lambda *args: appended.setdefault("ensured", args),
    )
    monkeypatch.setattr(
        sheets_client,
        "_append_sheet_values",
        lambda *args: appended.setdefault("appended", args),
    )

    sheets_client.append_readia_payload(
        {
            "received_at": "2026-05-22T10:00:00-03:00",
            "meeting_id": "meet-123",
            "title": "Monitoria",
            "summary": "Resumo",
            "report_url": "https://read.ai/report/meet-123",
            "payload_json": '{"meeting_id": "meet-123"}',
        }
    )

    assert appended["ensured"] == (service, "sheet-id", "ReadIA Payloads")
    assert appended["appended"] == (
        service,
        "sheet-id",
        "ReadIA Payloads",
        [
            [
                "2026-05-22T10:00:00-03:00",
                "meet-123",
                "Monitoria",
                "Resumo",
                "https://read.ai/report/meet-123",
                '{"meeting_id": "meet-123"}',
            ]
        ],
    )


def test_load_sheets_settings_aceita_json_da_service_account(monkeypatch) -> None:
    _set_required_sheets_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}')

    settings = sheets_client.load_sheets_settings()

    assert settings.service_account_json == '{"type": "service_account"}'
    assert settings.service_account_file is None


def test_build_sheets_service_prioriza_json_da_service_account(monkeypatch) -> None:
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

    settings = SheetsSettings(
        service_account_file="credentials/google-service-account.json",
        spreadsheet_id="sheet-id",
        sheet_nao_agendados="Em Analise",
        sheet_finalizados="Finalizaram",
        sheet_faltas="Faltas",
        sheet_presentes="Presentes",
        sheet_ativos="Ativo",
        default_agente="Natanael",
        service_account_json='{"type": "service_account"}',
    )

    monkeypatch.setattr(sheets_client.service_account, "Credentials", FakeCredentials)
    monkeypatch.setattr(sheets_client, "build", lambda *args, **kwargs: (args, kwargs))

    service = sheets_client._build_sheets_service(settings)

    assert calls["info"] == ({"type": "service_account"}, sheets_client.SCOPES)
    assert "file" not in calls
    assert service == (
        ("sheets", "v4"),
        {"credentials": "credentials-from-info", "cache_discovery": False},
    )


def test_build_sheets_service_usa_arquivo_quando_json_nao_existe(monkeypatch) -> None:
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

    settings = SheetsSettings(
        service_account_file="credentials/google-service-account.json",
        spreadsheet_id="sheet-id",
        sheet_nao_agendados="Em Analise",
        sheet_finalizados="Finalizaram",
        sheet_faltas="Faltas",
        sheet_presentes="Presentes",
        sheet_ativos="Ativo",
        default_agente="Natanael",
    )

    monkeypatch.setattr(sheets_client.service_account, "Credentials", FakeCredentials)
    monkeypatch.setattr(sheets_client, "build", lambda *args, **kwargs: (args, kwargs))

    service = sheets_client._build_sheets_service(settings)

    assert calls["file"] == (
        "credentials/google-service-account.json",
        sheets_client.SCOPES,
    )
    assert "info" not in calls
    assert service == (
        ("sheets", "v4"),
        {"credentials": "credentials-from-file", "cache_discovery": False},
    )


def test_ensure_sheet_exists_cria_aba_quando_ausente() -> None:
    service = MagicMock()
    spreadsheets = service.spreadsheets.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Outra Aba"}}]
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {}

    created = sheets_client._ensure_sheet_exists(
        service,
        "sheet-id",
        "ReadIA Payloads",
    )

    assert created is True
    spreadsheets.batchUpdate.assert_called_once_with(
        spreadsheetId="sheet-id",
        body={
            "requests": [
                {"addSheet": {"properties": {"title": "ReadIA Payloads"}}}
            ]
        },
    )


def _set_required_sheets_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPREADSHEET_ID", "sheet-id")
    monkeypatch.setenv("SHEET_NAO_AGENDADOS", "Em Analise")
    monkeypatch.setenv("SHEET_FINALIZADOS", "Finalizaram")
    monkeypatch.setenv("SHEET_FALTAS", "Faltas")
