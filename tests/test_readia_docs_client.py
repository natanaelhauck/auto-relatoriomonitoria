"""Tests for Read IA Google Docs parsing."""

from src.readia_docs_client import (
    extract_readia_doc_report,
    find_readia_notes_folder_id,
    google_doc_to_text,
)


def test_google_doc_to_text_extrai_texto_de_paragrafos() -> None:
    document = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Meeting: Monitoria\n"}},
                        ],
                    },
                },
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Summary\n"}},
                            {"textRun": {"content": "Aluno consumiu Banco de Dados."}},
                        ],
                    },
                },
            ],
        },
    }

    assert google_doc_to_text(document) == (
        "Meeting: Monitoria\nSummary\nAluno consumiu Banco de Dados."
    )


def test_extract_readia_doc_report_extrai_meeting_summary_e_link() -> None:
    raw_text = """Meeting: 2026-05-27 - SIMONE NUNES GOMES PDBD164 and Natanael Hauck
Event time: 2026-05-27 14:00

Summary
A aluna concluiu Banco de Dados.

Action Items
Revisar atividades.

Transcript
Texto da conversa.
"""
    file = {
        "id": "doc123",
        "name": "2026-05-27 - SIMONE NUNES GOMES PDBD164 and Natanael Hauck",
        "webViewLink": "https://docs.google.com/document/d/doc123/edit",
    }

    report = extract_readia_doc_report(file, raw_text)

    assert report["date"] == "2026-05-27"
    assert report["title"] == file["name"]
    assert report["meeting"] == (
        "2026-05-27 - SIMONE NUNES GOMES PDBD164 and Natanael Hauck"
    )
    assert report["event_time"] == "2026-05-27 14:00"
    assert report["summary"] == "A aluna concluiu Banco de Dados."
    assert report["transcript"] == "Texto da conversa."
    assert report["report_url"] == file["webViewLink"]
    assert report["raw_text"] == raw_text


def test_extract_readia_doc_report_normaliza_headings_com_emojis() -> None:
    raw_text = """Meeting: Monitoria Simone PDBD164
Event time: 2026-05-27 14:00

✨ Summary
A aluna assistiu Banco de Dados.

✅ Action Items
Deve fazer Python I na próxima semana.

 Key Questions
Pergunta importante.

 Chapters & Topics
Tópico registrado.

 Transcript
Linha um da transcrição.
✅ Action Items
Esta linha ainda pertence ao transcript.
"""

    report = extract_readia_doc_report(
        {"id": "doc789", "name": "2026-05-27 - SIMONE PDBD164"},
        raw_text,
    )

    assert report["meeting"] == "Monitoria Simone PDBD164"
    assert report["event_time"] == "2026-05-27 14:00"
    assert report["summary"] == "A aluna assistiu Banco de Dados."
    assert report["transcript"] == (
        "Linha um da transcrição.\n"
        "✅ Action Items\n"
        "Esta linha ainda pertence ao transcript."
    )


def test_extract_readia_doc_report_monta_link_quando_drive_nao_traz_webview() -> None:
    report = extract_readia_doc_report(
        {"id": "doc456", "name": "2026-05-27 - Monitoria"},
        "Summary: Resumo curto",
    )

    assert report["summary"] == "Resumo curto"
    assert report["report_url"] == "https://docs.google.com/document/d/doc456/edit"


def test_find_readia_notes_folder_id_usa_id_configurado(monkeypatch) -> None:
    monkeypatch.setenv("READIA_DOCS_FOLDER_ID", "folder123")

    assert find_readia_notes_folder_id(object()) == "folder123"
