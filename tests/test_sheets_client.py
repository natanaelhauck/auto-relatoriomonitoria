"""Tests for Google Sheets row normalization."""

from src.sheets_client import _normalize_header, _normalize_row


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
