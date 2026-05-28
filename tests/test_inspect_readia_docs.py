"""Tests for Read IA Google Docs inspection."""

from src import inspect_readia_docs


def test_inspect_readia_docs_mostra_aviso_quando_summary_vazio(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        inspect_readia_docs,
        "list_readia_docs_for_date",
        lambda report_date: [
            {
                "date": report_date,
                "title": "2026-05-27 - Aluno PDITA001",
                "meeting": "Monitoria",
                "summary": "",
                "readia_report_url": "https://docs.google.com/document/d/doc1/edit",
                "link_google_docs": "https://docs.google.com/document/d/doc1/edit",
            }
        ],
    )

    exit_code = inspect_readia_docs.inspect_readia_docs(report_date="2026-05-27")

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Total docs encontrados: 1" in output
    assert "AVISO: summary vazio" in output
    assert "link_readia: https://docs.google.com/document/d/doc1/edit" in output
    assert "link_google_docs: https://docs.google.com/document/d/doc1/edit" in output
    assert "AVISO: usando link do Google Docs como fallback" in output
