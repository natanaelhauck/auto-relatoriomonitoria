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

    try:
        monkeypatch.setattr(webhook_readia, "PAYLOAD_DIR", payload_dir)
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
        saved_files = list(payload_dir.glob("*.json"))
        assert len(saved_files) == 1
        assert "readia_abc123" in saved_files[0].name

        document = json.loads(saved_files[0].read_text(encoding="utf-8"))
        assert document["received_at"]
        assert "headers" in document
        assert document["payload"]["session_id"] == "abc123"
        assert document["payload"]["summary"] == "Resumo do encontro"
    finally:
        shutil.rmtree(payload_dir, ignore_errors=True)
