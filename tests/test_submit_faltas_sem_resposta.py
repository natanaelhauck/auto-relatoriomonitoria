"""Tests for absence submissions based on Calendar and Read IA."""

from src import submit_faltas_sem_resposta as faltas


def test_build_faltas_rows_from_agenda_readia_retorna_eventos_sem_match(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        faltas,
        "get_events_for_date",
        lambda report_date: [
            _event("Aluno Ausente PDITA123 and Natanael Hauck"),
            _event("Aluno Presente PDITA999 and Natanael Hauck"),
        ],
    )
    monkeypatch.setattr(
        faltas,
        "load_readia_meetings",
        lambda report_date: [_meeting("Aluno Presente PDITA999 and Natanael Hauck")],
    )

    rows = faltas.build_faltas_rows_from_agenda_readia("2026-05-21")

    assert rows == [
        {
            "nome": "Aluno Ausente",
            "matricula": "PDITA123",
            "motivo_falta": "Sem resposta",
        }
    ]


def test_submit_faltas_sem_resposta_envia_batch_sem_sheet_faltas(monkeypatch) -> None:
    captured = {}
    rows = [
        {
            "nome": "Aluno Ausente",
            "matricula": "PDITA123",
            "motivo_falta": "Sem resposta",
        }
    ]

    monkeypatch.setattr(
        faltas,
        "build_faltas_rows_from_agenda_readia",
        lambda report_date: rows,
    )

    def fake_run_batch(batch_rows, status, dry_run, **kwargs):
        captured["args"] = (batch_rows, status, dry_run)
        captured["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(faltas, "run_batch", fake_run_batch)

    exit_code = faltas.submit_faltas_sem_resposta(
        dry_run=True,
        report_date="2026-05-21",
        limit=1,
        only_matricula="PDITA123",
        assume_yes=True,
    )

    assert exit_code == 0
    assert captured["args"] == (rows, "Falta", True)
    assert captured["kwargs"]["report_date"] == "2026-05-21"
    assert captured["kwargs"]["payload_defaults"] == {"motivo_falta": "Sem resposta"}
    assert captured["kwargs"]["skip_existing"] is True
    assert captured["kwargs"]["limit"] == 1
    assert captured["kwargs"]["only_matricula"] == "PDITA123"
    assert captured["kwargs"]["assume_yes"] is True


def _event(title: str) -> dict[str, object]:
    return {
        "title": title,
        "start": "",
        "end": "",
        "description": "",
        "attendees": [],
    }


def _meeting(title: str) -> dict[str, object]:
    return {
        "date": "2026-05-21",
        "start_time": "",
        "title": title,
        "summary": "",
        "report_url": "https://read.ai/report/abc",
        "participants": [],
        "emails": [],
        "raw_text": "",
    }
