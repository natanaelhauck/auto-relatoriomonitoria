"""Tests for Google Sheets row normalization."""

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


def test_load_sheets_settings_aceita_json_da_service_account(monkeypatch) -> None:
    _set_required_sheets_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}')

    settings = sheets_client.load_sheets_settings()

    assert settings.service_account_json == '{"type": "service_account"}'
    assert settings.service_account_file is None
    assert not hasattr(settings, "sheet_faltas")


def test_load_sheets_settings_nao_exige_sheet_faltas(monkeypatch) -> None:
    _set_required_sheets_env(monkeypatch)
    monkeypatch.setenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "credentials/google-service-account.json",
    )
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.delenv("SHEET_FALTAS", raising=False)

    settings = sheets_client.load_sheets_settings()

    assert not hasattr(settings, "sheet_faltas")


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


def _set_required_sheets_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPREADSHEET_ID", "sheet-id")
    monkeypatch.setenv("SHEET_NAO_AGENDADOS", "Em Analise")
    monkeypatch.setenv("SHEET_FINALIZADOS", "Finalizaram")
