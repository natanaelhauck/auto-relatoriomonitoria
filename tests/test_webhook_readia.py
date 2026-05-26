"""Tests for the Read IA webhook."""

import json
import shutil
from pathlib import Path

from src import webhook_readia


def test_health_retorna_ok() -> None:
    client = webhook_readia.app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_read_webhook_salva_arquivo_json(monkeypatch) -> None:
    payload_dir = Path("tests/_tmp_read_payloads")
    shutil.rmtree(payload_dir, ignore_errors=True)
    payload_dir.mkdir(parents=True)
    appended_rows = []

    try:
        monkeypatch.setattr(webhook_readia, "PAYLOAD_DIR", payload_dir)
        monkeypatch.setattr(webhook_readia, "append_readia_payload", appended_rows.append)
        client = webhook_readia.app.test_client()

        response = client.post(
            "/read-webhook",
            json={
                "session_id": "abc123",
                "title": "Monitoria",
                "summary": "Resumo do encontro",
            },
        )

        assert response.status_code == 202
        assert response.get_json()["sheet_status"] == "saved"
        saved_files = list(payload_dir.glob("*.json"))
        assert len(saved_files) == 1
        assert "readia_abc123" in saved_files[0].name

        document = json.loads(saved_files[0].read_text(encoding="utf-8"))
        assert document["received_at"]
        assert "headers" in document
        assert document["payload"]["session_id"] == "abc123"
        assert document["payload"]["summary"] == "Resumo do encontro"

        assert len(appended_rows) == 1
        assert appended_rows[0]["meeting_id"] == "abc123"
        assert appended_rows[0]["title"] == "Monitoria"
        assert appended_rows[0]["summary"] == "Resumo do encontro"
        assert appended_rows[0]["payload_json_size"]
        assert appended_rows[0]["sheet_status"] == "saved"
        assert appended_rows[0]["sheet_error"] == ""
    finally:
        shutil.rmtree(payload_dir, ignore_errors=True)


def test_build_readia_payload_row_extrai_campos_principais() -> None:
    row = webhook_readia.build_readia_payload_row(
        {
            "meeting": {
                "meetingId": "meet-123",
                "meetingTitle": "Monitoria Read IA",
                "reportSummary": "Resumo gerado",
                "reportUrl": "https://read.ai/report/meet-123",
            }
        },
        received_at="2026-05-22T10:00:00-03:00",
    )

    assert row["received_at"] == "2026-05-22T10:00:00-03:00"
    assert row["meeting_id"] == "meet-123"
    assert row["title"] == "Monitoria Read IA"
    assert row["summary"] == "Resumo gerado"
    assert row["report_url"] == "https://read.ai/report/meet-123"
    assert json.loads(row["payload_json"])["meeting"]["meetingId"] == "meet-123"
    assert row["payload_json_size"] == str(len(row["payload_json"]))
    assert row["sheet_status"] == "saved"
    assert row["sheet_error"] == ""


def test_build_readia_payload_row_trunca_payload_grande() -> None:
    row = webhook_readia.build_readia_payload_row(
        {"meeting_id": "meet-big", "summary": "x" * 50000},
        received_at="2026-05-22T10:00:00-03:00",
    )

    assert row["payload_json"].startswith(webhook_readia.TRUNCATED_PAYLOAD_WARNING)
    assert len(row["payload_json"]) <= webhook_readia.MAX_SHEET_PAYLOAD_JSON_CHARS
    assert int(row["payload_json_size"]) > webhook_readia.MAX_SHEET_PAYLOAD_JSON_CHARS
    assert row["summary"] == "x" * 50000


def test_read_webhook_retorna_500_quando_sheets_falha(monkeypatch) -> None:
    payload_dir = Path("tests/_tmp_read_payloads_sheet_error")
    shutil.rmtree(payload_dir, ignore_errors=True)
    payload_dir.mkdir(parents=True)

    def fail_append(row):
        raise RuntimeError("Sheets indisponivel")

    try:
        monkeypatch.setattr(webhook_readia, "PAYLOAD_DIR", payload_dir)
        monkeypatch.setattr(webhook_readia, "append_readia_payload", fail_append)
        client = webhook_readia.app.test_client()

        response = client.post("/read-webhook", json={"meeting_id": "meet-error"})

        body = response.get_json()
        assert response.status_code == 500
        assert body["status"] == "sheet_error"
        assert body["sheet_status"] == "error"
        assert body["error"] == "Sheets indisponivel"
        assert len(list(payload_dir.glob("*.json"))) == 1
    finally:
        shutil.rmtree(payload_dir, ignore_errors=True)


def test_read_webhook_retorna_duplicate_skipped(monkeypatch) -> None:
    payload_dir = Path("tests/_tmp_read_payloads_duplicate")
    shutil.rmtree(payload_dir, ignore_errors=True)
    payload_dir.mkdir(parents=True)

    try:
        monkeypatch.setattr(webhook_readia, "PAYLOAD_DIR", payload_dir)
        monkeypatch.setattr(
            webhook_readia,
            "append_readia_payload",
            lambda row: "duplicate_skipped",
        )
        client = webhook_readia.app.test_client()

        response = client.post("/read-webhook", json={"meeting_id": "meet-dup"})

        assert response.status_code == 202
        assert response.get_json()["sheet_status"] == "duplicate_skipped"
    finally:
        shutil.rmtree(payload_dir, ignore_errors=True)
